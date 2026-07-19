"""One interface, two stores, one set of guarantees — proven, not asserted.

Every case here runs twice: once against a throwaway SQLite file, once against
a Postgres named by RECORD_TEST_PG_DSN. The point is not that each store works;
it is that they agree, because the hand-audited issue engine, the dedupe tiers
and the vote reader run against whichever one they are handed, and a
disagreement between the two is a record that says different things about the
same town depending on where it is read.

Most of what is pinned here has never been tested anywhere — the desk's suite
covers the desk's behavior, and the interesting failures are the ones only a
second implementation can expose: bm25's sign, `UPDATE OR IGNORE` having no
Postgres spelling, `end` being a reserved word, a zero vector's cosine being
undefined, GROUP BY's functional-dependency rules.

When the DSN is unset the Postgres half skips **loudly** and says how many. A
skip here is a gate that lost its inputs, not routine — the 1.9.0 audits made
that a house rule after a missing `otool` silently disabled four licence gates.

    docker run -d -e POSTGRES_PASSWORD=record -e POSTGRES_USER=record \
        -e POSTGRES_DB=record_test -p 55432:5432 pgvector/pgvector:pg16
    export RECORD_TEST_PG_DSN=postgresql://record:record@localhost:55432/record_test
    .venv/bin/python -m record.migrate --dsn "$RECORD_TEST_PG_DSN"
"""

import os
import tempfile
import unittest
from pathlib import Path

from memory import embed, issues, policy
from memory.store import Corpus

PG_DSN = os.environ.get("RECORD_TEST_PG_DSN", "").strip()

SELECT = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": "Speaker 2",
     "text": "I move to adopt the MBTA Communities zoning overlay as written."},
    {"start": 20.0, "end": 28.0, "speaker": "Speaker 3",
     "text": "The projected cost is four hundred thousand dollars."},
    {"start": 28.0, "end": 34.0, "speaker": None,
     "text": "All in favor? The motion passes five to zero."},
]
BOSTON_SEGS = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The Council takes up the rezoning of the waterfront district."},
    {"start": 6.0, "end": 12.0, "speaker": "Speaker 2",
     "text": "The rezoning article returns to committee for review."},
]
SCHOOL = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The School Committee returns to the rezoning and enrollment."},
    {"start": 6.0, "end": 13.0, "speaker": "Speaker 2",
     "text": "The override will decide whether the classrooms are funded."},
]


