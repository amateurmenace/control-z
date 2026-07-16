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

    # Tools every template must contain (the load-bearing node of each). These
    # are checked against a live paste-test in free Resolve — see CHANGELOG
    # 2026-07-16 "the template pack". `Bitmap` (an invalid RegID that pastes as
    # a no-op Dummy) is deliberately NOT here: the correct id is `BitmapMask`.
    EXPECTED = {
        "fog": ["BitmapMask", "Background", "Merge"],
        "rack-focus": ["VariBlur", "Custom"],
        "depth-grade": ["BitmapMask", "ColorCorrector"],
        "parallax": ["Displace", "Transform"],
        "haze-light": ["BitmapMask", "SoftGlow"],
        "veil-blur": ["Blur", "BitmapMask", "Scale", "Merge"],
        "cutout": ["MatteControl", "Background", "Merge"],
        "matte-tune": ["ErodeDilate", "BitmapMask", "Merge"],
        "confidence-grain": ["FastNoise", "BitmapMask", "Merge"],
        "social-vertical": ["Transform", "Blur", "Background", "Merge"],
    }

    # Tool RegIDs that only exist in DaVinci Resolve Studio (ResolveFX, Neural
    # Engine, optical-flow) — none may appear in a free-edition pack. Also
    # `Bitmap`, which Fusion silently turns into a Dummy on paste.
    FORBIDDEN = ["Bitmap ", "OpticalFlow", "ResolveFX", "SmartVector",
                 "DepthMap", "SurfaceTracker", "MagicMask", "DCTL"]

    def test_all_present_and_balanced(self):
        from depth.cli import ALL_TEMPLATES

        self.assertEqual(len(ALL_TEMPLATES), 10)
        for t in ALL_TEMPLATES:
            text = (self.DIR / f"{t}.setting").read_text()
            self.assertEqual(text.count("{"), text.count("}"), f"{t}: unbalanced braces")
            self.assertIn("Tools = ordered()", text, t)

    def test_expected_tools(self):
        for t, tools in self.EXPECTED.items():
            text = (self.DIR / f"{t}.setting").read_text()
            for tool in tools:
                self.assertIn(tool + " {", text, f"{t}: missing tool {tool}")

    def test_has_sticky_note(self):
        from depth.cli import ALL_TEMPLATES

        for t in ALL_TEMPLATES:
            text = (self.DIR / f"{t}.setting").read_text()
            self.assertIn("Note {", text, f"{t}: no sticky Note")
            self.assertIn("control-z", text, f"{t}: Note missing brand line")

    def test_no_studio_only_tools(self):
        from depth.cli import ALL_TEMPLATES

        for t in ALL_TEMPLATES:
            text = (self.DIR / f"{t}.setting").read_text()
            for bad in self.FORBIDDEN:
                self.assertNotIn(bad, text, f"{t}: Studio-only/invalid tool {bad!r}")

    def test_cz_node_names(self):
        from depth.cli import ALL_TEMPLATES

        for t in ALL_TEMPLATES:
            text = (self.DIR / f"{t}.setting").read_text()
            self.assertIn("CZ", text, f"{t}: node names should be CZ*-prefixed")

    def test_cli_writes_all_ten(self):
        import tempfile

        from depth.cli import ALL_TEMPLATES, main

        with tempfile.TemporaryDirectory() as d:
            main(["templates", "-o", d])
            written = list(Path(d).glob("*.setting"))
            self.assertEqual(len(written), len(ALL_TEMPLATES))

    def test_zip_lists_all_ten(self):
        import zipfile

        from depth.cli import ALL_TEMPLATES

        zpath = self.DIR.parent.parent / "packs" / "control-z-fusion-templates.zip"
        with zipfile.ZipFile(zpath) as z:
            names = {n.replace(".setting", "") for n in z.namelist()}
        self.assertEqual(names, set(ALL_TEMPLATES))


if __name__ == "__main__":
    unittest.main()
