"""The pipeline: input classification, dedupe, and a full reuse-path ingest.

No network, no ASR: the media root is redirected with a monkeypatch (never
set_media_root — that persists to real user config), and the transcript is
seeded as a scribe sidecar so the pipeline takes its reuse door. That exercises
resolve → analyze → embed → store end to end through a real JobManager job.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from czcore.appshell.jobs import JobManager
from memory import ingest, store
from memory.store import Corpus

SEGS = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": "Speaker 2",
     "text": "I move to adopt the MBTA Communities zoning overlay as written."},
    {"start": 20.0, "end": 28.0, "speaker": "Speaker 3",
     "text": "The projected cost is four hundred thousand dollars."},
    {"start": 28.0, "end": 34.0, "speaker": "Speaker 1",
     "text": "All in favor? The motion passes five to zero."},
]


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-ing-")
        root = Path(self.td.name)

        def md(tool):
            d = root / tool
            d.mkdir(parents=True, exist_ok=True)
            return d

        for module in (ingest, store):
            p = mock.patch.object(module, "media_dir", md)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.td.cleanup)
        self.c = Corpus()

    # -- classification ---------------------------------------------------

    def test_resolve_youtube(self):
        plan = ingest.resolve_input(
            {"url": "https://www.youtube.com/watch?v=MIXnmQnw0gU"})
        self.assertEqual(plan["kind"], "youtube")
        self.assertEqual(plan["video_id"], "MIXnmQnw0gU")
        self.assertEqual(plan["id"], "MIXnmQnw0gU")
        self.assertEqual(plan["url_canon"], "youtube:MIXnmQnw0gU")

    def test_resolve_generic_url_strips_tracking(self):
        plan = ingest.resolve_input(
            {"url": "https://portal.example/meeting/42?utm_source=news&si=abc"})
        self.assertEqual(plan["kind"], "url")
        self.assertTrue(plan["id"].startswith("url:"))
        self.assertNotIn("utm_", plan["url_canon"])

    def test_resolve_file(self):
        f = Path(self.td.name) / "meeting.mp4"
        f.write_bytes(b"a real file standing in for a video" * 100)
        plan = ingest.resolve_input({"path": str(f)})
        self.assertEqual(plan["kind"], "file")
        self.assertTrue(plan["source_hash"])
        self.assertTrue(plan["id"].startswith("file:"))

    def test_file_hash_stable(self):
        f = Path(self.td.name) / "x.bin"
        f.write_bytes(b"abc" * 2000)
        self.assertEqual(ingest.file_hash(f), ingest.file_hash(f))
        self.assertEqual(ingest.file_hash(Path("/no/such/file")), "")

    def test_shingles_similar_vs_different(self):
        a = set(ingest._shingles(SEGS).split())
        near = set(ingest._shingles(
            SEGS + [{"start": 40.0, "end": 42.0, "text": "Meeting adjourned."}]).split())
        diff = set(ingest._shingles(
            [{"start": 0.0, "end": 3.0,
              "text": "completely unrelated coffee weather parking flooded"}]).split())
        self.assertTrue(a & near)      # near-identical share shingles
        self.assertFalse(a & diff)     # unrelated do not

    # -- the pipeline (reuse door — no ASR, no network) -------------------

    def _seed_sidecar(self, plan, segs, title):
        wd = ingest.meetings_dir() / ingest._safe(plan["id"])
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "meeting.scribe.json").write_text(json.dumps(
            {"version": 1, "model": "scribe", "duration": segs[-1]["end"],
             "segments": segs}))
        (wd / "meeting.info.json").write_text(json.dumps({"title": title}))

    def _run(self, plan):
        jm = JobManager()
        job = jm.start("t", lambda j: ingest.run(self.c, plan, j))
        for _ in range(3000):
            if job.status in ("done", "error", "cancelled"):
                break
            time.sleep(0.01)
        return job

    def test_pipeline_reuse_lands_a_live_meeting(self):
        plan = ingest.resolve_input(
            {"path": "/civic/brookline-select.mp4", "town": "Brookline",
             "body": "Select Board"})
        self._seed_sidecar(plan, SEGS, "Brookline Select Board — May 19")
        job = self._run(plan)
        self.assertEqual(job.status, "done", job.error)
        self.assertEqual(job.result["status"], "live")
        m = self.c.get_meeting(plan["id"])
        self.assertEqual(m["status"], "live")
        self.assertEqual(m["origin"], "scribe")
        self.assertEqual(m["n_segments"], len(SEGS))
        self.assertEqual(m["town"], "Brookline")
        self.assertEqual(m["body"], "Select Board")
        self.assertTrue(m["analysis"]["brief"])          # the reading landed
        self.assertTrue(self.c.search("rezoning"))        # searchable

    def test_resubmit_is_exists(self):
        plan = ingest.resolve_input({"path": "/civic/brookline-select.mp4"})
        self._seed_sidecar(plan, SEGS, "Brookline")
        self._run(plan)
        dup = ingest.submit_dedupe(
            self.c, ingest.resolve_input({"path": "/civic/brookline-select.mp4"}))
        self.assertIsNotNone(dup)
        self.assertEqual(dup["id"], plan["id"])

    def test_shingle_dedupe_links_second_source(self):
        p1 = ingest.resolve_input(
            {"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA"})
        self._seed_sidecar(p1, SEGS, "A")
        self._run(p1)
        p2 = ingest.resolve_input(
            {"url": "https://www.youtube.com/watch?v=BBBBBBBBBBB"})
        self._seed_sidecar(p2, SEGS, "B")  # same words, different id
        job = self._run(p2)
        self.assertEqual(job.result["status"], "exists")
        self.assertTrue(job.result.get("linked"))
        self.assertEqual(self.c.stats()["live"], 1)       # not duplicated

    def test_captions_parse_to_store(self):
        from highlighter.highlights import parse_vtt
        vtt = ("WEBVTT\n\n00:00:00.000 --> 00:00:03.000\n"
               "The rezoning article is next.\n\n"
               "00:00:03.000 --> 00:00:06.000\nThe motion carries.\n")
        segs = parse_vtt(vtt)
        self.assertTrue(segs)
        self.c.upsert_meeting({"id": "cap", "status": "live", "origin": "captions",
                               "n_segments": len(segs)})
        self.c.replace_segments("cap", segs)
        self.assertTrue(self.c.search("rezoning"))


if __name__ == "__main__":
    unittest.main()
