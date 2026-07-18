"""The Meeting Library, read together — cross-meeting analytics from the
sidecars already on this machine.

The web app calls this its Knowledge Base and asks a cloud model to enrich
it; here every number is counted per meeting by highlighter/insight.py
(cached beside each transcript) and aggregated in plain code. Nothing
uploads, nothing is modeled, and a meeting without words says so instead
of pretending.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .highlighter import (VIDEO_EXTS, _info_for, _is_session, _lib,
                          _meetings_dir, _session_meta, _sidecars,
                          insight_payload)

# a library file named "…[3923-3927].mp4" is a downloaded SPAN of a
# meeting, and "reel-YYYYMMDD-HHMMSS.mp4" (or "….reel.mp4") is a reel the
# Highlighter RENDERED — outputs, not meetings
_SPAN_CLIP = re.compile(r"\[\d+(?:\.\d+)?-\d+(?:\.\d+)?\]$")
_REEL_OUT = re.compile(r"(?:^reel-\d{8}-\d{6}$)|(?:\.reel$)")


def is_span_clip(p: Path) -> bool:
    return bool(_SPAN_CLIP.search(p.stem)) or bool(_REEL_OUT.search(p.stem))


def kb_sources(cap: int = 60) -> list:
    """Every meeting this machine holds: URL sessions first, then full
    library videos (span downloads excluded — their session is the
    meeting). Capped, oldest caps out first because sessions sort by id."""
    out = []
    if _meetings_dir().exists():
        out += sorted(d for d in _meetings_dir().iterdir() if d.is_dir())
    if _lib().exists():
        out += sorted(p for p in _lib().iterdir()
                      if p.suffix.lower() in VIDEO_EXTS
                      and not is_span_clip(p))
    return out[:cap]


def _meta_row(src: Path) -> dict:
    from highlighter.insight import meeting_day

    if src.is_dir():
        meta = _session_meta(src)
        title, kind = meta.get("title") or src.name, "session"
    else:
        # a library file that is some session's downloaded twin belongs to
        # that session — listing both would count one meeting twice
        title, kind = src.stem, "file"
    info = _info_for(str(src))
    sc, _, _ = _sidecars(str(src))
    return {
        "source": str(src),
        "title": title,
        "kind": kind,
        "day": meeting_day(title, str(info.get("upload_date") or "")),
        "read": sc.exists(),
    }


def _twin_session_ids() -> set:
    """Video ids whose session dir exists — their library twins are
    duplicates in a meeting count."""
    if not _meetings_dir().exists():
        return set()
    return {d.name for d in _meetings_dir().iterdir() if d.is_dir()}


def library_rows() -> list:
    twins = _twin_session_ids()
    rows = []
    for src in kb_sources():
        if src.is_file() and any(f"[{t}]" in src.name for t in twins):
            continue
        rows.append(_meta_row(src))
    # oldest first — every cross-meeting chart reads left to right in time
    rows.sort(key=lambda r: (r["day"] is None, r["day"] or "", r["title"]))
    return rows


def register_kb(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.get("/api/kb/overview")
    def api_overview():
        rows = library_rows()
        return {"meetings": rows,
                "read": sum(1 for r in rows if r["read"])}

    @app.post("/api/kb/matrix")
    def api_matrix(body: dict = Body(default={})):
        """Per-meeting counted readings, aggregated for the cross-meeting
        cards. Reads each meeting's cached insight (computing and caching
        it once when absent — same door the analyzer uses); meetings
        without words are listed as skipped, not invented."""
        rows, skipped = [], []
        for meta in library_rows():
            # no "read" gate here: a session that only has captions gets
            # its transcript parsed (and cached) by the payload call
            try:
                data = insight_payload(meta["source"])
            except (LookupError, ValueError):
                skipped.append(meta["title"])
                continue
            ent = data.get("entities") or {}
            qtypes: dict = {}
            for q in data.get("questions") or []:
                qtypes[q["type"]] = qtypes.get(q["type"], 0) + 1
            outcomes: dict = {}
            for d in data.get("decisions") or []:
                outcomes[d["outcome"]] = outcomes.get(d["outcome"], 0) + 1
            rows.append({
                **meta,
                "duration": (data.get("pace") or {}).get("duration", 0),
                "wpm_avg": (data.get("pace") or {}).get("wpm_avg", 0),
                "framing": [{k: l[k] for k in
                             ("lens", "color", "count", "share", "drift",
                              "moments")}
                            for l in (data.get("framing") or {})
                            .get("lenses", [])],
                "entities": {k: (ent.get(k) or [])[:8]
                             for k in ("people", "places", "organizations")},
                "topics": (data.get("topics") or [])[:10],
                "decisions": len(data.get("decisions") or []),
                "outcomes": outcomes,
                "questions": len(data.get("questions") or []),
                "qtypes": qtypes,
                "disagreements": len(data.get("disagreements") or []),
            })
        return {"rows": rows, "skipped": skipped}

    @app.post("/api/kb/discourse")
    def api_discourse(body: dict = Body(...)):
        """Trace one term through every meeting, oldest first — counted
        mentions, a per-thousand-words rate so a seven-hour meeting can't
        out-shout a one-hour one, and the first moments as receipts."""
        q = str(body.get("q", "")).strip().lower()
        if len(q) < 3:
            return JSONResponse({"error": "too short to trace"},
                                status_code=422)
        out = []
        for meta in library_rows():
            if not meta["read"]:
                continue
            sc, _, _ = _sidecars(meta["source"])
            try:
                segs = json.loads(sc.read_text()).get("segments") or []
            except (ValueError, OSError):
                continue
            count, words, first_t, moments = 0, 0, None, []
            for s in segs:
                text = str(s.get("text", ""))
                words += len(text.split())
                low = text.lower()
                if q in low:
                    count += low.count(q)
                    if first_t is None:
                        first_t = round(float(s.get("start", 0)), 1)
                    if len(moments) < 3:
                        moments.append(
                            {"t": round(float(s.get("start", 0)), 1),
                             "text": text[:150]})
            out.append({**meta, "count": count,
                        "rate": round(count / max(1, words) * 1000, 2),
                        "first_t": first_t, "moments": moments})
        return {"q": q, "rows": out}
