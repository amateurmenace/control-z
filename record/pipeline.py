"""The approved-submissions pipeline: a steward's yes becomes a meeting.

This is the stage that had never run. The connector polls three real channels
and files candidates correctly; the console lets a steward approve them; and
then, until now, nothing picked them up. `submissions.status='approved'` was a
terminal state pretending to be a queue, and `queued`/`live` were schema-only —
declared in the migration, written by nobody. So was `submissions.meeting_id`,
the column that says which meeting a submission became.

What runs here is not a port. `memory/ingest.py` is the desk's pipeline and it
is store-agnostic by construction (`memory/seam.py`), so this module opens
Postgres instead of SQLite and calls the same `ingest.run` the desk calls —
same captions-first order, same three dedupe tiers, same issue assignment, same
vote reading. `tests/test_record_store_parity.py` is what makes that sentence
safe to write. A second implementation would be a second set of bugs.

**Three things a container does not have, and what is done about each.**

*A media folder.* `memory/ingest` wrote sidecars under `czcore.paths.media_dir`,
which resolves `~/Movies` and creates it as a side effect of being asked. In a
container that becomes `/root/Videos/…` — writable, in-memory, against the job's
own memory limit, and gone at exit. `ingest.run` now takes a `workdir`, which is
the resolver `web.bake.Bake` already took and `record/press.py` already passed;
this job hands it a scratch directory it made and removes it afterwards.

*Scribe.* There is no ASR in this image and there will not be (specs/19 §R1.4).
A meeting whose captions come back empty is not a failure and is not retried
into a GPU bill: it lands `no_transcript`, parks a row in `asr_tasks` for the
desk drain (specs/17 §6.4), and the console says so. Filing that row is this
stage's job — the connector deliberately refuses to, because at poll time no
meeting exists yet and writing one would be ingest through the back door.

*The neural half.* `replace_segments` writes only the 256-dim lexical vector, so
a freshly ingested meeting is invisible to `space=neural` until it is embedded.
The embed stage runs here, under the same spend cap as the backfill, and a cap
that stops it is reported rather than raised — the meeting is already in the
record and readable; only meaning-search is behind.

**Nothing ingests without a human.** This job reads `approved` and nothing else.
It cannot promote a `submitted` row, and a `rejected` row is invisible to it.
The covenant's line about a human in the middle is enforced by the SELECT.

    python -m record.pipeline                 # drain the approved queue
    python -m record.pipeline --limit 1       # one meeting, which is how to
                                              #   walk the first one by hand
    python -m record.pipeline --dry-run       # say what would run, touch nothing
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

# The states this job moves a submission between. `approved` is written by the
# steward console and is the only thing this job will pick up; `queued` says a
# job has it; `live` says the meeting landed. Kept as constants because a state
# machine spelled in string literals across three modules is one typo from a
# row nothing will ever look at again.
APPROVED, QUEUED, LIVE, FAILED = "approved", "queued", "live", "failed"


class JobLog:
    """What `memory/ingest.run` means by `job`, for a process with no UI.

    The desk passes a `czcore.appshell.jobs.Job` that a window is watching.
    Nothing is watching this one, so progress and messages become log lines —
    which is the right shape anyway: Cloud Run's log is where an operator finds
    out what a job did, and `OPERATING.md` promises those read like sentences.

    `check_cancel` is a no-op that must still exist. `ingest.run` calls it
    between stages and catches `JobCancelled` to drop a half-built meeting; a
    job with no cancel button simply never raises, and the shape stays honest
    rather than the caller growing a `if job is not None` at every stage."""

    def __init__(self, label: str = "", quiet: bool = False):
        self.label = label
        self.quiet = quiet
        self.progress = 0.0
        self._message = ""

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, text: str) -> None:
        self._message = text
        if text and not self.quiet:
            print(f"    {text}", flush=True)

    def check_cancel(self) -> None:
        return None


def approved_queue(corpus, limit: int = 0) -> List[dict]:
    """The submissions a steward has said yes to, oldest first.

    Oldest first on purpose: a queue that serves the newest submission first
    starves the one somebody has been waiting on, and the steward who approved
    it has already forgotten which order they clicked in."""
    sql = ("SELECT * FROM submissions WHERE status=%s ORDER BY added_at ASC")
    args: tuple = (APPROVED,)
    if limit:
        sql += " LIMIT %s"
        args = (APPROVED, limit)
    with corpus._con() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def _mark(corpus, sub_id: str, status: str, meeting_id: str = "",
          reason: str = "") -> None:
    """Advance a submission, and say what it became.

    `meeting_id` is the link the schema has carried since the first migration
    and nothing has ever written. Without it a steward can see that a
    submission was approved and cannot get from there to the meeting — the
    queue remembers the decision and forgets the outcome."""
    with corpus._con() as con:
        con.execute(
            "UPDATE submissions SET status=%s, meeting_id=%s, reason=%s, "
            "updated_at=%s WHERE id=%s",
            (status, meeting_id, reason, time.time(), sub_id))


def park_asr_task(corpus, meeting_id: str, town: str, url: str,
                  note: str = "") -> str:
    """File a drain ticket for a meeting that arrived without captions.

    This is a ticket, never a bill. Cloud GPU ASR stays a priced, deliberate
    choice nobody has made (specs/17 §6.4); what this row means is "a desk
    running the suite can transcribe this on its own hardware when one
    volunteers." Until R2.2 builds `/api/asr/*` nothing claims these, and that
    is the honest state — the row exists so the console can say *waiting for a
    transcript* instead of the meeting looking simply broken.

    Idempotent on meeting id: re-running the pipeline over a meeting that is
    still without captions must not file a second ticket for the same work.
    The id is derived from the meeting rather than random for that reason —
    `ON CONFLICT DO NOTHING` can only hold if the same work computes the same
    id. Written out here rather than borrowed from `store.submission_id`,
    which stamps a `sub:` prefix: these are two different kinds of row and an
    ASR ticket wearing a submission's prefix is a thing somebody debugs at
    11pm."""
    import hashlib
    digest = hashlib.blake2b(meeting_id.encode("utf-8"),
                             digest_size=8).hexdigest()
    task_id = f"asr:{digest}"
    now = time.time()
    with corpus._con() as con:
        con.execute(
            "INSERT INTO asr_tasks (id, meeting_id, town, url, status, note, "
            "added_at, updated_at) VALUES (%s,%s,%s,%s,'parked',%s,%s,%s) "
            "ON CONFLICT (id) DO NOTHING",
            (task_id, meeting_id, town, url, note, now, now))
    return task_id


def _embed(corpus, town: str, meeting_id: str = "",
           quiet: bool = False) -> dict:
    """Give the new meeting its meaning vectors, under the cap.

    Separate from `ingest.run` because `replace_segments` writes the lexical
    vector and nothing else — so without this stage a meeting is on the record,
    readable, cited, and invisible to `space=neural`, which is the exact
    silent-degradation the search endpoint's honest note exists to prevent.

    Scoped to the one meeting on purpose. Handed only a town, `backfill` walks
    every unembedded segment that town has — correct and capped, and on a
    corpus with a backlog it is hours of work this stage did not ask for, so
    the nightly ingest times out on somebody else's job. The backlog is
    `record-embed`'s; this is the meeting that just arrived.

    A cap that stops this is reported, not raised. The meeting has landed; what
    is behind is meaning-search, and the record is designed to read without it."""
    from . import embed_neural
    if not embed_neural.available():
        why = embed_neural.status().get("reason", "")
        if not quiet:
            print(f"    meaning-search skipped — {why or 'no neural half here'}")
        return {"embedded": 0, "note": why}
    try:
        r = embed_neural.backfill(corpus, town=town, meeting_id=meeting_id,
                                  verbose=False)
    except Exception as exc:
        if not quiet:
            print(f"    meaning-search deferred — {exc}")
        return {"embedded": 0, "note": str(exc)}
    if not quiet:
        print(f"    embedded {r.get('embedded', 0)} segment(s) "
              f"· ${r.get('spent_usd', 0):.4f}")
        if r.get("stopped_at_cap"):
            print(f"    ⚠ the ${r.get('cap_usd', 0):.2f} spend cap stopped this "
                  f"before the record was whole — the meeting reads, and "
                  f"meaning-search is behind for the rest")
    return r


def ingest_one(corpus, sub: dict, workdir: Path, quiet: bool = False) -> dict:
    """One approved submission, all the way to a meeting somebody can read.

    Returns a result dict rather than raising, because a queue drain that dies
    on its third row and leaves the first two unexplained is worse than one
    that reports three outcomes."""
    from memory import ingest

    label = sub.get("url") or sub.get("id")
    if not quiet:
        print(f"  {label}")

    plan = ingest.resolve_input({
        "url": sub.get("url", ""), "town": sub.get("town", ""),
        "body": sub.get("body", ""), "date": sub.get("date", "")})

    # The cheap dedupe tiers, before a job is claimed: the same meeting may have
    # arrived through the poller and through a resident's paste.
    already = ingest.submit_dedupe(corpus, plan)
    if already:
        _mark(corpus, sub["id"], LIVE, meeting_id=already["id"],
              reason="already on the record")
        if not quiet:
            print(f"    already on the record as {already['id']}")
        return {"submission": sub["id"], "meeting_id": already["id"],
                "status": "exists"}

    _mark(corpus, sub["id"], QUEUED)

    # The shell, before the job — exactly as `suite/tools/memory.py` does it at
    # the desk, and for a reason that only shows up here. `ingest.run` opens
    # with `set_status`, which is an UPDATE: on a meeting that does not exist
    # it changes nothing and says nothing. The desk never noticed because its
    # submissions route creates the shell first. Postgres notices immediately —
    # `replace_segments` runs before `upsert_meeting` inside `ingest.run`, and
    # `segments.meeting_id` carries a foreign key SQLite was not enforcing. So
    # the first meeting this pipeline ever fetched captions for died on the
    # constraint after doing all the work.
    #
    # Creating it here rather than reordering `ingest.run` keeps one ingest
    # contract for both stores: the caller owns the shell, the engine fills it.
    corpus.upsert_meeting({
        "id": plan["id"], "status": "queued",
        "url": plan.get("url", ""), "url_canon": plan.get("url_canon", ""),
        "source_kind": plan["kind"], "video_id": plan.get("video_id", ""),
        "source_hash": plan.get("source_hash", ""),
        "title": plan.get("title", ""), "town": plan.get("town", ""),
        "body": plan.get("body", ""), "date": plan.get("date", ""),
    })

    job = JobLog(label=label, quiet=quiet)
    try:
        result = ingest.run(corpus, plan, job, workdir=workdir)
    except Exception as exc:
        # `ingest.run` has already set the meeting to `error` with this
        # sentence on it; the submission carries the same sentence so the
        # console can show it without joining two tables to find out why.
        _mark(corpus, sub["id"], FAILED, reason=str(exc))
        if not quiet:
            print(f"    failed — {exc}")
        return {"submission": sub["id"], "status": "failed", "error": str(exc)}

    mid = result.get("meeting_id", "")
    status = result.get("status", "")

    if status == "no_transcript":
        note = result.get("note", "")
        task = park_asr_task(corpus, mid, sub.get("town", ""),
                             sub.get("url", ""), note)
        _mark(corpus, sub["id"], LIVE, meeting_id=mid,
              reason="waiting for a transcript")
        if not quiet:
            print(f"    no captions — parked for the drain ({task})")
        return {"submission": sub["id"], "meeting_id": mid,
                "status": "no_transcript", "asr_task": task}

    if status == "exists":
        _mark(corpus, sub["id"], LIVE, meeting_id=mid,
              reason="already on the record")
        return {"submission": sub["id"], "meeting_id": mid, "status": "exists"}

    # Linked before embedded, and the order matters. The meeting is on the
    # record the moment ingest returns; embedding adds a way to find it. If the
    # job dies in the embed stage — a timeout, a refused batch — a submission
    # marked afterwards would still read `queued` against a meeting that is
    # live and unlinked, which is the one state the console cannot explain.
    _mark(corpus, sub["id"], LIVE, meeting_id=mid)
    emb = _embed(corpus, sub.get("town", ""), meeting_id=mid, quiet=quiet)
    return {"submission": sub["id"], "meeting_id": mid, "status": LIVE,
            "segments": result.get("segments", 0),
            "origin": result.get("origin", ""),
            "title": result.get("title", ""),
            "resurfaced": result.get("resurfaced", []),
            "embedded": emb.get("embedded", 0)}


def drain(corpus, limit: int = 0, dry_run: bool = False,
          quiet: bool = False) -> dict:
    """Work the approved queue. Returns what happened to each row."""
    queue = approved_queue(corpus, limit=limit)
    if not quiet:
        print(f"{len(queue)} approved submission(s) waiting"
              + (" — dry run, nothing is written" if dry_run else ""))
    if dry_run or not queue:
        return {"queued": len(queue), "results": [],
                "would": [s["id"] for s in queue]}

    # One scratch root for the whole drain, removed at the end. Sidecars are
    # intermediate artefacts — the meeting is in Postgres and the tape is on
    # YouTube; keeping a VTT after the words are in the record would be storing
    # a copy of the thing we already have, in the one place that does not
    # survive the job exiting anyway.
    root = Path(tempfile.mkdtemp(prefix="record-ingest-"))
    results = []
    try:
        for sub in queue:
            results.append(ingest_one(corpus, sub, root, quiet=quiet))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    landed = [r for r in results if r.get("status") == LIVE]
    parked = [r for r in results if r.get("status") == "no_transcript"]
    failed = [r for r in results if r.get("status") == "failed"]
    if not quiet:
        print(f"\n{len(landed)} landed · {len(parked)} waiting on a transcript "
              f"· {len(failed)} failed")
        for r in failed:
            print(f"  ✗ {r['submission']}: {r.get('error', '')}")
    return {"queued": len(queue), "results": results,
            "landed": len(landed), "parked": len(parked), "failed": len(failed)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m record.pipeline",
        description="Turn approved submissions into meetings on the record.")
    ap.add_argument("--dsn", default="")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N submissions (0 = the whole queue). "
                         "Use --limit 1 to walk the first meeting by hand.")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would run; write nothing")
    ap.add_argument("--json", action="store_true",
                    help="print the result as JSON instead of prose")
    args = ap.parse_args(argv)

    from .store import PgCorpus
    corpus = PgCorpus(dsn=args.dsn)
    try:
        r = drain(corpus, limit=args.limit, dry_run=args.dry_run,
                  quiet=args.json)
        if args.json:
            print(json.dumps(r, indent=2, default=str))
        # A failure inside one submission is reported, not raised — but the job
        # exits non-zero so a scheduler notices, because a nightly run that
        # always exits 0 is a nightly run nobody ever reads.
        return 1 if r.get("failed") else 0
    finally:
        corpus.close()


if __name__ == "__main__":
    sys.exit(main())
