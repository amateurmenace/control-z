import unittest
import xml.etree.ElementTree as ET
from fractions import Fraction

from czcore.exports.fcpxml import frame_duration, selects_csv, stringout

CLIPS = [
    {"path": "/a/interview [x1].mov", "name": "interview [x1].mov",
     "duration": 12.5, "fps": 29.97, "width": 1920, "height": 1080,
     "audio": True},
    {"path": "/b/broll & more.mp4", "duration": 8.0, "fps": 25.0,
     "width": 1280, "height": 720, "audio": False},
]


class TestFrameDuration(unittest.TestCase):
    def test_ntsc_rates_get_exact_rationals(self):
        self.assertEqual(frame_duration(29.97), Fraction(1001, 30000))
        self.assertEqual(frame_duration(23.976), Fraction(1001, 24000))
        self.assertEqual(frame_duration(59.94), Fraction(1001, 60000))

    def test_integer_rates(self):
        self.assertEqual(frame_duration(25.0), Fraction(1, 25))
        self.assertEqual(frame_duration(24.0), Fraction(1, 24))

    def test_missing_rate_defaults(self):
        self.assertEqual(frame_duration(None), Fraction(1, 25))


class TestStringout(unittest.TestCase):
    def test_wellformed_and_complete(self):
        xml = stringout(CLIPS)
        root = ET.fromstring(xml)  # would raise on bad escaping ("&" in name)
        self.assertEqual(root.tag, "fcpxml")
        self.assertEqual(len(root.findall(".//asset")), 2)
        self.assertEqual(len(root.findall(".//spine/asset-clip")), 2)

    def test_offsets_accumulate(self):
        root = ET.fromstring(stringout(CLIPS))
        offsets = [c.get("offset") for c in root.findall(".//spine/asset-clip")]
        self.assertEqual(offsets[0], "0s")
        self.assertEqual(offsets[1], "25/2s")  # 12.5s as a rational

    def test_src_is_a_file_url(self):
        root = ET.fromstring(stringout(CLIPS))
        srcs = [a.get("src") for a in root.findall(".//asset")]
        self.assertTrue(all(s.startswith("file://") for s in srcs))
        self.assertIn("%20", srcs[0])  # spaces percent-encoded

    def test_empty_selection_is_an_error(self):
        with self.assertRaises(ValueError):
            stringout([])

    def test_csv_row_per_clip(self):
        lines = selects_csv(CLIPS).strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2


if __name__ == "__main__":
    unittest.main()
