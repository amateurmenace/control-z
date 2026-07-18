import unittest
from pathlib import Path

from highlighter.insight import meeting_day
from suite.tools.kb import is_span_clip


class TestMeetingDay(unittest.TestCase):
    def test_title_month_name_wins(self):
        self.assertEqual(
            meeting_day("Brookline Select Board Meeting - March 10, 2026",
                        "20260315"),
            "2026-03-10")

    def test_title_numeric_date(self):
        self.assertEqual(meeting_day("Select Board 3.10.26"), "2026-03-10")
        self.assertEqual(meeting_day("Hearing 3/9/2026"), "2026-03-09")

    def test_numeric_day_first_swaps(self):
        # "18.3.2026" can only mean day-month — read it, don't refuse it
        self.assertEqual(meeting_day("Meeting 18.3.2026"), "2026-03-18")

    def test_upload_date_is_the_fallback(self):
        self.assertEqual(meeting_day("Council Meeting", "20260203"),
                         "2026-02-03")

    def test_nothing_speaks(self):
        self.assertIsNone(meeting_day("Me at the zoo", ""))

    def test_impossible_dates_refused(self):
        self.assertIsNone(meeting_day("Meeting - February 30, 2026", ""))


class TestSpanClipFilter(unittest.TestCase):
    def test_span_downloads_are_not_meetings(self):
        self.assertTrue(is_span_clip(
            Path("Brookline School Committee [2YhgO14jXys] [3923-3927].mp4")))

    def test_rendered_reels_are_not_meetings(self):
        self.assertTrue(is_span_clip(Path("reel-20260717-183931.mp4")))
        self.assertTrue(is_span_clip(Path("meeting.reel.mp4")))

    def test_full_videos_are(self):
        self.assertFalse(is_span_clip(
            Path("Select Board Meeting - March 10, 2026 [wAFa8pUa4IQ].mp4")))


if __name__ == "__main__":
    unittest.main()
