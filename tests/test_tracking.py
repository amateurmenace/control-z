import unittest

from pivot.tracking import Track, Tracker, iou, select_subject, targets_from_track


def moving_box(i, x0=0.2, dx=0.004, y=0.4, size=0.12):
    return ((x0 + dx * i, y, size, size), 0.9)


class TestIoU(unittest.TestCase):
    def test_identity(self):
        b = (0.1, 0.1, 0.2, 0.2)
        self.assertAlmostEqual(iou(b, b), 1.0)

    def test_disjoint(self):
        self.assertEqual(iou((0, 0, 0.1, 0.1), (0.5, 0.5, 0.1, 0.1)), 0.0)


class TestTracker(unittest.TestCase):
    def test_moving_subject_is_one_track(self):
        tr = Tracker()
        for i in range(0, 100, 2):
            tr.update(i, [moving_box(i)])
        self.assertEqual(len(tr.tracks), 1)
        self.assertEqual(len(tr.tracks[0].frames), 50)

    def test_two_subjects_two_tracks(self):
        tr = Tracker()
        for i in range(0, 60, 2):
            tr.update(i, [moving_box(i, x0=0.15), moving_box(i, x0=0.65)])
        self.assertEqual(len(tr.tracks), 2)

    def test_long_gap_starts_new_track(self):
        tr = Tracker(max_gap=10)
        tr.update(0, [moving_box(0)])
        tr.update(40, [moving_box(0)])
        self.assertEqual(len(tr.tracks), 2)

    def test_fast_motion_caught_by_distance(self):
        tr = Tracker()
        tr.update(0, [((0.20, 0.4, 0.1, 0.1), 0.9)])
        tr.update(2, [((0.29, 0.4, 0.1, 0.1), 0.9)])  # zero IoU, within reach
        self.assertEqual(len(tr.tracks), 1)


class TestSelection(unittest.TestCase):
    def test_prefers_big_central_persistent(self):
        tr = Tracker()
        for i in range(0, 100, 2):
            tr.update(i, [
                ((0.45, 0.3, 0.16, 0.16), 0.9),   # big, central
                ((0.05, 0.3, 0.06, 0.06), 0.9),   # small, edge
            ])
        subject = select_subject(tr.tracks)
        self.assertAlmostEqual(subject.boxes[0][2], 0.16)

    def test_min_detections_filter(self):
        tr = Tracker()
        tr.update(0, [moving_box(0)])
        self.assertIsNone(select_subject(tr.tracks, min_detections=3))


class TestTargets(unittest.TestCase):
    def test_interpolation_between_detections(self):
        track = Track(1)
        track.add(10, (0.2, 0.4, 0.1, 0.1), 0.9)
        track.add(20, (0.4, 0.4, 0.1, 0.1), 0.9)
        t = targets_from_track(track, 0, 30)
        self.assertIsNone(t[0])            # before first detection
        self.assertAlmostEqual(t[10], 0.25)  # box center x
        self.assertAlmostEqual(t[15], 0.35)  # halfway
        self.assertAlmostEqual(t[20], 0.45)
        self.assertIsNone(t[29])           # after last detection

    def test_none_track(self):
        self.assertEqual(targets_from_track(None, 0, 5), [None] * 5)

    def test_shot_slicing(self):
        tr = Tracker()
        for i in range(0, 100, 2):
            tr.update(i, [moving_box(i)])
        sliced = tr.tracks[0].slice(40, 60)
        self.assertTrue(all(40 <= f < 60 for f in sliced.frames))
        self.assertEqual(sliced.tid, tr.tracks[0].tid)


if __name__ == "__main__":
    unittest.main()
