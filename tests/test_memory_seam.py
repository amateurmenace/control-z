"""The store seam — what the engine may assume, pinned.

These run against a throwaway SQLite file only; the Postgres half of the seam
is proven in tests/test_record_store_parity.py, which needs a server. What is
pinned here is the part that must hold before a second store is even worth
writing: that the desk's Corpus satisfies the interface, that the record's
judgement calls live in one place, and that an embedding can be read back
without knowing which store handed it over.
"""

import tempfile
import unittest
from pathlib import Path

from memory import embed, policy
from memory.seam import CorpusStore
from memory.store import Corpus

SELECT = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": None,
     "text": "I move to adopt the MBTA Communities zoning overlay as written."},
]


class SeamTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-seam-")
        self.addCleanup(self.td.cleanup)
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))

    def test_the_desk_store_satisfies_the_interface(self):
        """The acceptance test for the whole seam: Corpus is a CorpusStore
        without inheriting from one. If this fails, a method was renamed and
        publicrecord's store is about to diverge silently."""
        self.assertIsInstance(self.c, CorpusStore)

    def test_every_declared_method_exists_and_is_callable(self):
        """runtime_checkable Protocols check names, not signatures — so check
        the names exhaustively rather than trusting isinstance alone."""
        declared = [n for n in CorpusStore.__annotations__] + [
            n for n in vars(CorpusStore)
            if not n.startswith("_") and callable(getattr(CorpusStore, n, None))]
        missing = [n for n in declared if not hasattr(self.c, n)]
        self.assertEqual(missing, [])

    def test_unit_is_transparent_at_the_desk(self):
        """unit() exists for publicrecord's multi-call verbs. At the desk it must
        change nothing at all — one writer, WAL, already serialised."""
        with self.c.unit() as u:
            self.assertIs(u, self.c)
            self.c.upsert_meeting({"id": "m1", "title": "Select", "status": "live"})
        self.assertEqual(self.c.get_meeting("m1")["title"], "Select")

    def test_close_is_safe_and_the_store_still_reads(self):
        self.c.upsert_meeting({"id": "m1", "status": "live"})
        self.c.replace_segments("m1", SELECT)
        self.c.close()
        self.assertEqual(len(self.c.transcript("m1")), 3)   # reopens per call

    # -- the new methods that closed the engine's escapes ------------------

    def test_linked_seg_ids_reports_what_belongs_to_an_issue(self):
        self.c.upsert_meeting({"id": "m1", "town": "Brookline", "status": "live"})
        self.c.replace_segments("m1", SELECT)
        segs = self.c.segments_of("m1")
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning"})
        self.c.link_segments("i1", [(segs[1]["id"], "m1", 1.0, "alias")])
        self.assertEqual(self.c.linked_seg_ids("m1"), {segs[1]["id"]})
        self.assertEqual(self.c.linked_seg_ids("nope"), set())

    def test_unlink_meeting_detaches_only_that_pair(self):
        self.c.upsert_meeting({"id": "m1", "town": "Brookline", "status": "live"})
        self.c.upsert_meeting({"id": "m2", "town": "Brookline", "status": "live"})
        self.c.replace_segments("m1", SELECT)
        self.c.replace_segments("m2", SELECT)
        a, b = self.c.segments_of("m1")[0], self.c.segments_of("m2")[0]
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning"})
        self.c.link_segments("i1", [(a["id"], "m1", 1.0, "alias"),
                                    (b["id"], "m2", 1.0, "alias")])
        self.assertEqual(self.c.unlink_meeting("i1", "m1"), 1)
        self.assertEqual(self.c.linked_seg_ids("m1"), set())
        self.assertEqual(self.c.linked_seg_ids("m2"), {b["id"]})   # untouched

    # -- embeddings are opaque --------------------------------------------

    def test_as_vec_reads_every_shape_a_store_might_hand_back(self):
        """bytes at the desk, an array from pgvector, a plain list over JSON —
        all the same 256 numbers, and no caller should have to know which."""
        v = embed.embed("the harvard street rezoning article")
        self.assertEqual(len(embed.as_vec(embed.to_bytes(v))), embed.DIM)
        self.assertEqual(len(embed.as_vec(v)), embed.DIM)
        self.assertEqual(len(embed.as_vec(list(map(float, v)))), embed.DIM)
        for empty in (None, b"", []):
            self.assertIsNone(embed.as_vec(empty))

    def test_as_vec_round_trips_bit_for_bit(self):
        v = embed.embed("the override will decide whether classrooms are funded")
        back = embed.as_vec(embed.to_bytes(v))
        self.assertEqual(embed.to_bytes(back), embed.to_bytes(v))

    def test_filler_segments_carry_no_vector_and_stay_word_only(self):
        """A segment that is nothing but filler — "I think so, you know." — has
        every token dropped as a stopword, so its vector is all zeros. It is
        cosine-0 against every query, which makes it reachable by word and not
        by meaning. Under pgvector a zero vector is worse than useless (cosine
        distance against it is undefined), so both stores must agree it is
        simply absent from the vector half rather than present and zeroed.

        Note '[music]' is NOT such a segment — 'music' is a real token and
        embeds normally. The filler class is pure stopwords."""
        z = embed.embed("I think so, you know.")
        self.assertEqual(float((z * z).sum()), 0.0)               # no direction at all
        self.c.upsert_meeting({"id": "m1", "status": "live", "title": "S"})
        self.c.replace_segments(
            "m1", [{"start": 0.0, "end": 1.0, "text": "I think so, you know."}])
        self.assertEqual(self.c.semantic(embed.embed("think")), [])
        self.assertEqual(len(self.c.search("think")), 1)          # FTS still finds it

    def test_transcript_promises_none_not_empty_string(self):
        """A store with a NOT NULL DEFAULT '' column owes this conversion."""
        self.c.upsert_meeting({"id": "m1", "status": "live"})
        self.c.replace_segments("m1", SELECT)
        speakers = [s["speaker"] for s in self.c.transcript("m1")]
        self.assertEqual(speakers, ["Speaker 1", "Speaker 1", None])


