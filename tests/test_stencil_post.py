import unittest

try:
    import cv2  # noqa: F401
    import numpy as np
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False


@unittest.skipUnless(HAVE_DEPS, "needs numpy+cv2 (pip install -r requirements.txt)")
class TestPostChain(unittest.TestCase):
    def _disk(self, r=20, size=100):
        m = np.zeros((size, size), np.uint8)
        cv2.circle(m, (size // 2, size // 2), r, 255, -1)
        return m

    def test_temporal_majority_kills_single_frame_flicker(self):
        from stencil.post import temporal_majority

        solid = self._disk()
        empty = np.zeros_like(solid)
        # flash frame between two solid frames survives as solid
        self.assertTrue((temporal_majority(solid, empty, solid) == solid).all())
        # lone frame between two empties is removed
        self.assertTrue((temporal_majority(empty, solid, empty) == 0).all())

    def test_grow_shrink_monotonic(self):
        from stencil.post import grow_shrink

        m = self._disk()
        self.assertGreater(int(grow_shrink(m, 4).sum()), int(m.sum()))
        self.assertLess(int(grow_shrink(m, -4).sum()), int(m.sum()))
        self.assertTrue((grow_shrink(m, 0) == m).all())

    def test_feather_preserves_mass_roughly(self):
        from stencil.post import feather

        m = self._disk()
        f = feather(m, 3.0)
        self.assertLess(abs(float(f.sum()) - float(m.sum())) / float(m.sum()), 0.05)
        self.assertGreater(((f > 0) & (f < 255)).sum(), 0)  # actual soft edge

    def test_despeckle_drops_small_islands(self):
        from stencil.post import despeckle

        m = self._disk()
        m[2:5, 2:5] = 255  # 9-px speck
        out = despeckle(m, 64)
        self.assertEqual(int(out[2:5, 2:5].sum()), 0)
        self.assertGreater(int(out.sum()), 0)

    def test_chain_order_and_length(self):
        from stencil.post import PostParams, apply_chain

        masks = [self._disk() for _ in range(5)]
        out = list(apply_chain(masks, PostParams(grow=2, feather=2.0)))
        self.assertEqual(len(out), 5)


class TestPromptGrouping(unittest.TestCase):
    """Regression: every point for a frame+object must go in ONE SAM2 call.

    SAM2 clears old points per call, so feeding them individually kept only the
    last one — an exclude point alone produced an empty matte (found 2026-07-16
    while re-shooting the site demos on Tears of Steel)."""

    def test_points_grouped_by_frame_and_object(self):
        from stencil.core import Prompt, group_prompts

        g = group_prompts([
            Prompt(frame=0, xy=(.5, .4), label=1, obj=1),
            Prompt(frame=0, xy=(.6, .9), label=1, obj=1),   # same frame+obj
            Prompt(frame=0, xy=(.1, .3), label=0, obj=1),   # the exclude
            Prompt(frame=10, xy=(.5, .5), label=1, obj=1),  # later correction
            Prompt(frame=0, xy=(.2, .2), label=1, obj=2),   # second object
        ])
        self.assertEqual(len(g[(0, 1)]), 3, "frame 0 object 1 must keep all 3 points")
        self.assertEqual([p.label for p in g[(0, 1)]], [1, 1, 0])
        self.assertEqual(len(g[(10, 1)]), 1)
        self.assertEqual(len(g[(0, 2)]), 1)

    def test_single_point_still_one_group(self):
        from stencil.core import Prompt, group_prompts

        g = group_prompts([Prompt(frame=0, xy=(.5, .5), label=1, obj=1)])
        self.assertEqual(len(g), 1)


class TestPromptSchema(unittest.TestCase):
    def test_prompt_validation(self):
        import json
        import tempfile

        from stencil.cli import load_prompts

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"objects": [{"id": 1, "points": [
                {"frame": 0, "xy": [0.5, 0.4]},
                {"frame": 9, "xy": [0.6, 0.5], "label": 0}]}]}, f)
            name = f.name
        prompts = load_prompts(name)
        self.assertEqual(len(prompts), 2)
        self.assertEqual(prompts[1].label, 0)

    def test_bad_xy_rejected(self):
        import json
        import tempfile

        from stencil.cli import load_prompts

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"objects": [{"points": [{"frame": 0, "xy": [12, 0.4]}]}]}, f)
            name = f.name
        with self.assertRaises(ValueError):
            load_prompts(name)


if __name__ == "__main__":
    unittest.main()
