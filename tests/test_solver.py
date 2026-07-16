"""Golden tests for the Pivot path solver (specs/01-pivot.md).

These pin the *math* — physics caps, overshoot bounds, mode decisions. Re-pinning
any number here requires a CHANGELOG entry (Hush golden policy).
"""

import math
import unittest

from pivot.solver import PRESETS, SolverParams, classify, solve

P = SolverParams()
HW = 0.25  # roomy crop so step/sine tests never touch the frame edges


def caps_ok(centers, p=P, tol=1e-9):
    """|velocity| <= v_max and |acceleration| <= a_max, everywhere."""
    v = [b - a for a, b in zip(centers, centers[1:])]
    a = [b - c for c, b in zip(v, v[1:])]
    return (all(abs(x) <= p.v_max + tol for x in v),
            all(abs(x) <= p.a_max + tol for x in a))


class TestPunch(unittest.TestCase):
    def test_static_target_is_static_crop(self):
        path = solve([0.5] * 200, HW)
        self.assertEqual(path.mode, "punch")
        self.assertTrue(all(c == 0.5 for c in path.centers))
        self.assertTrue(path.is_static)

    def test_outliers_do_not_move_the_punch(self):
        targets = [0.4] * 190 + [0.9] * 10
        path = solve(targets, HW)
        self.assertEqual(path.mode, "punch")
        self.assertAlmostEqual(path.centers[0], 0.4, places=9)

    def test_short_shot_always_punches(self):
        moving = [0.2 + 0.02 * i for i in range(30)]  # big motion, 30 frames @24
        self.assertEqual(classify(moving, 24.0), "punch")

    def test_fps_scales_the_short_shot_rule(self):
        moving = [0.2 + 0.008 * i for i in range(70)]
        self.assertEqual(classify(moving, 60.0), "punch")   # 70 < 120 @60fps
        self.assertEqual(classify(moving, 24.0), "follow")  # 70 >= 48 @24fps

    def test_low_motion_long_shot_punches(self):
        targets = [0.5 + 0.03 * math.sin(i / 9) for i in range(400)]
        self.assertEqual(classify(targets, 24.0), "punch")

    def test_punch_clamps_to_frame(self):
        path = solve([0.05] * 100, 0.3)
        self.assertTrue(all(c == 0.3 for c in path.centers))

    def test_all_missing_targets_center_punch(self):
        path = solve([None] * 100, HW)
        self.assertEqual(path.mode, "punch")
        self.assertTrue(all(c == 0.5 for c in path.centers))

    def test_crop_wider_than_frame_is_center(self):
        path = solve([0.1] * 60, 0.5)
        self.assertTrue(all(c == 0.5 for c in path.centers))


class TestFollow(unittest.TestCase):
    def _step_targets(self, n=300, at=60, a=0.3, b=0.7):
        return [a if i < at else b for i in range(n)]

    def test_step_settles_without_overshoot(self):
        target = 0.7
        path = solve(self._step_targets(), HW, mode="follow")
        self.assertEqual(path.mode, "follow")
        self.assertEqual(path.moves, 1)
        # discrete braking crosses by <= ~4 acceleration quanta (2·a crossing +
        # 2·a reversal), ~0.5% of frame width at defaults — pinned here
        self.assertLessEqual(max(path.centers), target + 4 * P.a_max + 1e-9)
        # settled: last 100 frames parked within settle margin of the target
        for c in path.centers[-100:]:
            self.assertLessEqual(abs(c - target), P.settle + 1e-6)

    def test_step_respects_physics_caps(self):
        path = solve(self._step_targets(), HW, mode="follow")
        v_ok, a_ok = caps_ok(path.centers)
        self.assertTrue(v_ok, "velocity cap violated")
        self.assertTrue(a_ok, "acceleration cap violated")

    def test_anticipation_moves_before_the_subject_arrives(self):
        path = solve(self._step_targets(at=60), HW, mode="follow")
        # lookahead median (12 ahead) sees the step ~6 frames early
        self.assertNotEqual(path.centers[59], path.centers[0])

    def test_jitter_inside_deadzone_never_moves(self):
        targets = [0.5 + (0.02 if i % 2 else -0.02) for i in range(300)]
        path = solve(targets, HW, mode="follow")
        self.assertEqual(path.moves, 0)
        self.assertEqual(len(set(path.centers)), 1)

    def test_slow_sine_is_tracked_with_bounded_lag(self):
        n, amp = 480, 0.25
        targets = [0.5 + amp * math.sin(2 * math.pi * i / 240) for i in range(n)]
        path = solve(targets, HW)
        self.assertEqual(path.mode, "follow")
        self.assertGreaterEqual(path.moves, 1)
        v_ok, a_ok = caps_ok(path.centers)
        self.assertTrue(v_ok and a_ok)
        worst = max(abs(c - t) for c, t in zip(path.centers, targets))
        self.assertLess(worst, amp / 2, "camera lost the subject")

    def test_missing_targets_are_filled_not_fatal(self):
        targets = ([0.3] * 80 + [None] * 15 + [0.7] * 105)
        path = solve(targets, HW, mode="follow")
        self.assertEqual(len(path.centers), len(targets))
        self.assertTrue(all(math.isfinite(c) for c in path.centers))
        self.assertLessEqual(abs(path.centers[-1] - 0.7), P.settle + 1e-6)

    def test_path_stays_inside_frame(self):
        targets = [0.02] * 100 + [0.98] * 200
        path = solve(targets, 0.2, mode="follow")
        self.assertGreaterEqual(min(path.centers), 0.2 - 1e-9)
        self.assertLessEqual(max(path.centers), 0.8 + 1e-9)

    def test_presets_are_sane(self):
        for name, p in PRESETS.items():
            self.assertGreater(p.v_max, 0, name)
            self.assertGreater(p.deadzone, p.settle, name)


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_path(self):
        targets = [0.5 + 0.2 * math.sin(i / 30) + (0.05 if i % 7 == 0 else 0)
                   for i in range(400)]
        a = solve(targets, HW)
        b = solve(targets, HW)
        self.assertEqual(a.mode, b.mode)
        self.assertEqual(a.centers, b.centers)


if __name__ == "__main__":
    unittest.main()