class PolicyTest(unittest.TestCase):
    """The judgement calls, tested without a database — which is the point of
    having lifted them out of one."""

    def test_rank_scores_are_order_derived_not_relevance_derived(self):
        """SQLite's bm25 is negative and sorted ascending, Postgres's
        ts_rank_cd is positive and sorted descending. Neither number survives
        the trip; the ordering does, so the scores are made from the ordering."""
        scored = policy.rank_scores(["a", "b", "c", "d"])
        self.assertEqual([r for r, _ in scored], ["a", "b", "c", "d"])
        self.assertEqual(scored[0][1], 1.0)
        self.assertTrue(all(scored[i][1] > scored[i + 1][1] for i in range(3)))
        self.assertGreaterEqual(scored[-1][1], 0.5)   # the band never crosses

    def test_blend_keeps_provenance_and_prefers_the_word(self):
        kw = [{"seg_id": 1, "score": 1.0}, {"seg_id": 2, "score": 0.75}]
        vec = [({"seg_id": 1, "score": 1.0}, 0.4), ({"seg_id": 9}, 0.9)]
        out = policy.blend(kw, vec, limit=10)
        why = {h["seg_id"]: h["why"] for h in out}
        self.assertEqual(why, {1: "both", 2: "word", 9: "related"})
        self.assertEqual(out[0]["seg_id"], 1)          # 1.0 beats the 0.9 vector
        self.assertEqual([h["seg_id"] for h in out], [1, 9, 2])

    def test_blend_respects_the_limit(self):
        kw = [{"seg_id": i, "score": 1.0 - i / 100} for i in range(50)]
        self.assertEqual(len(policy.blend(kw, [], limit=10)), 10)

    def test_jaccard_hit_at_the_threshold_boundary(self):
        """The desk suite never tested near 0.9 — it tested 'same' and
        'unrelated'. The boundary is where two stores would diverge."""
        base = {f"s{i}" for i in range(100)}

        def overlapping(shared):
            return ({f"s{i}" for i in range(shared)} |
                    {f"x{j}" for j in range(100 - shared)})

        self.assertTrue(policy.jaccard_hit(base, set(base)))            # 1.00000
        self.assertAlmostEqual(policy.jaccard(base, overlapping(95)),
                               95 / 105, places=5)
        self.assertTrue(policy.jaccard_hit(base, overlapping(95)))      # 0.90476 — in
        self.assertFalse(policy.jaccard_hit(base, overlapping(92)))     # 0.85185 — out
        self.assertFalse(policy.jaccard_hit(base, set()))               # empty never matches

    def test_merge_plan_never_shrinks(self):
        fresh, cols = policy.merge_plan({"id": "m1", "title": "Select"}, now=123.0)
        self.assertEqual(cols, ["title"])                 # only what was passed
        self.assertEqual(fresh["added_at"], 123.0)
        self.assertEqual(fresh["title"], "Select")
        _, cols2 = policy.merge_plan({"id": "m1"}, now=124.0)
        self.assertEqual(cols2, [])                       # nothing to set, nothing blanked

    def test_query_tokens_are_the_shared_tokenizer(self):
        self.assertEqual(policy.query_tokens("Harvard St. rezoning!"),
                         ["Harvard", "St", "rezoning"])
        self.assertEqual(policy.query_tokens(""), [])

    def test_meeting_cols_match_the_actual_schema(self):
        """policy.MEETING_COLS is a hand-maintained mirror of CREATE TABLE.
        With two stores it is the thing most likely to drift, so it is checked
        against the store that actually built the table."""
        td = tempfile.TemporaryDirectory(prefix="cz-mem-cols-")
        self.addCleanup(td.cleanup)
        c = Corpus(db_path=str(Path(td.name) / "corpus.db"))
        with c._con() as con:
            actual = [r[1] for r in con.execute("PRAGMA table_info(meetings)")]
        self.assertEqual(actual, policy.MEETING_COLS)


if __name__ == "__main__":
    unittest.main()
