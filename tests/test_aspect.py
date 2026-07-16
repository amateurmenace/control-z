import unittest

from pivot.aspect import CropGeometry, crop_geometry, parse_aspect, rect_for_center


class TestParseAspect(unittest.TestCase):
    def test_forms(self):
        self.assertAlmostEqual(parse_aspect("9:16"), 9 / 16)
        self.assertAlmostEqual(parse_aspect("9x16"), 9 / 16)
        self.assertAlmostEqual(parse_aspect("1:1"), 1.0)
        self.assertAlmostEqual(parse_aspect("0.5625"), 0.5625)

    def test_bad(self):
        for bad in ("0:9", "9:0", "-1", "sideways"):
            with self.assertRaises(ValueError):
                parse_aspect(bad)


class TestCropGeometry(unittest.TestCase):
    def test_hd_to_vertical(self):
        g = crop_geometry(1920, 1080, 9 / 16)
        self.assertEqual((g.crop_w, g.crop_h, g.axis), (608, 1080, "x"))
        self.assertAlmostEqual(g.half_width_norm, 304 / 1920)

    def test_hd_to_square(self):
        g = crop_geometry(1920, 1080, 1.0)
        self.assertEqual((g.crop_w, g.crop_h, g.axis), (1080, 1080, "x"))

    def test_vertical_source_to_wide(self):
        g = crop_geometry(1080, 1920, 16 / 9)
        self.assertEqual((g.crop_w, g.crop_h, g.axis), (1080, 608, "y"))
        self.assertAlmostEqual(g.half_width_norm, 304 / 1920)

    def test_same_aspect(self):
        g = crop_geometry(1920, 1080, 16 / 9)
        self.assertEqual(g.axis, "none")

    def test_even_dimensions(self):
        g = crop_geometry(1919, 1079, 9 / 16)
        self.assertEqual(g.crop_w % 2, 0)
        self.assertEqual(g.crop_h % 2, 0)

    def test_punch_in_factor(self):
        g = crop_geometry(1920, 1080, 9 / 16)
        self.assertAlmostEqual(g.punch_in_factor(1080), 1080 / 608)


class TestRectForCenter(unittest.TestCase):
    def setUp(self):
        self.g = crop_geometry(1920, 1080, 9 / 16)

    def test_center(self):
        self.assertEqual(rect_for_center(self.g, 0.5), (656, 0, 608, 1080))

    def test_clamped_edges(self):
        self.assertEqual(rect_for_center(self.g, 0.0)[0], 0)
        self.assertEqual(rect_for_center(self.g, 1.0)[0], 1920 - 608)

    def test_vertical_axis(self):
        g = crop_geometry(1080, 1920, 16 / 9)
        x, y, w, h = rect_for_center(g, 0.0)
        self.assertEqual((x, y, w, h), (0, 0, 1080, 608))
        self.assertEqual(rect_for_center(g, 1.0)[1], 1920 - 608)


if __name__ == "__main__":
    unittest.main()
