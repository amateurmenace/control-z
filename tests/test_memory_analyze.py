"""The reading: extractive by default, generative only with a key — and always
falling back so a keyless suite still shows something true.

Mirrors the covenant test in test_llm_names: no key → the summary is extractive
(verbatim, timestamped); a key → labeled generative; an API error → back to
extractive, never an exception in the user's face.
"""

import unittest
from unittest import mock

from memory import analyze

SEGS = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": "Speaker 2",
     "text": "I move to adopt the MBTA Communities zoning overlay."},
    {"start": 20.0, "end": 28.0, "speaker": "Speaker 3",
     "text": "The projected cost is four hundred thousand dollars."},
    {"start": 28.0, "end": 34.0, "speaker": "Speaker 1",
     "text": "All in favor? The motion passes five to zero."},
]
SOURCE = " ".join(s["text"] for s in SEGS)


class AnalyzeTest(unittest.TestCase):
    def test_read_is_extractive(self):
        a = analyze.read(SEGS)
        self.assertTrue(a["brief"])
        for row in a["brief"]:
            self.assertIn(row["text"], SOURCE)        # verbatim, never paraphrased
            self.assertIsInstance(row["t"], float)
        self.assertIn("decisions", a)
        self.assertIn("participation", a)

    def test_summary_extractive_without_key(self):
        with mock.patch.object(analyze.llm, "enabled", lambda: False):
            text, origin = analyze.summary(SEGS)
        self.assertEqual(origin, "extractive")
        self.assertTrue(text)
        # extractive = sentences lifted from the meeting
        self.assertIn(text.split(".")[0].strip(), SOURCE)

    def test_summary_generative_when_keyed_and_labeled(self):
        with mock.patch.object(analyze.llm, "enabled", lambda: True), \
             mock.patch.object(analyze.llm, "complete",
                               lambda *a, **k: "The board advanced the rezoning."), \
             mock.patch.object(analyze.llm, "status",
                               lambda: {"model": "claude-haiku-4-5"}):
            text, origin = analyze.summary(SEGS)
        self.assertEqual(text, "The board advanced the rezoning.")
        self.assertTrue(origin.startswith("ai:"))
        self.assertIn("claude", origin)

    def test_summary_falls_back_when_the_api_errors(self):
        def boom(*a, **k):
            raise RuntimeError("429 rate limited")
        with mock.patch.object(analyze.llm, "enabled", lambda: True), \
             mock.patch.object(analyze.llm, "complete", boom):
            text, origin = analyze.summary(SEGS)
        self.assertEqual(origin, "extractive")            # never raises at the user
        self.assertTrue(text)

    def test_summary_empty_meeting(self):
        self.assertEqual(analyze.summary([]), ("", "none"))


if __name__ == "__main__":
    unittest.main()
