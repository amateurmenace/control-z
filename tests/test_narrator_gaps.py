"""Narrator's maps — gaps, budgets, stillness, the cue plan. Pure math,
no video, no models."""

import unittest

from narrator import gaps


def segs(*rows):
    return [{"start": s, "end": e, "text": t} for s, e, t in rows]


class TestSpeechSpans(unittest.TestCase):
    def test_merge_within_breath(self):
        spans = gaps.speech_spans(segs((0, 2, "a"), (2.3, 4, "b"),
                                       (6, 7, "c")))
        self.assertEqual(spans, [(0.0, 4.0), (6.0, 7.0)])

    def test_empty_and_zero_length_dropped(self):
        self.assertEqual(gaps.speech_spans(segs((0, 2, "  "), (3, 3, "x"))),
                         [])

    def test_bracket_markers_are_air_not_speech(self):
        spans = gaps.speech_spans(segs((0, 8, "[Music]"), (8, 10, "hello"),
                                       (10, 12, "(applause)")))
        self.assertEqual(spans, [(8.0, 10.0)])
        g = gaps.gap_map(segs((0, 8, "[Music]"), (8, 10, "words words")),
                         duration=10)
        self.assertEqual(len(g), 1)     # the music IS the gap
        self.assertEqual(g[0]["start"], 0.25)


class TestGapMap(unittest.TestCase):
    def test_lead_mid_and_tail_gaps(self):
        g = gaps.gap_map(segs((10, 20, "talk"), (25, 30, "more")),
                         duration=40, min_gap=2.0)
        self.assertEqual(len(g), 3)
        lead, mid, tail = g
        self.assertEqual(lead["start"], 0.25)          # edge pad
        self.assertEqual(lead["end"], 9.75)
        self.assertEqual(mid["start"], 20.25)
        self.assertEqual(tail["end"], 39.75)
        self.assertEqual(lead["words_budget"], int(9.5 * gaps.WPS))

    def test_short_pauses_are_not_gaps(self):
        g = gaps.gap_map(segs((0, 10, "a"), (11.5, 20, "b")), duration=20)
        self.assertEqual(g, [])   # 1.5s minus pads is under min_gap

    def test_silence_only_program(self):
        g = gaps.gap_map([], duration=30)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["end"], 29.75)

    def test_fits_budget(self):
        self.assertTrue(gaps.fits("a wide shot of the chamber", 3.0))
        self.assertFalse(gaps.fits(" ".join(["word"] * 30), 3.0))


class TestShots(unittest.TestCase):
    def test_shot_seconds(self):
        self.assertEqual(gaps.shot_seconds([(0, 60), (60, 90)], fps=30),
                         [(0.0, 2.0), (2.0, 3.0)])

    def test_shot_motion_windows(self):
        diffs = [0.1, 0.1, 0.5, 0.0]   # between frames 0-1,1-2,2-3,3-4
        m = gaps.shot_motion(diffs, [(0, 3), (3, 5)])
        self.assertEqual(m, [0.1, 0.0])

    def test_graphic_shots_need_length_and_stillness(self):
        shots_s = [(0.0, 20.0), (20.0, 25.0), (25.0, 60.0)]
        motion = [0.001, 0.001, 0.4]
        g = gaps.graphic_shots(shots_s, motion, min_dur=12, max_motion=0.012)
        self.assertEqual(g, [{"start": 0.0, "end": 20.0, "dur": 20.0}])


class TestPlanCues(unittest.TestCase):
    def test_gaps_become_scene_cues(self):
        cues = gaps.plan_cues([{"start": 1, "end": 5, "dur": 4,
                                "words_budget": 10}], [])
        self.assertEqual(cues[0]["kind"], "scene")
        self.assertEqual(cues[0]["status"], "empty")
        self.assertTrue(1 <= cues[0]["at"] <= 5)

    def test_graphic_overlapping_gap_upgrades_it(self):
        cues = gaps.plan_cues(
            [{"start": 10, "end": 14, "dur": 4, "words_budget": 10}],
            [{"start": 8, "end": 40, "dur": 32}])
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["kind"], "graphic")
        self.assertGreaterEqual(cues[0]["at"], 8.5)

    def test_gapless_graphic_still_gets_a_cue(self):
        cues = gaps.plan_cues([], [{"start": 5, "end": 30, "dur": 25}])
        self.assertEqual(cues[0]["kind"], "graphic")
        self.assertEqual(cues[0]["words_budget"], 0)   # transcript-only

    def test_wall_to_wall_falls_back_to_shot_cues(self):
        cues = gaps.plan_cues([], [], shots_s=[(0.0, 9.0), (9.0, 19.0)])
        self.assertEqual(len(cues), 2)
        self.assertTrue(all(c["words_budget"] == 0 for c in cues))
        # a real gap map means no fallback fires
        cues2 = gaps.plan_cues(
            [{"start": 1, "end": 5, "dur": 4, "words_budget": 10}], [],
            shots_s=[(0.0, 19.0)])
        self.assertEqual(len(cues2), 1)
        self.assertEqual(cues2[0]["words_budget"], 10)

    def test_sorted_by_start(self):
        cues = gaps.plan_cues(
            [{"start": 50, "end": 55, "dur": 5, "words_budget": 13}],
            [{"start": 5, "end": 30, "dur": 25}])
        self.assertEqual([c["start"] for c in cues], [5, 50])


if __name__ == "__main__":
    unittest.main()
