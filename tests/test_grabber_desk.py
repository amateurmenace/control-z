"""The Grabber desk's pure logic — the weekly clock and the re-namer."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from suite.tools.grabber import broadcast_name, sched_due


def sched(**kw):
    base = {"enabled": True, "weekday": 3, "hour": 9,   # Thursday 09:00
            "created": "2026-07-01T12:00:00", "last_run": None}
    base.update(kw)
    return base


class TestClock(unittest.TestCase):
    def test_fires_after_tick_passes(self):
        # created July 1 (Wed); Thursday July 2 09:00 has passed by the 3rd
        self.assertTrue(sched_due(sched(), datetime(2026, 7, 3, 10, 0)))

    def test_waits_before_first_tick(self):
        # created Wed noon; Thursday 09:00 hasn't arrived yet
        self.assertFalse(sched_due(sched(), datetime(2026, 7, 1, 23, 0)))

    def test_does_not_refire_same_week(self):
        s = sched(last_run="2026-07-02T09:00:05")
        self.assertFalse(sched_due(s, datetime(2026, 7, 5, 12, 0)))

    def test_fires_again_next_week(self):
        s = sched(last_run="2026-07-02T09:00:05")
        self.assertTrue(sched_due(s, datetime(2026, 7, 9, 9, 30)))

    def test_missed_week_catches_up_on_launch(self):
        # app was closed through two Thursdays — one catch-up fire, not two
        s = sched(last_run="2026-07-02T09:00:05")
        self.assertTrue(sched_due(s, datetime(2026, 7, 17, 8, 0)))

    def test_disabled_never_fires(self):
        self.assertFalse(sched_due(sched(enabled=False),
                                   datetime(2026, 7, 30, 12, 0)))


class TestRenamer(unittest.TestCase):
    def _mk(self, td, name, info=None):
        p = Path(td) / name
        p.write_bytes(b"\x00")
        if info is not None:
            import json
            p.with_suffix(".info.json").write_text(json.dumps(info))
        return p

    def test_strips_machinery_and_spaces(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mk(td, "Select Board Meeting - March 10, 2026 "
                             "[wAFa8pUa4IQ].mp4",
                         {"upload_date": "20260310"})
            self.assertEqual(broadcast_name(p),
                             "Select_Board_Meeting_March_10_2026_20260310.mp4")

    def test_span_tag_removed_and_mtime_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mk(td, "clip [abc123def45] [10-20].mp4")
            out = broadcast_name(p, "{title}_{date}")
            self.assertNotIn("[", out)
            self.assertRegex(out, r"^clip_\d{8}\.mp4$")

    def test_pattern_is_respected_and_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mk(td, "a b.mp4", {"upload_date": "20260101"})
            self.assertEqual(broadcast_name(p, "BIG_{date}_{title}"),
                             "BIG_20260101_a_b.mp4")

    def test_never_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mk(td, "[abc123def45].mp4")
            self.assertTrue(broadcast_name(p).endswith(".mp4"))
            self.assertGreater(len(broadcast_name(p)), 4)


if __name__ == "__main__":
    unittest.main()
