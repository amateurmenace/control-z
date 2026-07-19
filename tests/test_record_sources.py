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


class SpendCapTest(unittest.TestCase):
    """The cap is the one number standing between a loop and a bill.

    It is tested because a documented ceiling that nothing enforces is exactly
    the failure this project keeps naming — a hiddenimport is not an
    installation, and a number in a runbook is not a limit.
    """

    def test_the_rate_is_pinned_and_the_arithmetic_is_right(self):
        from record import embed_neural as en
        self.assertEqual(en.USD_PER_MILLION_TOKENS, 0.15)   # verified 2026-07-19
        # 1M segments x 60 tokens = 60M tokens = $9.00
        self.assertAlmostEqual(en.estimate_usd(1_000_000), 9.0, places=4)
        self.assertEqual(en.estimate_usd(0), 0.0)

    def test_the_real_backfill_is_nowhere_near_the_cap(self):
        """72,816 segments — the whole imported record — costs well under a
        dollar. If this ever approaches the cap, either the corpus grew by two
        orders of magnitude or the pinned rate went stale."""
        from record import embed_neural as en
        self.assertLess(en.estimate_usd(72_816), 1.0)

    def test_the_cap_defaults_to_a_hundred_and_reads_the_environment(self):
        from unittest import mock
        from record.settings import Settings
        self.assertEqual(Settings().spend_cap_usd, 100.0)
        with mock.patch.dict("os.environ", {"RECORD_SPEND_CAP_USD": "5"}):
            self.assertEqual(Settings().spend_cap_usd, 5.0)

    def test_backfill_refuses_before_buying_when_the_ledger_is_over(self):
        """Checked BEFORE the batch, against the ledger rather than a local
        counter — so it survives a restart and two jobs running at once. A cap
        enforced after the purchase is a receipt."""
        from unittest import mock

        from record import embed_neural as en

        class Ledger:
            """A corpus whose ledger already shows more spent than the cap."""
            def _con(self):
                raise AssertionError("must not reach the database to decide")

        with mock.patch.object(en, "available", lambda: True), \
             mock.patch.object(en, "spent_usd", lambda c: 999.0):
            out = en.backfill(Ledger(), verbose=False, cap_usd=1.0)
        self.assertTrue(out["available"])
        self.assertEqual(out["embedded"], 0)


class NightlyCliTest(unittest.TestCase):
    """The command the scheduler runs, and the two ways to ask for nothing.

    `--source` used to be `required=True`, which meant the nightly job the
    runbook documented (`--all-towns`) would have exited on argparse before
    touching the database — a scheduler firing at 03:00 into an error nobody
    was awake to read. The flags are mutually exclusive rather than merely
    both-accepted, because "poll this one feed, and also all of them" has no
    sensible reading and guessing at one is how a poll files a town's meetings
    under the wrong body.

    No network and no database: argparse rejects both shapes before the
    connector imports a store.
    """

    def parse(self, argv):
        from record.connectors import youtube
        return youtube.main(argv)

    def test_asking_for_neither_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            self.parse([])
        self.assertEqual(e.exception.code, 2)

    def test_asking_for_both_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            self.parse(["--source", "UCabc", "--all-towns"])
        self.assertEqual(e.exception.code, 2)

    def test_all_towns_reaches_the_town_loop(self):
        """It gets past argparse and asks the database for live towns — which
        is the whole point, and the thing `required=True` prevented."""
        from unittest import mock

        from record.connectors import youtube
        with mock.patch.object(youtube, "_poll_all_towns",
                               lambda args: 0) as _:
            self.assertEqual(self.parse(["--all-towns"]), 0)


