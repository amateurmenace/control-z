"""The stage that turns a steward's yes into a meeting.

Until this module existed, `submissions.status='approved'` was a terminal state
dressed as a queue: the console wrote it, the schema declared `queued` and
`live` after it, and nothing anywhere selected it. So the cases that matter
most here are not the happy path — they are the four promises the pipeline
makes about rows it must *not* touch and states it must not skip.

**Nothing ingests without a human.** The drain reads `approved` and nothing
else. A `submitted` row is a submission nobody has looked at; a `rejected` row
is a steward's no. Both are invisible to this job, and that is the covenant's
"a human is in the middle" enforced by a WHERE clause rather than by a habit.

**A meeting with no captions is not a failure.** It parks in `asr_tasks` for
the desk drain and the submission says what it is waiting for. The ticket is
idempotent on the meeting, because a nightly re-run must not file the same work
twice.

**The link is written.** `submissions.meeting_id` has been in the schema since
the first migration and nothing had ever written it, which meant a steward
could see that a submission was approved and not get from there to the meeting.

The network is never touched: `memory.ingest.run` is replaced with a stand-in
in every case here, because what is under test is the queue's state machine,
not YouTube's caption service. The ingest engine itself is proven against both
stores by `tests/test_record_store_parity.py`.

Skips loudly without RECORD_TEST_PG_DSN.
"""

import os
import time
import unittest
from unittest import mock

PG_DSN = os.environ.get("RECORD_TEST_PG_DSN", "").strip()

CAPTIONS = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
]


@unittest.skipUnless(PG_DSN, "RECORD_TEST_PG_DSN unset — the hosted ingest "
                             "pipeline is UNPROVEN in this run")
