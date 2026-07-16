import unittest

from czcore.shots import cuts_from_diffs, shots_from_cuts


def synthetic_diffs(n_frames=300, cuts=(100, 200), noise=0.02, spike=0.6):
    diffs = [noise] * (n_frames - 1)
    for c in cuts:
        diffs[c - 1] = spike  # diff between frame c-1 and c => cut at frame c
    return diffs


class TestCuts(unittest.TestCase):
    def test_clean_cuts_found(self):
        self.assertEqual(cuts_from_diffs(synthetic_diffs()), [100, 200])

    def test_min_shot_length_suppresses_flash(self):
        diffs = synthetic_diffs(cuts=(100, 104))
        self.assertEqual(cuts_from_diffs(diffs, min_shot_len=12), [100])

    def test_adaptive_rejects_sustained_motion(self):
        # handheld strobe: every diff is huge, so none is a *relative* spike
        diffs = [0.5] * 299
        self.assertEqual(cuts_from_diffs(diffs), [])

    def test_fixed_threshold_mode_still_available(self):
        diffs = [0.5] * 299
        cuts = cuts_from_diffs(diffs, adaptive=False)
        self.assertGreater(len(cuts), 0)

    def test_empty(self):
        self.assertEqual(cuts_from_diffs([]), [])


class TestShotsFromCuts(unittest.TestCase):
    def test_spans_cover_everything(self):
        self.assertEqual(
            shots_from_cuts([100, 200], 300), [(0, 100), (100, 200), (200, 300)]
        )

    def test_no_cuts_one_shot(self):
        self.assertEqual(shots_from_cuts([], 300), [(0, 300)])

    def test_out_of_range_cuts_ignored(self):
        self.assertEqual(shots_from_cuts([0, 300, 400], 300), [(0, 300)])

    def test_zero_frames(self):
        self.assertEqual(shots_from_cuts([10], 0), [])


if __name__ == "__main__":
    unittest.main()
