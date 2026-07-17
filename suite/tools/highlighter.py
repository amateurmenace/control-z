"""Highlighter inside the suite — the web app's shape, the suite's engine.

A meeting is a **source**: either a local file (sidecars beside it, as
everywhere in the suite) or a URL session — a folder under the library's
.meetings/<video id>/ holding info json, captions, transcript and insight,
so the whole read (brief, entities, questions, ask) works *before any video
is downloaded*. Downloads are then smart: the full recording, or only the
kept sections, each arriving as its own clip.

The page opens → the nightly yt-dlp check runs (that's the stated deal).
Reading is local and labeled: the brief is extractive, ask is retrieval.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from czcore import ytdlp
from czcore.paths import media_dir

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v")


def _lib() -> Path:
    return media_dir("highlighter")


def _meetings_dir() -> Path:
    d = _lib() / ".meetings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_session(source: str) -> bool:
    return Path(source).is_dir()


def _sidecars(source: str):
    """(scribe.json, highlights.json, insight.json) for either source kind."""
    p = Path(source)
    if p.is_dir():
        return (p / "meeting.scribe.json", p / "meeting.highlights.json",
                p / "insight.json")
    return (p.with_suffix(".scribe.json"), p.with_suffix(".highlights.json"),
            p.with_suffix(".insight.json"))


def _captions_for(path: Path):
    """The .vtt/.srt beside a source (session dir or local file).
    startswith, not glob — these names carry "[id]", poison to glob."""
    if path.is_dir():
        hits = sorted(s for s in path.iterdir() if s.suffix in (".vtt", ".srt"))
        return hits[0] if hits else None
    for ext in (".vtt", ".srt"):
        hits = sorted(s for s in path.parent.iterdir()
                      if s.name.startswith(path.stem) and s.suffix == ext)
        if hits:
            return hits[0]
    return None


def _session_meta(d: Path) -> dict:
    info = d / "meeting.info.json"
    meta = {"id": d.name, "title": d.name, "duration": None, "uploader": None,
            "url": None}
    if info.exists():
        try:
            raw = json.loads(info.read_text())
            meta.update({"title": raw.get("title") or d.name,
                         "duration": raw.get("duration"),
                         "uploader": raw.get("uploader") or raw.get("channel"),
                         "url": raw.get("webpage_url")})
        except ValueError:
            pass
    return meta


def _load_transcript(source: str):
    """(transcript dict, origin) — scribe sidecar, else captions, else the
    library twin's words (a session whose video was already downloaded
    borrows the local copy's transcript instead of re-asking YouTube)."""
    from highlighter.highlights import parse_vtt, transcript_dict

    sc, _, _ = _sidecars(source)
    if sc.exists():
        try:
            t = json.loads(sc.read_text())
            origin = ("captions" if str(t.get("model", "")).startswith("captions")
                      else "scribe")
            return t, origin
        except ValueError:
            pass
    p = Path(source)
    cap = _captions_for(p)
    if not cap and p.is_dir():
        twin = next((f for f in _lib().iterdir()
                     if f.suffix.lower() in VIDEO_EXTS
                     and f"[{p.name}]" in f.name), None)
        if twin:
            tsc, _, _ = _sidecars(str(twin))
            if tsc.exists():
                sc.write_text(tsc.read_text())
                return _load_transcript(source)
            cap = _captions_for(twin)
    if cap:
        segs = parse_vtt(cap.read_text(errors="replace"))
        if segs:
            t = transcript_dict(segs, str(Path(source).resolve()),
                                origin=f"captions:{cap.name}")
            sc.write_text(json.dumps(t))
            return t, "captions"
    return None, None


