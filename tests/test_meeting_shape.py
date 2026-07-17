"""The meeting's shape — pace, dynamics, agenda — and the title card.

All counted reads: words per bin, keyword hits per bin, timestamp lines.
The card test only asserts a real PNG of the asked-for size lands — layout
is taste, presence is contract.
"""

import tempfile
import unittest
from pathlib import Path

from highlighter.insight import agenda, dynamics, pace


def seg(t, text, end=None):
    return {"start": float(t), "end": float(end if end is not None else t + 4),
            "text": text}


class TestPace(unittest.TestCase):
    def test_counts_words_into_bins(self):
        segs = [seg(0, "one two three four five"), seg(95, "six seven", 100)]
        p = pace(segs, bins=10)
        self.assertEqual(len(p["bins"]), 10)
        self.assertEqual(p["duration"], 100)
        self.assertGreater(p["bins"][0], 0)      # five words land in bin 0
        self.assertGreater(p["bins"][9], 0)      # two words land in bin 9
        self.assertEqual(sum(1 for b in p["bins"] if b), 2)
        self.assertGreater(p["wpm_avg"], 0)

    def test_empty_is_empty(self):
        self.assertEqual(pace([])["bins"], [])


class TestDynamics(unittest.TestCase):
    def test_three_lanes_counted(self):
        segs = [seg(0, "Why is this here? And who pays?"),
                seg(50, "The motion passes, adopted unanimous.", 60),
                seg(90, "I am concerned and frustrated about this.", 100)]
        d = dynamics(segs, bins=10)
        self.assertEqual(d["lanes"]["questions"][0], 2)
        self.assertGreaterEqual(d["lanes"]["decisions"][5], 2)
        self.assertGreaterEqual(d["lanes"]["tension"][9], 2)

    def test_empty_meeting(self):
        d = dynamics([], bins=5)
        self.assertEqual(d["lanes"]["questions"], [0] * 5)


class TestAgenda(unittest.TestCase):
    def test_chapters_win(self):
        info = {"chapters": [
            {"start_time": 0, "title": "Call to order"},
            {"start_time": 300, "title": "Public comment"},
        ], "description": "0:00 ignored\n5:00 also ignored"}
        a = agenda(info)
        self.assertEqual(len(a), 2)
        self.assertEqual(a[1], {"t": 300.0, "label": "Public comment"})

    def test_description_timestamps_as_fallback(self):
        info = {"description":
                "Select Board agenda:\n"
                "0:00 - Call to order\n"
                "12:30 Public comment\n"
                "1:02:05 — Harvard Street crosswalk\n"
                "not a timestamp line"}
        a = agenda(info)
        self.assertEqual([x["t"] for x in a], [0, 750, 3725])
        self.assertEqual(a[2]["label"], "Harvard Street crosswalk")

    def test_one_timestamp_is_a_link_not_an_agenda(self):
        self.assertEqual(agenda({"description": "0:00 start"}), [])
        self.assertEqual(agenda(None), [])
        self.assertEqual(agenda({}), [])


class TestTitleCard(unittest.TestCase):
    def test_card_png_lands_at_size(self):
        from highlighter.reel import _card_png
        with tempfile.TemporaryDirectory() as td:
            p = str(Path(td) / "card.png")
            _card_png(p, 640, 360, "Select Board — March 10",
                      "The crosswalk motion passes after public comment",
                      "1:02:05")
            raw = Path(p).read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            from PIL import Image
            with Image.open(p) as img:
                self.assertEqual(img.size, (640, 360))


if __name__ == "__main__":
    unittest.main()
