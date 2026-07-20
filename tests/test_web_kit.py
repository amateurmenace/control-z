"""The kit plane's derivation — Publisher's reading half, pressed (specs/20
§7.9 P2).

`web.kit.kit_from_meeting` turns a pressed meeting into the same kit dict the
desk's `publisher.kit.new_kit` builds — but from the moments plane and the
meeting's own analysis, not from local sidecars. These tests pin the gates
(what earns a kit and what doesn't), the clip identity the reel model depends
on (kind, t), and the covenant fact that keeps the press honest: no model, and
nothing rendered.
"""

import unittest

from web.kit import kit_from_meeting


def _meeting(**over):
    """A pressed-meeting doc, minimally shaped like `web.bake.bake_meetings`."""
    m = {
        "id": "vid1", "pid": "vid1", "title": "Select Board — March",
        "date": "2026-03-10", "town": "Testville", "body": "Select Board",
        "video_id": "vid1", "url": "https://youtube.com/watch?v=vid1",
        "duration": 3600, "summary": "The board discussed a budget override.",
        "thumb": "https://i.ytimg.com/vi/vid1/hqdefault.jpg",
        "analysis": {"entities": {"people": [{"name": "Chair Alpha", "count": 3}],
                                  "organizations": [], "places": [], "money": []}},
        "moments": [
            {"t": 12.0, "start": 8.0, "end": 30.0, "kind": "vote", "score": 0.95,
             "reason": "passes · 3–0", "quote": "Motion to approve the budget override."},
            {"t": 200.0, "start": 196.0, "end": 214.0, "kind": "question",
             "score": 0.5, "reason": "clarifying",
             "quote": "How does this affect the tax rate for seniors?"},
        ],
    }
    m.update(over)
    return m


class TestGates(unittest.TestCase):
    def test_a_meeting_with_video_and_moments_gets_a_kit(self):
        kit = kit_from_meeting(_meeting())
        self.assertIsNotNone(kit)
        self.assertEqual(kit["slug"], "vid1")
        self.assertEqual(len(kit["clips"]), 2)

    def test_no_video_no_kit(self):
        """A meeting with no tape has nothing a desk Publisher could render
        against — so no kit is pressed, and /app/press stays honest."""
        self.assertIsNone(kit_from_meeting(_meeting(video_id="")))

    def test_no_moments_no_kit(self):
        self.assertIsNone(kit_from_meeting(_meeting(moments=[])))
        self.assertIsNone(kit_from_meeting(_meeting(moments=None)))


class TestShape(unittest.TestCase):
    def test_clips_are_the_moments_in_order_carrying_their_identity(self):
        kit = kit_from_meeting(_meeting())
        clips = kit["clips"]
        # chronological by clip start
        self.assertEqual([c["start"] for c in clips], sorted(c["start"] for c in clips))
        # the reel model's clip identity rides along: (kind, t, quote)
        self.assertEqual(clips[0]["kind"], "vote")
        self.assertEqual(clips[0]["t"], 12.0)
        self.assertIn("budget override", clips[0]["text"])
        # every clip has the desk render's fields
        self.assertTrue(all(c["ratios"] for c in clips))
        self.assertTrue(all("keep" in c and "label" in c for c in clips))

    def test_copy_is_extractive_and_labeled_nothing_rendered(self):
        kit = kit_from_meeting(_meeting())
        self.assertIn("extractive", kit["copy"]["origin"])
        self.assertIn("no model", kit["copy"]["origin"])   # the press calls no AI
        self.assertEqual(kit["files"], [])          # the render stays at the desk
        self.assertTrue(kit["copy"]["titles"])
        # the description carries the chapter list, timed to each clip's start
        self.assertIn("Moments:", kit["copy"]["description"])
        self.assertIn("0:08 — Motion to approve", kit["copy"]["description"])

    def test_meta_carries_the_handles_the_page_and_desk_need(self):
        kit = kit_from_meeting(_meeting())["meta"]
        for k in ("pid", "video_id", "url", "town", "body", "date", "thumb"):
            self.assertIn(k, kit)
        self.assertEqual(kit["video_id"], "vid1")

    def test_the_web_kit_is_a_desk_kit_the_publisher_shape_agrees(self):
        """The emitted kit must be the same object the desk builds, so a
        producer opens it and continues. Both go through
        czcore.kit.kit_from_parts — assert the web kit has the exact top-level
        shape publisher.kit.new_kit produces."""
        from czcore.kit import kit_from_parts
        ref = kit_from_parts({"title": "x", "date": ""}, [], {})
        kit = kit_from_meeting(_meeting())
        # every key the desk kit has, the web kit has (plus `slug`)
        self.assertTrue(set(ref).issubset(set(kit)))
        self.assertEqual(kit["version"], 1)


if __name__ == "__main__":
    unittest.main()
