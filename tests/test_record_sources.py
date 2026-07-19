"""The intake rules — what a town's channel may and may not put in the record.

These are the cost lever, so they are tested like one. Every fixture title in
here is a real title, taken from a live poll of the actual channels on
2026-07-19, because the whole failure mode this module exists to prevent is a
rule that looks sensible and does not match what a town actually posts.

Three of the four rule bugs pinned below were found that way and not by
reading: Boston's council titles committee sessions "<Name> on <Date>" and
never say "Committee on"; one June session spells it "Ways & Means" where the
July one says "and"; and City TV publishes a family of language-prefixed PSAs
that no keyword list would have anticipated.

No network, no database — `sources` is pure functions over a title and a
config, which is exactly what lets the steward console preview a rule change
before it changes anything.
"""

import unittest

from record import sources

# Verbatim from a live poll, 2026-07-19.
BROOKLINE_FEED = [
    {"title": "Transportation Board Meeting - July 15, 2026", "published": "2026-07-16"},
    {"title": "TV on TV - Macy Lee", "published": "2026-07-16"},
    {"title": "A 35 Year Celebration: Farewell to Brookline's Party Favor", "published": "2026-07-16"},
    {"title": "Brookline Select Board Meeting - July 14, 2026", "published": "2026-07-15"},
    {"title": "Brookline Select Board Meeting - July 14, 2026", "published": "2026-07-15"},
    {"title": "School Committee Meeting - June 29, 2026", "published": "2026-06-30"},
    {"title": "2026 Runkle Eighth Grade Graduation", "published": "2026-06-20"},
]
BOSTON_CITY_TV_FEED = [
    {"title": "Shaw-Roxbury Branch of Boston Public Library Dedication - July 17", "published": "2026-07-19"},
    {"title": "Stay Cool Indoors", "published": "2026-07-17"},
    {"title": "Boston Licensing Board Voting Hearing 7/16/2026", "published": "2026-07-17"},
    {"title": "BPDA Board of Directors Meeting 7/16/26", "published": "2026-07-17"},
    {"title": "(Spanish) Recycling in the Club", "published": "2026-07-16"},
    {"title": "(Haitian Creole) Recycling in the Club", "published": "2026-07-16"},
    {"title": "Never Leave Children or Pets in Cars", "published": "2026-07-17"},
]
BOSTON_COUNCIL_FEED = [
    {"title": "Ways and Means on July 15, 2026", "published": "2026-07-16"},
    {"title": "Boston City Council Meeting on July 8, 2026", "published": "2026-07-09"},
    {"title": "City Services on June 25, 2026", "published": "2026-06-26"},
    {"title": "Ways & Means on June 15, 2026", "published": "2026-06-16"},
    {"title": "Planning, Development, and Transportation on June 25, 2026", "published": "2026-06-26"},
    {"title": "Boston City Council Live Stream", "published": "2026-07-01"},
]


def src(town, i=0):
    return sources.SEEDS[town]["sources"][i]


class ClassifyTest(unittest.TestCase):
    def test_a_meeting_gets_the_body_that_named_it(self):
        v = sources.classify("Brookline Select Board Meeting - July 14, 2026",
                             src("Brookline"))
        self.assertEqual(v["verdict"], "file")
        self.assertEqual(v["body"], "Select Board")

    def test_default_deny_is_the_whole_design(self):
        """A title no rule names does NOT enter the record. This is the cost
        lever: ingest spends per meeting, so anything that reaches it must have
        been named by a human first."""
        v = sources.classify("Some Entirely New Committee", src("Brookline"))
        self.assertEqual(v["verdict"], "unmatched")
        self.assertIsNone(v["body"])

    def test_an_exclusion_beats_a_body_rule(self):
        """Specific 'not a meeting' must win, or a loose body pattern quietly
        swallows the retirement party."""
        v = sources.classify("TV on TV - Macy Lee", src("Brookline"))
        self.assertEqual(v["verdict"], "excluded")

    def test_the_language_prefixed_psas_are_a_shape_not_a_list(self):
        """City TV publishes 'Recycling in the Club' in five languages. Matching
        them one by one would miss the sixth."""
        s = src("Boston", 0)
        for lang in ("Spanish", "Vietnamese", "Simplified Chinese",
                     "Cabo Verdean Creole", "Somali"):
            v = sources.classify(f"({lang}) Recycling in the Club", s)
            self.assertEqual(v["verdict"], "excluded", lang)

    def test_boston_committees_are_matched_by_shape_not_by_the_word_committee(self):
        """The Council titles committee sessions '<Name> on <Date>' and never
        says 'Committee on'. A literal rule missed five real committees in one
        live poll."""
        s = src("Boston", 1)
        for title in ("City Services on June 25, 2026",
                      "Human Services on June 29, 2026",
                      "Planning, Development, and Transportation on June 25, 2026",
                      "Housing and Community Development on June 12, 2026"):
            v = sources.classify(title, s)
            self.assertEqual(v["verdict"], "file", title)
            self.assertEqual(v["body"], "City Council Committee")

    def test_ampersand_and_the_word_and_are_the_same_committee(self):
        s = src("Boston", 1)
        a = sources.classify("Ways and Means on July 15, 2026", s)
        b = sources.classify("Ways & Means on June 15, 2026", s)
        self.assertEqual(a["verdict"], "file")
        self.assertEqual(b["verdict"], "file")
        self.assertEqual(a["body"], b["body"])

    def test_the_council_meeting_proper_outranks_the_committee_shape(self):
        """Order matters: 'Boston City Council Meeting on July 8, 2026' also
        matches the committee date-shape, so the specific rule must come first."""
        v = sources.classify("Boston City Council Meeting on July 8, 2026",
                             src("Boston", 1))
        self.assertEqual(v["body"], "City Council")

    def test_a_live_stream_placeholder_is_not_a_meeting(self):
        v = sources.classify("Boston City Council Live Stream", src("Boston", 1))
        self.assertEqual(v["verdict"], "excluded")


