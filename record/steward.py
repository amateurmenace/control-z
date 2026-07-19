"""The eight verbs, over HTTP, with a name against every one.

specs/17 §7 asks for parity before growth, and parity is genuinely most of the
work already done: `rename / merge / split / promote / forget / rebuild`, plus
follow and mint, all exist at the desk as sequences of `Corpus` and
`memory.issues` calls that have been exercised against a real corpus. This
module's job is HTTP, auth, and the audit row — not a second implementation of
curation. Where a verb here looks thin, that is the point; the thinking is in
`memory/issues.py` and it is shared.

Two things are genuinely new.

**Every verb runs inside `corpus.unit()`.** A curation verb is a *sequence* —
merge is `merge_issues`, then `reassign_issue`, then `get_issue` — and at the
desk, with one writer on one file, a half-finished sequence is not a state the
world can observe. With several workers against one Postgres it is, and a
half-merged issue is worse than a refused merge. `unit()` exists for exactly
this, and this is its caller.

**Every verb writes to `audit`.** The record has always remembered its own
edits (specs/14 §8); hosting it means remembering who made them and when. The
audit write is deliberately outside the transaction and deliberately incapable
of raising: a steward who has seen a merge succeed must not have it rolled back
because the log was busy.

The submission queue is the other half — `submitted → approved → queued → live`
or `rejected`. Approving does not ingest inline; it marks the row and lets the
pipeline job pick it up, because a steward pressing a button should not be
holding an HTTP connection open while a meeting transcribes.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import Body, Header, Query
from fastapi.responses import JSONResponse

from memory import issues as issue_engine

from . import sources

from . import auth

# The verbs this console will perform, and nothing else. An allowlist rather
# than "whatever attribute name arrives" — the steward API takes a verb from
# the network, and getattr on user input is how a curation endpoint becomes a
# remote-code endpoint.
VERBS = ("rename", "merge", "split", "promote", "forget", "rebuild",
         "follow", "unfollow", "mint")


def register_steward(app, store, steward_of) -> None:
    """Mount `/api/steward/*`. `steward_of(authorization)` verifies and returns
    the steward, or raises `auth.AuthError` — the app owns that policy so this
    module cannot accidentally relax it."""

    def _audit(corpus, who: dict, verb: str, target: str = "",
               town: str = "", **payload) -> None:
        auth.audit(corpus, who["email"], verb, target, town, payload)

    # -- who am I ---------------------------------------------------------

    @app.get("/api/steward/me")
    def me(authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        return {"steward": who["email"], "name": who["name"],
                "verbs": list(VERBS)}

    # -- the review queue -------------------------------------------------

    @app.get("/api/steward/submissions")
    def list_submissions(status: str = Query("submitted"),
                         limit: int = Query(100, ge=1, le=500),
                         authorization: Optional[str] = Header(None)):
        steward_of(authorization)
        corpus = store()
        with corpus._con() as con:
            rows = con.execute(
                "SELECT * FROM submissions WHERE status=%s "
                "ORDER BY added_at DESC LIMIT %s", (status, limit)).fetchall()
        return {"status": status, "submissions": [dict(r) for r in rows]}

    @app.post("/api/steward/submissions/{sub_id:path}/approve")
    def approve(sub_id: str, authorization: Optional[str] = Header(None)):
        """Mark it for the pipeline. Approving does not transcribe a meeting
        inline — the steward should not be holding a connection open while a
        job runs, and the job is a Cloud Run Job for exactly that reason."""
        who = steward_of(authorization)
        corpus = store()
        with corpus.unit():
            with corpus._con() as con:
                row = con.execute("SELECT * FROM submissions WHERE id=%s",
                                  (sub_id,)).fetchone()
                if not row:
                    return JSONResponse({"error": "no such submission"},
                                        status_code=404)
                con.execute(
                    "UPDATE submissions SET status='approved', updated_at=%s "
                    "WHERE id=%s", (time.time(), sub_id))
        _audit(corpus, who, "approve", sub_id, row["town"], url=row["url"])
        return {"id": sub_id, "status": "approved"}

    @app.post("/api/steward/submissions/{sub_id:path}/reject")
    def reject(sub_id: str, body: dict = Body(default={}),
               authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        corpus = store()
        reason = (body.get("reason") or "").strip()
        with corpus._con() as con:
            row = con.execute("SELECT * FROM submissions WHERE id=%s",
                              (sub_id,)).fetchone()
            if not row:
                return JSONResponse({"error": "no such submission"},
                                    status_code=404)
            con.execute(
                "UPDATE submissions SET status='rejected', reason=%s, "
                "updated_at=%s WHERE id=%s", (reason, time.time(), sub_id))
        _audit(corpus, who, "reject", sub_id, row["town"], reason=reason)
        return {"id": sub_id, "status": "rejected", "reason": reason}

    # -- the eight verbs --------------------------------------------------

    @app.get("/api/steward/issues")
    def steward_issues(town: str = Query(""), status: str = Query("active"),
                       limit: int = Query(300, ge=1, le=1000),
                       authorization: Optional[str] = Header(None)):
        steward_of(authorization)
        return {"issues": store().list_issues(town=town, status=status,
                                              limit=limit)}

    @app.post("/api/steward/issues/{issue_id:path}/rename")
    def rename(issue_id: str, body: dict = Body(...),
               authorization: Optional[str] = Header(None)):
        """The verb the imported corpus needs first: `City Realy` is a caption
        garble that became a permanent issue id, and the import carried it
        across on purpose rather than making an unaudited edit."""
        who = steward_of(authorization)
        corpus = store()
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "an issue needs a name"},
                                status_code=422)
        aliases = body.get("aliases")
        before = corpus.get_issue(issue_id)
        if not before:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        with corpus.unit():
            out = corpus.rename_issue(issue_id, name, aliases)
            if aliases is not None:
                issue_engine.reassign_issue(corpus, issue_id)
                out = corpus.get_issue(issue_id)
        _audit(corpus, who, "rename", issue_id, before.get("town", ""),
               was=before.get("name"), now=name)
        return {"issue": out}

    @app.post("/api/steward/issues/{dst_id:path}/merge")
    def merge(dst_id: str, body: dict = Body(...),
              authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        corpus = store()
        src_ids = [s for s in (body.get("src_ids") or []) if s and s != dst_id]
        if not src_ids:
            return JSONResponse({"error": "merge what into it?"},
                                status_code=422)
        dst = corpus.get_issue(dst_id)
        if not dst:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        with corpus.unit():
            out = corpus.merge_issues(src_ids, dst_id)
            issue_engine.reassign_issue(corpus, dst_id)
            out = corpus.get_issue(dst_id)
        _audit(corpus, who, "merge", dst_id, dst.get("town", ""), sources=src_ids)
        return {"issue": out, "merged": src_ids}

    @app.post("/api/steward/issues/{issue_id:path}/split")
    def split(issue_id: str, body: dict = Body(...),
              authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        corpus = store()
        meeting_id = (body.get("meeting_id") or "").strip()
        if not meeting_id:
            return JSONResponse({"error": "split which meeting off?"},
                                status_code=422)
        src = corpus.get_issue(issue_id)
        if not src:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        with corpus.unit():
            out = issue_engine.split_off_meeting(
                corpus, issue_id, meeting_id, (body.get("name") or "").strip())
        if not out:
            return JSONResponse(
                {"error": "that meeting has no segments on this issue"},
                status_code=422)
        _audit(corpus, who, "split", issue_id, src.get("town", ""),
               meeting=meeting_id, into=out.get("id"))
        return {"issue": out}

    @app.post("/api/steward/issues/{issue_id:path}/promote")
    def promote(issue_id: str, authorization: Optional[str] = Header(None)):
        """A candidate becomes real. Deliberately no reassign and no centroid
        recompute — a promoted candidate keeps exactly the links the candidate
        queue gave it until the next rebuild, which is the desk's behavior and
        is what makes promote reviewable."""
        who = steward_of(authorization)
        corpus = store()
        before = corpus.get_issue(issue_id)
        if not before:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        with corpus.unit():
            corpus.upsert_issue({"id": issue_id, "status": "active",
                                 "origin": "steward", "note": ""})
        _audit(corpus, who, "promote", issue_id, before.get("town", ""))
        return {"issue": corpus.get_issue(issue_id)}

    @app.post("/api/steward/issues/{issue_id:path}/forget")
    def forget_issue(issue_id: str, authorization: Optional[str] = Header(None)):
        """The one destructive verb — contrast merge, which leaves a tombstone
        pointing home. Audited before the row is gone, so the log outlives it."""
        who = steward_of(authorization)
        corpus = store()
        before = corpus.get_issue(issue_id)
        if not before:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        _audit(corpus, who, "forget", issue_id, before.get("town", ""),
               name=before.get("name"), n_segments=before.get("n_segments"))
        with corpus.unit():
            ok = corpus.delete_issue(issue_id)
        return {"forgotten": ok, "id": issue_id}

    @app.post("/api/steward/rebuild")
    def rebuild(body: dict = Body(default={}),
                authorization: Optional[str] = Header(None)):
        """The heaviest verb: re-derive a town's issues from its segments. It
        keeps minted, steward-touched and followed issues — a rebuild refreshes
        links, it never forgets a human's work."""
        who = steward_of(authorization)
        corpus = store()
        town = (body.get("town") or "").strip()
        if not town:
            return JSONResponse({"error": "rebuild which town?"},
                                status_code=422)
        t0 = time.time()
        with corpus.unit():
            result = issue_engine.discover(corpus, town)
        _audit(corpus, who, "rebuild", town, town, result=result,
               seconds=round(time.time() - t0, 1))
        return {"town": town, "result": result,
                "seconds": round(time.time() - t0, 1)}

    @app.post("/api/steward/issues/{issue_id:path}/follow")
    def follow(issue_id: str, authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        corpus = store()
        out = corpus.follow(issue_id)
        if out is None:
            return JSONResponse({"error": "no such issue"}, status_code=404)
        _audit(corpus, who, "follow", issue_id)
        return {"thread": out}

    @app.delete("/api/steward/issues/{issue_id:path}/follow")
    def unfollow(issue_id: str, authorization: Optional[str] = Header(None)):
        who = steward_of(authorization)
        corpus = store()
        gone = corpus.unfollow(issue_id)
        _audit(corpus, who, "unfollow", issue_id)
        return {"unfollowed": gone, "id": issue_id}

    @app.post("/api/steward/mint")
    def mint(body: dict = Body(...), authorization: Optional[str] = Header(None)):
        """Mint an issue from a query — the steward's way of saying "this is a
        thing" about something the clusterer did not name."""
        who = steward_of(authorization)
        corpus = store()
        q = (body.get("q") or "").strip()
        town = (body.get("town") or "").strip()
        if not (q and town):
            return JSONResponse({"error": "mint needs a query and a town"},
                                status_code=422)
        with corpus.unit():
            out = issue_engine.mint_from_query(corpus, q, town)
        _audit(corpus, who, "mint", (out or {}).get("id", ""), town, q=q)
        return {"issue": out}


    # -- the intake: what the record is allowed to swallow -----------------
    #
    # This is the cost lever. Ingest spends money per meeting (embeddings
    # always, ASR when captions are missing), and a municipal channel is
    # mostly not meetings — so the steward's control here is not a
    # convenience, it is the budget.

    @app.get("/api/steward/towns")
    def steward_towns(authorization: Optional[str] = Header(None)):
        steward_of(authorization)
        corpus = store()
        with corpus._con() as con:
            rows = con.execute(
                "SELECT slug, name, state, status, sources FROM towns "
                "ORDER BY name").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            srcs = d.get("sources") or []
            if isinstance(srcs, str):
                srcs = json.loads(srcs)
            d["sources"] = srcs
            d["bodies"] = sorted({b for src in srcs
                                  for b in sources.bodies_of(src)})
            d["problems"] = [p for src in srcs for p in sources.bad_patterns(src)]
            out.append(d)
        return {"towns": out}

    @app.put("/api/steward/towns/{slug}/sources")
    def set_sources(slug: str, body: dict = Body(...),
                    authorization: Optional[str] = Header(None)):
        """Replace a town's intake rules. Refuses a config whose patterns do
        not compile — a bad regex must fail at the desk of the person who
        typed it, never at 3am inside a nightly job."""
        who = steward_of(authorization)
        srcs = body.get("sources")
        if not isinstance(srcs, list):
            return JSONResponse({"error": "sources must be a list"},
                                status_code=422)
        problems = [p for src in srcs for p in sources.bad_patterns(src)]
        if problems:
            return JSONResponse(
                {"error": "these patterns will not compile", "problems": problems},
                status_code=422)
        corpus = store()
        with corpus._con() as con:
            hit = con.execute("SELECT slug FROM towns WHERE slug=%s",
                              (slug,)).fetchone()
            if not hit:
                return JSONResponse({"error": "no such town"}, status_code=404)
            con.execute("UPDATE towns SET sources=%s, updated_at=%s WHERE slug=%s",
                        (json.dumps(srcs), time.time(), slug))
        _audit(corpus, who, "sources", slug, slug, sources=len(srcs))
        return {"slug": slug, "sources": srcs}

    @app.post("/api/steward/preview")
    def preview(body: dict = Body(...),
                authorization: Optional[str] = Header(None)):
        """What would a poll file, if it ran right now — and nothing written.

        The steward changes a rule and sees the three lists move before
        committing to anything. `unmatched` comes back with suggested rules
        attached, so the taxonomy is learned from what the town actually
        posts rather than guessed at."""
        steward_of(authorization)
        src = body.get("source") or {}
        if not src.get("url"):
            return JSONResponse({"error": "a source needs a url"},
                                status_code=422)
        problems = sources.bad_patterns(src)
        if problems:
            return JSONResponse({"error": "bad patterns", "problems": problems},
                                status_code=422)
        try:
            from .connectors import youtube
            items = youtube.poll(src["url"], limit=int(body.get("limit") or 15))
        except Exception as exc:
            return JSONResponse(
                {"error": f"could not reach the source ({exc})"},
                status_code=502)
        p = sources.plan(items, src)
        p["suggestions"] = sources.suggest_rules(p["unmatched"])
        p["polled"] = len(items)
        # The single number a steward is deciding on.
        p["would_cost"] = len(p["file"])
        return p

    @app.post("/api/steward/towns/{slug}/poll")
    def poll_town(slug: str, body: dict = Body(default={}),
                  authorization: Optional[str] = Header(None)):
        """Run the intake for real. Still files to the queue, never to the
        record — approval remains a separate, human act."""
        who = steward_of(authorization)
        corpus = store()
        with corpus._con() as con:
            row = con.execute("SELECT * FROM towns WHERE slug=%s",
                              (slug,)).fetchone()
        if not row:
            return JSONResponse({"error": "no such town"}, status_code=404)
        from .connectors import youtube
        result = youtube.poll_town(corpus, dict(row),
                                   limit=int(body.get("limit") or 15))
        _audit(corpus, who, "poll", slug, slug, filed=result.get("filed"))
        return result

    # -- the ledgers ------------------------------------------------------

    @app.get("/api/steward/audit")
    def audit_log(limit: int = Query(200, ge=1, le=1000),
                  authorization: Optional[str] = Header(None)):
        steward_of(authorization)
        corpus = store()
        with corpus._con() as con:
            rows = con.execute(
                "SELECT * FROM audit ORDER BY added_at DESC LIMIT %s",
                (limit,)).fetchall()
        return {"audit": [dict(r) for r in rows]}

    @app.get("/api/steward/spend")
    def spend(limit: int = Query(200, ge=1, le=1000),
              authorization: Optional[str] = Header(None)):
        """The AI-audit ledger, ported up from the desk: every token
        attributed, visible here rather than in a bill nobody reads. The
        server's spend is the project's; the reader's identity is never part
        of the price."""
        steward_of(authorization)
        corpus = store()
        with corpus._con() as con:
            rows = con.execute(
                "SELECT * FROM spend ORDER BY added_at DESC LIMIT %s",
                (limit,)).fetchall()
            totals = con.execute(
                "SELECT model, purpose, COUNT(*) AS calls, "
                "COALESCE(SUM(units),0) AS units FROM spend "
                "GROUP BY model, purpose ORDER BY units DESC").fetchall()
        return {"spend": [dict(r) for r in rows],
                "totals": [dict(r) for r in totals]}
