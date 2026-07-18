"""corpus.db → the Studio, and the proof that nothing was re-derived.

specs/17 §11.3: the Brookline corpus was hand-audited, so the import carries it
rather than recomputing it. What that means concretely is testable — the
vectors survive bit-for-bit, the issue links keep the scores and the reasons
they were given, and the two stores agree on every rollup afterwards.

The fixture is a small corpus built the way the desk builds one, plus the two
awkward cases the real record actually contains: a segment whose text is pure
filler (a 1024-byte blob of zeros that must become NULL, because cosine
distance against a zero vector is undefined under pgvector), and an issue whose
name is a caption garble, which comes across unchanged because fixing it here
would make the import the Studio's first unaudited edit.

Skips loudly without STUDIO_TEST_PG_DSN — a skip is a gate that lost its
inputs, not routine.
"""

import os
import tempfile
import unittest
from pathlib import Path

from memory import embed
from memory.store import Corpus

PG_DSN = os.environ.get("STUDIO_TEST_PG_DSN", "").strip()

SELECT = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": "Speaker 2",
     "text": "I move to adopt the MBTA Communities zoning overlay as written."},
    # the awkward one: every token is filler, so the vector is all zeros
    {"start": 20.0, "end": 22.0, "speaker": None, "text": "as to"},
]
SCHOOL = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The School Committee returns to the rezoning and enrollment."},
    {"start": 6.0, "end": 13.0, "speaker": "Speaker 2",
     "text": "The override will decide whether the classrooms are funded."},
]


def build_desk_corpus(path: str) -> Corpus:
    """A desk corpus shaped like the real one: two meetings of one town, an
    issue linked across both, a followed thread, a roll call, and a document."""
    c = Corpus(db_path=path)
    c.upsert_meeting({"id": "sel", "town": "Brookline", "body": "Select Board",
                      "title": "Select Board", "date": "2026-05-12",
                      "status": "live", "duration": 34.0, "origin": "captions",
                      "url": "https://www.youtube.com/watch?v=MIXnmQnw0gU",
                      "url_canon": "youtube:MIXnmQnw0gU", "video_id": "MIXnmQnw0gU",
                      "shingles": "aa bb cc dd ee"})
    c.replace_segments("sel", SELECT)
    c.upsert_meeting({"id": "sch", "town": "Brookline", "body": "School Committee",
                      "title": "School Committee", "date": "2026-05-19",
                      "status": "live", "duration": 13.0, "origin": "captions"})
    c.replace_segments("sch", SCHOOL)

    segs = c.segments_of("sel") + c.segments_of("sch")
    # a name that reads as a caption garble — carried across as-is, on purpose
    c.upsert_issue({"id": "issue:brookline:city-realy", "town": "Brookline",
                    "name": "City Realy", "status": "active", "origin": "auto",
                    "name_origin": "extractive", "aliases": ["city realy"],
                    "keywords": ["city realy"]})
    c.upsert_issue({"id": "issue:brookline:rezoning", "town": "Brookline",
                    "name": "Rezoning", "status": "active", "origin": "auto",
                    "name_origin": "extractive", "aliases": ["rezoning"],
                    "keywords": ["rezoning"]})
    c.link_segments("issue:brookline:rezoning",
                    [(segs[1]["id"], "sel", 1.0, "alias"),
                     (segs[4]["id"], "sch", 1.0, "alias")])
    c.recompute_centroid("issue:brookline:rezoning")
    c.follow("issue:brookline:rezoning")
    c.replace_votes("sel", [{"t": 30.0, "motion": "adopt the overlay",
                             "outcome": "passed", "tally": "5–0",
                             "roll": [{"name": "Chair", "vote": "yes",
                                       "t": 31.0, "quote": "aye"}]}])
    c.upsert_document({"id": "d1", "meeting_id": "sel", "town": "Brookline",
                       "kind": "Agenda", "title": "Agenda", "date": "2026-05-12",
                       "status": "live", "pages": 2})
    c.replace_doc_chunks("d1", [{"page": 1, "text": "Harvard Street rezoning."}])
    return c


@unittest.skipUnless(PG_DSN, "STUDIO_TEST_PG_DSN unset — the import is UNPROVEN "
                             "in this run")