def register_highlighter(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    lib = _lib()

    @app.get("/api/highlighter/status")
    def api_status():
        return {"ytdlp": ytdlp.status(), "library": str(lib)}

    @app.post("/api/highlighter/ytdlp-check")
    def api_ytdlp_check(body: dict = Body(default={})):
        return {"ytdlp": ytdlp.check_async(force=bool(body.get("force")))}

    # -- ingest: URL -> a readable meeting, before any video moves ---------

    @app.post("/api/highlighter/ingest")
    def api_ingest(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "paste a video URL"}, status_code=422)

        def work(job):
            from czcore import captions as ctext
            from czcore import proxy

            job.message = "reading the page…"
            meta = ytdlp.probe_url(url)
            vid = re.sub(r"[^\w-]", "", str(meta.get("id") or "")) or \
                re.sub(r"[^\w-]", "", url)[-24:]
            d = _meetings_dir() / vid
            d.mkdir(parents=True, exist_ok=True)
            job.message = "fetching the captions…"
            note = None
            try:
                ytdlp.fetch_captions(url, d)
            except RuntimeError as e:
                note = str(e)
            info_p = d / "meeting.info.json"
            if not info_p.exists():
                info_p.write_text(json.dumps({**meta, "webpage_url": url}))
            how = "captions via yt-dlp"
            if not _captions_for(d):
                # yt-dlp's caption routes are walled one by one — the watch
                # page's own timedtext is what the web app runs on, through
                # the user's Webshare proxy when one is configured
                purl = proxy.proxy_url()
                job.message = ("captions via watch page"
                               + (" + your proxy…" if purl else "…"))
                try:
                    got = ctext.fetch_vtt(url, proxy=purl)
                    (d / "meeting.en.vtt").write_text(got["vtt"])
                    how = ("captions via watch page"
                           + (" through your Webshare proxy" if purl else ""))
                    note = None
                except RuntimeError as e:
                    note = str(e)
            if not _captions_for(d) and proxy.relay_enabled():
                # last resort, zero setup: the web app's own public transcript
                # engine (BIG's deployment, its residential proxy behind it).
                # Off by one switch in Settings for the fully-independent.
                job.message = "captions via the community service…"
                try:
                    got = ctext.fetch_vtt_relay(url)
                    (d / "meeting.en.vtt").write_text(got["vtt"])
                    how = "captions via the community service"
                    note = None
                except RuntimeError as e:
                    note = str(e)
            t, origin = _load_transcript(str(d))
            job.message = (f"{len(t['segments'])} segments — {how}"
                           if t else "no captions — transcribe after download")
            return {"source": str(d), "meta": _session_meta(d),
                    "transcript": t, "origin": origin,
                    "captions_note": None if t else note}

        return jobs.start("ingest", work, tool="highlighter",
                          label=f"read — {url[:70]}").to_dict()

    @app.post("/api/highlighter/finder")
    def api_finder(body: dict = Body(...)):
        q = str(body.get("q", "")).strip()
        if not q:
            return JSONResponse({"error": "type what you're looking for"},
                                status_code=422)
        try:
            rows = ytdlp.search(q + " meeting", n=int(body.get("n", 10)))
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        return {"q": q, "rows": rows}

    # -- downloads: the whole thing, or only the kept sections --------------

    @app.post("/api/highlighter/fetch")
    def api_fetch(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        quality = str(body.get("quality", "1080"))
        sections = body.get("sections") or None
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "paste a video URL (YouTube, Zoom, "
                                          "Vimeo, a direct file…)"},
                                status_code=422)
        if sections:
            try:
                sections = [(float(s["start"]), float(s["end"]))
                            for s in sections]
            except (KeyError, TypeError, ValueError):
                return JSONResponse({"error": "sections need start and end "
                                              "seconds"}, status_code=422)

        def work(job):
            def prog(p, m):
                if p >= 0:
                    job.progress = p
                job.message = m or job.message

            got = ytdlp.download(url, lib, quality=quality, progress=prog,
                                 cancelled=lambda: job.cancel_requested,
                                 sections=sections)
            n = len(got.get("paths", [got["path"]]))
            job.message = (f"fetched {n} section clip{'s' if n > 1 else ''}"
                           if sections else
                           f"fetched {Path(got['path']).name}")
            return {**got, "sections": bool(sections),
                    "captions": _captions_for(Path(got["path"])) is not None}

        what = (f"{len(sections)} sections" if sections else quality)
        return jobs.start("fetch", work, tool="highlighter",
                          label=f"fetch ({what}) — {url[:60]}").to_dict()

    @app.get("/api/highlighter/library")
    def api_library():
        videos = []
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
            sc, hl, _ = _sidecars(str(p))
            videos.append({
                "path": str(p), "name": p.name, "size": p.stat().st_size,
                "mtime": p.stat().st_mtime, **info,
                "captions": _captions_for(p) is not None,
                "transcript": sc.exists(), "highlights": hl.exists(),
            })
        videos.sort(key=lambda r: -r["mtime"])
        meetings = []
        if _meetings_dir().exists():
            for d in sorted(_meetings_dir().iterdir()):
                if not d.is_dir():
                    continue
                sc, _, _ = _sidecars(str(d))
                meetings.append({"source": str(d), **_session_meta(d),
                                 "transcript": sc.exists(),
                                 "mtime": d.stat().st_mtime})
            meetings.sort(key=lambda r: -r["mtime"])
        return {"videos": videos, "meetings": meetings}

    # -- the read ------------------------------------------------------------

    @app.post("/api/highlighter/transcript")
    def api_transcript(body: dict = Body(...)):
        source = str(Path(body["path"]).expanduser())
        if not Path(source).exists():
            return JSONResponse({"error": f"no such source: {source}"},
                                status_code=404)
        t, origin = _load_transcript(source)
        _, hl, _ = _sidecars(source)
        picks = None
        if hl.exists():
            try:
                picks = json.loads(hl.read_text())
            except ValueError:
                picks = None
        meta = _session_meta(Path(source)) if _is_session(source) else None
        return {"transcript": t, "origin": origin, "highlights": picks,
                "meta": meta, "session": _is_session(source)}

    @app.post("/api/highlighter/insight")
    def api_insight(body: dict = Body(...)):
        from highlighter import insight

        source = str(Path(body["path"]).expanduser())
        t, origin = _load_transcript(source)
        if not t or not t.get("segments"):
            return JSONResponse({"error": "no transcript yet — the meeting "
                                          "needs words before it can be read"},
                                status_code=409)
        _, _, cache = _sidecars(source)
        if cache.exists() and not body.get("fresh"):
            try:
                data = json.loads(cache.read_text())
                if data.get("n_segments") == len(t["segments"]):
                    return data
            except ValueError:
                pass
        segs = t["segments"]
        data = {
            "origin": origin, "n_segments": len(segs),
            "brief": insight.brief(segs),
            "entities": insight.entities(segs),
            "wordfreq": insight.word_freq(segs),
            "questions": insight.questions(segs),
            "participation": insight.participation(segs),
            "topics": insight.topics(segs),
            "decisions": insight.decisions(segs),
        }
        cache.write_text(json.dumps(data))
        return data

    @app.post("/api/highlighter/ask")
    def api_ask(body: dict = Body(...)):
        from highlighter import insight

        source = str(Path(body["path"]).expanduser())
        t, _ = _load_transcript(source)
        if not t:
            return JSONResponse({"error": "no transcript to ask"},
                                status_code=409)
        return insight.ask(t["segments"], str(body.get("q", "")))

    @app.post("/api/highlighter/detect")
    def api_detect(body: dict = Body(...)):
        from highlighter.highlights import (audio_energy, blend_energy,
                                            build_reel, score_segments)

        source = str(Path(body["path"]).expanduser())
        target = float(body.get("target", 90.0))
        keywords = [k.strip() for k in str(body.get("keywords", "")).split(",")
                    if k.strip()]
        use_energy = bool(body.get("energy", True)) and not _is_session(source)
        name = Path(source).name
        t, origin = _load_transcript(source)
        if not t or not t.get("segments"):
            return JSONResponse(
                {"error": "no transcript yet — this needs words to read. "
                          "No captions came along; run the Scribe pass first."},
                status_code=409)

        def work(job):
            job.message = "reading the meeting…"
            scored = score_segments(t["segments"], keywords)
            if use_energy:
                job.message = "listening for the room…"
                scored = blend_energy(scored, audio_energy(
                    source, progress=lambda m: setattr(job, "message", m)))
            picks = build_reel(scored, target=target)
            payload = {"picks": picks, "target": target,
                       "origin": origin, "keywords": keywords,
                       "lane": [{"start": s["start"], "end": s["end"],
                                 "score": s["score"]} for s in scored]}
            _, hl, _ = _sidecars(source)
            hl.write_text(json.dumps(payload))
            total = sum(p["end"] - p["start"] for p in picks)
            job.message = f"{len(picks)} moments · {total:.0f}s"
            return payload

        return jobs.start("detect", work, tool="highlighter",
                          label=f"{name} — find the moments").to_dict()

    # -- the cut ---------------------------------------------------------------

    @app.post("/api/highlighter/reel")
    def api_reel(body: dict = Body(...)):
        from highlighter.reel import render_reel

        path = str(Path(body["path"]).expanduser())
        ranges = body.get("ranges", [])
        preset = str(body.get("preset", "h264"))
        if not ranges:
            return JSONResponse({"error": "the reel is empty — keep at least "
                                          "one moment"}, status_code=422)
        if not Path(path).is_file():
            return JSONResponse({"error": "that source isn't a local file — "
                                          "download it (or its sections) first"},
                                status_code=409)
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

    @app.post("/api/highlighter/stitch")
    def api_stitch(body: dict = Body(...)):
        from highlighter.reel import stitch_files

        files = [str(Path(f).expanduser()) for f in body.get("files", [])]
        files = [f for f in files if Path(f).is_file()]
        preset = str(body.get("preset", "h264"))
        if len(files) < 1:
            return JSONResponse({"error": "no section clips to stitch"},
                                status_code=422)
        out = str(lib / f"reel-{time.strftime('%Y%m%d-%H%M%S')}")

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            job.message = "stitching the sections…"
            rep = stitch_files(files, out, preset=preset, progress=prog,
                               cancelled=lambda: job.cancel_requested)
            job.message = f"{rep['clips']} clips · {rep['duration']}s"
            return rep

        return jobs.start("stitch", work, tool="highlighter",
                          label=f"stitch {len(files)} section clips").to_dict()

    # the viewer reuses /api/media/open; the selects EDL goes through
    # /api/scribe/selects — it IS the paper edit.