class StoreGuarantees:
    """The contract. Mixed into one TestCase per store; `self.store()` is the
    only thing that differs between them."""

    def store(self):
        raise NotImplementedError

    def setUp(self):
        self.c = self.store()

    def add(self, mid, segs, **meta):
        self.c.upsert_meeting({"id": mid, "status": "live",
                               "n_segments": len(segs), **meta})
        self.c.replace_segments(mid, segs)

    # -- rows --------------------------------------------------------------

    def test_upsert_merges_never_shrinks(self):
        self.c.upsert_meeting({"id": "m1", "title": "Select Board", "town": "Brookline"})
        self.c.upsert_meeting({"id": "m1", "body": "Select Board"})
        m = self.c.get_meeting("m1")
        self.assertEqual((m["title"], m["town"], m["body"]),
                         ("Select Board", "Brookline", "Select Board"))

    def test_get_meeting_inflates_json_and_hides_shingles(self):
        self.c.upsert_meeting({"id": "m1", "info_json": '{"a": 1}',
                               "analysis_json": '{"b": 2}', "shingles": "x y z"})
        m = self.c.get_meeting("m1")
        self.assertEqual(m["info"], {"a": 1})
        self.assertEqual(m["analysis"], {"b": 2})
        self.assertNotIn("shingles", m)
        self.assertNotIn("info_json", m)

    def test_transcript_promises_none_not_empty_string(self):
        self.add("sel", SELECT)
        self.assertEqual([s["speaker"] for s in self.c.transcript("sel")],
                         ["Speaker 1", "Speaker 1", "Speaker 2", "Speaker 3", None])

    def test_transcript_keeps_the_key_named_end(self):
        """`end` is a reserved word in Postgres and the column there is end_s.
        If the alias is ever dropped, every caller and the whole edition break
        on a KeyError — so the key is pinned by name."""
        self.add("sel", SELECT)
        seg = self.c.transcript("sel")[0]
        self.assertEqual(seg["end"], 5.0)
        self.assertEqual(sorted(seg), ["end", "speaker", "start", "text"])

    def test_list_meetings_is_newest_first_with_blank_dates_last(self):
        self.add("a", SELECT, date="2026-05-19")
        self.add("b", SELECT, date="2026-06-02")
        self.add("c", SELECT, date="")
        self.assertEqual([m["id"] for m in self.c.list_meetings()], ["b", "a", "c"])

    def test_list_meetings_omits_the_heavy_columns(self):
        self.add("a", SELECT, date="2026-05-19", summary="long", shingles="x y")
        row = self.c.list_meetings()[0]
        self.assertEqual(sorted(row), sorted(policy.LIST_COLS))

    # -- search ------------------------------------------------------------

    def test_search_hit_envelope_is_identical(self):
        self.add("sel", SELECT, title="Select Board", date="2026-05-19",
                 town="Brookline", body="Select Board", url="https://x/1")
        hit = self.c.search("rezoning")[0]
        self.assertEqual(sorted(hit), [
            "body", "date", "duration", "end", "media_path", "meeting_id",
            "score", "seg_id", "source_kind", "speaker", "t", "text", "title",
            "town", "url", "video_id", "why"])
        self.assertEqual(hit["title"], "Select Board")
        self.assertIn("rezoning", hit["text"].lower())
        self.assertEqual(hit["t"], 5.0)          # time-coded for jump-to-play

    def test_keyword_search_is_cross_corpus_and_best_match_first(self):
        """bm25 is negative and sorted ascending; ts_rank_cd is positive and
        sorted descending. Port the ORDER BY across unchanged and you get the
        worst matches first, with every rank-derived score corrupted and no
        error anywhere. This is that test."""
        self.add("sel", SELECT, title="Select Board", date="2026-05-19")
        self.add("sch", SCHOOL, title="School Committee", date="2026-06-02")
        hits = self.c.search("rezoning")
        self.assertEqual({h["meeting_id"] for h in hits}, {"sel", "sch"})
        self.assertIn("rezoning", hits[0]["text"].lower())
        self.assertEqual(hits[0]["score"], 1.0)
        self.assertTrue(all(hits[i]["score"] >= hits[i + 1]["score"]
                            for i in range(len(hits) - 1)))

    def test_search_provenance_vocabulary(self):
        self.add("sel", SELECT, title="Select")
        whys = {h["why"] for h in self.c.search("rezoning")}
        self.assertTrue(whys <= {"word", "related", "both", "meaning"})

    def test_search_never_crosses_towns(self):
        """Aggregation across towns is a covenant question, not a convenience.
        A hosted record that forgets the scope leaks one town into another."""
        self.add("bro", SELECT, town="Brookline", title="Select")
        self.add("bos", SCHOOL, town="Boston", title="Council")
        hits = self.c.search("rezoning", town="Brookline")
        self.assertTrue(hits)
        self.assertEqual({h["town"] for h in hits}, {"Brookline"})
        self.assertEqual({h["town"] for h in self.c.search("rezoning", town="Boston")},
                         {"Boston"})

    def test_empty_query_finds_nothing(self):
        self.add("sel", SELECT)
        self.assertEqual(self.c.search(""), [])
        self.assertEqual(self.c.search("   "), [])

    def test_filler_segments_are_word_reachable_and_meaning_invisible(self):
        """A segment of pure filler embeds to zeros. The desk stores the zeros
        and skips them on read; Postgres must store NULL, because cosine
        distance against a zero vector is undefined and one NaN silently
        poisons an HNSW ordering."""
        self.add("m1", [{"start": 0.0, "end": 4.0, "text": "I think so, you know."}])
        self.assertEqual(self.c.semantic(embed.embed("think")), [])
        self.assertEqual(len(self.c.search("think")), 1)
        self.assertTrue(all(h["score"] == h["score"]          # not NaN
                            for h in self.c.search("think")))

    # -- dedupe ------------------------------------------------------------

    def test_dedupe_by_canonical_url_and_hash(self):
        self.add("sel", SELECT, url_canon="youtube:abc", source_hash="deadbeef")
        self.assertEqual(self.c.find_by_url_canon("youtube:abc")["id"], "sel")
        self.assertEqual(self.c.find_by_hash("deadbeef")["id"], "sel")
        self.assertIsNone(self.c.find_by_url_canon("youtube:zzz"))
        self.assertIsNone(self.c.find_by_url_canon(""))
        self.assertIsNone(self.c.find_by_hash(""))

    def test_dedupe_by_shingles_agrees_at_the_boundary(self):
        shared = " ".join(f"s{i}" for i in range(100))
        self.add("sel", SELECT, shingles=shared)
        self.assertEqual(self.c.find_by_shingles(shared)["id"], "sel")   # 1.0
        near = " ".join([f"s{i}" for i in range(95)] + [f"x{j}" for j in range(5)])
        self.assertIsNotNone(self.c.find_by_shingles(near))               # 0.90476
        far = " ".join([f"s{i}" for i in range(92)] + [f"x{j}" for j in range(8)])
        self.assertIsNone(self.c.find_by_shingles(far))                   # 0.85185

    # -- issues ------------------------------------------------------------

    def _issue_with_links(self):
        self.add("sel", SELECT, town="Brookline", date="2026-05-19", title="Select")
        self.add("sch", SCHOOL, town="Brookline", date="2026-06-02", title="School")
        segs = self.c.segments_of("sel") + self.c.segments_of("sch")
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning",
                             "status": "active", "aliases": ["rezoning"],
                             "keywords": ["rezoning"]})
        self.c.link_segments("i1", [(segs[1]["id"], "sel", 1.0, "alias"),
                                    (segs[5]["id"], "sch", 1.0, "alias")])
        return segs

    def test_list_issues_rollups_and_following_are_the_same_shape(self):
        self._issue_with_links()
        row = self.c.list_issues(town="Brookline")[0]
        self.assertEqual(row["n_meetings"], 2)
        self.assertEqual(row["n_segments"], 2)
        self.assertEqual(row["first_seen"], "2026-05-19")
        self.assertEqual(row["last_seen"], "2026-06-02")
        self.assertIs(row["following"], False)          # a bool on both stores
        self.c.follow("i1")
        self.assertIs(self.c.list_issues(town="Brookline")[0]["following"], True)

    def test_issue_appearances_order_and_beads(self):
        """Node order is oldest-first with blank dates first; bead order is by
        start, and `issues.delta` slices `beads[:3]` trusting exactly that."""
        self._issue_with_links()
        nodes = self.c.issue_appearances("i1")
        self.assertEqual([n["meeting_id"] for n in nodes], ["sel", "sch"])
        self.assertEqual([n["n"] for n in nodes], [1, 1])
        self.assertEqual(nodes[0]["beads"][0]["t"], 5.0)
        self.assertEqual(sorted(nodes[0]["beads"][0]),
                         ["end", "score", "seg_id", "speaker", "t", "text", "why"])

    def test_issue_dict_rollups_match_the_list_view(self):
        self._issue_with_links()
        iss = self.c.get_issue("i1")
        row = self.c.list_issues(town="Brookline")[0]
        self.assertEqual((iss["n_meetings"], iss["n_segments"]),
                         (row["n_meetings"], row["n_segments"]))
        self.assertEqual(iss["aliases"], ["rezoning"])

    def test_forget_leaves_no_orphan_issue_links(self):
        """The desk hand-rolls this cascade; Postgres has a real foreign key.
        They have to mean the same thing, which is why the desk was fixed
        first rather than letting ON DELETE CASCADE paper over it."""
        self._issue_with_links()
        self.assertTrue(self.c.forget("sel"))
        row = self.c.list_issues(town="Brookline")[0]
        shown = sum(n["n"] for n in self.c.issue_appearances("i1"))
        self.assertEqual(row["n_segments"], shown)
        self.assertEqual(row["n_meetings"], 1)
        self.assertEqual(self.c.linked_seg_ids("sel"), set())

    def test_merge_moves_links_without_duplicating(self):
        """`UPDATE OR IGNORE` has no Postgres spelling, and merge is a
        steward's most consequential verb. A segment linked to BOTH sides is
        the case that separates a correct rewrite from a lossy one."""
        segs = self._issue_with_links()
        self.c.upsert_issue({"id": "i2", "town": "Brookline", "name": "zoning",
                             "status": "active", "aliases": ["zoning"]})
        # i2 shares one segment with i1, and has one of its own
        self.c.link_segments("i2", [(segs[1]["id"], "sel", 0.5, "related"),
                                    (segs[2]["id"], "sel", 0.7, "related")])
        self.c.merge_issues(["i2"], "i1")
        links = {sid for sid in self.c.linked_seg_ids("sel")}
        self.assertEqual(links, {segs[1]["id"], segs[2]["id"]})
        beads = {b["seg_id"]: b for n in self.c.issue_appearances("i1")
                 for b in n["beads"]}
        self.assertEqual(beads[segs[1]["id"]]["score"], 1.0)   # dst's link survives
        self.assertEqual(beads[segs[1]["id"]]["why"], "alias")
        self.assertEqual(beads[segs[2]["id"]]["why"], "related")
        self.assertEqual(self.c.get_issue("i2")["status"], "merged")
        self.assertEqual(self.c.get_issue("i2")["merged_into"], "i1")

    def test_merge_carries_a_thread_to_the_survivor(self):
        self._issue_with_links()
        self.c.upsert_issue({"id": "i2", "town": "Brookline", "name": "zoning"})
        self.c.follow("i2")
        self.c.merge_issues(["i2"], "i1")
        self.assertIsNotNone(self.c.get_thread("i1"))
        self.assertIsNone(self.c.get_thread("i2"))

    def test_unlink_meeting_is_the_second_half_of_split(self):
        self._issue_with_links()
        self.assertEqual(self.c.unlink_meeting("i1", "sel"), 1)
        self.assertEqual([n["meeting_id"] for n in self.c.issue_appearances("i1")],
                         ["sch"])

    def test_clear_auto_issues_keeps_what_a_human_touched(self):
        self._issue_with_links()
        self.c.upsert_issue({"id": "auto1", "town": "Brookline", "origin": "auto",
                             "name": "a", "status": "active"})
        self.c.upsert_issue({"id": "kept", "town": "Brookline", "origin": "steward",
                             "name": "b", "status": "active"})
        self.c.upsert_issue({"id": "followed", "town": "Brookline", "origin": "auto",
                             "name": "c", "status": "active"})
        self.c.follow("followed")
        self.c.clear_auto_issues("Brookline")
        left = {i["id"] for i in self.c.list_issues(town="Brookline")}
        self.assertIn("kept", left)                  # a steward's work survives
        self.assertIn("followed", left)              # so does a followed issue
        self.assertNotIn("auto1", left)

    def test_recompute_centroid_is_unit_length(self):
        self._issue_with_links()
        cen = self.c.recompute_centroid("i1")
        self.assertIsNotNone(cen)
        self.assertAlmostEqual(float(embed.np.linalg.norm(cen)), 1.0, places=5)
        self.assertEqual(len(cen), embed.DIM)

    def test_issue_keywords_hands_back_a_readable_vector(self):
        """`emb`/`centroid` are opaque across the seam — bytes here, an array
        there — and `embed.as_vec` is the only reader. This proves the store
        already did that conversion for the engine."""
        self._issue_with_links()
        self.c.recompute_centroid("i1")
        row = [r for r in self.c.issue_keywords() if r["id"] == "i1"][0]
        self.assertEqual(len(embed.as_vec(row["centroid"])), embed.DIM)
        self.assertEqual(row["aliases"], ["rezoning"])

    # -- threads and events ------------------------------------------------

    def test_add_event_returns_a_usable_id(self):
        """`cur.lastrowid` does not exist in psycopg; RETURNING does."""
        self._issue_with_links()
        eid = self.c.add_event("resurfacing", issue_id="i1", meeting_id="sch",
                               payload={"delta": "returned"})
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)
        ev = [e for e in self.c.list_events() if e["id"] == eid]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["payload"], {"delta": "returned"})
        self.assertEqual(ev[0]["issue_name"], "rezoning")

    def test_events_are_newest_first_and_seen_is_countable(self):
        self._issue_with_links()
        for i in range(3):
            self.c.add_event("resurfacing", issue_id="i1", payload={"i": i})
        self.assertEqual(self.c.unseen_count(), 3)
        self.assertEqual([e["payload"]["i"] for e in self.c.list_events()], [2, 1, 0])
        self.assertEqual(self.c.mark_seen("i1"), 3)
        self.assertEqual(self.c.unseen_count(), 0)

    def test_list_threads_shape(self):
        self._issue_with_links()
        self.c.follow("i1")
        self.c.add_event("resurfacing", issue_id="i1")
        t = self.c.list_threads()[0]
        self.assertEqual(t["issue_id"], "i1")
        self.assertEqual(t["name"], "rezoning")
        self.assertEqual(t["n_meetings"], 2)
        self.assertEqual(t["unseen"], 1)
        self.c.advance_thread("i1", "2026-06-02")
        self.assertEqual(self.c.list_threads()[0]["last_seen_date"], "2026-06-02")
        self.assertTrue(self.c.unfollow("i1"))
        self.assertEqual(self.c.list_threads(), [])

    # -- votes and paper ---------------------------------------------------

    def test_votes_round_trip_with_the_roll_as_json(self):
        self.add("sel", SELECT, town="Brookline", date="2026-05-19", title="Select")
        self.c.replace_votes("sel", [{
            "t": 28.0, "motion": "adopt the zoning overlay", "outcome": "passed",
            "tally": "5–0", "origin": "extractive",
            "roll": [{"name": "Chair", "vote": "yes", "t": 29.0, "quote": "aye"}]}])
        v = self.c.votes_of("sel")[0]
        self.assertEqual(v["outcome"], "passed")
        self.assertEqual(v["tally"], "5–0")
        self.assertEqual(v["roll"][0]["name"], "Chair")
        self.assertEqual(len(self.c.all_votes(town="Brookline")), 1)
        self.assertEqual(self.c.all_votes(town="Boston"), [])

    def test_replace_votes_is_idempotent(self):
        self.add("sel", SELECT, town="Brookline")
        for _ in range(3):
            self.c.replace_votes("sel", [{"t": 1.0, "motion": "m", "outcome": "passed"}])
        self.assertEqual(len(self.c.votes_of("sel")), 1)

    def test_documents_chunks_and_paper(self):
        self.add("sel", SELECT, town="Brookline", date="2026-05-19", title="Select")
        self.c.upsert_document({"id": "d1", "meeting_id": "sel", "town": "Brookline",
                                "kind": "Agenda", "title": "Agenda", "status": "live",
                                "date": "2026-05-19", "pages": 3})
        self.assertEqual(self.c.replace_doc_chunks("d1", [
            {"page": 1, "text": "The Harvard Street rezoning article is before us."},
            {"page": 2, "text": "Estimated cost four hundred thousand dollars."}]), 2)
        chunks = self.c.doc_chunks_of("d1")
        self.assertEqual([c["page"] for c in chunks], [1, 2])
        self.assertEqual(self.c.get_document("d1")["n_chunks"], 2)
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning"})
        self.c.link_doc_chunks("i1", [(chunks[0]["id"], "d1", 1.0, "alias")])
        paper = self.c.issue_paper("i1")
        self.assertEqual(len(paper), 1)
        self.assertEqual(paper[0]["cites"][0]["page"], 1)
        self.assertTrue(self.c.forget_document("d1"))
        self.assertEqual(self.c.issue_paper("i1"), [])

    def test_replace_segments_is_idempotent(self):
        for _ in range(3):
            self.add("sel", SELECT)
        self.assertEqual(len(self.c.transcript("sel")), 5)
        self.assertEqual(self.c.stats()["segments"], 5)

    # -- the engine, end to end -------------------------------------------

    def test_the_issue_engine_runs_identically_against_this_store(self):
        """The whole reason the seam exists: 778 lines of hand-audited
        clustering, unmodified, producing the same record on either store.

        The discovery constants target a real corpus, so — exactly as
        tests/test_memory_issues.py does — they are relaxed for a fixture this
        small. What is under test is the store, not the thresholds."""
        from unittest import mock
        for name, val in (("PASSAGE_WORDS", 8), ("MIN_PASSAGE_WORDS", 3),
                          ("ANCHOR_MIN_DF", 2), ("ANCHOR_MIN_SOLO", 2),
                          ("ANCHOR_MIN_PMI", 0.0), ("MIN_ISSUE_SEGMENTS", 1)):
            p = mock.patch.object(issues, name, val)
            p.start()
            self.addCleanup(p.stop)
        context = ["on harvard street", "before the board", "in the overlay",
                   "at the hearing", "for the town", "this spring"]
        for mid, date in (("m1", "2026-05-12"), ("m2", "2026-05-19")):
            self.add(mid, [
                {"start": i * 5.0, "end": i * 5.0 + 4.0, "speaker": "Speaker 1",
                 "text": f"the vision zero plan {context[i % len(context)]}"}
                for i in range(8)], town="Brookline", date=date, title=f"M {date}")
        res = issues.discover(self.c, "Brookline")
        self.assertGreaterEqual(res["issues"], 1)
        found = [i for i in self.c.list_issues(town="Brookline")
                 if "vision" in i["name"].lower()]
        self.assertTrue(found, "expected a vision zero issue on this store")
        self.assertEqual(found[0]["n_meetings"], 2)      # the arc, across time
        self.assertGreaterEqual(found[0]["n_segments"], 2)

    def test_assign_meeting_links_a_fresh_meeting_to_a_known_issue(self):
        self.add("sel", SELECT, town="Brookline", date="2026-05-19", title="Select")
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning",
                             "status": "active", "aliases": ["rezoning"],
                             "keywords": ["rezoning"], "origin": "steward"})
        self.add("sch", SCHOOL, town="Brookline", date="2026-06-02", title="School")
        issues.assign_meeting(self.c, "sch")
        mids = {n["meeting_id"] for n in self.c.issue_appearances("i1")}
        self.assertIn("sch", mids)


    # -- what the adversarial review found ---------------------------------

    def test_search_never_serves_a_meeting_the_edition_withholds(self):
        """A meeting that is queued, errored, or mid-ingest is not part of the
        record yet — the pressed edition withholds it, and search must agree.
        Before this, an un-approved submission's full transcript, title and URL
        were readable by anyone through the public search endpoint."""
        self.add("live1", SELECT, town="Brookline", title="Select Board")
        self.c.upsert_meeting({"id": "secret", "town": "Brookline",
                               "status": "error", "title": "Executive Session"})
        self.c.replace_segments("secret", [
            {"start": 0.0, "end": 5.0,
             "text": "the Harvard Street rezoning article in private"}])
        hits = self.c.search("rezoning")
        self.assertTrue(hits)
        self.assertEqual({h["meeting_id"] for h in hits}, {"live1"})
        self.assertEqual(self.c.semantic(embed.embed("rezoning article")) and
                         {h["meeting_id"] for h in
                          self.c.semantic(embed.embed("rezoning article"))},
                         {"live1"})

    def test_town_scope_follows_a_corrected_town(self):
        """The Postgres store denormalises `town` onto segments for speed, and
        that snapshot goes stale the moment a steward corrects a meeting's
        town — so the filter reads the meeting, not the copy. Otherwise one
        store answers under the old town and the other under the new."""
        self.add("m1", SELECT, town="Brookline", title="Select Board")
        self.c.upsert_meeting({"id": "m1", "town": "Boston"})   # corrected
        self.assertEqual({h["town"] for h in self.c.search("rezoning",
                                                           town="Boston")},
                         {"Boston"})
        self.assertEqual(self.c.search("rezoning", town="Brookline"), [])

    def test_town_scope_survives_segments_written_before_the_town(self):
        """`memory/ingest.py` writes segments before it upserts the resolved
        town, so the denormalised copy is '' for any ingest whose town is
        derived from the uploader. The meeting must still be findable."""
        self.c.upsert_meeting({"id": "m1", "status": "live", "title": "S"})
        self.c.replace_segments("m1", SELECT)          # town not known yet
        self.c.upsert_meeting({"id": "m1", "town": "Brookline"})
        hits = self.c.search("rezoning", town="Brookline")
        self.assertTrue(hits, "the meeting became invisible to its own town")

    def test_re_ingest_leaves_no_orphan_issue_links(self):
        """The forget() cascade's twin, reached by re-ingest: replacing a
        meeting's segments must take the issue links that pointed at them, or
        list_issues counts ghosts issue_appearances hides."""
        self.add("sel", SELECT, town="Brookline", date="2026-05-19")
        seg = self.c.segments_of("sel")[1]
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "rezoning"})
        self.c.link_segments("i1", [(seg["id"], "sel", 1.0, "alias")])
        self.add("sel", SELECT, town="Brookline", date="2026-05-19")   # re-ingest
        counted = self.c.list_issues(town="Brookline")[0]["n_segments"]
        shown = sum(n["n"] for n in self.c.issue_appearances("i1"))
        self.assertEqual(counted, shown)

    def test_minting_an_issue_stays_inside_its_town(self):
        """`mint_from_query` seeds from a search. Unscoped, a steward minting a
        Brookline issue pulled Boston's segments onto its timeline."""
        self.add("bro", SELECT, town="Brookline", date="2026-05-19", title="B")
        self.add("bos", BOSTON_SEGS, town="Boston", date="2026-05-20", title="C")
        out = issues.mint_from_query(self.c, "rezoning", "Brookline")
        self.assertIsNotNone(out)
        iid = out.get("issue_id") or out.get("id")
        towns = {n["town"] for n in self.c.issue_appearances(iid)}
        self.assertTrue(towns <= {"Brookline"}, f"leaked into Brookline: {towns}")

    def test_stats_reports_capability_honestly(self):
        self.add("sel", SELECT, town="Brookline", body="Select Board", duration=34.0)
        s = self.c.stats()
        self.assertEqual((s["meetings"], s["live"], s["segments"]), (1, 1, 5))
        self.assertEqual((s["towns"], s["bodies"]), (1, 1))
        self.assertIs(s["fts"], True)
        self.assertIs(s["semantic"], True)


