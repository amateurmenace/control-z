import unittest

from czcore.moments import KEYWORD_CLASSES
from highlighter.highlights import (blend_energy, build_reel, hits_in,
                                    parse_vtt, score_segments, transcript_dict)


def seg(start, end, text):
    return {"start": start, "end": end, "text": text}


MEETING = [
    seg(0, 5, "Call to order, roll call please."),
    seg(10, 18, "I move that we approve the $2 million budget for the crosswalk!"),
    seg(18, 24, "Second the motion. All in favor?"),
    seg(24, 30, "The motion carries, unanimous. [applause]"),
    seg(40, 52, "Now the long weather report, nothing notable here at all."),
]


class TestKeywordBoundary(unittest.TestCase):
    """hits_in matches word-like keywords on a *leading* word boundary, so a
    keyword reaches its own inflections but never a longer word that merely
    contains it — the fix that stops a celebration reading as a motion."""

    DECIDE = KEYWORD_CLASSES["decision"][1]

    def test_keyword_reaches_its_inflections(self):
        # a leading boundary with an open suffix: "vote" reaches votes/voted,
        # "unanimous" reaches unanimously, "adopt" reaches adoption — the
        # record's real language survives (one keyword can cover several forms)
        self.assertEqual(set(hits_in("and the chair votes I", self.DECIDE)),
                         {"vote"})
        self.assertEqual(set(hits_in("they voted to adopt it", self.DECIDE)),
                         {"vote", "voted", "adopt"})
        self.assertIn("unanimous", hits_in("passed unanimously last night",
                                           self.DECIDE))
        self.assertIn("adopt", hits_in("the board's adoption of the plan",
                                       self.DECIDE))

    def test_keyword_never_reaches_a_word_that_merely_contains_it(self):
        # devoted / emotion / commotion / emotional / promotion — the exact
        # substring false positives that read a celebration as a decision
        for phrase in ("staff who have devoted three decades", "a stand-up, "
                       "emotion, and comedy", "a commotion in the hallway",
                       "I'll try not to get emotional", "up for promotion"):
            self.assertEqual(hits_in(phrase, self.DECIDE), [],
                             f"a decision keyword leaked into {phrase!r}")

    def test_symbolic_keywords_stay_substring(self):
        # "$" and "[applause]" open on punctuation — a leading \b would never
        # fire, so they keep literal substring matching
        money = KEYWORD_CLASSES["money"][1]
        react = KEYWORD_CLASSES["reaction"][1]
        self.assertIn("$", hits_in("it will cost $2 million", money))
        self.assertIn("[applause]", hits_in("carries [applause]", react))

    def test_score_segments_ignores_the_substring_false_positive(self):
        # a celebration no longer scores as a decision, a real motion still does
        scored = {s["text"]: s for s in score_segments([
            seg(0, 6, "staff who have devoted three decades to our schools"),
            seg(6, 12, "I move that we adopt the budget, second the motion")])}
        celebration = scored["staff who have devoted three decades to our schools"]
        self.assertFalse(any("decision" in r for r in celebration["reasons"]))
        motion = scored["I move that we adopt the budget, second the motion"]
        self.assertTrue(any("decision" in r for r in motion["reasons"]))


class TestScoring(unittest.TestCase):
    def test_decisions_outscore_smalltalk(self):
        scored = score_segments(MEETING)
        by_text = {s["text"]: s for s in scored}
        self.assertGreater(by_text[MEETING[3]["text"]]["score"],
                           by_text[MEETING[4]["text"]]["score"])
        self.assertEqual(by_text[MEETING[0]["text"]]["score"], 0.0)

    def test_scores_normalized_to_unit(self):
        scored = score_segments(MEETING)
        self.assertEqual(max(s["score"] for s in scored), 1.0)

    def test_every_pick_names_its_reasons(self):
        scored = score_segments(MEETING)
        hot = [s for s in scored if s["score"] > 0.3]
        self.assertTrue(hot)
        for s in hot:
            self.assertTrue(s["reasons"], f"no reasons on: {s['text']}")

    def test_user_keywords_matter(self):
        scored = score_segments(
            [seg(0, 4, "the weather is mild"), seg(5, 9, "zoning override discussed")],
            extra_keywords=["zoning"])
        self.assertGreater(scored[1]["score"], scored[0]["score"])
        self.assertIn("your keyword: “zoning”", scored[1]["reasons"])


