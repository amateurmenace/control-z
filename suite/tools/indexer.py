"""Index inside the suite — the librarian's desk.

One catalog in app support; scans are queue jobs (they read every new
file's header), search is instant, selects leave as an FCPXML stringout or
CSV into ~/Movies/control-z/index. The catalog also knows what every clip
already carries (czcore.sidecars) — and the coverage band turns each gap
into one click of work (the batch line's first road: words for the
wordless, Scribe's engine, one queue job).
"""

from __future__ import annotations

import importlib.util
import tempfile
import time
from pathlib import Path

from czcore.paths import media_dir

# the road's stages, in the order they run. Each entry: id, label, the tool
# whose engine runs (accent + attribution), and what a clip needs for the
# stage to apply. Availability is checked at submit so a doomed stage is a
# sentence now, not N failures later.
ROAD_STAGES = (
    {"id": "words", "label": "words", "tool": "scribe",
     "needs": "audio", "skip_if": "words"},
    {"id": "clear", "label": "rescue", "tool": "clear",
     "needs": "audio", "skip_if": "clear"},
    {"id": "pivot", "label": "reframe 9:16", "tool": "pivot",
     "needs": "video", "skip_if": None},  # its own output check below
)


def _pivot_out(path: str) -> Path:
    p = Path(path)
    return p.with_name(f"{p.stem}.pivot-9x16.mp4")


def _run_clear_defaults(job, path: str, tag: str):
    """Clear's rescue pass at the road's defaults: de-hum if hum is found,
    de-click, nothing else — no isolation, no loudness bake, no remux. The
    road preps; the craft stays in the tool. Mirrors suite/tools/clear.py
    api_process (the authority if the two ever disagree)."""
    import soundfile as sf

    from clear.dsp import declick, dehum, detect_hum

    from .clear import _audio_source, _read

    src = _audio_source(path)
    audio, sr = _read(src)
    job.check_cancel()
    base = detect_hum(audio, sr)
    if base:
        audio = dehum(audio, sr, base)
    job.check_cancel()
    job.message = f"{tag} — de-click"[:120]
    audio, _nfix = declick(audio, sr)
    sf.write(str(Path(path).with_suffix(".clear.wav")), audio, sr)


def _run_pivot_9x16(job, path: str, tag: str):
    """Pivot's auto pass: analyze 9:16 (reusing a sidecar that already has
    it), then render at the tool's h264 preset. Mirrors suite/tools/pivot.py
    api_analyze + api_render (the authority if the two ever disagree)."""
    from czcore.media import resolve_preset
    from pivot.analyze import Analysis, analyze
    from pivot.render import render

    from ..frames import clip_cache_dir
    from .pivot import _sidecar

    sc = _sidecar(path)
    a = None
    if sc.exists():
        try:
            a = Analysis.from_json(sc.read_text())
            if "9:16" not in a.aspects:
                a = None
        except ValueError:
            a = None
    if a is None:
        job.message = f"{tag} — analyzing"[:120]
        cache = clip_cache_dir(path, 360)
        a = analyze(path, aspects=["9:16"], preset="standard",
                    frame_cache=str(cache),
                    progress=lambda n: setattr(
                        job, "message", f"{tag} — {n} frames"[:120]))
        sc.write_text(a.to_json())
    job.check_cancel()
    spec = resolve_preset("h264")
    total = max(1, a.n_frames)
    render(a, "9:16", str(_pivot_out(path)),
           codec_spec=spec,
           progress=lambda n: setattr(
               job, "message", f"{tag} — render {n}/{total}"[:120]),
           should_stop=lambda: job.cancel_requested)


def _road_plan(rows: list, stages: list) -> dict:
    """Which stages actually run for which clips — and which are skipped,
    each skip with its reason said plainly. Pure bookkeeping; the engines
    never see a clip this function ruled out."""
    order = [s["id"] for s in ROAD_STAGES]
    stages = [s for s in order if s in stages]
    by_id = {s["id"]: s for s in ROAD_STAGES}
    plan, skips = [], []
    for r in rows:
        todo = []
        for sid in stages:
            st = by_id[sid]
            carries = r.get("carries") or []
            if r.get("missing"):
                skips.append(f"{r['name']} · {st['label']}: drive unplugged?")
                continue
            if st["needs"] == "audio" and not r.get("audio"):
                skips.append(f"{r['name']} · {st['label']}: no audio track")
                continue
            if st["needs"] == "video" and not r.get("width"):
                skips.append(f"{r['name']} · {st['label']}: no picture")
                continue
            if st["skip_if"] and st["skip_if"] in carries:
                skips.append(f"{r['name']} · {st['label']}: already done")
                continue
            if sid == "pivot" and _pivot_out(r["path"]).exists():
                skips.append(f"{r['name']} · reframe: already rendered")
                continue
            todo.append(sid)
        if todo:
            plan.append({"path": r["path"], "name": r["name"],
                         "stages": todo})
    return {"plan": plan, "skips": skips, "stages": stages}


