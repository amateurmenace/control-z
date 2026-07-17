"""Highlighter inside the suite — fetch, read, mark, cut.

The page opens → the nightly yt-dlp check runs (that's the stated deal).
Transcripts are borrowed before they're computed: a Scribe sidecar wins,
YouTube's own captions seed one instantly (labeled as captions), and the
full Scribe pass is one click away because it's the same app. Detection
writes a .highlights.json sidecar; the reel is rendered from whatever
ranges the text surface says.
"""

from __future__ import annotations

import json
from pathlib import Path

from czcore import ytdlp
from czcore.paths import media_dir

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v")


def _hl_sidecar(path: str) -> Path:
    return Path(path).with_suffix(".highlights.json")


def _scribe_sidecar(path: str) -> Path:
    return Path(path).with_suffix(".scribe.json")


def _captions_for(path: Path):
    """The .vtt/.srt yt-dlp wrote beside this file, if any.
    startswith, not glob — these names carry "[id]", poison to glob."""
    for ext in (".vtt", ".srt"):
        hits = sorted(s for s in path.parent.iterdir()
                      if s.name.startswith(path.stem) and s.suffix == ext)
        if hits:
            return hits[0]
    return None


def _load_transcript(path: str):
    """(transcript dict, origin) — scribe sidecar, else captions, else None."""
    from highlighter.highlights import parse_vtt, transcript_dict

    sc = _scribe_sidecar(path)
    if sc.exists():
        try:
            t = json.loads(sc.read_text())
            origin = ("captions" if str(t.get("model", "")).startswith("captions")
                      else "scribe")
            return t, origin
        except ValueError:
            pass
    cap = _captions_for(Path(path))
    if cap:
        segs = parse_vtt(cap.read_text(errors="replace"))
        if segs:
            t = transcript_dict(segs, str(Path(path).resolve()),
                                origin=f"captions:{cap.name}")
            # written as the shared sidecar so Scribe can edit it and Index
            # can search it — model says where it came from, never a lie
            sc.write_text(json.dumps(t))
            return t, "captions"
    return None, None


def register_highlighter(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    lib = media_dir("highlighter")

    @app.get("/api/highlighter/status")
    def api_status():
        return {"ytdlp": ytdlp.status(), "library": str(lib)}

    @app.post("/api/highlighter/ytdlp-check")
    def api_ytdlp_check(body: dict = Body(default={})):
        return {"ytdlp": ytdlp.check_async(force=bool(body.get("force")))}

    @app.post("/api/highlighter/fetch")
    def api_fetch(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        quality = str(body.get("quality", "best"))
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "paste a video URL (YouTube, Zoom, "
                                          "Vimeo, a direct file…)"},
                                status_code=422)

        def work(job):
            def prog(p, m):
                if p >= 0:
                    job.progress = p
                job.message = m or job.message

            got = ytdlp.download(url, lib, quality=quality, progress=prog,
                                 cancelled=lambda: job.cancel_requested)
            p = Path(got["path"])
            job.message = f"fetched {p.name}"
            return {**got, "captions": _captions_for(p) is not None}

        label = f"fetch — {url[:80]}"
        return jobs.start("fetch", work, tool="highlighter", label=label).to_dict()

    @app.get("/api/highlighter/library")
    def api_library():
        rows = []
        for p in sorted(lib.iterdir()):
            if p.suffix.lower() not in VIDEO_EXTS:
                continue
            info = {}
            ij = p.with_suffix(".info.json")
            if ij.exists():
                try:
                    raw = json.loads(ij.read_text())
                    info = {"title": raw.get("title"),
                            "duration": raw.get("duration"),
                            "uploader": raw.get("uploader") or raw.get("channel"),
                            "url": raw.get("webpage_url")}
                except ValueError:
                    pass
            rows.append({
                "path": str(p), "name": p.name, "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                **info,
                "captions": _captions_for(p) is not None,
                "transcript": _scribe_sidecar(str(p)).exists(),
                "highlights": _hl_sidecar(str(p)).exists(),
            })
        rows.sort(key=lambda r: -r["mtime"])
        return rows

    @app.post("/api/highlighter/transcript")
    def api_transcript(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"}, status_code=404)
        t, origin = _load_transcript(path)
        picks = None
        hl = _hl_sidecar(path)
        if hl.exists():
            try:
                picks = json.loads(hl.read_text())
            except ValueError:
                picks = None
        return {"transcript": t, "origin": origin, "highlights": picks}

    @app.post("/api/highlighter/detect")
    def api_detect(body: dict = Body(...)):
        from highlighter.highlights import (audio_energy, blend_energy,
                                            build_reel, score_segments)

        path = str(Path(body["path"]).expanduser())
        target = float(body.get("target", 90.0))
        keywords = [k.strip() for k in str(body.get("keywords", "")).split(",")
                    if k.strip()]
        use_energy = bool(body.get("energy", True))
        name = Path(path).name
        t, origin = _load_transcript(path)
        if not t or not t.get("segments"):
            return JSONResponse(
                {"error": "no transcript yet — this needs words to read. "
                          "Fetch found no captions; run the Scribe pass first."},
                status_code=409)

        def work(job):
            job.message = "reading the meeting…"
            scored = score_segments(t["segments"], keywords)
            if use_energy:
                job.message = "listening for the room…"
                scored = blend_energy(scored, audio_energy(
                    path, progress=lambda m: setattr(job, "message", m)))
            picks = build_reel(scored, target=target)
            payload = {"picks": picks, "target": target,
                       "origin": origin, "keywords": keywords,
                       "lane": [{"start": s["start"], "end": s["end"],
                                 "score": s["score"]} for s in scored]}
            _hl_sidecar(path).write_text(json.dumps(payload))
            total = sum(p["end"] - p["start"] for p in picks)
            job.message = f"{len(picks)} moments · {total:.0f}s"
            return payload

        return jobs.start("detect", work, tool="highlighter",
                          label=f"{name} — find the moments").to_dict()

    @app.post("/api/highlighter/reel")
    def api_reel(body: dict = Body(...)):
        from highlighter.reel import render_reel

        path = str(Path(body["path"]).expanduser())
        ranges = body.get("ranges", [])
        preset = str(body.get("preset", "h264"))
        if not ranges:
            return JSONResponse({"error": "the reel is empty — keep at least "
                                          "one moment"}, status_code=422)
        p = Path(path)
        out = str(p.with_suffix("")) + ".reel"
        name = p.name

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            job.message = "cutting the reel…"
            rep = render_reel(path, ranges, out, preset=preset, progress=prog,
                              cancelled=lambda: job.cancel_requested)
            job.message = (f"{rep['clips']} cuts · {rep['duration']}s · "
                           f"{rep['encoder']}")
            return rep

        total = sum(float(r["end"]) - float(r["start"]) for r in ranges)
        return jobs.start(
            "reel", work, tool="highlighter",
            label=f"{name} — reel ({len(ranges)} cuts, {total:.0f}s)").to_dict()

    # that's the whole backend: the viewer reuses /api/media/open, and the
    # selects EDL goes through /api/scribe/selects — it IS the paper edit.
