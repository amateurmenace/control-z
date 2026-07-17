"""The BYO-key AI module and the names-for-Whisper harvest.

llm.py never touches the network here — these are config-precedence,
masking and covenant tests (no key ⇒ disabled, key never returned whole).
hotwords() is pure reading: the meeting's own words in, a decoder bias out.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from czcore import llm
from czcore.captions import parse_video_details
from highlighter.insight import hotwords


class TestLLMConfig(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-llm-test-")
        patch_dir = mock.patch.object(
            llm, "support_dir", lambda sub="": Path(self.td.name))
        patch_dir.start()
        self.addCleanup(patch_dir.stop)
        self.addCleanup(self.td.cleanup)
        saved = {k: os.environ.pop(k, None)
                 for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL",
                           "CONTROL_Z_LLM_MODEL")}
        self.addCleanup(lambda: [os.environ.update({k: v})
                                 for k, v in saved.items() if v is not None])

    def test_disabled_by_default(self):
        self.assertFalse(llm.enabled())
        st = llm.status()
        self.assertFalse(st["enabled"])
        self.assertIsNone(st["key_masked"])

    def test_stray_base_url_alone_never_activates(self):
        # dev shells export ANTHROPIC_BASE_URL; without a key it means nothing
        os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:9999"
        self.assertFalse(llm.enabled())

    def test_env_key_wins_over_file(self):
        llm.set_config("sk-file-key-123456", "claude-sonnet-5")
        os.environ["ANTHROPIC_API_KEY"] = "sk-env-key-654321"
        c = llm.get_config()
        self.assertEqual(c["source"], "env")
        self.assertEqual(c["api_key"], "sk-env-key-654321")

    def test_file_roundtrip_and_masking(self):
        st = llm.set_config("sk-ant-abcdef-7890", "")
        self.assertTrue(st["enabled"])
        self.assertEqual(st["model"], llm.DEFAULT_MODEL)
        self.assertEqual(st["key_masked"], "…7890")
        self.assertNotIn("sk-ant", str(st))  # the key never leaves whole
        mode = (Path(self.td.name) / "llm.json").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_clear_removes_file(self):
        llm.set_config("sk-something-longer", "")
        st = llm.set_config("", "")
        self.assertFalse(st["enabled"])
        self.assertFalse((Path(self.td.name) / "llm.json").exists())

    def test_complete_without_key_is_a_sentence(self):
        with self.assertRaises(RuntimeError) as cm:
            llm.complete("hello")
        self.assertIn("Settings", str(cm.exception))


class TestVideoDetails(unittest.TestCase):
    HTML = ('junk"videoDetails":{"videoId":"abc12345678","title":"Select '
            'Board 7/15","lengthSeconds":"7260","author":"BIG"},'
            '"annotations":[]more')

    def test_parses_the_watch_page_fields(self):
        d = parse_video_details(self.HTML)
        self.assertEqual(d["title"], "Select Board 7/15")
        self.assertEqual(d["duration"], 7260)
        self.assertEqual(d["uploader"], "BIG")
        self.assertEqual(d["id"], "abc12345678")

    def test_page_shape_change_is_empty_not_a_crash(self):
        self.assertEqual(parse_video_details("<html>nothing here</html>"), {})
        self.assertEqual(parse_video_details(
            '"videoDetails": {broken json},"playerConfig"'), {})


class TestHotwords(unittest.TestCase):
    SEGS = [
        {"text": "Councilor Vitolo moved to approve. Heather Hamilton "
                 "seconded the motion.", "start": 5.0},
        {"text": "The Harvard Street crosswalk, Bernard Greene said.",
         "start": 9.0},
        {"text": "Bernard Greene asked about Harvard Street again.",
         "start": 12.0},
    ]

    def test_people_and_places_harvested(self):
        s = hotwords(self.SEGS)
        self.assertIn("Bernard Greene", s)
        self.assertIn("Harvard Street", s)

    def test_title_names_ride_along(self):
        s = hotwords(self.SEGS, {"title": "Brookline Select Board — July"})
        self.assertIn("Brookline Select Board", s)

    def test_deduped_case_insensitive(self):
        s = hotwords(self.SEGS + [{"text": "BERNARD GREENE spoke.",
                                   "start": 20.0}])
        self.assertEqual(s.lower().count("bernard greene"), 1)

    def test_cap_cuts_on_a_comma(self):
        segs = [{"text": f"Member Name{i} Surname{i} was recognized by "
                         f"Member Name{i} Surname{i}.", "start": float(i)}
                for i in range(120)]
        s = hotwords(segs, cap=200)
        self.assertLessEqual(len(s), 200)
        self.assertFalse(s.endswith(","))

    def test_empty_meeting_is_empty_string(self):
        self.assertEqual(hotwords([]), "")


if __name__ == "__main__":
    unittest.main()