class PipelineTest(unittest.TestCase):
    def setUp(self):
        from record.store import PgCorpus

        self.c = PgCorpus(dsn=PG_DSN)
        self.addCleanup(self.c.close)
        with self.c._con() as con:
            con.execute(
                "TRUNCATE meetings, segments, issues, issue_segments, threads, "
                "events, documents, doc_chunks, issue_documents, votes, "
                "submissions, asr_tasks, audit, spend, towns "
                "RESTART IDENTITY CASCADE")

    # -- fixtures ----------------------------------------------------------

    def submit(self, sub_id="sub:1", status="approved",
               url="https://www.youtube.com/watch?v=aaaaaaaaaaa",
               town="Brookline", body="Select Board", added_at=None):
        now = time.time()
        with self.c._con() as con:
            con.execute(
                "INSERT INTO submissions (id, url, url_canon, town, body, date, "
                "note, status, added_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,'','',%s,%s,%s)",
                (sub_id, url, "", town, body, status,
                 added_at if added_at is not None else now, now))
        return sub_id

    def row(self, sub_id):
        with self.c._con() as con:
            return dict(con.execute("SELECT * FROM submissions WHERE id=%s",
                                    (sub_id,)).fetchone())

    def fake_ingest(self, result):
        """Stand in for `memory.ingest.run`, which would reach the network.

        Also writes the meeting the real one would have written, so the
        submission's `meeting_id` points at something that exists."""
        def _run(corpus, plan, job, workdir=None):
            job.message = "finding a transcript…"
            if result.get("status") == "live":
                corpus.upsert_meeting({
                    "id": plan["id"], "status": "live", "town": plan["town"],
                    "body": plan["body"], "title": "Select Board",
                    "date": "2026-07-14", "n_segments": len(CAPTIONS)})
                corpus.replace_segments(plan["id"], CAPTIONS)
            return {"meeting_id": plan["id"], **result}
        return _run

    def drain(self, result=None, **kw):
        from record import pipeline
        run = self.fake_ingest(result or {"status": "live", "segments": 2,
                                          "origin": "captions"})
        with mock.patch("memory.ingest.run", run), \
             mock.patch.object(pipeline, "_embed", lambda *a, **k: {"embedded": 0}):
            return pipeline.drain(self.c, quiet=True, **kw)

    # -- nothing ingests without a human -----------------------------------

    def test_only_approved_rows_are_picked_up(self):
        """The covenant's human-in-the-middle, enforced by the SELECT rather
        than by everyone remembering."""
        from record import pipeline
        self.submit("sub:new", status="submitted")
        self.submit("sub:no", status="rejected")
        self.submit("sub:yes", status="approved")
        self.assertEqual([s["id"] for s in pipeline.approved_queue(self.c)],
                         ["sub:yes"])

    def test_a_submitted_row_is_untouched_by_a_drain(self):
        self.submit("sub:new", status="submitted")
        self.drain()
        self.assertEqual(self.row("sub:new")["status"], "submitted")

    def test_a_rejected_row_stays_rejected(self):
        """A steward's no is not reconsidered by a nightly job."""
        self.submit("sub:no", status="rejected")
        self.drain()
        self.assertEqual(self.row("sub:no")["status"], "rejected")

    # -- the queue is ordered ----------------------------------------------

    def test_the_oldest_approval_is_served_first(self):
        from record import pipeline
        self.submit("sub:late", added_at=2000.0)
        self.submit("sub:early", added_at=1000.0)
        self.assertEqual([s["id"] for s in pipeline.approved_queue(self.c)],
                         ["sub:early", "sub:late"])

    def test_limit_stops_the_drain(self):
        """`--limit 1` is how the first meeting gets walked by hand."""
        from record import pipeline
        self.submit("sub:a", added_at=1000.0)
        self.submit("sub:b", added_at=2000.0)
        self.assertEqual(len(pipeline.approved_queue(self.c, limit=1)), 1)

    # -- the state machine's back half -------------------------------------

    def test_a_landed_meeting_marks_the_submission_live_and_links_it(self):
        """`meeting_id` is the column the schema has always carried and nothing
        had ever written."""
        self.submit("sub:1")
        r = self.drain()
        row = self.row("sub:1")
        self.assertEqual(row["status"], "live")
        self.assertTrue(row["meeting_id"])
        self.assertEqual(r["landed"], 1)
        self.assertIsNotNone(self.c.get_meeting(row["meeting_id"]))

    def test_a_failure_is_reported_not_raised(self):
        """A drain that dies on its third row and leaves the first two
        unexplained is worse than one that reports three outcomes."""
        from record import pipeline

        def boom(corpus, plan, job, workdir=None):
            raise RuntimeError("the caption service refused")

        self.submit("sub:1")
        with mock.patch("memory.ingest.run", boom):
            r = pipeline.drain(self.c, quiet=True)
        self.assertEqual(r["failed"], 1)
        row = self.row("sub:1")
        self.assertEqual(row["status"], "failed")
        self.assertIn("refused", row["reason"])

    def test_a_dry_run_writes_nothing(self):
        self.submit("sub:1")
        r = self.drain(dry_run=True)
        self.assertEqual(r["would"], ["sub:1"])
        self.assertEqual(self.row("sub:1")["status"], "approved")

    # -- no captions is a state, not an error ------------------------------

    def test_a_meeting_without_captions_parks_for_the_drain(self):
        """No Scribe in this container, and no GPU bill either — the meeting
        lands honestly and waits for a desk to volunteer (specs/17 §6.4)."""
        self.submit("sub:1")
        r = self.drain({"status": "no_transcript", "note": "no published captions"})
        self.assertEqual(r["parked"], 1)
        self.assertEqual(r["failed"], 0)
        with self.c._con() as con:
            tasks = [dict(t) for t in
                     con.execute("SELECT * FROM asr_tasks").fetchall()]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "parked")
        self.assertEqual(tasks[0]["town"], "Brookline")
        self.assertIn("transcript", self.row("sub:1")["reason"])

    def test_parking_the_same_meeting_twice_files_one_ticket(self):
        """A nightly re-run must not queue a station the same work again."""
        from record import pipeline
        pipeline.park_asr_task(self.c, "vid1", "Brookline", "u", "n")
        pipeline.park_asr_task(self.c, "vid1", "Brookline", "u", "n")
        with self.c._con() as con:
            n = con.execute("SELECT count(*) AS n FROM asr_tasks").fetchone()["n"]
        self.assertEqual(n, 1)

    # -- dedupe ------------------------------------------------------------

    def test_a_meeting_already_on_the_record_is_linked_not_reingested(self):
        """The poller and a resident's paste can reach the same meeting."""
        self.c.upsert_meeting({"id": "aaaaaaaaaaa", "status": "live",
                               "town": "Brookline", "title": "Select Board",
                               "url_canon": "youtube:aaaaaaaaaaa"})
        self.submit("sub:1")
        r = self.drain()
        self.assertEqual(r["results"][0]["status"], "exists")
        self.assertEqual(self.row("sub:1")["meeting_id"], "aaaaaaaaaaa")

    # -- the job stand-in ---------------------------------------------------

    def test_the_job_standin_satisfies_what_ingest_asks_of_it(self):
        """`ingest.run` sets `progress`, sets `message`, and calls
        `check_cancel()` between stages. A job with no cancel button never
        raises — but the method has to be there, or the first real run dies
        between two stages that both worked."""
        from record.pipeline import JobLog
        j = JobLog(quiet=True)
        j.progress = -1
        j.message = "finding a transcript…"
        self.assertIsNone(j.check_cancel())
        self.assertEqual(j.message, "finding a transcript…")


class WorkdirSeamTest(unittest.TestCase):
    """The container has no `~/Movies`, and asking for one creates it.

    `memory/ingest` resolved its sidecar directory through `czcore.paths`,
    which is right at a desk and meaningless in a job — it would have written
    `/root/Videos/control-z/memory/.meetings` into the container's own memory
    limit. Needs no database.
    """

    def test_the_default_is_still_the_desk(self):
        from memory import ingest
        self.assertEqual(ingest.workdir_root(), ingest.meetings_dir())

    def test_a_caller_can_say_where_sidecars_go(self):
        import tempfile
        from memory import ingest
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(str(ingest.workdir_root(d)), d)

    def test_local_media_survives_having_no_indexer(self):
        """The record's image ships no tool directories, and specs/18 removes
        `indexer/` from this repo entirely. An ImportError here would surface
        on a job retry — the one moment the branch is reachable and the worst
        moment to find out."""
        import builtins
        import tempfile
        from pathlib import Path

        from memory import ingest
        real = builtins.__import__

        def no_indexer(name, *a, **k):
            if name.startswith("indexer"):
                raise ImportError("no indexer in this image")
            return real(name, *a, **k)

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(builtins, "__import__", no_indexer):
                self.assertEqual(
                    ingest._local_media(Path(d), {"kind": "youtube"}), "")


if __name__ == "__main__":
    unittest.main()
