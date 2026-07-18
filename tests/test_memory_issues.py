"""The issue engine: anchors, grouping, discovery, incremental assignment,
threads + resurfacings, and the steward tools.

Offline by construction — no LLM key (the extractive paths run), no network, a
throwaway SQLite file. Discovery's thresholds are tuned for a real corpus of
thousands of passages, so the integration tests relax them for tiny fixtures via
patching; the unit tests exercise the pure helpers directly.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from memory import embed, issues
from memory.store import Corpus


def _passage(mid, text):
    return {"mid": mid, "date": "", "text": text, "seg_ids": [],
            "vec": embed.embed(text)}


class HelperTest(unittest.TestCase):
    def test_content_words_strip_filler(self):
        cw = issues.content_words("The board will vote on the vision zero plan tonight")
        self.assertIn("vision", cw)
        self.assertIn("zero", cw)
        self.assertNotIn("the", cw)
        self.assertNotIn("will", cw)      # discourse filler

    def test_phrases_are_contentful_and_drop_procedural(self):
        ph = issues.phrases("seeing none we adopt the vision zero action plan")
        self.assertIn("vision zero", ph)
        self.assertNotIn("seeing none", ph)       # procedural
        # no phrase may start or end on filler
        self.assertTrue(all(w not in issues.FILLER
                            for p in ph for w in (p.split()[0], p.split()[-1])))

    def test_anchors_prefer_sticky_collocations(self):
        # 'vision zero' co-occurs and is otherwise rare (sticky, high PMI);
        # 'budget item' is two words that are each common across the record and
        # only sometimes adjacent (compositional, low PMI). Threshold scaled to
        # this small fixture — production PMI is higher on a real corpus.
        ps = [_passage("m1", "vision zero reduces traffic fatalities citywide plan"),
              _passage("m1", "the vision zero program adds crossing treatments now"),
              _passage("m2", "vision zero targets the deadliest corridors first here"),
              _passage("m1", "the budget item passed after the review discussion"),
              _passage("m2", "a budget item returns to the finance committee soon"),
              _passage("m2", "the last budget item touched the housing overlay plan"),
              _passage("m1", "the budget for the schools grew this review cycle"),
              _passage("m2", "the water budget and the sewer budget were reviewed"),
              _passage("m1", "the next item and the following item were tabled"),
              _passage("m2", "an item on parking and an item on lighting came up")]
        with mock.patch.object(issues, "ANCHOR_MIN_PMI", 0.8):
            anchors, pset, mset = issues._anchors(ps)
        self.assertIn("vision zero", anchors)         # sticky, rare → high PMI
        self.assertNotIn("budget item", anchors)      # common words → low PMI

    def test_anchors_drop_person_names(self):
        ps = [_passage("m1", "chair rob shown recognizes the next speaker now"),
              _passage("m2", "rob shown asks the board about the budget timeline"),
              _passage("m1", "rob shown moves to the next warrant article please")]
        anchors, _, _ = issues._anchors(ps)
        self.assertNotIn("rob shown", anchors)    # a name is never an issue

    def test_group_anchors_merges_family_not_token_overlap(self):
        pset = {"design review": {0, 1, 2}, "design review committee": {0, 1},
                "climate action": {5, 6}, "favorable action": {8, 9}}
        groups = issues._group_anchors(
            ["design review", "design review committee", "climate action",
             "favorable action"], pset)
        fam = [g for g in groups if "design review" in g][0]
        self.assertIn("design review committee", fam)          # containment merges
        # shares only the token 'action', not passages → stays apart
        self.assertFalse(any("climate action" in g and "favorable action" in g
                             for g in groups))

    def test_title_keeps_acronyms(self):
        self.assertEqual(issues._title("mbta communities"), "MBTA Communities")
        self.assertEqual(issues._title("golf course"), "Golf Course")


# anchor phrase + rotating context so the phrase recurs in every cue (and so a
# passage window carries enough content words to survive the ≥MIN filter)
VZ = "vision zero"
GOLF = "golf course"
_CONTEXT = ["reduces traffic fatalities on our streets", "adds safer crossings",
            "slows speeds near the schools", "was discussed at length tonight",
            "returns to the board next month", "the plan targets the corridors",
            "with questions from the public comment", "under the parks budget item"]


def _meeting(corpus, mid, phrase, n, date, town="Brookline", body="Select Board"):
    corpus.upsert_meeting({"id": mid, "status": "live", "town": town, "body": body,
                           "date": date, "title": f"{body} {date}"})
    segs = [{"start": i * 5.0, "end": i * 5.0 + 4, "speaker": "Speaker 1",
             "text": f"the {phrase} {_CONTEXT[i % len(_CONTEXT)]}"}
            for i in range(n)]
    corpus.replace_segments(mid, segs)
    return segs


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-iss-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        # relax discovery for tiny fixtures (constants target a real corpus)
        for name, val in (("PASSAGE_WORDS", 8), ("MIN_PASSAGE_WORDS", 3),
                          ("ANCHOR_MIN_DF", 2), ("ANCHOR_MIN_SOLO", 2),
                          ("ANCHOR_MIN_PMI", 0.0), ("MIN_ISSUE_SEGMENTS", 1)):
            p = mock.patch.object(issues, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.td.cleanup)

    def test_discover_forms_issue_and_assigns_its_segments(self):
        _meeting(self.c, "m1", VZ, 8, "2026-05-12")
        _meeting(self.c, "m2", VZ, 8, "2026-05-19")
        res = issues.discover(self.c, "Brookline")
        self.assertGreaterEqual(res["issues"], 1)
        names = [i["name"].lower() for i in self.c.list_issues(town="Brookline")]
        self.assertTrue(any("vision" in n for n in names),
                        f"expected a vision zero issue, got {names}")
        # the issue spans both meetings and captured the 'vision zero' segments
        vz = next(i for i in self.c.list_issues(town="Brookline")
                  if "vision" in i["name"].lower())
        self.assertEqual(vz["n_meetings"], 2)
        self.assertGreaterEqual(vz["n_segments"], 2)

    def test_discover_keeps_followed_issue_across_rebuild(self):
        _meeting(self.c, "m1", VZ, 8, "2026-05-12")
        issues.discover(self.c, "Brookline")
        vz = next(i for i in self.c.list_issues(town="Brookline")
                  if "vision" in i["name"].lower())
        self.c.follow(vz["id"])
        # a second rebuild must not forget the followed issue
        issues.discover(self.c, "Brookline")
        self.assertIsNotNone(self.c.get_issue(vz["id"]))
        self.assertIsNotNone(self.c.get_thread(vz["id"]))


class AssignTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-asg-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        self.addCleanup(self.td.cleanup)

    def _issue(self, iid, name, keywords, **kw):
        self.c.upsert_issue({"id": iid, "town": "Brookline", "status": "active",
                             "name": name, "aliases": keywords,
                             "keywords": [k.lower() for k in keywords],
                             "origin": kw.get("origin", "auto")})

    def test_assign_meeting_links_by_keyword(self):
        self._issue("iss:vz", "Vision Zero", ["vision zero"])
        _meeting(self.c, "m1", VZ, 6, "2026-05-19")
        res = issues.assign_meeting(self.c, "m1", emit_events=False)
        self.assertGreater(res["assigned"], 0)
        beads = self.c.issue_appearances("iss:vz")
        self.assertEqual(beads[0]["meeting_id"], "m1")

    def test_resurfacing_event_delta_and_advance_on_followed_issue(self):
        self._issue("iss:vz", "Vision Zero", ["vision zero"])
        # a first meeting sets the baseline the follower has seen
        _meeting(self.c, "m1", VZ, 6, "2026-05-12")
        issues.assign_meeting(self.c, "m1", emit_events=False)
        self.c.follow("iss:vz")                      # last_seen := 2026-05-12
        # a newer meeting reopens the issue → one resurfacing, with a delta
        _meeting(self.c, "m2", VZ, 6, "2026-06-02")
        res = issues.assign_meeting(self.c, "m2", emit_events=True)
        self.assertEqual(len(res["resurfaced"]), 1)
        self.assertIn("vision zero", res["resurfaced"][0]["delta"].lower())
        self.assertEqual(self.c.unseen_count(), 1)
        self.assertEqual(self.c.get_thread("iss:vz")["last_seen_date"], "2026-06-02")

    def test_no_resurfacing_for_older_meeting(self):
        self._issue("iss:vz", "Vision Zero", ["vision zero"])
        _meeting(self.c, "m2", VZ, 6, "2026-06-02")
        issues.assign_meeting(self.c, "m2", emit_events=False)
        self.c.follow("iss:vz")                      # seen through 2026-06-02
        _meeting(self.c, "m1", VZ, 6, "2026-05-12")  # an older backfill
        res = issues.assign_meeting(self.c, "m1", emit_events=True)
        self.assertEqual(res["resurfaced"], [])
        self.assertEqual(self.c.unseen_count(), 0)

    def test_delta_extractive_names_issue_and_timestamp(self):
        self._issue("iss:vz", "Vision Zero", ["vision zero"])
        _meeting(self.c, "m1", VZ, 6, "2026-05-19")
        issues.assign_meeting(self.c, "m1", emit_events=False)
        d = issues.delta(self.c, self.c.get_issue("iss:vz"), "m1")
        self.assertIn("Vision Zero", d)
        self.assertRegex(d, r"\d\d:\d\d")            # a [MM:SS] a reader can check


class StewardTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-stw-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        self.addCleanup(self.td.cleanup)
        _meeting(self.c, "m1", VZ, 6, "2026-05-12")
        _meeting(self.c, "m2", VZ, 6, "2026-05-19")
        for iid, name, kw in (("iss:a", "Vision Zero", ["vision zero"]),
                              ("iss:b", "Traffic Safety", ["traffic fatalities"])):
            self.c.upsert_issue({"id": iid, "town": "Brookline", "status": "active",
                                 "name": name, "aliases": kw, "keywords": kw,
                                 "origin": "auto"})
            issues.reassign_issue(self.c, iid)

    def test_merge_folds_aliases_and_tombstones_source(self):
        merged = self.c.merge_issues(["iss:b"], "iss:a")
        self.assertIn("traffic fatalities", [a.lower() for a in merged["aliases"]])
        # the source survives as a tombstone that points home (the record
        # remembers its own edits), not a silent deletion
        src = self.c.get_issue("iss:b")
        self.assertEqual(src["status"], "merged")
        self.assertEqual(src["merged_into"], "iss:a")

    def test_split_off_meeting_creates_new_issue(self):
        new = issues.split_off_meeting(self.c, "iss:a", "m1")
        self.assertIsNotNone(new)
        # the split issue holds only m1; the original keeps m2
        self.assertEqual({n["meeting_id"] for n in self.c.issue_appearances(new["id"])},
                         {"m1"})
        self.assertNotIn("m1", {n["meeting_id"]
                                for n in self.c.issue_appearances("iss:a")})

    def test_rename_with_aliases_reassigns(self):
        self.c.rename_issue("iss:a", "Zero Deaths", ["vision zero", "zero deaths"])
        issues.reassign_issue(self.c, "iss:a")
        iss = self.c.get_issue("iss:a")
        self.assertEqual(iss["name"], "Zero Deaths")
        self.assertEqual(iss["origin"], "steward")


class MintDigestTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-mem-mint-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        self.addCleanup(self.td.cleanup)
        _meeting(self.c, "m1", GOLF, 6, "2026-05-12")

    def test_mint_new_issue_from_query_seeds_and_follows(self):
        res = issues.mint_from_query(self.c, "golf course lighting", "Brookline")
        self.assertFalse(res["attached"])
        self.assertGreaterEqual(res["seeded"], 1)
        self.assertIsNotNone(self.c.get_thread(res["issue_id"]))   # minting follows

    def test_mint_attaches_to_near_existing_issue(self):
        self.c.upsert_issue({"id": "iss:golf", "town": "Brookline", "status": "active",
                             "name": "Golf Course", "aliases": ["golf course"],
                             "keywords": ["golf course"], "origin": "auto"})
        issues.reassign_issue(self.c, "iss:golf")
        res = issues.mint_from_query(self.c, "golf course lighting", "Brookline")
        self.assertTrue(res["attached"])
        self.assertEqual(res["issue_id"], "iss:golf")

    def test_digest_splits_active_and_quiet(self):
        self.c.upsert_issue({"id": "iss:golf", "town": "Brookline", "status": "active",
                             "name": "Golf Course", "aliases": ["golf course"],
                             "keywords": ["golf course"], "origin": "auto"})
        self.c.follow("iss:golf")
        d = issues.digest(self.c)
        self.assertEqual(d["threads"], 1)
        self.assertEqual(d["quiet"], 1)              # followed, no new resurfacing
        self.assertIn("Still watching", d["markdown"])


if __name__ == "__main__":
    unittest.main()