class PlanTest(unittest.TestCase):
    def test_the_real_brookline_feed_sorts_correctly(self):
        p = sources.plan(BROOKLINE_FEED, src("Brookline"))
        self.assertEqual({r["body"] for r in p["file"]},
                         {"Select Board", "School Committee", "Transportation Board"})
        self.assertEqual(len(p["file"]), 4)          # incl. the double-posted one
        self.assertGreaterEqual(len(p["excluded"]), 2)

    def test_the_real_boston_feeds_leave_nothing_unnamed(self):
        """Both Boston sources reached zero unmatched after tuning. If a future
        edit reintroduces one, that is a rule that stopped matching."""
        for feed, s in ((BOSTON_CITY_TV_FEED, src("Boston", 0)),
                        (BOSTON_COUNCIL_FEED, src("Boston", 1))):
            p = sources.plan(feed, s)
            self.assertEqual(p["unmatched"], [], [r["title"] for r in p["unmatched"]])

    def test_the_cap_reports_what_it_held_back(self):
        """A cap that silently drops is a cap that loses meetings. It is a spend
        ceiling, and what it defers has to be visible."""
        s = {**src("Boston", 1), "max_per_poll": 2}
        p = sources.plan(BOSTON_COUNCIL_FEED, s)
        self.assertEqual(len(p["file"]), 2)
        self.assertEqual(p["capped"], len(p["over_cap"]))
        self.assertGreater(p["capped"], 0)

    def test_since_keeps_a_backfill_from_reaching_back_forever(self):
        s = {**src("Boston", 1), "since": "2026-07-01"}
        p = sources.plan(BOSTON_COUNCIL_FEED, s)
        self.assertTrue(p["too_old"])
        self.assertTrue(all(r["published"][:10] >= "2026-07-01" for r in p["file"]))

    def test_nothing_is_filed_without_a_body(self):
        """The reader's body filter depends on this: a meeting cannot arrive
        without a body, because the rule that let it in is the one that names
        the body."""
        for feed, s in ((BROOKLINE_FEED, src("Brookline")),
                        (BOSTON_CITY_TV_FEED, src("Boston", 0)),
                        (BOSTON_COUNCIL_FEED, src("Boston", 1))):
            for r in sources.plan(feed, s)["file"]:
                self.assertTrue(r["body"], r["title"])


class SuggestTest(unittest.TestCase):
    def test_unmatched_titles_become_offered_rules(self):
        """A miss must not be silent. What the town posts that the record has
        no name for is how the taxonomy gets written."""
        unmatched = [{"title": "Age Friendly Cities Ep 61 - Charles Carey"},
                     {"title": "Age Friendly Cities Episode 60"},
                     {"title": "One Off Thing"}]
        out = sources.suggest_rules(unmatched, min_count=2)
        self.assertTrue(out)
        self.assertIn("age friendly cities", out[0]["body"].lower())
        self.assertEqual(out[0]["seen"], 2)

    def test_a_single_sighting_is_not_yet_a_body(self):
        self.assertEqual(sources.suggest_rules([{"title": "A Lone Video"}]), [])


class ConfigTest(unittest.TestCase):
    def test_a_bad_pattern_is_caught_before_it_reaches_a_nightly_job(self):
        bad = {"bodies": [{"body": "X", "match": "((("}], "exclude": ["[z-a]"]}
        self.assertEqual(len(sources.bad_patterns(bad)), 2)
        self.assertEqual(sources.bad_patterns(src("Brookline")), [])

    def test_a_bad_pattern_still_classifies_rather_than_crashing(self):
        """If one ever gets past the guard, a poll degrades to literal matching
        instead of taking the whole town's intake down."""
        v = sources.classify("(((", {"bodies": [{"body": "X", "match": "((("}]})
        self.assertEqual(v["verdict"], "file")

    def test_bodies_come_from_config_not_from_the_corpus(self):
        """So a body with no meetings yet still reads as a thing that exists."""
        self.assertIn("School Committee", sources.bodies_of(src("Boston", 0)))
        self.assertIn("BPDA", sources.bodies_of(src("Boston", 0)))

    def test_both_towns_seed_cleanly(self):
        for slug in ("Brookline", "Boston"):
            town = sources.SEEDS[slug]
            self.assertTrue(town["sources"])
            for s in town["sources"]:
                self.assertTrue(s["url"] and s["bodies"])
                self.assertEqual(sources.bad_patterns(s), [])


if __name__ == "__main__":
    unittest.main()