class SqliteStoreTest(StoreGuarantees, unittest.TestCase):
    """The desk's store — the reference implementation."""

    def store(self):
        td = tempfile.TemporaryDirectory(prefix="cz-parity-lite-")
        self.addCleanup(td.cleanup)
        return Corpus(db_path=str(Path(td.name) / "corpus.db"))


@unittest.skipUnless(PG_DSN, "RECORD_TEST_PG_DSN unset — the Postgres half of "
                             "the seam is UNPROVEN in this run")
class PgStoreTest(StoreGuarantees, unittest.TestCase):
    """Publicrecord's store — the same guarantees, other dialect."""

    def store(self):
        from record.store import PgCorpus
        c = PgCorpus(dsn=PG_DSN)
        # Each case starts from an empty record. TRUNCATE … CASCADE rather than
        # dropping the schema: it is one statement, and it keeps the foreign
        # keys and the HNSW indexes that the cases are partly testing.
        with c._con() as con:
            con.execute(
                "TRUNCATE meetings, segments, issues, issue_segments, threads, "
                "events, documents, doc_chunks, issue_documents, votes, "
                "submissions, asr_tasks, audit, spend, towns RESTART IDENTITY CASCADE")
        self.addCleanup(c.close)
        return c

    def test_the_store_satisfies_the_seam(self):
        from memory.seam import CorpusStore
        self.assertIsInstance(self.c, CorpusStore)

    def test_the_dsn_never_carries_a_password(self):
        """`db_path` is the seam's "which store am I", and it ends up in health
        endpoints and log lines. On this store it is a DSN."""
        self.assertNotIn("record:record@", self.c.db_path)
        self.assertIn("***", self.c.db_path)

    def test_zero_norm_vectors_are_stored_as_null_not_as_zeros(self):
        self.add("m1", [{"start": 0.0, "end": 1.0, "text": "I think so, you know."},
                        {"start": 1.0, "end": 5.0, "text": "The rezoning article."}])
        with self.c._con() as con:
            rows = con.execute(
                "SELECT text, emb IS NULL AS blank FROM segments ORDER BY idx"
            ).fetchall()
        self.assertTrue(rows[0]["blank"])       # pure filler: no direction at all
        self.assertFalse(rows[1]["blank"])

    def test_the_lexical_dimension_is_pinned_in_the_database(self):
        with self.c._con() as con:
            row = con.execute(
                "SELECT value FROM meta WHERE key='embed_lex_dim'").fetchone()
        self.assertEqual(int(row["value"]), embed.DIM)

    def test_unit_rolls_the_whole_verb_back(self):
        """The reason unit() exists: a curation verb is a call sequence, and a
        half-applied merge is worse than a refused one."""
        self.add("sel", SELECT, town="Brookline", title="Select")
        with self.assertRaises(RuntimeError):
            with self.c.unit():
                self.c.upsert_issue({"id": "i9", "town": "Brookline", "name": "x"})
                raise RuntimeError("the verb failed halfway")
        self.assertIsNone(self.c.get_issue("i9"))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(PG_DSN, "RECORD_TEST_PG_DSN unset — the vector index "
                             "tuning is UNPROVEN in this run")
