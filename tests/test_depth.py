import unittest
from pathlib import Path

try:
    import cv2  # noqa: F401
    import numpy as np
    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "needs numpy+cv2")
class TestNormalize(unittest.TestCase):
    def test_shot_normalize_and_options(self):
        from depth.engine import normalize_shot

        rng = np.random.default_rng(11)
        depths = [rng.uniform(100, 900, (64, 64)).astype(np.float32)
                  for _ in range(6)]
        out, r = normalize_shot(depths)
        allv = np.concatenate([o.ravel() for o in out])
        self.assertGreaterEqual(float(allv.min()), 0.0)
        self.assertLessEqual(float(allv.max()), 1.0)
        self.assertLess(r["lo"], r["hi"])
        inv, _ = normalize_shot(depths, invert=True)
        self.assertAlmostEqual(float(out[0][0, 0] + inv[0][0, 0]), 1.0, places=5)

    def test_outliers_dont_crush_range(self):
        from depth.engine import normalize_shot

        d = np.full((64, 64), 500.0, np.float32)
        d[0, 0] = 1e9  # hot pixel
        out, r = normalize_shot([d])
        self.assertLess(r["hi"], 1e6)


@unittest.skipUnless(HAVE, "needs numpy+cv2")
class TestGuidedFilter(unittest.TestCase):
    def test_preserves_guide_edges(self):
        from depth.engine import guided_filter

        guide = np.zeros((80, 80), np.uint8)
        guide[:, 40:] = 255
        # blurry depth edge in the wrong place drifts toward the guide's edge
        src = np.zeros((80, 80), np.float32)
        src[:, 36:] = 1.0
        src = cv2.GaussianBlur(src, (0, 0), 6)
        out = guided_filter(guide, src, radius=8)
        # sharper transition at the guide edge than the blurred input
        grad_out = float(np.abs(np.diff(out[40])).max())
        grad_in = float(np.abs(np.diff(src[40])).max())
        self.assertGreater(grad_out, grad_in)


class TestTemplates(unittest.TestCase):
    DIR = Path(__file__).parent.parent / "depth" / "templates"

    def test_all_present_and_balanced(self):
        from depth.cli import TEMPLATES

        for t in TEMPLATES:
            text = (self.DIR / f"{t}.setting").read_text()
            self.assertEqual(text.count("{"), text.count("}"), t)
            self.assertIn("Tools = ordered()", text)
            self.assertIn("control-z Depth", text)
            self.assertIn("ActiveTool", text)

    def test_expected_tools(self):
        self.assertIn("VariBlur", (self.DIR / "rack-focus.setting").read_text())
        self.assertIn("Displace", (self.DIR / "parallax.setting").read_text())
        self.assertIn("SoftGlow", (self.DIR / "haze-light.setting").read_text())


if __name__ == "__main__":
    unittest.main()
