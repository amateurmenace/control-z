"""The corpus store: schema, upsert, cross-corpus search, three-tier dedupe.

Everything here runs against a throwaway SQLite file — no media root, no
network. The store is the record; these tests are its guardrails.
"""

import tempfile
import unittest
from pathlib import Path

from memory import ingest
from memory.store import Corpus

SELECT = [
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
SCHOOL = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The School Committee returns to the rezoning and enrollment."},
    {"start": 6.0, "end": 13.0, "speaker": "Speaker 2",
     "text": "The override will decide whether the classrooms are funded."},
]


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-store-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))

    def tearDown(self):
        self.td.cleanup()

    def add(self, mid, segs, **meta):
        self.c.upsert_meeting({"id": mid, "status": "live",
                               "n_segments": len(segs), **meta})
        self.c.replace_segments(mid, segs)

    def test_upsert_merges_never_shrinks(self):
        self.c.upsert_meeting({"id": "m1", "title": "Select Board", "town": "Brookline"})
        self.c.upsert_meeting({"id": "m1", "body": "Select Board"})  # add, don't blank
        m = self.c.get_meeting("m1")
        self.assertEqual(m["title"], "Select Board")
        self.assertEqual(m["town"], "Brookline")
        self.assertEqual(m["body"], "Select Board")

    def test_segments_roundtrip(self):
        self.add("m1", SELECT, title="Select")
        segs = self.c.transcript("m1")
        self.assertEqual(len(segs), 5)
        self.assertEqual(segs[1]["text"], "First is the Harvard Street rezoning article.")
        self.assertEqual(segs[0]["speaker"], "Speaker 1")

    def test_keyword_search_is_cross_corpus_and_timecoded(self):
        self.add("sel", SELECT, title="Select Board", date="2026-05-19")
        self.add("sch", SCHOOL, title="School Committee", date="2026-06-02")
        hits = self.c.search("rezoning")
        mids = {h["meeting_id"] for h in hits}
        self.assertEqual(mids, {"sel", "sch"})            # both meetings surface
        top = hits[0]
        self.assertIn("rezoning", top["text"].lower())
        self.assertIsInstance(top["t"], float)            # a second to jump to
        self.assertIn(top["why"], ("word", "both"))

    def test_semantic_finds_related_language(self):
        self.add("sel", SELECT, title="Select Board")
        # "housing overlay" never appears verbatim; the overlay motion should rank
        hits = self.c.search("housing overlay proposal")
        self.assertTrue(hits)
        self.assertTrue(any("overlay" in h["text"].lower() for h in hits))

    def test_dedupe_url_canon(self):
        self.add("yt", SELECT, url_canon="youtube:ABC123")
        self.assertIsNotNone(self.c.find_by_url_canon("youtube:ABC123"))
        self.assertIsNone(self.c.find_by_url_canon("youtube:NOPE"))

    def test_dedupe_hash(self):
        self.add("f", SELECT, source_hash="deadbeef")
        self.assertEqual(self.c.find_by_hash("deadbeef")["id"], "f")

    def test_dedupe_shingles(self):
        sh = ingest._shingles(SELECT)
        self.add("orig", SELECT, shingles=sh)
        # the same meeting posted again (near-identical words) links to the original
        near = SELECT + [{"start": 40.0, "end": 42.0, "text": "Meeting adjourned."}]
        self.assertEqual(self.c.find_by_shingles(ingest._shingles(near))["id"], "orig")
        # an unrelated meeting does not
        self.assertIsNone(self.c.find_by_shingles(ingest._shingles(SCHOOL)))

    def test_stats(self):
        self.add("sel", SELECT, title="Select", town="Brookline", body="Select Board",
                 duration=34.0)
        self.add("sch", SCHOOL, title="School", town="Brookline", body="School Committee",
                 duration=13.0)
        s = self.c.stats()
        self.assertEqual(s["live"], 2)
        self.assertEqual(s["segments"], 7)
        self.assertEqual(s["towns"], 1)
        self.assertEqual(s["bodies"], 2)
        self.assertTrue(s["fts"])

    def test_forget(self):
        self.add("sel", SELECT)
        self.assertTrue(self.c.forget("sel"))
        self.assertIsNone(self.c.get_meeting("sel"))
        self.assertEqual(self.c.transcript("sel"), [])
        self.assertEqual(self.c.search("rezoning"), [])
        self.assertFalse(self.c.forget("sel"))  # already gone

    def test_empty_search(self):
        self.assertEqual(self.c.search(""), [])


if __name__ == "__main__":
    unittest.main()