class TestReel(unittest.TestCase):
    def test_no_overlapping_picks_after_merge_growth(self):
        # regression: a merge could grow a pick into a neighbor it was never
        # compared against, leaving overlapping cuts in the reel
        picks = build_reel(score_segments(MEETING), target=30)
        for a, b in zip(picks, picks[1:]):
            self.assertGreater(b["start"], a["end"])

    def test_chronological_and_within_target_ballpark(self):
        picks = build_reel(score_segments(MEETING), target=20)
        self.assertEqual(picks, sorted(picks, key=lambda p: p["start"]))
        total = sum(p["end"] - p["start"] for p in picks)
        self.assertLess(total, 20 + 45)  # one pick may overshoot, never runaway

    def test_min_clip_expansion(self):
        picks = build_reel(score_segments(
            [seg(10, 11, "the motion carries! [applause]")]), target=30, min_clip=4)
        self.assertGreaterEqual(picks[0]["end"] - picks[0]["start"], 4.0)

    def test_energy_blend_marks_loud_moments(self):
        scored = score_segments(MEETING)
        energy = [(t / 2, 0.02) for t in range(0, 104)]
        energy += [(25.0, 0.9), (25.5, 0.95)]  # the applause
        blended = blend_energy(scored, energy)
        loud = next(s for s in blended if s["start"] == 24)
        self.assertTrue(any("room energy" in r for r in loud["reasons"]))


VTT = """WEBVTT
Kind: captions

00:00:00.000 --> 00:00:02.000
<00:00:00.240><c> good</c><00:00:00.480><c> evening</c><00:00:01.100><c> everyone</c>

00:00:02.000 --> 00:00:04.500
good evening everyone

00:00:02.500 --> 00:00:04.500
the<00:00:03.000><c> motion</c><00:00:03.500><c> passes</c>
"""


# YouTube's real auto-caption shape (from a Brookline Select Board VTT): a
# block opens with a one-space line, 10 ms snapshot cues re-show each
# finished line, and every cue carries the previous line above the new words
YT_ROLLING = """WEBVTT
Kind: captions
Language: en

00:10:52.160 --> 00:10:54.870 align:start position:0%
⎵
&gt;&gt; Good<00:10:52.399><c> evening</c><00:10:52.640><c> everyone.</c>

00:10:54.870 --> 00:10:54.880 align:start position:0%
&gt;&gt; Good evening everyone.
⎵

00:10:54.880 --> 00:10:58.470 align:start position:0%
&gt;&gt; Good evening everyone.
Welcome<00:10:56.640><c> to</c><00:10:57.120><c> the</c><00:10:58.079><c> board</c>

00:10:58.470 --> 00:10:58.480 align:start position:0%
Welcome to the board
⎵

00:10:58.480 --> 00:11:01.910 align:start position:0%
Welcome to the board
meeting.<00:10:59.680><c> To</c><00:11:00.079><c> open</c>
""".replace("⎵", " ")   # ⎵ marks the one-space lines


class TestVTT(unittest.TestCase):
    def test_youtube_rolling_lines_come_once_at_their_real_start(self):
        segs = parse_vtt(YT_ROLLING)
        self.assertEqual([s["text"] for s in segs], [
            "&gt;&gt; Good evening everyone.", "Welcome to the board",
            "meeting. To open"])
        # the opening line starts when it was SAID (the one-space line no
        # longer hides it until its snapshot, 2.7 s later)
        self.assertEqual(segs[0]["start"], 652.16)
        self.assertEqual([w["w"] for w in segs[1]["words"]],
                         ["Welcome", "to", "the", "board"])

    def test_whitespace_between_cues_still_ends_a_cue(self):
        # an SRT whose separators carry a stray space: the next cue's index
        # must never ride into the text before it ("Good evening. 2")
        srt = ("1\n00:00:01,000 --> 00:00:03,000\nGood evening.\n \n"
               "2\n00:00:03,000 --> 00:00:05,000\nThe meeting will come to order.\n\t\n")
        self.assertEqual([s["text"] for s in parse_vtt(srt)],
                         ["Good evening.", "The meeting will come to order."])

    def test_hand_made_captions_keep_a_real_repeat_and_a_short_cue(self):
        # no word tags = not YouTube's rolling shape: a roll call's second
        # "Aye." is a second vote, and a 40 ms cue is still a cue
        vtt = ("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCouncilor Smith?\n>> Aye.\n\n"
               "00:00:02.000 --> 00:00:03.000\n>> Aye.\nCouncilor Jones?\n\n"
               "00:00:03.000 --> 00:00:03.040\nNo.\n")
        self.assertEqual([s["text"] for s in parse_vtt(vtt)],
                         ["Councilor Smith? >> Aye.", ">> Aye. Councilor Jones?", "No."])

    def test_rolling_repeats_deduped(self):
        segs = parse_vtt(VTT)
        texts = [s["text"] for s in segs]
        self.assertEqual(texts.count("good evening everyone"), 1)

    def test_word_tags_become_timed_words(self):
        segs = parse_vtt(VTT)
        first = segs[0]
        self.assertEqual([w["w"] for w in first["words"]],
                         ["good", "evening", "everyone"])
        self.assertAlmostEqual(first["words"][0]["s"], 0.24)
        for w in first["words"]:
            self.assertGreater(w["e"], w["s"])

    def test_transcript_dict_is_scribe_shaped(self):
        t = transcript_dict(parse_vtt(VTT), "/x.mp4")
        for key in ("version", "source", "language", "model", "speakers",
                    "segments"):
            self.assertIn(key, t)
        self.assertTrue(str(t["model"]).startswith("captions"))


if __name__ == "__main__":
    unittest.main()
