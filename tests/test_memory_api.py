"""The HTTP surface: the routes lane A builds UI against, and the page's own.

Network-free by construction — every test either seeds the corpus directly or
hits a dedupe/validation path, so no route reaches out to YouTube or Scribe.
The submissions and context endpoints are the stable contract in PARALLEL; the
rest serve the page.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from czcore.appshell.jobs import JobManager
from memory import ingest, store
from memory.store import Corpus

SEGS = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The Select Board takes up the Harvard Street rezoning."},
    {"start": 6.0, "end": 13.0, "speaker": "Speaker 2",
     "text": "The overlay motion passes five to zero."},
]


class ApiTest(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from suite.tools import memory as memtool

        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-api-")
        root = Path(self.td.name)

        def md(tool):
            d = root / tool
            d.mkdir(parents=True, exist_ok=True)
            return d

        for module in (store, ingest):
            p = mock.patch.object(module, "media_dir", md)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.td.cleanup)

        app = FastAPI()
        memtool.register_memory(app, JobManager(), None)
        self.cl = TestClient(app)
        self.seed = Corpus()  # same (patched) path as the route's own Corpus

    def _seed(self, mid, segs, **meta):
        self.seed.upsert_meeting(
            {"id": mid, "status": "live", "n_segments": len(segs), **meta})
        self.seed.replace_segments(mid, segs)

    def test_submissions_requires_a_source(self):
        r = self.cl.post("/api/memory/submissions", json={})
        self.assertEqual(r.status_code, 422)

    def test_submissions_dedupes_to_exists(self):
        self._seed("MIXnmQnw0gU", SEGS, url_canon="youtube:MIXnmQnw0gU",
                   title="Brookline Select Board")
        r = self.cl.post("/api/memory/submissions",
                         json={"url": "https://www.youtube.com/watch?v=MIXnmQnw0gU"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"meeting_id": "MIXnmQnw0gU", "status": "exists"})

    def test_corpus_and_stats(self):
        self._seed("m1", SEGS, title="Select Board", town="Brookline",
                   body="Select Board", duration=13.0)
        d = self.cl.get("/api/memory/corpus").json()
        self.assertEqual(len(d["meetings"]), 1)
        self.assertEqual(d["stats"]["live"], 1)
        self.assertEqual(d["stats"]["segments"], 2)

    def test_search_returns_timecoded_hits(self):
        self._seed("m1", SEGS, title="Select Board")
        d = self.cl.get("/api/memory/search", params={"q": "rezoning"}).json()
        self.assertTrue(d["hits"])
        h = d["hits"][0]
        self.assertEqual(h["meeting_id"], "m1")
        self.assertIn("t", h)
        self.assertIn("rezoning", h["text"].lower())

    def test_meeting_detail_and_404(self):
        self._seed("m1", SEGS, title="Select Board")
        ok = self.cl.post("/api/memory/meeting", json={"id": "m1"})
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertEqual(body["meeting"]["title"], "Select Board")
        self.assertEqual(len(body["transcript"]["segments"]), 2)
        self.assertIn("moments", body)
        miss = self.cl.post("/api/memory/meeting", json={"id": "nope"})
        self.assertEqual(miss.status_code, 404)

    def test_context_shape_is_stable(self):
        self._seed("m1", SEGS, title="Select Board", date="2026-05-19")
        r = self.cl.post("/api/memory/context",
                         json={"texts": ["what is happening with the rezoning?"]})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["issues"], [])                 # issue engine deferred
        self.assertIn("prior", d)
        self.assertIn("stats", d)
        if d["prior"]:
            self.assertIn("ts", d["prior"][0])
            self.assertIn("meeting_id", d["prior"][0])

    def test_forget(self):
        self._seed("m1", SEGS, title="Select Board")
        r = self.cl.post("/api/memory/forget", json={"id": "m1"})
        self.assertTrue(r.json()["removed"])
        self.assertEqual(self.cl.get("/api/memory/corpus").json()["meetings"], [])

    def test_context_tolerates_non_list_texts(self):
        # a scalar `texts` must not 500 (list(5) would raise) — clean 200
        for bad in (5, True, {"a": 1}):
            r = self.cl.post("/api/memory/context", json={"texts": bad})
            self.assertEqual(r.status_code, 200, bad)
            self.assertEqual(r.json()["issues"], [])
        # a bare string is still accepted as one query
        self.assertEqual(
            self.cl.post("/api/memory/context", json={"texts": "rezoning"}).status_code,
            200)

    def test_search_clamps_negative_limit(self):
        self._seed("m1", SEGS, title="Select Board")
        r = self.cl.get("/api/memory/search", params={"q": "rezoning", "limit": -1})
        self.assertEqual(r.status_code, 200)               # no crash
        hits = r.json()["hits"]
        self.assertTrue(any(h["meeting_id"] == "m1" for h in hits))  # not dropped


if __name__ == "__main__":
    unittest.main()
