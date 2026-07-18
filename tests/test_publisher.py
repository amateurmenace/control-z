"""Publisher's pure logic — candidates, cues, copy, bundle text.

No ffmpeg, no network, no Pillow: these are the decisions, not the pixels.
"""

import json
import tempfile
import unittest
from pathlib import Path

from publisher.bundle import copy_markdown, slug
from publisher.kit import (candidates, copy_extractive, meeting_meta,
                           new_kit, sidecars)
from publisher.render import cues_for_span

SEGS = [
    {"start": 0.0, "end": 4.0, "text": "Call to order.", "words": []},
    {"start": 10.0, "end": 16.0,
     "text": "Motion to approve the budget, seconded.",
     "words": [{"w": "Motion", "s": 10.0, "e": 10.4, "p": .9},
               {"w": "to", "s": 10.4, "e": 10.5, "p": .9},
               {"w": "approve", "s": 10.5, "e": 11.0, "p": .9},
               {"w": "the", "s": 11.0, "e": 11.1, "p": .9},
               {"w": "budget,", "s": 11.1, "e": 11.6, "p": .9},
               {"w": "seconded.", "s": 12.0, "e": 12.8, "p": .9}]},
    {"start": 16.0, "end": 40.0, "text": ("A very long untimed remark about "
     "housing and traffic and the library and everything else that came up "
     "in public comment tonight, which runs on far past one caption's worth "
     "of screen time and must be split."), "words": []},
]


class TestCues(unittest.TestCase):
    def test_times_go_relative_and_clip_to_span(self):
        cues = cues_for_span(SEGS, 10.0, 16.0)
        self.assertTrue(cues)
        self.assertTrue(all(0.0 <= c["s"] < c["e"] <= 6.0 for c in cues))
        self.assertIn("Motion", cues[0]["text"])

    def test_word_timing_drives_grouping(self):
        cues = cues_for_span(SEGS, 10.0, 16.0, max_chars=12)
        self.assertGreater(len(cues), 1)          # forced to break
        self.assertLess(cues[0]["e"], 4.0)        # ends with its words

    def test_long_untimed_segment_splits(self):
        cues = cues_for_span(SEGS, 16.0, 40.0, max_chars=40)
        self.assertGreater(len(cues), 1)
        joined = " ".join(c["text"] for c in cues)
        self.assertIn("public comment", joined)

    def test_no_overlapping_strips(self):
        cues = cues_for_span(SEGS, 0.0, 40.0, max_chars=20)
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a["e"], b["s"] + 1e-6)

    def test_outside_span_is_silence(self):
        self.assertEqual(cues_for_span(SEGS, 100.0, 120.0), [])


class TestKit(unittest.TestCase):
    def _source(self, td, with_highlights=True):
        src = Path(td) / "meeting.mp4"
        src.write_bytes(b"\x00")   # existence is all the kit logic needs
        sc = sidecars(str(src))
        sc["scribe"].write_text(json.dumps({"segments": SEGS}))
        if with_highlights:
            sc["highlights"].write_text(json.dumps({"picks": [
                {"start": 10.0, "end": 16.0, "text": SEGS[1]["text"],
                 "score": 1.0, "reasons": ["decision: “motion”"]},
                {"start": 16.0, "end": 30.0, "text": SEGS[2]["text"][:60],
                 "score": 0.5, "reasons": ["community: “housing”"]},
            ]}))
        return str(src)

    def test_candidates_prefer_existing_detection(self):
        with tempfile.TemporaryDirectory() as td:
            cands = candidates(self._source(td), n=5)
            self.assertEqual(len(cands), 2)
            self.assertEqual(cands[0]["start"], 10.0)   # chronological
            self.assertTrue(cands[0]["reasons"])

    def test_candidates_fall_back_to_fresh_scoring(self):
        with tempfile.TemporaryDirectory() as td:
            cands = candidates(self._source(td, with_highlights=False), n=3)
            self.assertTrue(cands)
            self.assertTrue(all(c["end"] > c["start"] for c in cands))

    def test_no_sidecars_no_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "bare.mp4"
            src.write_bytes(b"\x00")
            self.assertEqual(candidates(str(src)), [])

    def test_meta_reads_filename_and_date(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "select_board_2026-03-10 [abcdefghijk].mp4"
            src.write_bytes(b"\x00")
            m = meeting_meta(str(src))
            self.assertNotIn("[", m["title"])
            self.assertEqual(m["date"], "2026-03-10")

    def test_new_kit_shape(self):
        with tempfile.TemporaryDirectory() as td:
            kit = new_kit(self._source(td))
            self.assertEqual(kit["version"], 1)
            self.assertEqual(len(kit["clips"]), len(kit["candidates"]))
            self.assertTrue(all(cl["ratios"] for cl in kit["clips"]))
            self.assertIn("extractive", kit["copy"]["origin"])


class TestCopy(unittest.TestCase):
    def test_extractive_copy_is_grounded_and_labeled(self):
        meta = {"title": "Select Board", "date": "2026-03-10", "source": "x"}
        cands = [{"start": 10.0, "end": 16.0,
                  "text": "Motion to approve the budget, seconded.",
                  "score": 1.0, "reasons": []}]
        c = copy_extractive(meta, cands, {})
        self.assertIn("extractive", c["origin"])
        self.assertTrue(c["titles"])
        self.assertTrue(all(len(t) <= 90 for t in c["titles"]))
        self.assertIn("0:10", c["description"])          # chapter line
        self.assertEqual(len(c["alt_text"]), 1)
        self.assertIn("Select Board", c["alt_text"][0])

    def test_copy_markdown_carries_provenance(self):
        kit = {"meta": {"title": "Select Board", "date": "2026-03-10"},
               "copy": {"origin": "extractive — assembled from the "
                        "transcript, no model", "titles": ["A title"],
                        "description": "Desc", "chapters": [],
                        "newsletter": "Blurb", "alt_text": ["alt"],
                        "social": {"feed": "post"}},
               "clips": [{"keep": True, "label": "the vote", "start": 10.0,
                          "end": 16.0, "ratios": ["16x9"]}]}
        md = copy_markdown(kit)
        for needle in ("# Select Board", "extractive", "## Titles",
                       "## Newsletter blurb", "the vote"):
            self.assertIn(needle, md)


class TestSlug(unittest.TestCase):
    def test_slug_tidies(self):
        self.assertEqual(slug("Select Board — March 10, 2026!"),
                         "select-board-march-10-2026")
        self.assertEqual(slug("///"), "program")


if __name__ == "__main__":
    unittest.main()
