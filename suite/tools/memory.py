"""Community Memory — the record across meetings and years.

Routes only; the engine lives in the top-level `memory/` package (lane B owns
both). Ingest and the pipeline run as JobManager jobs so the Queue page and
toasts show them — one queue is covenant. Every AI surface here is labeled and
supplements the official record; it never replaces it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# lane B owns memory/, but `[tool.setuptools] packages` is lane A's file — until
# the HANDOFF ask lands there, make the sibling package importable by path so
# the suite finds it no matter the working directory. Harmless once added.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from memory import detect, embed, ingest, issues   # noqa: E402
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
        limit = max(1, min(int(limit), 200))   # clamp both ends; -1 would scan all
        hits = corpus.search(q, limit=limit)
        return {"q": q, "hits": hits, "stats": corpus.stats()}

    # -- context: prior appearances + tracked issues for Highlighter (stable)
    #
    # Body {texts:[...]} → {issues, prior, stats}. `prior` is the related-language
    # search over the corpus (unchanged shape); `issues` now carries the tracked
    # issues those texts land on — the telescope answering the microscope.
    @app.post("/api/memory/context")
    def api_context(body: dict = Body(...)):
        texts = body.get("texts") or []
        # accept a list of strings; tolerate a bare string; ignore anything else
        # (a scalar would blow up list() with a 500 instead of a clean answer)
        if isinstance(texts, str):
            texts = [texts]
        elif not isinstance(texts, list):
            texts = []
        texts = [str(t) for t in list(texts)[:20] if str(t).strip()]
        prior, seen = [], set()
        for tx in texts:
            for h in corpus.semantic(embed.embed(tx), limit=6):
                key = (h["meeting_id"], round(h["t"], 1))
                if key in seen:
                    continue
                seen.add(key)
                prior.append({
                    "meeting_id": h["meeting_id"], "ts": h["t"],
                    "text": h["text"], "speaker": h["speaker"],
                    "title": h["title"], "date": h["date"], "score": h["score"]})
        prior.sort(key=lambda p: p["score"], reverse=True)
        issue_hits = _issues_for_texts(corpus, texts, limit=6)
        st = corpus.stats()
        return {"issues": issue_hits, "prior": prior[:40],
                "stats": {"meetings": st["live"], "segments": st["segments"],
                          "issues": st["issues"],
                          "note": "prior appearances by related language; "
                                  "issues are the tracked topics they land on"}}

    # -- issues: the long view --------------------------------------------
    #
    # The record's tracked topics, their timelines, and the steward tools that
    # keep them honest. Officials-only aggregation by default; Memory supplements
    # the official record, never replaces it — said on every AI surface.
    @app.get("/api/memory/issues")
    def api_issues(town: str = "", status: str = "active", limit: int = 200):
        limit = max(1, min(int(limit), 500))
        return {"issues": corpus.list_issues(town=town, status=status, limit=limit),
                "candidates": corpus.list_issues(town=town, status="candidate",
                                                 limit=60),
                "towns": corpus.live_towns(), "stats": corpus.stats()}

    @app.post("/api/memory/issue")
    def api_issue(body: dict = Body(...)):
        iid = str(body.get("id", "")).strip()
        iss = corpus.get_issue(iid)
        if not iss:
            return JSONResponse({"error": "no such issue on the record"},
                                status_code=404)
        nodes = _timeline(corpus, iid)
        return {"issue": iss, "timeline": nodes,
                "overview": _issue_overview(iss, nodes)}

    @app.post("/api/memory/issues/rebuild")
    def api_issues_rebuild(body: dict = Body(default={})):
        town = str((body or {}).get("town", "")).strip()

        def work(job):
            towns = [town] if town else (corpus.live_towns() or [""])
            out = [issues.discover(corpus, t, job) for t in towns]
            return {"towns": out}

        j = jobs.start("memory-issues", work, tool="memory",
                       label="rebuilding the long view")
        return {"status": "queued", "job": j.to_dict()}

    # -- steward tools: merge / split / rename / promote / discard ---------
    @app.post("/api/memory/issue/rename")
    def api_issue_rename(body: dict = Body(...)):
        iid = str(body.get("id", "")).strip()
        name = str(body.get("name", "")).strip()
        aliases = body.get("aliases")
        if not corpus.get_issue(iid) or not name:
            return JSONResponse({"error": "need an issue id and a new name"},
                                status_code=422)
        aliases = [str(a).strip() for a in aliases if str(a).strip()] \
            if isinstance(aliases, list) else None
        corpus.rename_issue(iid, name, aliases)
        if aliases is not None:
            issues.reassign_issue(corpus, iid)   # new words → refreshed membership
        return {"issue": corpus.get_issue(iid)}

    @app.post("/api/memory/issue/merge")
    def api_issue_merge(body: dict = Body(...)):
        dst = str(body.get("dst", "")).strip()
        src = [str(s).strip() for s in (body.get("src") or []) if str(s).strip()]
        if not dst or not src:
            return JSONResponse({"error": "merge needs dst and src[]"},
                                status_code=422)
        merged = corpus.merge_issues(src, dst)
        if not merged:
            return JSONResponse({"error": "no such destination issue"},
                                status_code=404)
        issues.reassign_issue(corpus, dst)
        return {"issue": corpus.get_issue(dst)}

    @app.post("/api/memory/issue/split")
    def api_issue_split(body: dict = Body(...)):
        iid = str(body.get("id", "")).strip()
        mid = str(body.get("meeting_id", "")).strip()
        new = issues.split_off_meeting(corpus, iid, mid,
                                       str(body.get("name", "")).strip())
        if not new:
            return JSONResponse(
                {"error": "need an issue id and one of its meetings"},
                status_code=422)
        return {"issue": new, "from": corpus.get_issue(iid)}

    @app.post("/api/memory/issue/promote")
    def api_issue_promote(body: dict = Body(...)):
        iid = str(body.get("id", "")).strip()
        if not corpus.get_issue(iid):
            return JSONResponse({"error": "no such issue"}, status_code=404)
        corpus.upsert_issue({"id": iid, "status": "active", "origin": "steward",
                             "note": ""})
        return {"issue": corpus.get_issue(iid)}

    @app.post("/api/memory/issue/forget")
    def api_issue_forget(body: dict = Body(...)):
        return {"removed": corpus.delete_issue(str(body.get("id", "")).strip())}

    # -- threads: follow an issue, mint one from a search -----------------
    @app.post("/api/memory/thread")
    def api_thread(body: dict = Body(...)):
        iid = str(body.get("issue_id", "")).strip()
        if body.get("follow") is False:
            return {"following": False, "removed": corpus.unfollow(iid)}
        t = corpus.follow(iid)
        if not t:
            return JSONResponse({"error": "no such issue to follow"},
                                status_code=404)
        return {"following": True, "thread": t}

    @app.get("/api/memory/threads")
    def api_threads():
        return {"threads": corpus.list_threads(),
                "unseen": corpus.unseen_count()}

    @app.post("/api/memory/thread/mint")
    def api_thread_mint(body: dict = Body(...)):
        res = issues.mint_from_query(corpus, str(body.get("q", "")).strip(),
                                     str(body.get("town", "")).strip())
        if not res:
            return JSONResponse({"error": "give me something to follow"},
                                status_code=422)
        return res

    @app.post("/api/memory/thread/ack")
    def api_thread_ack(body: dict = Body(default={})):
        return {"marked": corpus.mark_seen(str((body or {}).get("issue_id", "")))}

    # -- resurfacings + the "still watching" digest -----------------------
    @app.get("/api/memory/notifications")
    def api_notifications(limit: int = 40):
        return {"events": corpus.list_events(unseen_only=False,
                                             limit=max(1, min(int(limit), 100))),
                "unseen": corpus.unseen_count()}

    @app.get("/api/memory/digest")
    def api_digest():
        return issues.digest(corpus)


# -- helpers (module level; the routes close over `corpus`) ----------------

def _issues_for_texts(corpus, texts, limit=6):
    """The tracked issues a set of agenda/transcript texts land on — the telescope
    half of the context API. Scored by how much the text uses each issue's own
    words (precise) plus centroid nearness (a nudge), so Highlighter can say
    'this topic: N prior appearances across M meetings'."""
    if not texts:
        return []
    known = corpus.issue_keywords(active_only=True)
    if not known:
        return []
    joined = " " + " ".join(texts).lower() + " "
    best = {}
    qvecs = [embed.embed(t) for t in texts]
    for iss in known:
        if iss.get("status") != "active":
            continue
        word_hit = any(kw and re.search(r"\b" + re.escape(kw) + r"\b", joined)
                       for kw in (iss.get("keywords") or []))
        score = 1.0 if word_hit else 0.0
        cen = iss.get("centroid")
        if cen is not None:
            for qv in qvecs:
                if qv is not None:
                    score = max(score, float(cen @ qv))
        # a named-word hit is a real prior appearance; a centroid-only match must
        # be strong to count, or the panel fills with faint neighbours
        if word_hit or score >= 0.5:
            best[iss["id"]] = score
    top = sorted(best.items(), key=lambda kv: -kv[1])[:limit]
    out = []
    for iid, score in top:
        d = corpus.get_issue(iid)
        if not d:
            continue
        out.append({
            "id": iid, "name": d["name"], "town": d.get("town", ""),
            "n_meetings": d["n_meetings"], "n_segments": d["n_segments"],
            "first_seen": d.get("first_seen"), "last_seen": d.get("last_seen"),
            "following": d.get("following", False), "score": round(score, 4)})
    return out


def _timeline(corpus, issue_id):
    """Appearances as nodes, each with its time-coded beads and any votes that
    landed on this issue (a decision within ~90s of one of the issue's beads) —
    votes as milestones, every node a deep-link into playback."""
    nodes = corpus.issue_appearances(issue_id)
    for node in nodes:
        m = corpus.get_meeting(node["meeting_id"]) or {}
        decisions = ((m.get("analysis") or {}).get("decisions")) or []
        bead_ts = [b["t"] for b in node["beads"]]
        mis = []
        for d in decisions:
            dt = d.get("t")
            if dt is None:
                continue
            if any(abs(dt - bt) <= 90 for bt in bead_ts):
                mis.append({"t": dt, "text": d.get("text", ""),
                            "outcome": d.get("outcome", "")})
        node["milestones"] = mis[:8]
    return nodes


def _issue_overview(issue, nodes):
    """A plain one-liner for the issue page — the arc so far, extractive and
    honest (the generative 'what changed' lives on each resurfacing)."""
    n_m = len(nodes)
    span = " ".join(x for x in (issue.get("first_seen"), issue.get("last_seen"))
                    if x)
    if issue.get("first_seen") and issue.get("last_seen") \
            and issue["first_seen"] != issue["last_seen"]:
        span = f"{issue['first_seen']} → {issue['last_seen']}"
    parts = [f"“{issue['name']}” appears in {n_m} meeting"
             f"{'s' if n_m != 1 else ''} on the record"]
    if span:
        parts.append(span)
    parts.append(f"{issue.get('n_segments', 0)} moments tracked")
    return " · ".join(parts)
