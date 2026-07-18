"""The Vote Ledger — roll-call extraction, roster gating, per-member records.

Hermetic and network-free. A synthetic roll call (in the ASR shape a real
Brookline meeting produces — "Aye" heard as "I.", names on their own lines) is
read back into structured votes, and the officials-only guarantee is checked:
without a roster, junk single-word tokens never become an official's vote.
"""

import tempfile
import unittest
from pathlib import Path

from memory import votes
from memory.store import Corpus

# a roll call as the ASR renders it: a trigger, then Name / "I." pairs, then a
# resolution. The first token+name segment ("I. John Warren,") is the ASR
# merging a prior echo with the next voter.
ROLL = [
    {"start": 100.0, "end": 101.0, "text": "I move approval of the minutes."},
    {"start": 101.0, "end": 102.0, "text": "All in favor, please indicate by saying"},
    {"start": 102.0, "end": 103.0, "text": "I. John Warren,"},
    {"start": 103.0, "end": 104.0, "text": "I."},
    {"start": 104.0, "end": 105.0, "text": "David Pearlman,"},
    {"start": 105.0, "end": 106.0, "text": "I."},
    {"start": 106.0, "end": 107.0, "text": "Michael Stone,"},
    {"start": 107.0, "end": 108.0, "text": "No."},
    {"start": 108.0, "end": 109.0, "text": "The motion passes."},
]
ROSTER = ["John Warren", "David Pearlman", "Michael Stone", "Bernard Greene"]


class ExtractTest(unittest.TestCase):
    def test_reads_a_roll_call_with_roster(self):
        vs = votes.extract(ROLL, ROSTER)
        self.assertEqual(len(vs), 1)
        v = vs[0]
        names = {r["name"]: r["vote"] for r in v["roll"]}
        self.assertEqual(names.get("John Warren"), "yes")
        self.assertEqual(names.get("David Pearlman"), "yes")
        self.assertEqual(names.get("Michael Stone"), "no")
        self.assertEqual(v["tally"], "2–1")
        self.assertEqual(v["outcome"], "passes")
        # every roll entry is a receipt — a timestamp and the spoken word
        self.assertTrue(all("t" in r and "quote" in r for r in v["roll"]))

    def test_roster_canonicalizes_a_garbled_name(self):
        garbled = ROLL[:]
        garbled[4] = {"start": 104.0, "end": 105.0, "text": "David Perlman,"}
        vs = votes.extract(garbled, ROSTER)
        names = [r["name"] for r in vs[0]["roll"]]
        self.assertIn("David Pearlman", names)   # Perlman -> Pearlman via roster

    def test_officials_only_without_roster_records_nothing(self):
        # THE COVENANT (officials-only by construction): without a roster to
        # verify a name against, we never manufacture an official — not even
        # from full, clean-looking names. A misheard public-comment speaker
        # inside a roll-call window must never become a voting record.
        ungated = votes.extract(ROLL, [])
        self.assertEqual(ungated, [])
        junk = [
            {"start": 10.0, "end": 11.0, "text": "All in favor, please indicate by saying"},
            {"start": 11.0, "end": 12.0, "text": "Sarah Chen,"},
            {"start": 12.0, "end": 13.0, "text": "I."},
        ]
        self.assertEqual(votes.extract(junk, []), [])

    def test_asr_aye_echo_is_stripped_from_the_name(self):
        # the ASR merges a prior "Aye" echo onto the next voter ("I. John
        # Warren,") — the echo must not fragment the official's record
        self.assertEqual(votes._looks_like_name("I. John Warren,"), "John Warren")
        vs = votes.extract(ROLL, ROSTER)
        self.assertIn("John Warren", [r["name"] for r in vs[0]["roll"]])
        self.assertNotIn("I. John Warren", [r["name"] for r in vs[0]["roll"]])

    def test_vote_timestamps_floor_to_a_whole_second(self):
        # the rounding law: a vote at 12.97s must int()-floor to 12 (its
        # transcript anchor), never round up to 13 and mint a dead #t link
        rc = [
            {"start": 100.0, "end": 101.0, "text": "All in favor, please indicate by saying"},
            {"start": 101.0, "end": 102.0, "text": "John Warren,"},
            {"start": 102.97, "end": 103.4, "text": "I."},
            {"start": 103.5, "end": 104.0, "text": "David Pearlman,"},
            {"start": 104.97, "end": 105.4, "text": "I."}]
        vs = votes.extract(rc, ROSTER)
        for r in vs[0]["roll"]:
            # int() of the stored float lands on the whole-second anchor
            self.assertEqual(int(r["t"]), int(float(r["t"])))
            self.assertLess(r["t"] - int(r["t"]), 1.0)

    def test_no_trigger_no_vote(self):
        chatter = [{"start": 0.0, "end": 5.0,
                    "text": "We had a good discussion about the budget."}]
        self.assertEqual(votes.extract(chatter, ROSTER), [])


class StoreAndRecordsTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-votes-")
        self.c = Corpus(db_path=str(Path(self.td.name) / "corpus.db"))
        self.c.upsert_meeting({"id": "m1", "status": "live", "town": "Brookline",
                               "body": "Select Board", "date": "2026-05-19",
                               "title": "Select Board", "video_id": "vid1"})
        self.c.replace_segments("m1", ROLL)

    def tearDown(self):
        self.td.cleanup()

    def test_replace_and_read_votes(self):
        vs = votes.extract(ROLL, ROSTER)
        self.c.replace_votes("m1", vs)
        got = self.c.votes_of("m1")
        self.assertEqual(len(got), 1)
        self.assertIsInstance(got[0]["roll"], list)   # JSON round-trip
        # all_votes only surfaces live meetings, and carries the meeting meta
        allv = self.c.all_votes("Brookline")
        self.assertEqual(len(allv), 1)
        self.assertEqual(allv[0]["date"], "2026-05-19")

    def test_member_records_are_per_official(self):
        self.c.replace_votes("m1", votes.extract(ROLL, ROSTER))
        recs = votes.member_records(self.c, "Brookline")
        by_name = {r["name"]: r for r in recs}
        self.assertEqual(by_name["Michael Stone"]["no"], 1)
        self.assertEqual(by_name["John Warren"]["yes"], 1)
        # each record carries the receipt trail
        self.assertTrue(all("meeting_id" in v for v in by_name["John Warren"]["votes"]))

    def test_forget_meeting_takes_its_votes(self):
        self.c.replace_votes("m1", votes.extract(ROLL, ROSTER))
        self.c.forget("m1")
        self.assertEqual(self.c.all_votes(), [])


if __name__ == "__main__":
    unittest.main()
