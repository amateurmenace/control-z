"""Community Memory — the record across meetings and years.

Routes only; the engine lives in the top-level `memory/` package (lane B owns
both). Ingest and the pipeline run as JobManager jobs so the Queue page and
toasts show them — one queue is covenant. Every AI surface here is labeled and
supplements the official record; it never replaces it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# lane B owns memory/, but `[tool.setuptools] packages` is lane A's file — until
# the HANDOFF ask lands there, make the sibling package importable by path so
# the suite finds it no matter the working directory. Harmless once added.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from memory import detect, embed, ingest          # noqa: E402
from memory.store import Corpus                    # noqa: E402


def register_memory(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    corpus = Corpus()

    # -- the record: the corpus list + counts -----------------------------
    @app.get("/api/memory/corpus")
    def api_corpus():
        return {"meetings": corpus.list_meetings(), "stats": corpus.stats()}

    @app.get("/api/memory/status")
    def api_status():
        from czcore import llm, ytdlp
        return {"corpus": corpus.stats(), "llm": llm.status(),
                "ytdlp": ytdlp.status()}

    # -- submissions: ingest + "Send to the Record" (the stable surface) ---
    #
    # Body {url} or {path} plus optional {town, body, date} →
    #   {meeting_id, status: "exists"|"queued"}. Highlighter's and Publisher's
    #   "Send to the Record" buttons call this; so does the page's own add box.
    @app.post("/api/memory/submissions")
    def api_submissions(body: dict = Body(...)):
        if not (body.get("url") or body.get("path")):
            return JSONResponse(
                {"error": "give me a meeting URL or a local file path"},
                status_code=422)
        plan = ingest.resolve_input(body)
        dup = ingest.submit_dedupe(corpus, plan)
        if dup:
            return {"meeting_id": dup["id"], "status": "exists"}

        corpus.upsert_meeting({
            "id": plan["id"], "status": "queued",
            "url": plan.get("url", ""), "url_canon": plan.get("url_canon", ""),
            "source_kind": plan["kind"], "video_id": plan.get("video_id", ""),
            "source_hash": plan.get("source_hash", ""),
            "title": plan.get("title", ""), "town": plan.get("town", ""),
            "body": plan.get("body", ""), "date": plan.get("date", ""),
        })

        def work(job):
            return ingest.run(corpus, plan, job)

        label = (plan.get("title") or plan.get("url") or plan.get("path") or "")[:60]
        j = jobs.start("memory-ingest", work, tool="memory",
                       label=f"to the record — {label}")
        return {"meeting_id": plan["id"], "status": "queued", "job": j.to_dict()}

    # -- a meeting page: transcript, reading, moments ---------------------
    @app.post("/api/memory/meeting")
    def api_meeting(body: dict = Body(...)):
        mid = str(body.get("id", "")).strip()
        m = corpus.get_meeting(mid)
        if not m:
            return JSONResponse({"error": "no such meeting in the record"},
                                status_code=404)
        segs = corpus.transcript(mid)
        moments = detect.moments(segs) if segs else []
        return {"meeting": m, "transcript": {"segments": segs},
                "moments": moments}

    @app.post("/api/memory/forget")
    def api_forget(body: dict = Body(...)):
        return {"removed": corpus.forget(str(body.get("id", "")).strip())}

    # -- the long view: cross-corpus search with jump-to-timestamp --------
    @app.get("/api/memory/search")
    def api_search(q: str = "", limit: int = 80):
        hits = corpus.search(q, limit=min(int(limit), 200))
        return {"q": q, "hits": hits, "stats": corpus.stats()}

    # -- context: prior appearances for Highlighter's panel (stable) ------
    #
    # Body {texts:[...]} → {issues, prior, stats}. Issue threads arrive with the
    # telescope (the issue engine, after lane A's merge); for now `prior` is the
    # related-language search over the corpus, honestly labeled, and `issues` is
    # empty rather than faked.
    @app.post("/api/memory/context")
    def api_context(body: dict = Body(...)):
        texts = body.get("texts") or []
        if isinstance(texts, str):
            texts = [texts]
        prior, seen = [], set()
        for tx in list(texts)[:20]:
            for h in corpus.semantic(embed.embed(str(tx)), limit=6):
                key = (h["meeting_id"], round(h["t"], 1))
                if key in seen:
                    continue
                seen.add(key)
                prior.append({
                    "meeting_id": h["meeting_id"], "ts": h["t"],
                    "text": h["text"], "speaker": h["speaker"],
                    "title": h["title"], "date": h["date"], "score": h["score"]})
        prior.sort(key=lambda p: p["score"], reverse=True)
        st = corpus.stats()
        return {"issues": [], "prior": prior[:40],
                "stats": {"meetings": st["live"], "segments": st["segments"],
                          "note": "prior appearances by related language; "
                                  "issue threads arrive with the telescope"}}
