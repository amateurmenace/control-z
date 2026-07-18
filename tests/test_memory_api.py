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
from memory import ingest, issues, store
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
        self.jm = JobManager()
        memtool.register_memory(app, self.jm, None)
        self.cl = TestClient(app)
        self.seed = Corpus()  # same (patched) path as the route's own Corpus

    def _seed(self, mid, segs, **meta):
        self.seed.upsert_meeting(
            {"id": mid, "status": "live", "n_segments": len(segs), **meta})
        self.seed.replace_segments(mid, segs)

    def _seed_issue(self, iid, name, aliases, town="Brookline"):
        self.seed.upsert_issue({
            "id": iid, "town": town, "status": "active", "origin": "auto",
            "name": name, "aliases": aliases,
            "keywords": [a.lower() for a in aliases]})
        issues.reassign_issue(self.seed, iid)   # link segments that say its words
        return iid

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

    # -- the issue engine's HTTP surface ----------------------------------

    def test_issues_list_and_detail_with_timeline(self):
        self._seed("m1", SEGS, title="Select Board", date="2026-05-19",
                   body="Select Board", town="Brookline")
        iid = self._seed_issue("iss:rez", "Harvard Street Rezoning",
                               ["harvard street rezoning", "rezoning"])
        lst = self.cl.get("/api/memory/issues", params={"town": "Brookline"}).json()
        self.assertTrue(any(i["id"] == iid for i in lst["issues"]))
        self.assertIn("Brookline", lst["towns"])
        d = self.cl.post("/api/memory/issue", json={"id": iid}).json()
        self.assertEqual(d["issue"]["name"], "Harvard Street Rezoning")
        self.assertTrue(d["timeline"])                      # a node per meeting
        self.assertEqual(d["timeline"][0]["meeting_id"], "m1")
        self.assertIn("t", d["timeline"][0]["beads"][0])    # a second to jump to
        self.assertIn("overview", d)
        miss = self.cl.post("/api/memory/issue", json={"id": "nope"})
        self.assertEqual(miss.status_code, 404)

    def test_context_fills_issues_with_tracked_topics(self):
        self._seed("m1", SEGS, title="Select Board", date="2026-05-19")
        self._seed_issue("iss:rez", "Harvard Street Rezoning",
                         ["harvard street rezoning", "rezoning"])
        r = self.cl.post("/api/memory/context",
                         json={"texts": ["what is the story on the rezoning?"]})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(any(i["id"] == "iss:rez" for i in d["issues"]))
        hit = next(i for i in d["issues"] if i["id"] == "iss:rez")
        self.assertIn("n_meetings", hit)
        self.assertIn("prior", d)                           # prior shape unchanged

    def test_thread_follow_list_and_unfollow(self):
        self._seed("m1", SEGS, title="Select Board")
        iid = self._seed_issue("iss:rez", "Rezoning", ["rezoning"])
        f = self.cl.post("/api/memory/thread", json={"issue_id": iid}).json()
        self.assertTrue(f["following"])
        ts = self.cl.get("/api/memory/threads").json()
        self.assertEqual(ts["threads"][0]["issue_id"], iid)
        un = self.cl.post("/api/memory/thread",
                          json={"issue_id": iid, "follow": False}).json()
        self.assertTrue(un["removed"])
        self.assertEqual(self.cl.get("/api/memory/threads").json()["threads"], [])

    def test_thread_mint_from_query(self):
        self._seed("m1", SEGS, title="Select Board")
        r = self.cl.post("/api/memory/thread/mint",
                         json={"q": "overlay motion", "town": "Brookline"}).json()
        self.assertIn("issue_id", r)
        # minting follows it, so it shows on the threads list
        self.assertTrue(self.cl.get("/api/memory/threads").json()["threads"])

    def test_steward_rename_and_merge(self):
        self._seed("m1", SEGS, title="Select Board")
        a = self._seed_issue("iss:a", "Rezoning", ["rezoning"])
        b = self._seed_issue("iss:b", "Overlay", ["overlay"])
        rn = self.cl.post("/api/memory/issue/rename",
                          json={"id": a, "name": "Harvard St Rezoning",
                                "aliases": ["rezoning", "harvard street"]}).json()
        self.assertEqual(rn["issue"]["name"], "Harvard St Rezoning")
        mg = self.cl.post("/api/memory/issue/merge",
                          json={"dst": a, "src": [b]}).json()
        self.assertIn("overlay", [x.lower() for x in mg["issue"]["aliases"]])
        self.assertEqual(self.seed.get_issue(b)["status"], "merged")

    def test_issue_forget(self):
        self._seed("m1", SEGS, title="Select Board")
        iid = self._seed_issue("iss:rez", "Rezoning", ["rezoning"])
        self.assertTrue(self.cl.post("/api/memory/issue/forget",
                                     json={"id": iid}).json()["removed"])
        self.assertIsNone(self.seed.get_issue(iid))

    def test_digest_and_notifications_shapes(self):
        self._seed("m1", SEGS, title="Select Board")
        iid = self._seed_issue("iss:rez", "Rezoning", ["rezoning"])
        self.cl.post("/api/memory/thread", json={"issue_id": iid})
        dg = self.cl.get("/api/memory/digest").json()
        self.assertIn("markdown", dg)
        self.assertEqual(dg["threads"], 1)
        nt = self.cl.get("/api/memory/notifications").json()
        self.assertIn("events", nt)
        self.assertIn("unseen", nt)

    # -- documents, votes, officials, publish (the new desk surfaces) ------

    def _seed_vote(self, mid):
        self.seed.replace_votes(mid, [{
            "t": 8.0, "motion": "to approve the overlay", "outcome": "passes",
            "tally": "2–0", "origin": "extractive",
            "roll": [{"name": "Chair A", "vote": "yes", "t": 8.0, "quote": "aye"},
                     {"name": "Member B", "vote": "yes", "t": 9.0, "quote": "aye"}]}])

    def test_issue_route_carries_paper_and_ledger(self):
        self._seed("m1", SEGS, title="Select Board", date="2026-05-19",
                   town="Brookline", body="Select Board")
        iid = self._seed_issue("iss:rez", "Rezoning", ["rezoning"])
        # a document linked to the issue
        self.seed.upsert_document({"id": "doc:1", "meeting_id": "m1",
                                   "town": "Brookline", "kind": "Agenda"})
        self.seed.replace_doc_chunks("doc:1", [
            {"page": 3, "text": "public hearing on the rezoning overlay"}])
        from memory import documents
        documents.assign_document(self.seed, "doc:1")
        self._seed_vote("m1")
        d = self.cl.post("/api/memory/issue", json={"id": iid}).json()
        self.assertIn("paper", d)
        self.assertIn("ledger", d)
        self.assertTrue(d["paper"])                       # the town's paper
        self.assertEqual(d["paper"][0]["cites"][0]["page"], 3)
        self.assertTrue(d["ledger"])                      # the roll call
        self.assertEqual(d["ledger"][0]["tally"], "2–0")

    def test_officials_route(self):
        self._seed("m1", SEGS, title="Select Board", town="Brookline",
                   body="Select Board", date="2026-05-19")
        self._seed_vote("m1")
        r = self.cl.get("/api/memory/officials").json()
        names = {o["name"] for o in r["officials"]}
        self.assertEqual(names, {"Chair A", "Member B"})

    def test_meeting_documents_route(self):
        self._seed("m1", SEGS, title="Select Board")
        self._seed_vote("m1")
        r = self.cl.post("/api/memory/meeting/documents", json={"id": "m1"}).json()
        self.assertEqual(len(r["votes"]), 1)
        self.assertIn("documents", r)

    def test_publish_starts_a_job_and_reports_a_diff(self):
        # mock the bake so NO real edition is pressed — the route targets the
        # repo's real site/docs/app, and the job runs on a background thread, so
        # we hold the mock in place until the job is terminal (a race here once
        # wiped the committed edition). We assert the diff shape the button reads.
        import time as _time

        from web import bake as webbake

        def fake_bake(corpus_db, out_dir, version, base):
            return {"meetings": 3, "issues": 5,
                    "manifest": {"corpus_hash": "deadbeef", "edition_date": "2026-06-18",
                                 "counts": {"meetings": 3, "issues": 5}},
                    "total_gz": 1000, "busts": 0}
        with mock.patch.object(webbake, "bake", fake_bake):
            r = self.cl.post("/api/memory/publish", json={})
            self.assertIn(r.status_code, (200, 422))
            if r.status_code != 200:
                self.assertIn("error", r.json())
                return
            jid = r.json()["job"]["id"]
            for _ in range(200):        # wait for the (mocked) job under the mock
                job = self.jm.get(jid)
                if job and job.status in ("done", "error", "cancelled"):
                    break
                _time.sleep(0.02)
        self.assertEqual(job.status, "done")
        res = job.result or {}
        self.assertEqual(res["meetings"], 3)
        self.assertEqual(res["corpus_hash"], "deadbeef")


if __name__ == "__main__":
    unittest.main()