def register_indexer(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from indexer.catalog import Catalog

    cat = Catalog()

    @app.get("/api/index/status")
    def api_status():
        return {"folders": cat.folders(), "stats": cat.stats(),
                "exports": str(media_dir("index"))}

    @app.post("/api/index/folders")
    def api_folders(body: dict = Body(...)):
        try:
            if body.get("add"):
                cat.add_folder(str(body["add"]))
            if body.get("remove"):
                cat.remove_folder(str(body["remove"]))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        return {"folders": cat.folders()}

    @app.post("/api/index/scan")
    def api_scan():
        if not cat.folders():
            return JSONResponse({"error": "add a folder first — Index only "
                                          "reads where you point it"},
                                status_code=409)

        def work(job):
            st = cat.scan(progress=lambda m: setattr(job, "message", m[:120]),
                          cancelled=lambda: job.cancel_requested)
            job.message = (f"{st['seen']} seen · {st['added']} added · "
                           f"{st['updated']} updated · {st['missing']} missing")
            return st

        return jobs.start("scan", work, tool="index",
                          label="library scan").to_dict()

    @app.get("/api/index/search")
    def api_search(q: str = "", limit: int = 60):
        rows = cat.search(q, limit=max(1, min(500, limit)))
        return {"q": q, "rows": rows, "fts": cat.fts}

    @app.post("/api/index/export")
    def api_export(body: dict = Body(...)):
        from czcore.exports.fcpxml import selects_csv, stringout

        paths = body.get("paths") or []
        kind = str(body.get("kind", "fcpxml"))
        clips = cat.get_clips([str(p) for p in paths])
        if not clips:
            return JSONResponse({"error": "nothing selected — tick some clips "
                                          "first"}, status_code=422)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = media_dir("index") / f"selects-{stamp}.{ 'csv' if kind == 'csv' else 'fcpxml' }"
        # the catalog stores audio as a stream count; fcpxml wants a flag
        for c in clips:
            c["audio"] = bool(c.get("audio"))
        out.write_text(selects_csv(clips) if kind == "csv" else stringout(clips))
        note = ("open in a spreadsheet" if kind == "csv" else
                "Resolve: File → Import → Timeline → the .fcpxml — it arrives "
                "as a stringout of your selects")
        return {"out": str(out), "clips": len(clips), "note": note}

    @app.get("/api/index/clip")
    def api_clip(path: str):
        rows = cat.get_clips([path])
        if not rows:
            return JSONResponse({"error": "not in the catalog"}, status_code=404)
        return rows[0]

    @app.get("/api/index/gaps")
    def api_gaps(kind: str = "words"):
        return {"kind": kind, "clips": cat.gaps(kind)}

    @app.post("/api/index/transcribe-missing")
    def api_transcribe_missing(body: dict = Body(...)):
        """The batch line, first road: words for every clip that has sound
        and no transcript. Scribe's engine, imported never reimplemented;
        one queue job; per-clip failures reported by name, not swallowed.
        Speakers are the desk's craft — the batch writes words only and
        says so."""
        model = str(body.get("model", "base"))
        clips = ([c for c in cat.gaps("words")
                  if c["path"] in {str(p) for p in body["paths"]}]
                 if body.get("paths") else cat.gaps("words"))
        if not clips:
            return JSONResponse(
                {"error": "every clip with sound already has its words — "
                          "there is no gap to fill"}, status_code=409)

        def work(job):
            import subprocess

            from czcore.tools import ffmpeg_path
            from scribe.transcribe import transcribe

            done, failed = [], []
            exe = ffmpeg_path()
            for i, c in enumerate(clips, 1):
                job.check_cancel()
                p = Path(c["path"])
                if not p.is_file():
                    failed.append(f"{p.name}: drive unplugged?")
                    continue
                job.message = f"{i}/{len(clips)} · {p.name}"
                try:
                    with tempfile.TemporaryDirectory(
                            prefix="index-batch-") as td:
                        wav16 = str(Path(td) / "audio.16k.wav")
                        subprocess.run(
                            [exe, "-y", "-v", "quiet", "-i", str(p),
                             "-ac", "1", "-ar", "16000", wav16], check=True)
                        job.check_cancel()
                        t = transcribe(
                            wav16, model=model,
                            progress=lambda m, i=i: setattr(
                                job, "message",
                                f"{i}/{len(clips)} · {p.name} — {m}"[:120]))
                    t.source = str(p.resolve())
                    p.with_suffix(".scribe.json").write_text(t.to_json())
                    done.append(str(p))
                except (ImportError, OSError) as e:
                    # a missing runtime dooms every clip the same way —
                    # stop with the sentence instead of failing N times
                    raise RuntimeError(
                        f"the ASR engine isn't ready ({e}) — open Scribe "
                        "once, or Settings → runtimes, then run the batch "
                        "again") from e
                except Exception as e:
                    failed.append(f"{p.name}: {e}")
            job.message = "re-logging the fresh words…"
            cat.scan(only=done)
            msg = f"{len(done)} of {len(clips)} clips got their words"
            if failed:
                msg += f" · {len(failed)} failed"
            job.message = msg + " (words only — open a clip in Scribe for speakers)"
            return {"done": done, "failed": failed}

        label = (f"the batch line — words for {len(clips)} "
                 f"clip{'s' if len(clips) != 1 else ''} ({model})")
        return jobs.start("index-words", work, tool="index",
                          label=label).to_dict()

    # -- the road: ticked clips through the tools, clip by clip --------------

    @app.get("/api/index/road-stages")
    def api_road_stages():
        """What the road can run today — each stage honest about why not."""
        out = []
        for st in ROAD_STAGES:
            ok, why = True, ""
            if st["id"] == "pivot" and not importlib.util.find_spec("torch"):
                ok, why = False, ("the person detector needs torch — "
                                  "Settings → runtimes")
            out.append({**{k: st[k] for k in ("id", "label", "tool")},
                        "ok": ok, "why": why})
        return {"stages": out}

    @app.post("/api/index/road")
    def api_road(body: dict = Body(...)):
        stages = [str(s) for s in (body.get("stages") or [])]
        known = {s["id"] for s in ROAD_STAGES}
        if not stages or not set(stages) <= known:
            return JSONResponse(
                {"error": f"pick stages from {sorted(known)}"}, status_code=422)
        if "pivot" in stages and not importlib.util.find_spec("torch"):
            return JSONResponse(
                {"error": "reframe needs torch for the person detector — "
                          "Settings → runtimes, then run the road again"},
                status_code=409)
        rows = cat.get_clips([str(p) for p in (body.get("paths") or [])])
        if not rows:
            return JSONResponse({"error": "nothing ticked — the road needs "
                                          "clips"}, status_code=422)
        planned = _road_plan(rows, stages)
        if not planned["plan"]:
            return JSONResponse(
                {"error": "nothing to do — every ticked clip already has "
                          "what the road would make",
                 "skips": planned["skips"][:20]}, status_code=409)

        def work(job):
            import subprocess

            from czcore.tools import ffmpeg_path

            done, failed = [], list(planned["skips"])
            n = len(planned["plan"])
            for ci, item in enumerate(planned["plan"], 1):
                p = Path(item["path"])
                job.progress = (ci - 1) / n
                for sid in item["stages"]:
                    job.check_cancel()
                    tag = f"{ci}/{n} · {p.name} · {sid}"
                    job.message = tag[:120]
                    try:
                        if sid == "words":
                            from scribe.transcribe import transcribe
                            with tempfile.TemporaryDirectory(
                                    prefix="road-") as td:
                                wav16 = str(Path(td) / "a.wav")
                                subprocess.run(
                                    [ffmpeg_path(), "-y", "-v", "quiet",
                                     "-i", str(p), "-ac", "1", "-ar", "16000",
                                     wav16], check=True)
                                t = transcribe(
                                    wav16,
                                    progress=lambda m: setattr(
                                        job, "message",
                                        f"{tag} — {m}"[:120]))
                            t.source = str(p.resolve())
                            p.with_suffix(".scribe.json").write_text(
                                t.to_json())
                        elif sid == "clear":
                            _run_clear_defaults(job, str(p), tag)
                        elif sid == "pivot":
                            _run_pivot_9x16(job, str(p), tag)
                    except Exception as e:
                        failed.append(f"{p.name} · {sid}: {e}")
                done.append(str(p))
            job.progress = 1.0
            job.message = "re-logging what the road made…"
            cat.scan(only=done)
            ok_n = len(done)
            job.message = (f"{ok_n} clip{'s' if ok_n != 1 else ''} down the "
                           f"road · {len(failed)} skipped or failed")
            return {"done": done, "failed": failed}

        stages_lbl = "+".join(planned["stages"])
        label = (f"the road — {stages_lbl} for {len(planned['plan'])} "
                 f"clip{'s' if len(planned['plan']) != 1 else ''}")
        return jobs.start("index-road", work, tool="index",
                          label=label).to_dict()
