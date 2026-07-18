"""The pipeline: a source in, a meeting in the record out.

Captions-first, exactly the way Highlighter already works and the way Stephen
asked for: the bulk of the civic corpus is YouTube/portal video that already
carries a published transcript, so we take those words directly — instant,
free, already timestamped. Scribe's ASR runs *only* for video with no
transcript to be found, and even then it is the suite's shared engine, never a
whisper run of our own.

One JobManager job runs every stage back-to-back (the suite has a single FIFO
worker, so chained jobs would interleave with other tools — the stages live
inside one `work(job)` instead). The job is re-runnable: a crash leaves a
meeting `error`, and re-submitting it starts clean.

Transcript resolution order:
  1. reuse — a scribe sidecar already sits in the meeting's workdir
  2. captions — the watch page, then yt-dlp; parsed to segments (origin captions)
  3. ASR — local file (or a URL with no captions, downloaded) → 16k wav → Scribe
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from czcore.paths import media_dir
from highlighter import insight

from . import analyze

_YT_TOWNS = ("Brookline", "Boston", "Cambridge", "Somerville", "Newton")


def meetings_dir() -> Path:
    d = media_dir("memory") / ".meetings"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------
# input classification — cheap, no network, safe to run before queueing a job
# --------------------------------------------------------------------------

def resolve_input(body: dict) -> dict:
    """A submission → a plan the pipeline and the dedupe check can both use."""
    from czcore import captions as ctext

    url = str(body.get("url", "") or "").strip()
    path = str(body.get("path", "") or "").strip()
    plan = {
        "url": url, "path": path,
        "town": str(body.get("town", "") or "").strip(),
        "body": str(body.get("body", "") or "").strip(),
        "date": str(body.get("date", "") or "").strip(),
        "video_id": "", "title": "",
    }
    if path:
        p = Path(path).expanduser()
        plan["path"] = str(p)
        plan["kind"] = "file"
        plan["title"] = p.stem
        plan["source_hash"] = file_hash(p) if p.is_file() else ""
        plan["url_canon"] = ""
        plan["id"] = f"file:{plan['source_hash'][:12]}" if plan["source_hash"] \
            else "file:" + _short(str(p))
        return plan
    vid = ctext.video_id(url) if url else None
    if vid:
        plan.update(kind="youtube", video_id=vid, id=vid,
                    url_canon=f"youtube:{vid}", source_hash="")
        return plan
    plan.update(kind="url", url_canon=_canon_url(url), source_hash="",
                id="url:" + _short(_canon_url(url)))
    return plan


def submit_dedupe(corpus, plan: dict) -> Optional[dict]:
    """The cheap, local dedupe tiers — deterministic id, canonical URL, then
    media hash — so the submissions route can answer 'exists' without queueing.
    (Transcript-shingle similarity is the third tier; it needs the words and so
    runs inside the job.)"""
    hit = corpus.get_meeting(plan["id"])
    if not hit:
        hit = corpus.find_by_url_canon(plan.get("url_canon", ""))
    if not hit and plan.get("source_hash"):
        hit = corpus.find_by_hash(plan["source_hash"])
    if hit and hit.get("status") == "live":
        return hit
    return None


# --------------------------------------------------------------------------
# the pipeline
# --------------------------------------------------------------------------

def run(corpus, plan: dict, job) -> dict:
    """The whole pipeline, inside one job. Returns a JSON-safe result dict."""
    from czcore.appshell.jobs import JobCancelled

    mid = plan["id"]
    try:
        corpus.set_status(mid, "transcribing")
        job.progress = -1
        job.message = "finding a transcript…"
        tr = _resolve_transcript(corpus, plan, job)
        segs = tr["segments"]
        if not segs:
            if plan["kind"] in ("youtube", "url"):
                # a known, non-alarming state: the meeting is on the shelf, it
                # just has no words yet. Not an error, not a runaway download.
                note = ("no published captions found — YouTube may be gating "
                        "them here. Bring the video file in for on-device "
                        "Scribe, or enable the caption service in Settings.")
                corpus.upsert_meeting({
                    "id": mid, "status": "no_transcript", "error": note,
                    "url": plan.get("url", ""), "url_canon": plan.get("url_canon", ""),
                    "source_kind": plan["kind"], "video_id": plan.get("video_id", ""),
                    "title": tr["meta"].get("title") or plan.get("title", ""),
                    "town": plan.get("town", ""), "body": plan.get("body", "")})
                job.message = "no captions yet — needs a transcript"
                return {"meeting_id": mid, "status": "no_transcript", "note": note}
            raise RuntimeError(
                "could not transcribe — the file produced no words (no audio, "
                "or an unreadable track)")
        job.check_cancel()

        # third-tier dedupe: the same meeting posted at a second URL
        sh = _shingles(segs)
        dup = corpus.find_by_shingles(sh)
        if dup and dup["id"] != mid:
            corpus.forget(mid)  # drop the queued shell; link to the original
            job.message = f"already in the record as {dup['id']}"
            return {"meeting_id": dup["id"], "status": "exists", "linked": True}

        corpus.set_status(mid, "analyzing")
        job.progress = 0.7
        job.message = "reading the record…"
        info = tr["meta"]
        analysis = analyze.read(segs, info)
        summ, summ_origin = analyze.summary(segs, info)
        job.check_cancel()

        date = plan.get("date") or insight.meeting_day(
            info.get("title", ""), info.get("upload_date", ""))
        town = plan.get("town") or _town_guess(info.get("uploader", ""))
        n_speakers = len({s.get("speaker") for s in segs if s.get("speaker")})
        duration = float(tr.get("duration") or (segs[-1]["end"] if segs else 0))

        corpus.replace_segments(mid, segs)
        corpus.upsert_meeting({
            "id": mid, "origin": tr["origin"], "duration": duration,
            "media_path": tr.get("media_path", ""),
            "video_id": plan.get("video_id", ""),
            "url": plan.get("url", ""), "url_canon": plan.get("url_canon", ""),
            "source_kind": plan.get("kind", ""),
            "source_hash": plan.get("source_hash", ""),
            "title": info.get("title") or plan.get("title", ""),
            "uploader": info.get("uploader", ""),
            "date": date or "", "town": town, "body": plan.get("body", ""),
            "n_segments": len(segs), "n_speakers": n_speakers,
            "shingles": sh, "info_json": json.dumps(info),
            "analysis_json": json.dumps(analysis),
            "summary": summ, "summary_origin": summ_origin,
            "status": "live", "error": "",
        })
        job.progress = 1.0
        job.message = f"in the record — {len(segs)} segments · {tr['origin']}"
        return {"meeting_id": mid, "status": "live", "segments": len(segs),
                "origin": tr["origin"], "title": info.get("title", ""),
                "path": corpus.db_path}
    except JobCancelled:
        corpus.forget(mid)   # the shell never became a meeting
        raise
    except Exception as e:
        corpus.set_status(mid, "error", str(e))
        raise


def _resolve_transcript(corpus, plan: dict, job) -> dict:
    """{segments, origin, meta, media_path, duration}. Captions-first."""
    workdir = meetings_dir() / _safe(plan["id"])
    workdir.mkdir(parents=True, exist_ok=True)
    sc = workdir / "meeting.scribe.json"
    info_p = workdir / "meeting.info.json"

    # 1) reuse a sidecar already here (re-ingest, or a twin from Highlighter)
    if sc.exists():
        try:
            t = json.loads(sc.read_text())
            origin = ("captions" if str(t.get("model", "")).startswith("captions")
                      else "scribe")
            meta = _read_info(info_p)
            return {"segments": t.get("segments", []), "origin": origin,
                    "meta": meta, "media_path": _local_media(workdir, plan),
                    "duration": t.get("duration") or meta.get("duration") or 0}
        except ValueError:
            pass

    # 2) captions — the bulk of the corpus. A URL never auto-downloads its
    #    video here: like Highlighter, ingest is captions-only, and Scribe is a
    #    separate, deliberate step (bring the file in) — so a six-hour meeting
    #    is never fetched behind the user's back.
    if plan["kind"] in ("youtube", "url"):
        segs, meta = _fetch_captions(plan, workdir, job)
        if segs:
            from highlighter.highlights import transcript_dict
            t = transcript_dict(segs, str(workdir), origin="captions:youtube")
            sc.write_text(json.dumps(t))
            _merge_info(info_p, meta)
            return {"segments": segs, "origin": "captions", "meta": meta,
                    "media_path": "", "duration": meta.get("duration") or 0}
        return {"segments": [], "origin": "none", "meta": _read_info(info_p),
                "media_path": "", "duration": 0}

    # 3) ASR — a local file the user brought in (already on disk, bounded and
    #    explicit). This is the "video without a transcript" path.
    media = _local_media(workdir, plan)
    if media:
        segs, meta = _transcribe(media, workdir, job)
        if segs:
            _merge_info(info_p, meta)
            return {"segments": segs, "origin": "scribe", "meta": meta,
                    "media_path": media,
                    "duration": meta.get("duration") or (segs[-1]["end"] if segs else 0)}
    return {"segments": [], "origin": "none", "meta": _read_info(info_p),
            "media_path": media or "", "duration": 0}


def _fetch_captions(plan: dict, workdir: Path, job):
    """Published captions → segments, the three ways Highlighter tries them:
    the watch page, then the yt-dlp binary, then — only if the user left the
    community caption service on in Settings — BIG's own relay. Each is a
    caption route, never a video download. Returns (segments, meta)."""
    from highlighter.highlights import parse_vtt
    from czcore import proxy
    url = plan["url"]
    meta: dict = {}
    vtt_text = ""
    notes = []
    job.message = "asking for the published captions…"

    # a) the watch page (no binary needed)
    try:
        from czcore import captions as ctext
        got = ctext.fetch_vtt(url, proxy=proxy.proxy_url())
        vtt_text = got.get("vtt", "") or ""
        meta = got.get("meta") or {}
    except Exception as e:
        notes.append(str(e))
        meta = dict(getattr(e, "meta", None) or {})

    # b) the yt-dlp binary (its own TLS — survives a broken system SSL)
    if not vtt_text:
        try:
            from czcore import ytdlp
            ytdlp.fetch_captions(url, workdir)
            cap = _captions_file(workdir)
            if cap:
                vtt_text = cap.read_text(errors="replace")
        except Exception as e:
            notes.append(str(e))

    # c) the community caption service — BIG's own relay, opt-out in Settings
    if not vtt_text and proxy.relay_enabled():
        job.message = "captions via the community service…"
        try:
            from czcore import captions as ctext
            got = ctext.fetch_vtt_relay(url)
            vtt_text = got.get("vtt", "") or ""
        except Exception as e:
            notes.append(str(e))

    if not vtt_text:
        job.message = "no captions found this pass"
        return [], meta
    (workdir / "meeting.en.vtt").write_text(vtt_text)
    return parse_vtt(vtt_text), meta


def _transcribe(media: str, workdir: Path, job):
    """16k mono wav → Scribe's engine → segments. Diarize when the models are
    already on disk (never a surprise download)."""
    from scribe.transcribe import transcribe

    job.message = "extracting audio for Scribe…"
    with tempfile.TemporaryDirectory(prefix="memory-asr-") as td:
        wav16 = str(Path(td) / "audio.16k.wav")
        _extract_wav(media, wav16)
        job.check_cancel()

        def prog(m):
            job.message = str(m)[:120]

        job.message = "Scribe is listening…"
        t = transcribe(wav16, model="base", progress=prog)
        t.source = str(Path(media).resolve())
        job.check_cancel()
        try:
            from scribe import diarize as dz
            if dz.available():
                job.message = "labeling speakers…"
                dz.diarize(t, wav16, progress=prog)
        except Exception:
            pass  # diarization is a bonus, never a blocker

    (workdir / "meeting.scribe.json").write_text(t.to_json())
    segs = [{"start": s.start, "end": s.end, "text": s.text,
             "speaker": s.speaker} for s in t.segments]
    meta = {"duration": t.duration, "title": Path(media).stem}
    return segs, meta


def _extract_wav(src: str, out_wav: str) -> None:
    from czcore.tools import ToolNotFound, ffmpeg_path
    try:
        exe = ffmpeg_path()
    except ToolNotFound as e:
        raise RuntimeError(f"ffmpeg is needed to transcribe: {e}")
    subprocess.run([exe, "-y", "-v", "quiet", "-i", src, "-vn", "-ac", "1",
                    "-ar", "16000", out_wav], check=True)


# --------------------------------------------------------------------------
# small local helpers
# --------------------------------------------------------------------------

def file_hash(path: Path, cap: int = 1 << 20) -> str:
    """A fast, stable fingerprint: size plus the head and tail of the file.
    Enough to catch 'the same file submitted twice' without reading gigabytes."""
    try:
        st = path.stat()
    except OSError:
        return ""
    h = hashlib.sha1(str(st.st_size).encode())
    try:
        with open(path, "rb") as f:
            h.update(f.read(cap))
            if st.st_size > cap:
                f.seek(-cap, 2)
                h.update(f.read(cap))
    except OSError:
        return ""
    return h.hexdigest()


def _shingles(segments: List[dict], k: int = 5, cap: int = 240) -> str:
    words = re.findall(r"[a-z0-9]+",
                       " ".join(s.get("text", "") for s in segments).lower())
    grams = {hashlib.blake2b(" ".join(words[i:i + k]).encode(),
                             digest_size=6).hexdigest()
             for i in range(max(0, len(words) - k + 1))}
    return " ".join(sorted(grams)[:cap])


def _canon_url(url: str) -> str:
    u = re.sub(r"#.*$", "", url or "")
    u = re.sub(r"[?&](utm_[^=&]+|feature|si|list|index|t)=[^&]*", "", u)
    return "url:" + u.rstrip("/&?")


def _short(s: str) -> str:
    return hashlib.blake2b(s.encode(), digest_size=6).hexdigest()


def _safe(s: str) -> str:
    return re.sub(r"[^\w.-]", "_", s)[:64]


def _town_guess(uploader: str) -> str:
    for t in _YT_TOWNS:
        if t.lower() in (uploader or "").lower():
            return t
    return ""


def _captions_file(d: Path) -> Optional[Path]:
    for ext in (".vtt", ".srt"):
        hits = sorted(d.glob(f"*{ext}"))
        if hits:
            return hits[0]
    return None


def _local_media(workdir: Path, plan: dict) -> str:
    if plan.get("kind") == "file" and plan.get("path") and Path(plan["path"]).is_file():
        return plan["path"]
    from indexer.catalog import AUDIO_EXTS, VIDEO_EXTS
    for p in sorted(workdir.iterdir()) if workdir.exists() else []:
        if p.suffix.lower() in VIDEO_EXTS | AUDIO_EXTS:
            return str(p)
    return ""


def _read_info(info_p: Path) -> dict:
    if info_p.exists():
        try:
            return json.loads(info_p.read_text())
        except ValueError:
            pass
    return {}


def _merge_info(info_p: Path, meta: dict) -> None:
    existing = _read_info(info_p)
    merged = {**existing, **{k: v for k, v in (meta or {}).items() if v}}
    if merged:
        info_p.write_text(json.dumps(merged))