class PollObeysTheRulesTest(unittest.TestCase):
    """The preview and the poll must be the same decision, computed once.

    They were not. `sources.plan` — every rule in this file, every exclusion
    tuned against a live channel — was reached by exactly one caller: the
    console's preview. `connectors.youtube.discover` filed every entry the feed
    returned. So the console promised "would file 4" and the first real nightly
    run filed 30, PSAs and ribbon cuttings included, across three channels.

    Nothing caught it because the rules were tested as pure functions and the
    connector was tested for filing, and no test asked whether the connector
    used the rules. That is what this class is: the seam, asserted.

    `max_per_poll` is the same story. It is documented as the thing that makes
    an unattended nightly poll safe, and it lived only in `plan`.
    """

    def feed(self, titles):
        # Real-shaped ids (11 chars of YouTube's alphabet) — `canon` falls back
        # to `url:<the whole thing>` for anything else, which would quietly test
        # the wrong path.
        return [{"title": t, "url": f"https://www.youtube.com/watch?v=vid{i:08d}",
                 "video_id": f"vid{i:08d}", "published": "2026-07-16"}
                for i, t in enumerate(titles)]

    def discover(self, titles, rules, **kw):
        """Run `discover` over a fixed feed with the database stubbed out."""
        from unittest import mock

        from record.connectors import youtube

        class NothingKnown:
            """A corpus that has never seen anything and records what is filed."""
            def __init__(self):
                self.filed = []

            def find_by_url_canon(self, key):
                return None

        corpus = NothingKnown()
        items = self.feed(titles)
        with mock.patch.object(youtube, "poll", lambda *a, **k: items), \
             mock.patch.object(youtube, "_submission_for", lambda c, k: None), \
             mock.patch.object(youtube, "captions_probe",
                               lambda v, **k: {"captions": True, "note": ""}), \
             mock.patch.object(youtube, "_file_submission",
                               lambda c, sub: corpus.filed.append(sub) or True):
            out = youtube.discover(corpus, "Boston", "", "UCx", rules=rules, **kw)
        return out, corpus.filed

    # -- default-deny actually denies --------------------------------------

    def test_a_poll_files_only_what_a_rule_names(self):
        """The exact failure: PSAs and ceremonies entering the queue."""
        s = src("Boston", 0)
        out, filed = self.discover([
            "Boston Licensing Board Voting Hearing 7/16/2026",   # a rule names it
            "(Spanish) Recycling in the Club",                   # excluded
            "Peace Park Ribbon Cutting Ceremony",                # excluded
            "Some Entirely New Committee",                       # unmatched
        ], s)
        self.assertEqual(out["filed"], 1)
        self.assertEqual(out["excluded"], 2)
        self.assertEqual(out["unmatched"], 1)
        self.assertEqual([f["url_canon"] for f in filed],
                         ["youtube:vid00000000"])

    def test_the_poll_files_exactly_what_the_preview_promised(self):
        """One decision, computed once. If these ever diverge, the console is
        lying about what a poll will cost."""
        s = src("Boston", 0)
        titles = ["Boston Licensing Board Voting Hearing 7/16/2026",
                  "BPDA Board of Directors Meeting 7/16/26",
                  "(Haitian Creole) Recycling in the Club",
                  "Stay Cool Indoors",
                  "Madison Park Roundtable"]
        promised = sources.plan(self.feed(titles), s)["file"]
        out, filed = self.discover(titles, s)
        self.assertEqual(out["filed"], len(promised))
        self.assertEqual([f["url_canon"] for f in filed],
                         [f"youtube:{p['video_id']}" for p in promised])

    def test_the_matched_rule_names_the_body_not_the_caller(self):
        """One channel carries several bodies; stamping one string on all of
        them files the School Committee's meetings under the BPDA."""
        s = src("Boston", 0)
        _, filed = self.discover([
            "Boston School Committee Meeting 7/15/2026",
            "BPDA Board of Directors Meeting 7/16/26"], s)
        self.assertEqual([f["body"] for f in filed],
                         ["School Committee", "BPDA"])

    # -- the cap that makes a scheduler safe to leave alone -----------------

    def test_max_per_poll_holds_a_backlog_back(self):
        """Documented as the reason a nightly poll is safe unattended, and it
        lived only in the preview."""
        s = {**src("Boston", 0), "max_per_poll": 2}
        out, filed = self.discover(
            ["Boston Licensing Board Voting Hearing 7/1{}/2026".format(i)
             for i in range(5)], s)
        self.assertEqual(out["filed"], 2)
        self.assertEqual(out["capped"], 3)
        self.assertEqual(len(filed), 2)

    # -- the manual path keeps its meaning ---------------------------------

    def test_without_rules_the_human_who_named_the_body_is_the_rule(self):
        """`--source --body` is a person pointing at one feed. That naming is
        the rule, and the connector must not start second-guessing it."""
        from unittest import mock

        from record.connectors import youtube
        filed = []
        items = self.feed(["Anything At All", "Also This"])

        class NothingKnown:
            def find_by_url_canon(self, key):
                return None

        with mock.patch.object(youtube, "poll", lambda *a, **k: items), \
             mock.patch.object(youtube, "_submission_for", lambda c, k: None), \
             mock.patch.object(youtube, "_file_submission",
                               lambda c, sub: filed.append(sub) or True):
            out = youtube.discover(NothingKnown(), "Brookline", "Select Board",
                                   "UCx", check_captions=False)
        self.assertEqual(out["filed"], 2)
        self.assertEqual({f["body"] for f in filed}, {"Select Board"})