class ImportTest(unittest.TestCase):
    def setUp(self):
        from studio.store import PgCorpus
        self.td = tempfile.TemporaryDirectory(prefix="cz-studio-import-")
        self.addCleanup(self.td.cleanup)
        self.src = str(Path(self.td.name) / "corpus.db")
        self.desk = build_desk_corpus(self.src)
        self.pg = PgCorpus(dsn=PG_DSN)
        self.addCleanup(self.pg.close)
        with self.pg._con() as con:
            con.execute(
                "TRUNCATE meetings, segments, issues, issue_segments, threads, "
                "events, documents, doc_chunks, issue_documents, votes, "
                "submissions, asr_tasks, audit, spend, towns RESTART IDENTITY CASCADE")

    def _import(self):
        from studio import import_desk
        return import_desk.import_corpus(self.src, self.pg, verbose=False)

    def test_import_is_lossless_and_verifies_itself(self):
        from studio import import_desk
        counts = self._import()
        self.assertEqual(counts["meetings"], 2)
        self.assertEqual(counts["segments"], 6)
        self.assertEqual(counts["issues"], 2)
        self.assertEqual(counts["issue_segments"], 2)
        result = import_desk.verify(self.src, self.pg, sample=50, verbose=False)
        self.assertTrue(result["ok"], result["problems"])
        self.assertEqual(result["vectors"]["differing"], 0)
        self.assertEqual(result["vectors"]["wrongly_kept"], 0)

    def test_vectors_arrive_bit_for_bit(self):
        """The audited artifact. `memory/embed.py` writes 256 float32 in raw C
        order with no header — the import reinterprets, it does not recompute."""
        self._import()
        for want in self.desk.segments_of("sel"):
            with self.pg._con() as con:
                got = con.execute("SELECT emb FROM segments WHERE id=%s",
                                  (want["id"],)).fetchone()
            here = embed.as_vec(got["emb"])
            there = embed.as_vec(want["emb"])
            if there is None or float(there @ there) == 0:
                self.assertIsNone(here)          # filler carries no direction
            else:
                self.assertEqual(embed.to_bytes(here), embed.to_bytes(there))

    def test_the_filler_segment_becomes_null_not_zeros(self):
        self._import()
        with self.pg._con() as con:
            row = con.execute(
                "SELECT emb IS NULL AS blank FROM segments "
                "WHERE text='as to'").fetchone()
        self.assertTrue(row["blank"])

    def test_issue_links_keep_their_score_and_their_reason(self):
        """392 links in the real corpus, every one `score=1.0, why='alias'` —
        a record of *how* each was decided. Re-deriving would erase that."""
        self._import()
        nodes = self.pg.issue_appearances("issue:brookline:rezoning")
        beads = [b for n in nodes for b in n["beads"]]
        self.assertEqual(len(beads), 2)
        self.assertTrue(all(b["score"] == 1.0 for b in beads))
        self.assertTrue(all(b["why"] == "alias" for b in beads))

    def test_a_garbled_issue_name_comes_across_unchanged(self):
        """`City Realy` is a caption garble that became a permanent issue id.
        It is wrong, and it is the record; the steward console's rename verb is
        the tool for it. Fixing it here would be the first unaudited edit."""
        self._import()
        self.assertEqual(
            self.pg.get_issue("issue:brookline:city-realy")["name"], "City Realy")

    def test_rollups_agree_between_the_two_stores(self):
        self._import()
        a = {i["id"]: (i["n_meetings"], i["n_segments"], i["following"])
             for i in self.desk.list_issues(town="Brookline")}
        b = {i["id"]: (i["n_meetings"], i["n_segments"], i["following"])
             for i in self.pg.list_issues(town="Brookline")}
        self.assertEqual(a, b)

    def test_the_thread_and_the_roll_call_survive(self):
        self._import()
        self.assertIsNotNone(self.pg.get_thread("issue:brookline:rezoning"))
        v = self.pg.votes_of("sel")
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["tally"], "5–0")
        self.assertEqual(v[0]["roll"][0]["name"], "Chair")

    def test_town_is_denormalised_onto_segments(self):
        """The column a hosted multi-town search cannot do without — the desk
        reaches it by JOIN and never needed it stored."""
        self._import()
        with self.pg._con() as con:
            rows = con.execute(
                "SELECT DISTINCT town FROM segments").fetchall()
        self.assertEqual([r["town"] for r in rows], ["Brookline"])

    def test_the_town_becomes_a_row(self):
        self._import()
        with self.pg._con() as con:
            row = con.execute("SELECT * FROM towns WHERE slug='Brookline'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "live")

    def test_importing_twice_does_not_duplicate(self):
        """A re-run after a partial failure has to be safe, or nobody will dare
        run it against the real thing."""
        self._import()
        self._import()
        self.assertEqual(self.pg.stats()["segments"], 6)
        self.assertEqual(len(self.pg.list_issues(town="Brookline")), 2)
        nodes = self.pg.issue_appearances("issue:brookline:rezoning")
        self.assertEqual(sum(n["n"] for n in nodes), 2)

    def test_search_works_on_the_imported_record(self):
        self._import()
        hits = self.pg.search("rezoning", town="Brookline")
        self.assertTrue(hits)
        self.assertEqual({h["meeting_id"] for h in hits}, {"sel", "sch"})
        self.assertEqual(hits[0]["title"], "Select Board")

    def test_the_source_corpus_is_opened_read_only(self):
        """The source is somebody's actual record. Opening it read-write would
        let SQLite create a journal beside a file the desk may also have open."""
        from studio import import_desk
        con = import_desk._open_source(self.src)
        self.addCleanup(con.close)
        import sqlite3
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("CREATE TABLE nope (x INTEGER)")


if __name__ == "__main__":
    unittest.main()
