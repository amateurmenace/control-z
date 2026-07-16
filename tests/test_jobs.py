"""Job store: legacy immediate mode unchanged; queued mode persists, cancels."""

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from czcore.appshell.jobs import JobCancelled, JobManager


def wait_for(pred, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return False


class TestImmediateMode(unittest.TestCase):
    """The per-tool micro-UIs (pivot.app) rely on exactly this behavior."""

    def test_runs_and_finishes(self):
        jm = JobManager()
        job = jm.start("t", lambda j: {"x": 1})
        self.assertTrue(wait_for(lambda: job.status == "done"))
        self.assertEqual(job.result, {"x": 1})
        self.assertEqual(job.progress, 1.0)
        self.assertIs(jm.get(job.id), job)

    def test_error_surfaced(self):
        jm = JobManager()
        def boom(j):
            raise ValueError("nope")
        job = jm.start("t", boom)
        self.assertTrue(wait_for(lambda: job.status == "error"))
        self.assertIn("ValueError: nope", job.error)

    def test_to_dict_shape(self):
        jm = JobManager()
        job = jm.start("t", lambda j: None)
        wait_for(lambda: job.status == "done")
        d = job.to_dict()
        for key in ("id", "kind", "status", "progress", "message", "result",
                    "error", "tool", "label", "created_at"):
            self.assertIn(key, d)


class TestQueuedMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "jobs.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fifo_one_at_a_time(self):
        jm = JobManager(db_path=self.db, queued=True)
        order = []
        gate = {"first_running": False}

        def slow(j):
            gate["first_running"] = True
            time.sleep(0.15)
            order.append("a")

        def quick(j):
            order.append("b")

        ja = jm.start("t", slow)
        jb = jm.start("t", quick)
        self.assertTrue(wait_for(lambda: gate["first_running"]))
        self.assertEqual(jb.status, "queued")  # strictly one at a time
        self.assertTrue(wait_for(lambda: jb.status == "done"))
        self.assertEqual(order, ["a", "b"])
        self.assertEqual(ja.status, "done")

    def test_persists_history(self):
        jm = JobManager(db_path=self.db, queued=True)
        job = jm.start("render", lambda j: {"out": "/x.mov"},
                       tool="pivot", label="x.mov → 9:16")
        self.assertTrue(wait_for(lambda: job.status == "done"))
        rows = JobManager(db_path=self.db, queued=False).list()
        self.assertEqual(rows[0]["id"], job.id)
        self.assertEqual(rows[0]["status"], "done")
        self.assertEqual(rows[0]["tool"], "pivot")
        self.assertEqual(rows[0]["result"], {"out": "/x.mov"})

    def test_cancel_queued_never_runs(self):
        jm = JobManager(db_path=self.db, queued=True)
        ran = []
        block = {"go": False}

        def blocker(j):
            wait_for(lambda: block["go"], timeout=5)

        def never(j):
            ran.append(1)

        jm.start("t", blocker)
        victim = jm.start("t", never)
        self.assertTrue(jm.cancel(victim.id))
        block["go"] = True
        self.assertTrue(wait_for(lambda: jm.active_count() == 0))
        self.assertEqual(victim.status, "cancelled")
        self.assertEqual(ran, [])

    def test_cancel_running_cooperative(self):
        jm = JobManager(db_path=self.db, queued=True)
        started = {"yes": False}

        def loops(j):
            started["yes"] = True
            for _ in range(1000):
                j.check_cancel()
                time.sleep(0.01)

        job = jm.start("t", loops)
        self.assertTrue(wait_for(lambda: started["yes"]))
        jm.cancel(job.id)
        self.assertTrue(wait_for(lambda: job.status == "cancelled"))
        self.assertIsNone(job.error)  # cancel is not an error

    def test_interrupted_marked_on_restart(self):
        con = sqlite3.connect(self.db)
        con.executescript(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL, "
            "tool TEXT NOT NULL DEFAULT '', label TEXT NOT NULL DEFAULT '', "
            "status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0, "
            "message TEXT NOT NULL DEFAULT '', result TEXT, error TEXT, "
            "created_at REAL NOT NULL, started_at REAL, finished_at REAL);")
        con.execute("INSERT INTO jobs (id, kind, status, created_at) "
                    "VALUES ('dead1', 'render', 'running', 1.0)")
        con.commit()
        con.close()
        jm = JobManager(db_path=self.db, queued=True)
        row = [r for r in jm.list() if r["id"] == "dead1"][0]
        self.assertEqual(row["status"], "error")
        self.assertIn("interrupted", row["error"])

    def test_listeners_fire(self):
        jm = JobManager(db_path=self.db, queued=True)
        seen = []
        jm.on_update(lambda d: seen.append(d["status"]))
        job = jm.start("t", lambda j: None)
        self.assertTrue(wait_for(lambda: job.status == "done"))
        self.assertIn("queued", seen)
        self.assertIn("done", seen)

    def test_fn_raising_cancelled_is_cancelled(self):
        jm = JobManager(db_path=self.db, queued=True)

        def stops(j):
            raise JobCancelled()

        job = jm.start("t", stops)
        self.assertTrue(wait_for(lambda: job.status == "cancelled"))


if __name__ == "__main__":
    unittest.main()
