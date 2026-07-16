import unittest

from czcore.exports.fusion_setting import animated_crop_setting, bezier_spline


class TestFusionSetting(unittest.TestCase):
    def setUp(self):
        self.rects = [(656 + i, 0, 608, 1080) for i in range(24)]
        self.text = animated_crop_setting(self.rects, 1920, 1080)

    def test_structure(self):
        for needle in ("Tools = ordered()", "PivotCrop = Crop", "PivotPathX = BezierSpline",
                       "PivotPathY = BezierSpline", 'ActiveTool = "PivotCrop"'):
            self.assertIn(needle, self.text)

    def test_crop_size_static(self):
        self.assertIn("XSize = Input { Value = 608, }", self.text)
        self.assertIn("YSize = Input { Value = 1080, }", self.text)

    def test_one_key_per_frame(self):
        x_block = self.text.split("PivotPathX = BezierSpline")[1] \
                           .split("PivotPathY = BezierSpline")[0]
        self.assertEqual(x_block.count("] = {"), 24)
        self.assertIn("[0] = { 656 }", x_block)
        self.assertIn("[23] = { 679 }", x_block)

    def test_spline_offsets(self):
        s = bezier_spline("S", [1.5, 2.0], start_frame=10)
        self.assertIn("[10] = { 1.5 }", s)
        self.assertIn("[11] = { 2 }", s)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            animated_crop_setting([], 1920, 1080)


if __name__ == "__main__":
    unittest.main()
