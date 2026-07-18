import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from slate.lowerthird import ANIMS, STYLES, LowerThird, phase_at

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:  # the stdlib-only test run still covers the params/easing
    HAVE_PIL = False


class TestParams(unittest.TestCase):
    def test_from_dict_clamps_and_defaults(self):
        p = LowerThird.from_dict({"style": "nonsense", "anim": "also-no",
                                  "width": 99999, "fps": 500, "x": 4.0,
                                  "plate_opacity": 9})
        self.assertIn(p.style, STYLES)
        self.assertIn(p.anim, ANIMS)
        self.assertLessEqual(p.width, 7680)
        self.assertLessEqual(p.fps, 120.0)
        self.assertLessEqual(p.x, 0.9)
        self.assertLessEqual(p.plate_opacity, 1.0)

    def test_unknown_keys_ignored(self):
        p = LowerThird.from_dict({"line1": "A", "hacker": "field"})
        self.assertEqual(p.line1, "A")


class TestBrandDefaults(unittest.TestCase):
    """Slate reads the station brand (publisher/brand.py) as lower-third
    defaults — one brand, every lower third — but only once a brand is set,
    so a fresh install keeps Slate's own look."""

    def _patch_support(self, root):
        from czcore import paths
        from publisher import brand
        for mod in (paths, brand):
            p = mock.patch.object(mod, "support_dir",
                                  lambda sub="", _r=root: _r)
            p.start(); self.addCleanup(p.stop)

    def test_no_brand_file_is_not_configured(self):
        with tempfile.TemporaryDirectory() as td:
            self._patch_support(Path(td))
            from suite.tools.slate import _brand_defaults
            self.assertFalse(_brand_defaults()["configured"])

    def test_a_set_brand_becomes_the_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._patch_support(root)
            (root / "publisher-brand.json").write_text(json.dumps({
                "station": "Brookline Interactive Group", "accent": "#C24",
                "plate": "#101014", "style": "block", "lt_seconds": 6.0,
                "line2": "community media"}))
            from suite.tools.slate import _brand_defaults
            d = _brand_defaults()
            self.assertTrue(d["configured"])
            self.assertEqual(d["accent"], "#C24")
            self.assertEqual(d["plate_color"], "#101014")
            self.assertEqual(d["style"], "block")
            self.assertEqual(d["hold"], 6.0)
            self.assertEqual(d["line2"], "community media")
            self.assertEqual(d["station"], "Brookline Interactive Group")

    def test_duration_and_frames(self):
        p = LowerThird.from_dict({"in_dur": 0.5, "hold": 2.0, "out_dur": 0.5,
                                  "fps": 30})
        self.assertAlmostEqual(p.duration(), 3.0)
        self.assertEqual(p.n_frames(), 90)


class TestPhases(unittest.TestCase):
    def test_hold_is_fully_present(self):
        p = LowerThird.from_dict({"in_dur": 0.5, "hold": 2.0, "out_dur": 0.5})
        k, phase = phase_at(p, 1.5)
        self.assertEqual((k, phase), (1.0, "hold"))

    def test_in_rises_and_out_falls(self):
        p = LowerThird.from_dict({"in_dur": 1.0, "hold": 1.0, "out_dur": 1.0})
        k_in, _ = phase_at(p, 0.25)
        self.assertTrue(0 < k_in < 1)
        k_out, phase = phase_at(p, 2.9)
        self.assertEqual(phase, "out")
        self.assertLess(k_out, 0.2)


@unittest.skipUnless(HAVE_PIL, "Pillow not installed (core tests stay stdlib)")
class TestRendering(unittest.TestCase):
    def _render(self, style):
        from slate.lowerthird import Renderer
        p = LowerThird.from_dict({
            "line1": "Maya Okafor", "line2": "Select Board Chair",
            "style": style, "width": 480, "height": 270, "supersample": 2})
        return Renderer(p).hold_frame()

    def test_every_style_renders_with_alpha(self):
        for style in STYLES:
            img = self._render(style)
            self.assertEqual(img.mode, "RGBA")
            self.assertEqual(img.size, (480, 270))
            lo, hi = img.split()[3].getextrema()
            self.assertEqual(lo, 0, f"{style}: background must stay clear")
            self.assertGreater(hi, 200, f"{style}: type must be present")

    def test_faded_out_frame_is_empty(self):
        from slate.lowerthird import Renderer
        p = LowerThird.from_dict({"width": 480, "height": 270,
                                  "in_dur": 0.5, "hold": 1.0, "out_dur": 0.5})
        img = Renderer(p).frame(999.0)
        self.assertEqual(img.split()[3].getextrema()[1], 0)


if __name__ == "__main__":
    unittest.main()
