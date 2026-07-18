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
# meeting, and "reel-…"/"montage-…" (or "….reel.mp4") is something the
# suite RENDERED — outputs, not meetings
_SPAN_CLIP = re.compile(r"\[\d+(?:\.\d+)?-\d+(?:\.\d+)?\]$")
_REEL_OUT = re.compile(r"(?:^(?:reel|montage)-\d{8}-\d{6}$)|(?:\.reel$)")


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


def _entity_union(rows: list) -> list:
    """Every meeting's entities as one folded roll: caption spellings of
    a name join across meetings too (a February council may write
    "Councelor" where June writes "Councilor"). The most-counted spelling
    keeps the seat — and its kind — while the others ride in `also`, so
    the fold shows its work. person↔org may fold together (the harvester
    reads "Council Hamilton" as an org and "Councelor Hamilton" as a
    person — same caption noise); places stay strict. per =
    {row_index: count}."""
    from highlighter.insight import names_match

    def kinds_ok(a: str, b: str) -> bool:
        return a == b or {a, b} == {"person", "org"}

    union: list = []
    for ri, r in enumerate(rows):
        for bucket, kind in (("people", "person"), ("places", "place"),
                             ("organizations", "org")):
            for e in (r.get("entities") or {}).get(bucket) or []:
                hit = next((u for u in union
                            if kinds_ok(u["_kind"], kind)
                            and names_match(u["_spell"], e["name"])), None)
                if hit is None:
                    hit = {"_kind": kind, "_spell": e["name"], "total": 0,
                           "per": {}, "spellings": {}, "kinds": {}}
                    union.append(hit)
                hit["total"] += e["count"]
                hit["per"][ri] = hit["per"].get(ri, 0) + e["count"]
                hit["spellings"][e["name"]] = (
                    hit["spellings"].get(e["name"], 0) + e["count"])
                hit["kinds"][e["name"]] = kind
    out = []
    for u in union:
        name = max(u["spellings"], key=u["spellings"].get)
        also = sorted(s for s in u["spellings"] if s != name)
        out.append({"name": name, "kind": u["kinds"][name],
                    "total": u["total"], "per": u["per"], "also": also})
    out.sort(key=lambda u: (-len(u["per"]), -u["total"]))
    return out[:16]


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
        return {"rows": rows, "skipped": skipped,
                "entity_union": _entity_union(rows)}

    @app.post("/api/kb/ai-compare")
    def api_ai_compare(body: dict = Body(default={})):
        """A narrative read ACROSS meetings, on the user's own key — and
        only over the counted record. The model sees the matrix digest
        (dates, framing counts, topics, entities, decision/question
        tallies); the transcripts never leave this machine."""
        from czcore import llm

        if not llm.enabled():
            return JSONResponse({"error": "no API key configured — "
                                          "Settings → AI"}, status_code=409)
        rows, skipped = [], []
        for meta in library_rows():
            try:
                data = insight_payload(meta["source"])
            except (LookupError, ValueError):
                continue
            rows.append({
                "title": meta["title"][:80], "day": meta["day"],
                "duration_min": round(
                    (data.get("pace") or {}).get("duration", 0) / 60),
                "wpm": (data.get("pace") or {}).get("wpm_avg", 0),
                "framing": {l["lens"]: l["count"] for l in
                            (data.get("framing") or {}).get("lenses", [])
                            if l["count"]},
                "topics": [f"{t['topic']} ×{t['count']}"
                           for t in (data.get("topics") or [])[:8]],
                "entities": {k: [e["name"] for e in v[:6]]
                             for k, v in (data.get("entities") or {}).items()
                             if k != "money" and v},
                "decisions": len(data.get("decisions") or []),
                "questions": len(data.get("questions") or []),
                "tense_moments": len(data.get("disagreements") or []),
            })
        if len(rows) < 2:
            return JSONResponse({"error": "the comparison needs at least "
                                          "two read meetings"},
                                status_code=409)

        def work(job):
            job.message = "asking the model for a read across meetings…"
            digest = json.dumps(rows, ensure_ascii=False)
            text = llm.complete(
                "Here are counted readings of public meetings from one "
                "town's library — dates, civic-lens word counts, recurring "
                "topics, harvested names, decision and question tallies. "
                "No transcripts are included. Write a grounded comparison "
                "across the meetings: what themes rise or fade over time, "
                "which bodies talk about what, where the tension "
                "concentrates, and what a community journalist should "
                "look at next. Only claim what these counts support, and "
                "name the meetings by their dates.\n\n" + digest,
                system="You read civic meeting statistics for a community "
                       "media station. You are careful: counts are counts, "
                       "not proof of intent. Short paragraphs, no headers, "
                       "no bullet spam.",
                max_tokens=900)
            st = llm.status()
            u = llm.last_usage()
            job.message = "the read is in"
            return {"text": text, "meetings": len(rows),
                    "origin": f"generative ({st.get('model')}, your key) — "
                              "counted inputs only, no transcripts sent",
                    "usage": (f"{u['tokens_in']:,} in / "
                              f"{u['tokens_out']:,} out · "
                              f"{u['window_pct']}% of the context window"
                              if u else "")}

        return jobs.start("ai-compare", work, tool="kb",
                          label=f"AI read across {len(rows)} meetings").to_dict()

    @app.post("/api/kb/montage")
    def api_montage(body: dict = Body(...)):
        """A reel cut across meetings. Local sources are trimmed in place;
        URL sessions download ONLY the picked seconds (a span already on
        disk is reused, nothing re-downloads); then one stitch, each clip
        wearing a card that names its own meeting. Sequential and staged —
        the job narrates every step."""
        import tempfile
        import time as _time

        picks = body.get("picks") or []
        want_cards = bool(body.get("cards", True))
        preset = str(body.get("preset", "h264"))
        if not picks:
            return JSONResponse({"error": "pick at least one moment first"},
                                status_code=422)
        try:
            picks = [{"source": str(p["source"]),
                      "start": float(p["start"]),
                      "end": float(p.get("end") or float(p["start"]) + 12.0),
                      "label": str(p.get("label", ""))[:80],
                      "title": str(p.get("title", ""))[:60]}
                     for p in picks]
        except (KeyError, TypeError, ValueError):
            return JSONResponse({"error": "each pick needs a source and a "
                                          "start (seconds)"}, status_code=422)
        # a pick may name a meeting by video id alone ("vid:<id>" — Memory's
        # search hits travel light); it resolves to the Highlighter session
        # that holds the tape, or says honestly what to do
        for p in picks:
            if p["source"].startswith("vid:"):
                sess = _meetings_dir() / p["source"][4:]
                if not sess.is_dir():
                    return JSONResponse(
                        {"error": f"{p['title'] or p['source']} isn't in the "
                                  "Highlighter library yet — open it there "
                                  "once and the reel can cut it"},
                        status_code=409)
                p["source"] = str(sess)
        for p in picks:
            if p["end"] <= p["start"]:
                p["end"] = p["start"] + 12.0

        def _local_video(src: Path):
            """The full local file for a source: itself, or a session's
            downloaded twin in the library (span clips don't count)."""
            if src.is_file():
                return src
            for f in _lib().iterdir():
                if (f.suffix.lower() in VIDEO_EXTS
                        and f"[{src.name}]" in f.name
                        and not is_span_clip(f)):
                    return f
            return None

        def _span_on_disk(sid: str, a: float, b: float):
            tag = f"[{int(a)}-{int(b)}]"
            for f in _lib().iterdir():
                if (f.suffix.lower() in VIDEO_EXTS and tag in f.name
                        and f"[{sid}]" in f.name):
                    return f
            return None

        def work(job):
            from czcore import ytdlp
            from highlighter.reel import render_reel, stitch_files

            n = len(picks)
            with tempfile.TemporaryDirectory(prefix="kb-montage-") as td:
                clips, cards = [], []
                for i, p in enumerate(picks):
                    job.check_cancel()
                    src = Path(p["source"])
                    where = p["title"] or src.stem
                    local = _local_video(src)
                    if local is not None:
                        job.message = (f"{i + 1}/{n} · cutting "
                                       f"{p['start']:.0f}s from {where}…")
                        rep = render_reel(
                            str(local),
                            [{"start": p["start"], "end": p["end"]}],
                            str(Path(td) / f"cut{i}"), preset=preset,
                            cancelled=lambda: job.cancel_requested)
                        clips.append(rep["out"])
                    else:
                        meta = _session_meta(src) if src.is_dir() else {}
                        url = meta.get("url")
                        if not url:
                            raise RuntimeError(
                                f"{where} has no local video and no URL on "
                                "record — open it in the Highlighter once")
                        have = _span_on_disk(src.name, p["start"], p["end"])
                        if have is not None:
                            job.message = (f"{i + 1}/{n} · {have.name} is "
                                           "already on disk — nothing "
                                           "re-downloads")
                            clips.append(str(have))
                        else:
                            job.message = (f"{i + 1}/{n} · downloading "
                                           f"{p['end'] - p['start']:.0f}s "
                                           f"of {where} from its URL…")
                            got = ytdlp.download(
                                url, _lib(),
                                sections=[(p["start"], p["end"])],
                                cancelled=lambda: job.cancel_requested)
                            clips.append(got.get("paths", [got["path"]])[0])
                    cards.append({"title": where, "label": p["label"],
                                  "t": p["start"]})

                job.message = f"stitching {len(clips)} clips into the montage…"
                out = str(_lib() / ("montage-"
                                    + _time.strftime("%Y%m%d-%H%M%S")))

                def prog(frac, m):
                    job.progress = frac
                    if m:
                        job.message = m

                rep = stitch_files(clips, out, preset=preset, progress=prog,
                                   cancelled=lambda: job.cancel_requested,
                                   cards=cards if want_cards else None,
                                   title="Meeting Montage")
                srcs = len({p["source"] for p in picks})
                job.message = (f"montage: {rep['clips']} moments from "
                               f"{srcs} meeting{'s' if srcs > 1 else ''}"
                               + (f" · {rep['cards']} cards"
                                  if rep.get("cards") else "")
                               + f" · {rep['duration']}s")
                return rep

        srcs = len({p["source"] for p in picks})
        return jobs.start(
            "montage", work, tool="kb",
            label=f"montage — {len(picks)} moments from {srcs} "
                  f"meeting{'s' if srcs > 1 else ''}").to_dict()

    @app.post("/api/kb/context")
    def api_context(body: dict = Body(...)):
        """The transcript around one second of one meeting — the pull-up
        behind every mark in the analytics. ±window seconds, capped."""
        source = str(body.get("source", ""))
        t = float(body.get("t", 0) or 0)
        window = min(120.0, float(body.get("window", 40) or 40))
        sc, _, _ = _sidecars(source)
        if not sc.exists():
            return JSONResponse({"error": "that meeting has no transcript "
                                          "on this machine"}, status_code=404)
        try:
            segs = json.loads(sc.read_text()).get("segments") or []
        except (ValueError, OSError):
            return JSONResponse({"error": "the transcript wouldn't parse"},
                                status_code=500)
        keep = [{"start": round(float(s.get("start", 0)), 1),
                 "text": str(s.get("text", ""))[:300],
                 "speaker": s.get("speaker")}
                for s in segs
                if abs(float(s.get("start", 0)) - t) <= window]
        return {"t": t, "segments": keep[:80]}

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
