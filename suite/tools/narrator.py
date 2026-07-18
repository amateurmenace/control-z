"""Narrator inside the suite — the review timeline around the AD pass.

A source is any read meeting whose full recording is local (the picture
is the product; words alone can't be described). Three jobs, one queue:
map (shots + gaps + the graphics wedge), draft (vision on the user's
key, DCMP-linted), render (TTS per accepted cue → ducked mix → mixed
track, narration track, descriptions VTT). The reviewer owns the text:
nothing unaccepted reaches a track, and the sidecar keeps every draft.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from czcore import tts
from czcore.shots import cuts_from_diffs, frame_diffs, shots_from_cuts

from interpreter import sources as sourcesmod
from narrator import gaps as gapsmod
from narrator import script as scriptmod
from narrator.describe import describe_frame, frame_jpeg, lint
from narrator.mix import run_mix

_MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4",
                ".webm": "video/webm", ".mov": "video/quicktime",
                ".mkv": "video/x-matroska"}


def _duration_fps(video: str) -> tuple:
    from czcore.media import probe
    info = probe(video)
    v = info.video
    return float(info.duration or 0.0), float(v.fps if v else 30.0) or 30.0


def _vision_label(model: str) -> str:
    """Render a script's vision origin honestly: 'moondream (on-device)',
    'claude-… (your key)', or, for a track drawn by both, the honest union
    'moondream (on-device) + claude-… (your key)'. The origin string is
    'local:<name>', 'ai:<model>', or 'mixed:<a>+<b>' (older scripts carry a
    bare model name from the key path)."""
    m = model or "?"
    if m.startswith("mixed:"):
        return " + ".join(_vision_label(p) for p in m[6:].split("+"))
    if m.startswith("local:"):
        return f"{m[6:]} (on-device)"
    if m.startswith("ai:"):
        return f"{m[3:]} (your key)"
    return f"{m} (your key)" if m != "?" else "?"


def _note(script: dict) -> str:
    tail = (" · reviewer-approved" if script.get("review") == "approved"
            else " · in review")
    return ("audio description — beta · vision "
            f"{_vision_label(script.get('model'))} · voice "
            f"{script.get('voice') or '?'}{tail} · control-z Community "
            "Narrator")


def register_narrator(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import FileResponse, JSONResponse

    @app.get("/api/narrator/status")
    def api_status():
        from czcore import llm, vision
        loc = vision.available()
        if loc["ok"]:
            vis = {"ok": True, "engine": "local", "model": loc["model"],
                   "sentence": loc["sentence"]}
        elif llm.enabled():
            vis = {"ok": True, "engine": "key", "model": llm.status()["model"],
                   "sentence": "descriptions draft on your key — "
                               + llm.status()["model"]}
        else:
            vis = {"ok": False, "engine": None, "model": None,
                   "sentence": "no vision engine — install an on-device model "
                               "on the Models page, or add your API key in "
                               "Settings → AI; the page still reads and edits "
                               "an existing script"}
        return {"tts": tts.available(), "ai": llm.status(), "vision": vis}

    @app.get("/api/narrator/library")
    def api_library():
        rows = [r for r in sourcesmod.list_sources() if r["video"]]
        return {"rows": rows}

    def _payload(src: str) -> dict:
        video = sourcesmod.video_for(src)
        meta = sourcesmod.meta(src)
        script = scriptmod.load(src)
        outs = scriptmod.out_paths(src)
        return {"source": src, "meta": meta, "video": video,
                "script": script,
                "outputs": {k: str(p) for k, p in outs.items()
                            if k != "work" and p.exists()}}

    @app.post("/api/narrator/open")
    def api_open(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        p = Path(src)
        if not (p.is_file() or p.is_dir()):
            return JSONResponse({"error": f"nothing at {src}"},
                                status_code=404)
        video = sourcesmod.video_for(src)
        if not video:
            return JSONResponse(
                {"error": "no local recording — description needs the "
                          "picture. Fetch the full video in Highlighter "
                          "first."}, status_code=409)
        t, _ = sourcesmod.transcript(src)
        if not t or not t.get("segments"):
            return JSONResponse(
                {"error": "no words yet — the gap map reads the "
                          "transcript. Open it in Highlighter first."},
                status_code=409)
        app.state.session.add_recent(src, "narrator")
        return _payload(src)

    @app.post("/api/narrator/plan")
    def api_plan(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        video = sourcesmod.video_for(src)
        t, _ = sourcesmod.transcript(src)
        if not video or not t:
            return JSONResponse({"error": "open a describable meeting "
                                          "first"}, status_code=409)
        title = sourcesmod.meta(src).get("title") or Path(src).name

        def work(job):
            job.message = "watching for the cuts…"
            duration, fps = _duration_fps(video)
            diffs = frame_diffs(video)
            job.check_cancel()
            cuts = cuts_from_diffs(diffs)
            shots = shots_from_cuts(cuts, len(diffs) + 1)
            shots_s = gapsmod.shot_seconds(shots, fps)
            motion = gapsmod.shot_motion(diffs, shots)
            job.message = "listening for the pauses…"
            gap_rows = gapsmod.gap_map(t["segments"], duration)
            graphics = gapsmod.graphic_shots(shots_s, motion)
            cues = gapsmod.plan_cues(gap_rows, graphics, shots_s=shots_s)
            script = scriptmod.load(src) or scriptmod.new(src)
            script.update({"cues": cues, "duration": duration, "fps": fps,
                           "n_shots": len(shots), "planned": int(time.time()),
                           "review": "unreviewed"})
            scriptmod.save(src, script)
            job.message = (f"{len(gap_rows)} gaps · {len(graphics)} "
                           f"graphics · {len(cues)} cue slots")
            if cues and not gap_rows and not graphics:
                job.message = (f"wall-to-wall dialogue — {len(cues)} shot "
                               "descriptions for the transcript and "
                               "extended mode; no air for a mix")
            return {"cues": len(cues), "gaps": len(gap_rows),
                    "graphics": len(graphics), "shots": len(shots)}

        return jobs.start("ad-plan", work, tool="narrator",
                          label=f"map the program — {title[:52]}").to_dict()

    @app.post("/api/narrator/describe")
    def api_describe(body: dict = Body(...)):
        from czcore import llm, vision

        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        only = body.get("only")
        if not vision.available()["ok"] and not llm.enabled():
            return JSONResponse({"error": "descriptions need an on-device model "
                                          "(Models page) or your API key "
                                          "— Settings → AI"},
                                status_code=409)
        video = sourcesmod.video_for(src)
        script = scriptmod.load(src)
        if not video or not script or not script.get("cues"):
            return JSONResponse({"error": "map the program first — the "
                                          "cues come from the plan"},
                                status_code=409)
        idxs = ([int(i) for i in only] if only else
                [i for i, c in enumerate(script["cues"])
                 if c.get("status") == "empty"])
        if not idxs:
            return JSONResponse({"error": "nothing to draft — every cue "
                                          "has words (regenerate one from "
                                          "its card)"}, status_code=422)
        title = sourcesmod.meta(src).get("title") or Path(src).name

        def work(job):
            done = 0
            for k, i in enumerate(idxs):
                job.check_cancel()
                cues = script["cues"]
                c = cues[i]
                job.progress = k / len(idxs)
                job.message = (f"cue {i + 1} — {'the graphic' if c['kind'] == 'graphic' else 'the scene'} "
                               f"at {int(c['at'] // 60)}:{int(c['at'] % 60):02d}")
                try:
                    jpeg = frame_jpeg(video, c["at"])
                    text, origin = describe_frame(jpeg, c["kind"],
                                                  int(c.get("words_budget") or 0))
                except RuntimeError as e:
                    c["status"] = "failed"
                    c["lint"] = [f"draft failed: {str(e)[:80]}"]
                    scriptmod.save(src, script)
                    continue
                c["text"] = text
                c["status"] = "draft"
                c["origin"] = origin      # what actually drew this cue
                c["lint"] = lint(text, float(c.get("dur") or 0)
                                 if c.get("words_budget") else 0)
                # the script-level stamp is the UNION of every drawn cue's
                # origin, never just the last one — a track that spent key
                # tokens on even one cue must never read as purely on-device
                origins = sorted({cc["origin"] for cc in cues
                                  if cc.get("origin")})
                script["model"] = (origins[0] if len(origins) == 1
                                   else "mixed:" + "+".join(origins)) \
                    if origins else script.get("model")
                scriptmod.save(src, script)
                done += 1
            job.message = f"{done} of {len(idxs)} cues drafted — your read next"
            return {"drafted": done, "asked": len(idxs),
                    "origin": script.get("model")}

        return jobs.start("ad-draft", work, tool="narrator",
                          label=f"draft descriptions ({len(idxs)}) — "
                                f"{title[:44]}").to_dict()

    @app.post("/api/narrator/cue")
    def api_cue(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        script = scriptmod.load(src)
        i = int(body.get("i", -1))
        if not script or not (0 <= i < len(script.get("cues", []))):
            return JSONResponse({"error": "that cue isn't on the plan"},
                                status_code=404)
        c = script["cues"][i]
        if "text" in body:
            c["text"] = str(body["text"]).strip()
            c["status"] = "edited" if c["text"] else "empty"
            c["lint"] = lint(c["text"], float(c.get("dur") or 0)
                             if c.get("words_budget") else 0)
        status = str(body.get("status") or "")
        if status in ("accepted", "draft", "empty"):
            c["status"] = status if (c.get("text") or status == "empty") \
                else "empty"
        cues = script["cues"]
        if all(x.get("status") in ("accepted", "edited") for x in cues
               if x.get("text")) and any(x.get("text") for x in cues):
            script["review"] = "approved"
        else:
            script["review"] = "in review"
        scriptmod.save(src, script)
        return {"i": i, "cue": c, "review": script["review"]}

    @app.post("/api/narrator/transcript")
    def api_transcript(body: dict = Body(...)):
        """The descriptions transcript alone — no voice needed. Every
        accepted description belongs to the record even when no pause
        would carry it on air (the extended-mode contract)."""
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        script = scriptmod.load(src)
        if not script or not any(c.get("text") and c.get("status")
                                 in ("accepted", "edited")
                                 for c in script.get("cues", [])):
            return JSONResponse({"error": "no accepted descriptions yet"},
                                status_code=422)
        outs = scriptmod.out_paths(src)
        outs["vtt"].write_text(
            scriptmod.described_vtt(script["cues"], _note(script)))
        return {"vtt": str(outs["vtt"])}

    @app.post("/api/narrator/render")
    def api_render(body: dict = Body(...)):
        src = str(Path(str(body.get("path", "")).strip()).expanduser())
        video = sourcesmod.video_for(src)
        script = scriptmod.load(src)
        if not video or not script:
            return JSONResponse({"error": "map and draft first"},
                                status_code=409)
        accepted = [(i, c) for i, c in enumerate(script.get("cues", []))
                    if c.get("text") and c.get("status") in ("accepted",
                                                             "edited")]
        if not accepted:
            return JSONResponse({"error": "no accepted descriptions yet — "
                                          "accept or edit at least one "
                                          "cue"}, status_code=422)
        # the broadcast mix carries the FITTED subset only; a description
        # with no pause never speaks over the meeting (specs/15 §6.4)
        ready = [(i, c) for i, c in accepted
                 if int(c.get("words_budget") or 0) > 0]
        if not ready:
            return JSONResponse(
                {"error": "no pauses fit narration in this program — the "
                          "descriptions live in the transcript and the "
                          "extended mode (Write transcript does that); "
                          "a mix needs air"}, status_code=422)
        voice = tts.available()
        if not voice["ok"]:
            return JSONResponse({"error": voice["sentence"]},
                                status_code=409)
        outs = scriptmod.out_paths(src)
        title = sourcesmod.meta(src).get("title") or Path(src).name
        duration = float(script.get("duration") or 0.0)

        def work(job):
            nonlocal duration
            if not duration:
                duration, _ = _duration_fps(video)
            work_dir = outs["work"]
            work_dir.mkdir(parents=True, exist_ok=True)
            cue_wavs = []
            spoken = None
            for k, (i, c) in enumerate(ready):
                job.check_cancel()
                job.progress = (k / len(ready)) * 0.5
                job.message = f"speaking cue {i + 1} of {len(script['cues'])}"
                tag = hashlib.sha1(c["text"].encode()).hexdigest()[:12]
                wav = work_dir / f"cue-{i:03d}-{tag}.wav"
                if not wav.exists():
                    got = tts.synth(c["text"], str(wav))
                    spoken = got["voice"]
                else:
                    spoken = spoken or tts.available()["voice"]
                cue_wavs.append((str(wav), float(c["start"])))
            job.message = "mixing under the program…"

            def prog(frac, _m):
                job.progress = 0.5 + frac * 0.5

            written = run_mix(video, cue_wavs, outs, duration,
                              want_video=True, progress=prog,
                              cancelled=lambda: job.cancel_requested)
            script["voice"] = spoken
            script["rendered"] = int(time.time())
            outs["vtt"].write_text(
                scriptmod.described_vtt(script["cues"], _note(script)))
            scriptmod.save(src, script)
            job.message = (f"{len(cue_wavs)} descriptions · mixed track, "
                           "narration track, transcript — written")
            return {"cues": len(cue_wavs),
                    "written": {**written, "vtt": str(outs["vtt"])}}

        return jobs.start("ad-render", work, tool="narrator",
                          label=f"render AD ({len(ready)} cues) — "
                                f"{title[:46]}").to_dict()

    @app.get("/api/narrator/track")
    def api_track(path: str, kind: str = "vtt", dl: int = 0):
        src = str(Path(path).expanduser())
        outs = scriptmod.out_paths(src)
        f = outs.get(kind if kind in ("vtt", "ad", "mix_audio",
                                      "mix_video") else "vtt")
        if f is None or not f.exists():
            return JSONResponse({"error": "not rendered yet"},
                                status_code=404)
        headers = {"Cache-Control": "no-cache"}
        if dl:
            headers["Content-Disposition"] = \
                f'attachment; filename="{f.name}"'
        media = {"vtt": "text/vtt", "ad": "audio/wav",
                 "mix_audio": "audio/mp4",
                 "mix_video": "video/mp4"}[kind]
        return FileResponse(str(f), media_type=media, headers=headers)

    @app.get("/api/narrator/media")
    def api_media(path: str):
        p = Path(path).expanduser()
        if not p.is_file():
            return JSONResponse({"error": "file moved or deleted"},
                                status_code=404)
        return FileResponse(str(p), media_type=_MEDIA_TYPES.get(
            p.suffix.lower(), "application/octet-stream"))
