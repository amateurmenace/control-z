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


def _info_for(source: str) -> dict:
    """The full info json for either source kind — chapters, description,
    the fields _session_meta doesn't carry. Empty dict when absent."""
    p = Path(source)
    ij = (p / "meeting.info.json") if p.is_dir() else p.with_suffix(".info.json")
    if ij.exists():
        try:
            return json.loads(ij.read_text())
        except ValueError:
            pass
    return {}


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
    #
    # The web app answers in one round trip; this matches it. YouTube URLs
    # skip the yt-dlp probe entirely (the id is in the URL, the title is in
    # the watch page the caption fetch already reads) and the two local
    # caption routes RACE on threads — first one home wins. The community
    # relay only runs after both local routes lose. A session that was
    # already read returns instantly.

    def _finish_ingest(job, d, how, note, t0):
        t, origin = _load_transcript(str(d))
        took = time.monotonic() - t0
        job.message = (f"read in {took:.1f}s — {len(t['segments'])} segments, "
                       f"{how}" if t
                       else "no captions — transcribe after download")
        return {"source": str(d), "meta": _session_meta(d),
                "transcript": t, "origin": origin,
                "captions_note": None if t else note}

    def _ingest_youtube(job, url, vid, t0):
        from concurrent.futures import (FIRST_COMPLETED, ThreadPoolExecutor,
                                        wait)

        from czcore import captions as ctext
        from czcore import proxy

        d = _meetings_dir() / vid
        d.mkdir(parents=True, exist_ok=True)
        purl = proxy.proxy_url()
        job.message = ("asking YouTube both ways at once…"
                       + (" (your proxy rides along)" if purl else ""))

        def watch_page():
            got = ctext.fetch_vtt(url, proxy=purl)
            return {"how": "captions via watch page"
                           + (" through your Webshare proxy" if purl else ""),
                    "vtt": got["vtt"], "meta": got.get("meta") or {}}

        def via_ytdlp():
            ytdlp.fetch_captions(url, d)   # writes info.json + vtt into d
            if not _captions_for(d):
                raise RuntimeError("yt-dlp reached the page but captions "
                                   "didn't come")
            return {"how": "captions via yt-dlp", "vtt": None, "meta": {}}

        notes, scraped_meta, winner = [], {}, None
        gated = False
        ex = ThreadPoolExecutor(max_workers=2)
        try:
            pending = {ex.submit(watch_page), ex.submit(via_ytdlp)}
            while pending and winner is None and not gated:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    try:
                        winner = winner or f.result()
                    except Exception as e:  # each loser explains itself
                        notes.append(str(e))
                        scraped_meta.update(getattr(e, "meta", None) or {})
                        # the empty-200 is YouTube's definitive gate tell —
                        # don't wait out the other doomed route, go to relay
                        gated = gated or "empty body" in str(e)
        finally:
            # the loser may still be running; let it finish in the background
            # (same files, same session dir) rather than stalling the answer
            ex.shutdown(wait=False, cancel_futures=True)

        if winner and winner.get("vtt"):
            (d / "meeting.en.vtt").write_text(winner["vtt"])
        if winner:
            scraped_meta.update(winner.get("meta") or {})
        if not _captions_for(d) and proxy.relay_enabled():
            # last resort, zero setup: the web app's own public transcript
            # engine (BIG's deployment, its residential proxy behind it).
            # Off by one switch in Settings for the fully-independent.
            job.message = "captions via the community service…"
            try:
                got = ctext.fetch_vtt_relay(url)
                (d / "meeting.en.vtt").write_text(got["vtt"])
                winner = {"how": "captions via the community service"}
            except RuntimeError as e:
                notes.append(str(e))
        info_p = d / "meeting.info.json"
        existing = {}
        if info_p.exists():
            try:
                existing = json.loads(info_p.read_text())
            except ValueError:
                pass
        if scraped_meta or not existing:
            # merge, never shrink: a re-read with fresher scraped fields
            # (title, description → the agenda) upgrades the session
            info_p.write_text(json.dumps(
                {**existing, "id": vid, "webpage_url": url,
                 **{k: v for k, v in scraped_meta.items() if v}}))
        how = (winner["how"] if winner
               else "no caption route today — kept what was already here")
        return _finish_ingest(job, d, how, " · ".join(notes[-2:]) or None, t0)

    @app.post("/api/highlighter/ingest")
    def api_ingest(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        fresh = bool(body.get("fresh"))
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "paste a video URL"}, status_code=422)

        def work(job):
            from czcore import captions as ctext
            from czcore import proxy

            t0 = time.monotonic()
            vid = ctext.video_id(url)
            if vid:
                d = _meetings_dir() / vid
                sc, _, _ = _sidecars(str(d))
                if d.exists() and sc.exists() and not fresh:
                    return _finish_ingest(job, d, "already read (cached)",
                                          None, t0)
                return _ingest_youtube(job, url, vid, t0)

            # not YouTube-shaped: yt-dlp knows the other thousand sites —
            # probe for the id first, then ask it for captions
            job.message = "reading the page…"
            meta = ytdlp.probe_url(url)
            svid = re.sub(r"[^\w-]", "", str(meta.get("id") or "")) or \
                re.sub(r"[^\w-]", "", url)[-24:]
            d = _meetings_dir() / svid
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
            return _finish_ingest(job, d, "captions via yt-dlp", note, t0)

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
                # "framing" gates the cache: caches from before the
                # analyzer grew rebuild once instead of shipping half
                if data.get("n_segments") == len(t["segments"]) \
                        and "framing" in data:
                    return data
            except ValueError:
                pass
        segs = t["segments"]
        meta = _session_meta(Path(source)) if _is_session(source) else None
        data = {
            "origin": origin, "n_segments": len(segs),
            "brief": insight.brief(segs),
            "entities": insight.entities(segs),
            "wordfreq": insight.word_freq(segs),
            "questions": insight.questions(segs),
            "participation": insight.participation(segs),
            "topics": insight.topics(segs),
            "decisions": insight.decisions(segs),
            # names for Whisper's decoder — harvested here so the Scribe
            # upgrade can teach it the people/places before it listens
            "hotwords": insight.hotwords(segs, meta),
            # the shape of the meeting — counted, not modeled
            "pace": insight.pace(segs),
            "dynamics": insight.dynamics(segs),
            # the upload's own agenda: chapters, else description timestamps
            "agenda": insight.agenda(_info_for(source)),
            # the analyzer's map and its friction points
            "topic_map": insight.topic_map(segs),
            "disagreements": insight.disagreements(segs),
            # how the meeting talks, and who appears beside whom
            "framing": insight.framing(segs),
            "crossref": insight.crossref(segs),
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

    # -- the generative upgrade: the user's own key, the meeting's own words --
    #
    # These two endpoints exist only when the user configured a key
    # (Settings → AI). The local extractive/retrieval reads stay the
    # default; these are labeled generative in the UI and cite timestamps
    # so every claim can be clicked and checked.

    def _transcript_lines(t, budget: int = 60000) -> str:
        lines = [f"[{int(s['start'] // 60):02d}:{int(s['start'] % 60):02d}] "
                 f"{(s.get('speaker') + ': ') if s.get('speaker') else ''}"
                 f"{s.get('text', '')}"
                 for s in t["segments"]]
        text = "\n".join(lines)
        if len(text) <= budget:
            return text
        # long meeting: keep every line's timestamp shape but stride-sample
        stride = max(2, len(text) // budget + 1)
        return "\n".join(lines[::stride])

    @app.post("/api/highlighter/ai-brief")
    def api_ai_brief(body: dict = Body(...)):
        from czcore import llm

        if not llm.enabled():
            return JSONResponse({"error": "no API key configured — "
                                          "Settings → AI"}, status_code=409)
        source = str(Path(body["path"]).expanduser())
        t, _ = _load_transcript(source)
        if not t or not t.get("segments"):
            return JSONResponse({"error": "no transcript to brief"},
                                status_code=409)
        meta = _session_meta(Path(source)) if _is_session(source) else {}
        title = meta.get("title") or Path(source).name
        # one meeting, one spend: the summary caches beside the transcript
        # and reopening answers from disk unless the words changed
        p = Path(source)
        cache_p = (p / "ai-brief.json") if p.is_dir() \
            else p.with_suffix(".ai-brief.json")
        if cache_p.exists() and not body.get("fresh"):
            try:
                cached = json.loads(cache_p.read_text())
                if cached.get("n_segments") == len(t["segments"]):
                    def cached_work(job):
                        job.message = "executive summary — cached"
                        return cached
                    return jobs.start("ai-brief", cached_work,
                                      tool="highlighter",
                                      label=f"AI brief (cached) — {title[:50]}"
                                      ).to_dict()
            except ValueError:
                pass

        def work(job):
            job.message = f"asking {llm.status()['model']} (your key)…"
            text = llm.complete(
                system=("You write executive briefs of public civic meetings "
                        "for busy residents. Ground every claim in the "
                        "transcript; keep the [MM:SS] timestamps you quote "
                        "inline so readers can click them. Plain language, "
                        "no filler, no speculation."),
                prompt=(f"Meeting: {title}\n\nTranscript (timestamped):\n"
                        f"{_transcript_lines(t)}\n\n"
                        "Write: 1) a two-sentence what-happened lede, "
                        "2) 4-6 bullet points of decisions/major discussion "
                        "each starting with its [MM:SS], 3) one sentence on "
                        "what's next. Under 250 words."))
            job.message = "brief written — generative, your key"
            out = {"text": text, "model": llm.status()["model"],
                   "n_segments": len(t["segments"])}
            cache_p.write_text(json.dumps(out))
            return out

        return jobs.start("ai-brief", work, tool="highlighter",
                          label=f"AI brief — {title[:60]}").to_dict()

    @app.post("/api/highlighter/ai-ask")
    def api_ai_ask(body: dict = Body(...)):
        from czcore import llm

        from highlighter import insight

        if not llm.enabled():
            return JSONResponse({"error": "no API key configured — "
                                          "Settings → AI"}, status_code=409)
        source = str(Path(body["path"]).expanduser())
        q = str(body.get("q", "")).strip()
        if not q:
            return JSONResponse({"error": "ask something"}, status_code=422)
        t, _ = _load_transcript(source)
        if not t:
            return JSONResponse({"error": "no transcript to ask"},
                                status_code=409)
        # retrieval grounds the generation: the model answers FROM the
        # passages, and says so when they don't contain the answer
        hits = insight.ask(t["segments"], q, k=8)

        def work(job):
            job.message = f"asking {llm.status()['model']} (your key)…"
            passages = "\n".join(
                f"[{int(p['t'] // 60):02d}:{int(p['t'] % 60):02d}] "
                f"{(p.get('speaker') + ': ') if p.get('speaker') else ''}"
                f"{p['text']}" for p in hits.get("passages", []))
            text = llm.complete(
                system=("Answer questions about a civic meeting using ONLY "
                        "the provided transcript passages. Cite [MM:SS] "
                        "inline for every claim. If the passages don't "
                        "answer it, say exactly that."),
                prompt=f"Passages:\n{passages or '(none matched)'}\n\n"
                       f"Question: {q}",
                max_tokens=600)
            job.message = "answered — generative, your key"
            return {"text": text, "passages": hits.get("passages", []),
                    "model": llm.status()["model"]}

        return jobs.start("ai-ask", work, tool="highlighter",
                          label=f"AI answer — {q[:60]}").to_dict()

    @app.post("/api/highlighter/ai-reel")
    def api_ai_reel(body: dict = Body(...)):
        """The web app's "Make AI Highlight Reel", bring-your-own-key: the
        model reads the timestamped transcript and answers with moments;
        every pick is validated against the transcript's own clock before
        it becomes a clip. Local scoring stays the no-key default."""
        from czcore import llm

        if not llm.enabled():
            return JSONResponse({"error": "no API key configured — "
                                          "Settings → AI (the local Make "
                                          "Highlight Reel needs none)"},
                                status_code=409)
        source = str(Path(body["path"]).expanduser())
        target = float(body.get("target", 90.0))
        t, origin = _load_transcript(source)
        if not t or not t.get("segments"):
            return JSONResponse({"error": "no transcript yet"}, status_code=409)
        duration = max(float(s.get("end", 0)) for s in t["segments"])
        meta = _session_meta(Path(source)) if _is_session(source) else {}
        title = meta.get("title") or Path(source).name

        def work(job):
            job.message = f"asking {llm.status()['model']} for the moments…"
            raw = llm.complete(
                system=("You pick highlight moments from civic meeting "
                        "transcripts for a public highlight reel. Answer "
                        "with ONLY a JSON array, no prose: "
                        '[{"start": seconds, "end": seconds, '
                        '"label": "5-9 words", "reason": "why it matters"}]. '
                        "Each moment 8-45 seconds, complete thoughts, the "
                        "most consequential decisions/testimony first."),
                prompt=(f"Meeting: {title}\nTotal length: {duration:.0f}s\n"
                        f"Pick moments totaling ~{target:.0f}s.\n\n"
                        f"Transcript:\n{_transcript_lines(t)}"),
                max_tokens=1500)
            m = re.search(r"\[.*\]", raw, re.S)
            if not m:
                raise RuntimeError("the model answered without a JSON array "
                                   "of moments — try again")
            try:
                rows = json.loads(m.group(0))
            except ValueError as e:
                raise RuntimeError("the model's answer wasn't valid JSON "
                                   f"({e}) — try again") from e
            picks = []
            for i, r in enumerate(rows[:10]):
                try:
                    a = max(0.0, min(float(r["start"]), duration - 1))
                    b = min(float(r["end"]), duration)
                except (KeyError, TypeError, ValueError):
                    continue
                if b - a < 3:          # too short to mean anything on air
                    continue
                picks.append({
                    "start": round(a, 1), "end": round(b, 1),
                    "text": str(r.get("label", ""))[:90],
                    "reasons": [f"AI pick: {str(r.get('reason', ''))[:120]}"],
                    "score": round(1.0 - i * 0.06, 2),
                })
            if not picks:
                raise RuntimeError("no usable moments survived validation — "
                                   "the local Make Highlight Reel still works")
            payload = {"picks": picks, "target": target,
                       "origin": f"ai:{llm.status()['model']}",
                       "keywords": [], "lane": []}
            _, hl, _ = _sidecars(source)
            hl.write_text(json.dumps(payload))
            total = sum(p["end"] - p["start"] for p in picks)
            job.message = (f"{len(picks)} moments · {total:.0f}s — "
                           f"generative, your key")
            return payload

        return jobs.start("ai-reel", work, tool="highlighter",
                          label=f"AI highlight reel — {title[:55]}").to_dict()

    # -- investigate: a name, looked up where lookups live --------------------

    @app.post("/api/highlighter/investigate")
    def api_investigate(body: dict = Body(...)):
        """Google News RSS for a proper noun — fetched server-side (the
        browser can't cross-origin it), parsed with stdlib, returned as
        plain rows. Wikipedia rides client-side (its API allows CORS)."""
        import urllib.parse
        import urllib.request
        import xml.etree.ElementTree as ET

        q = str(body.get("q", "")).strip()
        if not q:
            return JSONResponse({"error": "select or type a name first"},
                                status_code=422)
        url = ("https://news.google.com/rss/search?q="
               + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "control-z-suite"})
            raw = urllib.request.urlopen(req, timeout=15).read()
            root = ET.fromstring(raw)
        except Exception as e:
            return JSONResponse({"error": f"news lookup didn't answer "
                                          f"({e.__class__.__name__})"},
                                status_code=502)
        rows = []
        for item in root.iter("item"):
            src = item.find("source")
            rows.append({
                "title": (item.findtext("title") or "")[:160],
                "link": item.findtext("link") or "",
                "date": (item.findtext("pubDate") or "")[:16],
                "source": (src.text if src is not None else "")[:40],
            })
            if len(rows) >= 10:
                break
        return {"q": q, "rows": rows}

    @app.post("/api/highlighter/documents")
    def api_documents(body: dict = Body(...)):
        """The meeting's paper trail: the town's own CivicClerk portal,
        searched around the meeting's date through the Grabber's reader.
        Agendas and minutes come back as typed rows with real file URLs —
        found by date and name match, not by a model."""
        import datetime as dt

        from grabber import civicclerk

        source = str(body.get("path", ""))
        tenant = str(body.get("tenant") or civicclerk.DEFAULT_TENANT)
        window = min(30, max(1, int(body.get("window_days") or 10)))
        title = str(body.get("title", ""))
        raw_date = str(body.get("date", ""))
        if source and not title:
            p = Path(source)
            title = (_session_meta(p)["title"] if _is_session(source)
                     else p.stem)
        if source and not raw_date:
            raw_date = str(_info_for(source).get("upload_date") or "")
        day = None
        # the title's own date is the meeting's day ("… - March 10, 2026");
        # upload_date only says when the video landed, so it goes second
        months = ("january february march april may june july august "
                  "september october november december").split()
        m = re.search(r"(" + "|".join(months) + r")\s+(\d{1,2}),?\s+(\d{4})",
                      title.lower())
        if m:
            try:
                day = dt.date(int(m.group(3)), months.index(m.group(1)) + 1,
                              int(m.group(2)))
            except ValueError:
                pass
        if day is None:
            m = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", raw_date)
            if m:
                try:
                    day = dt.date(int(m.group(1)), int(m.group(2)),
                                  int(m.group(3)))
                except ValueError:
                    pass
        if day is None:
            # no date on record — read the recent window and let the
            # name match do the work
            day, window = dt.date.today(), 30
        try:
            # two half-windows, each ordered newest-first by the portal: a
            # busy civic calendar can out-count the page cap, and one wide
            # query would keep only its far edge — the nearest days lose
            before = civicclerk.search_events(
                tenant, (day - dt.timedelta(days=window)).isoformat(),
                day.isoformat())
            after = civicclerk.search_events(
                tenant, day.isoformat(),
                (day + dt.timedelta(days=window)).isoformat())
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        events, seen_ids = [], set()
        for ev in before + after:
            if ev["id"] in seen_ids:
                continue
            seen_ids.add(ev["id"])
            events.append(ev)
        # score: shared word pairs first ("select board" names the body;
        # single words tie half the calendar), then civic-boilerplate-free
        # single words, then date distance
        low_title = title.lower()
        months = ("january february march april may june july august "
                  "september october november december").split()
        drop = {"meeting", "the", "of", "and", "town", "session", "work",
                "special", "regular", "committee", "board", *months}
        drop |= {w for w in re.findall(r"[a-z]+", low_title)
                 if tenant.startswith(w)}
        tw = [w for w in re.findall(r"[a-z]+", low_title) if len(w) > 2]
        tpairs = {f"{a} {b}" for a, b in zip(tw, tw[1:])}
        twords = {w for w in tw if w not in drop}
        rows = []
        for ev in events:
            elow = f"{ev['name']} {ev['category']}".lower()
            ewords = set(re.findall(r"[a-z]+", elow))
            overlap = (2 * sum(1 for p in tpairs if p in elow)
                       + len(twords & ewords))
            ev_day = None
            m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(ev.get("when", "")))
            if m2:
                ev_day = dt.date(*map(int, m2.groups()))
            dist = abs((ev_day - day).days) if ev_day else window
            if not ev["files"] and not overlap:
                continue
            rows.append({**ev, "score": overlap, "days_off": dist})
        rows.sort(key=lambda r: (-r["score"], r["days_off"]))
        return {"tenant": tenant, "around": day.isoformat(),
                "window_days": window, "matched_words": sorted(twords),
                "events": rows[:12]}

    @app.post("/api/highlighter/mentions")
    def api_mentions(body: dict = Body(...)):
        """The desktop's own knowledge base: every meeting in the library
        that says this name, counted from the transcripts already on disk."""
        q = str(body.get("q", "")).strip().lower()
        current = str(body.get("path", ""))
        if len(q) < 3:
            return JSONResponse({"error": "too short to search"},
                                status_code=422)
        rows = []
        sources = []
        if _meetings_dir().exists():
            sources += [d for d in _meetings_dir().iterdir() if d.is_dir()]
        sources += [p for p in lib.iterdir()
                    if p.suffix.lower() in VIDEO_EXTS]
        for src in sources[:120]:
            if str(src) == current:
                continue
            sc, _, _ = _sidecars(str(src))
            if not sc.exists():
                continue
            try:
                segs = json.loads(sc.read_text()).get("segments") or []
            except ValueError:
                continue
            count, first_t = 0, None
            for s in segs:
                if q in str(s.get("text", "")).lower():
                    count += 1
                    if first_t is None:
                        first_t = round(float(s.get("start", 0)), 1)
            if count:
                meta = _session_meta(src) if src.is_dir() else {}
                rows.append({"source": str(src),
                             "title": meta.get("title") or src.name,
                             "count": count, "t": first_t})
        rows.sort(key=lambda r: -r["count"])
        return {"q": q, "rows": rows[:20]}

    # -- the full report: one document, sourced to the second ----------------

    @app.post("/api/highlighter/report")
    def api_report(body: dict = Body(...)):
        from czcore import llm, pdfout

        source = str(Path(body["path"]).expanduser())
        t, origin = _load_transcript(source)
        if not t or not t.get("segments"):
            return JSONResponse({"error": "no transcript to report on"},
                                status_code=409)
        meta = _session_meta(Path(source)) if _is_session(source) else {}
        title = meta.get("title") or Path(source).stem
        p = Path(source)
        md_p = (p / "report.md") if p.is_dir() else p.with_suffix(".report.md")
        pdf_p = md_p.with_suffix(".pdf")
        if md_p.exists() and pdf_p.exists() and not body.get("fresh"):
            def cached_work(job):
                job.message = "full report — cached"
                return {"md": str(md_p), "pdf": str(pdf_p),
                        "text": md_p.read_text()}
            return jobs.start("report", cached_work, tool="highlighter",
                              label=f"report (cached) — {title[:50]}"
                              ).to_dict()

        def work(job):
            from highlighter import insight

            segs = t["segments"]
            job.message = "reading the meeting…"
            dur = max(float(s.get("end", 0)) for s in segs)
            parts = [f"# {title}",
                     f"Full meeting report - {len(segs)} transcript segments,"
                     f" {int(dur // 3600)}h {int(dur % 3600 // 60)}m."
                     f" Words from {origin or 'the transcript'}."]
            if llm.enabled():
                job.message = f"writing the narrative ({llm.status()['model']}, your key)…"
                try:
                    parts += ["", llm.complete(
                        system=("You write thorough civic meeting reports "
                                "for the public record. Markdown; ## section "
                                "headings; keep every [MM:SS] timestamp you "
                                "cite inline. Ground every claim in the "
                                "transcript."),
                        prompt=("Write the report: ## Executive Summary "
                                "(a paragraph), ## Key Decisions (bullets "
                                "with [MM:SS]), ## Discussion (2-3 "
                                "paragraphs), ## Public Comment, ## What's "
                                "Next. Under 800 words.\n\nMeeting: "
                                f"{title}\n\n{_transcript_lines(t)}"),
                        max_tokens=2200)]
                except RuntimeError as e:
                    parts += ["", f"(AI narrative unavailable - {e})"]
            job.message = "counting the record…"
            dec = insight.decisions(segs)
            parts += ["", "## Decisions and motions (counted)"]
            parts += [f"- [{int(d['t'] // 60):02d}:{int(d['t'] % 60):02d}] "
                      f"({d['outcome']}) {d['text'][:140]}" for d in dec[:12]] \
                or ["- none detected"]
            ent = insight.entities(segs)
            for bucket, label in (("people", "People"), ("places", "Places"),
                                  ("organizations", "Organizations"),
                                  ("money", "Money")):
                rows = ent.get(bucket) or []
                if rows:
                    parts += ["", f"## {label} mentioned"]
                    parts += [f"- {r['name']} (x{r['count']})"
                              for r in rows[:10]]
            part = insight.participation(segs)
            if part:
                parts += ["", "## Who spoke"]
                parts += [f"- {r['speaker']}: {int(r['seconds'] // 60)}m "
                          f"{int(r['seconds'] % 60)}s across {r['turns']} turns"
                          for r in part[:10]]
            qs = insight.questions(segs)
            if qs:
                parts += ["", f"## Questions asked ({len(qs)})"]
                parts += [f"- [{int(q['t'] // 60):02d}:{int(q['t'] % 60):02d}] "
                          f"({q['type']}) {q['text'][:120]}" for q in qs[:10]]
            md = "\n".join(parts) + "\n"
            md_p.write_text(md)
            job.message = "writing the PDF…"
            pdfout.write_pdf(str(pdf_p), pdfout.md_blocks(md),
                             footer=f"{title} - control-z Community "
                                    "Highlighter")
            job.message = "report written — markdown + PDF"
            return {"md": str(md_p), "pdf": str(pdf_p), "text": md}

        return jobs.start("report", work, tool="highlighter",
                          label=f"full report — {title[:55]}").to_dict()

    # -- translate: the summary or the whole transcript, any language --------

    @app.post("/api/highlighter/translate")
    def api_translate(body: dict = Body(...)):
        from czcore import llm

        if not llm.enabled():
            return JSONResponse({"error": "translation runs on your API key "
                                          "— Settings → AI"}, status_code=409)
        source = str(Path(body["path"]).expanduser())
        what = str(body.get("what", "summary"))
        lang = str(body.get("lang", "Spanish"))[:40]
        t, _ = _load_transcript(source)
        if not t:
            return JSONResponse({"error": "no words to translate"},
                                status_code=409)
        p = Path(source)
        stem = (p / f"meeting.{lang.lower()}") if p.is_dir() \
            else p.with_suffix(f".{lang.lower()}")

        def work(job):
            segs = t["segments"]
            if what == "summary":
                brief_p = (p / "ai-brief.json") if p.is_dir() \
                    else p.with_suffix(".ai-brief.json")
                base = ""
                if brief_p.exists():
                    try:
                        base = json.loads(brief_p.read_text()).get("text", "")
                    except ValueError:
                        pass
                if not base:
                    from highlighter import insight
                    base = "\n".join(x["text"] for x in insight.brief(segs))
                job.message = f"translating the summary into {lang}…"
                out = llm.complete(
                    system=(f"Translate into {lang}. Keep every [MM:SS] "
                            "timestamp exactly as written. Answer with the "
                            "translation only."),
                    prompt=base, max_tokens=1800)
                out_p = Path(str(stem) + ".summary.txt")
                out_p.write_text(out)
                job.message = f"summary in {lang} — written"
                return {"text": out, "path": str(out_p), "lang": lang}
            # the whole transcript, chunked, timings kept
            CH = 60
            translated: list = []
            chunks = [segs[i:i + CH] for i in range(0, len(segs), CH)]
            for ci, chunk in enumerate(chunks):
                job.progress = ci / max(1, len(chunks))
                job.message = (f"translating transcript into {lang} — "
                               f"chunk {ci + 1}/{len(chunks)}")
                job.check_cancel()
                numbered = "\n".join(
                    f"{k}|{str(s.get('text', '')).strip()}"
                    for k, s in enumerate(chunk))
                try:
                    out = llm.complete(
                        system=(f"Translate each line into {lang}. Keep the "
                                "N| prefixes exactly; one line out per line "
                                "in; no commentary."),
                        prompt=numbered, max_tokens=3600)
                    got = {}
                    for ln in out.splitlines():
                        if "|" in ln:
                            k, txt = ln.split("|", 1)
                            try:
                                got[int(k.strip())] = txt.strip()
                            except ValueError:
                                pass
                    translated += [got.get(k, str(s.get("text", "")))
                                   for k, s in enumerate(chunk)]
                except RuntimeError:
                    translated += [str(s.get("text", "")) for s in chunk]
            def ts(x):
                return (f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:"
                        f"{int(x % 60):02d},{int(x % 1 * 1000):03d}")
            srt = "\n".join(
                f"{i + 1}\n{ts(float(s['start']))} --> {ts(float(s['end']))}"
                f"\n{translated[i]}\n"
                for i, s in enumerate(segs))
            srt_p = Path(str(stem) + ".srt")
            txt_p = Path(str(stem) + ".txt")
            srt_p.write_text(srt)
            txt_p.write_text("\n".join(translated) + "\n")
            job.message = f"transcript in {lang} — .srt and .txt written"
            return {"srt": str(srt_p), "txt": str(txt_p), "lang": lang}

        return jobs.start("translate", work, tool="highlighter",
                          label=f"translate {what} → {lang}").to_dict()

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
        want_cards = bool(body.get("cards"))
        title = str(body.get("title", "")) or Path(path).stem
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
        cards = ([{"label": str(r.get("label", "")) or f"Moment {k + 1}",
                   "t": float(r.get("start", 0))}
                  for k, r in enumerate(ranges)] if want_cards else None)

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            job.message = "cutting the reel…"
            rep = render_reel(path, ranges, out, preset=preset, progress=prog,
                              cancelled=lambda: job.cancel_requested,
                              cards=cards, title=title)
            job.message = (f"{rep['clips']} cuts"
                           + (f" · {rep['cards']} title cards"
                              if rep.get("cards") else "")
                           + f" · {rep['duration']}s · {rep['encoder']}")
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
        title = str(body.get("title", ""))
        fx = body.get("fx") or None         # [{speed, fade}] aligned with files
        cards = body.get("cards") or None   # [{label, t}] aligned with files
        if cards:
            cards = [{"label": str(c.get("label", "")), "t": float(c.get("t", 0))}
                     for c in cards]
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
                               cancelled=lambda: job.cancel_requested,
                               cards=cards, title=title, fx=fx)
            job.message = (f"{rep['clips']} clips"
                           + (f" · {rep['cards']} title cards"
                              if rep.get("cards") else "")
                           + f" · {rep['duration']}s")
            return rep

        return jobs.start("stitch", work, tool="highlighter",
                          label=f"stitch {len(files)} section clips").to_dict()

    # the viewer reuses /api/media/open; the selects EDL goes through
    # /api/scribe/selects — it IS the paper edit.