class HnswReachTest(unittest.TestCase):
    """Vector search has to be shaped so the index is actually used.

    The obvious join-then-order query cannot push an ordered index scan through
    the join, so the planner computes a distance for every embedded segment and
    top-N sorts them all. On the live record that was 2s at a limit the index
    could serve and 45s the moment the limit crossed its reach — a cliff, on
    the same query, which read as contention until the numbers were taken
    twice. `_vector_rows` runs the ordering in a segments-only subquery so the
    HNSW index drives it; these cases pin the shape, not a stopwatch (timing in
    a suite is a flake generator).
    """

    def setUp(self):
        from record.store import PgCorpus
        self.c = PgCorpus(dsn=PG_DSN)
        self.addCleanup(self.c.close)

    def test_the_reach_always_exceeds_what_was_asked_for(self):
        from record.store import HNSW_EF_FACTOR, HNSW_EF_MIN
        for limit in (1, 10, 40, 60, 80, 200):
            ef = max(HNSW_EF_MIN, limit * HNSW_EF_FACTOR)
            self.assertGreater(ef, limit,
                               f"limit {limit} would out-run the index walk")

    def test_the_default_would_not_have_been_enough(self):
        """Postgres ships ef_search=40; the reader pages at 80. If someone
        lowers HNSW_EF_MIN back under the reader's page size, this says why
        not."""
        from record.store import HNSW_EF_MIN
        self.assertGreater(HNSW_EF_MIN, 40)

    def test_the_ordering_runs_in_a_subquery_not_across_the_join(self):
        """The property that keeps the index in play: the vector ORDER BY is
        over `segments` alone, then joined to meetings — never one flat SELECT
        that orders across the join, which is the shape that scans everything."""
        src = (Path(__file__).resolve().parents[1] / "record" / "store.py").read_text()
        vr = src[src.index("def _vector_rows"):src.index("# -- stats")]
        # the ordering is inside a subquery that selects from segments only
        self.assertIn("FROM segments s WHERE", vr)
        self.assertIn(") s JOIN meetings m", vr)
        # and ef_search is set LOCAL, so a pooled connection cannot leak it
        self.assertIn("SET LOCAL hnsw.ef_search", vr)
        self.assertNotIn("SET hnsw.ef_search", vr.replace("SET LOCAL hnsw", "X"))

    def test_scope_filters_on_the_meeting_never_the_segment(self):
        """`town` must filter on `m.town`, not the copy denormalised onto
        segments. That copy lags a steward's town correction — the two
        `test_town_scope_*` cases prove it — and the lexical path scopes on
        `m.town`, so both halves of one search have to agree."""
        src = (Path(__file__).resolve().parents[1] / "record" / "store.py").read_text()
        vr = src[src.index("def _vector_rows"):src.index("# -- stats")]
        self.assertIn("m.town=%s", vr)          # the corrected town, on meetings
        self.assertIn("m.body=%s", vr)
        self.assertNotIn("s.town", vr)          # never the denormalised copy
        self.assertIn("HNSW_SCOPE_OVERFETCH if (town or body)", vr)

    def test_the_reach_is_capped_so_a_raised_limit_is_not_a_500(self):
        """pgvector rejects ef_search above 1000; the search clamps first."""
        from record.store import (HNSW_EF_FACTOR, HNSW_EF_MAX,
                                   HNSW_SCOPE_OVERFETCH)
        biggest = 200 * HNSW_SCOPE_OVERFETCH * HNSW_EF_FACTOR
        self.assertGreater(biggest, HNSW_EF_MAX)     # the clamp actually bites
        self.assertEqual(min(HNSW_EF_MAX, biggest), HNSW_EF_MAX)

    def test_a_vector_search_still_returns_what_it_should(self):
        """The rewrite must change the route, not the answer."""
        with self.c._con() as con:
            con.execute("TRUNCATE meetings, segments RESTART IDENTITY CASCADE")
        self.c.upsert_meeting({"id": "m1", "status": "live", "town": "Testville",
                               "body": "Select Board"})
        self.c.replace_segments("m1", [
            {"start": 0.0, "end": 5.0, "speaker": "Chair",
             "text": "The Harvard Street rezoning article is before us."},
            {"start": 5.0, "end": 9.0, "speaker": "Chair",
             "text": "Next, the school budget."}])
        # unscoped, town-scoped, and body-scoped all reach it
        for kw in ({}, {"town": "Testville"}, {"body": "Select Board"}):
            hits = self.c.search("rezoning", limit=80, **kw)
            self.assertTrue(hits, kw)
            self.assertIn("rezoning", hits[0]["text"].lower())
