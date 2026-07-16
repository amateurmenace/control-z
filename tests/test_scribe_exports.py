import unittest

from scribe.exports import PRESETS, Select, to_marker_edl, to_selects_edl, to_srt, to_vtt
from scribe.timecode import frames_to_tc, seconds_to_tc, srt_time, tc_to_frames
from scribe.transcript import Segment, Transcript, Word


def t_short():
    return Transcript(
        source="/x/interview.mov", language="en", duration=10.0,
        segments=[
            Segment(0.5, 2.0, "Hello there.", speaker="Speaker 1",
                    words=[Word("Hello", 0.5, 1.0), Word("there.", 1.2, 2.0)]),
            Segment(3.0, 5.5, "Welcome to the station.", speaker="Speaker 2"),
        ], speakers=["Speaker 1", "Speaker 2"])


class TestTimecode(unittest.TestCase):
    def test_roundtrip(self):
        for fps in (24.0, 23.976, 29.97, 30.0, 59.94):
            self.assertEqual(tc_to_frames(frames_to_tc(123456, fps), fps), 123456)

    def test_ndf_base(self):
        self.assertEqual(seconds_to_tc(3600, 24.0), "01:00:00:00")
        self.assertEqual(frames_to_tc(24, 23.976), "00:00:01:00")
        # NDF at 23.976 legitimately drifts from wall clock (why DF exists);
        # we count frames, so an hour of real time reads 59:56 — documented.
        self.assertEqual(seconds_to_tc(3600, 23.976), "00:59:56:10")

    def test_srt_time(self):
        self.assertEqual(srt_time(3661.5), "01:01:01,500")
        self.assertEqual(srt_time(0), "00:00:00,000")


class TestCaptions(unittest.TestCase):
    def test_srt_basic(self):
        srt = to_srt(t_short())
        self.assertIn("1\n00:00:00,500 --> 00:00:02,000\nHello there.", srt)
        self.assertIn("Welcome to the station.", srt)

    def test_vtt_header(self):
        self.assertTrue(to_vtt(t_short()).startswith("WEBVTT"))

    def test_long_segment_splits_with_word_timings(self):
        words = [Word(f"word{i}", i * 0.4, i * 0.4 + 0.3) for i in range(40)]
        t = Transcript("/x.mov", "en", 20.0, [
            Segment(0.0, 16.0, " ".join(w.w for w in words), words=words)])
        srt = to_srt(t, "social")  # 24 chars x 1 line -> many blocks
        blocks = [b for b in srt.split("\n\n") if b.strip()]
        self.assertGreater(len(blocks), 5)
        # second block must start at its own words' time, not the segment start
        self.assertNotIn("00:00:00,000 --> 00:00:16,000", srt)

    def test_preset_line_limits(self):
        srt = to_srt(t_short(), "broadcast")
        for block in srt.split("\n\n"):
            lines = block.strip().splitlines()[2:]
            self.assertLessEqual(len(lines), PRESETS["broadcast"].max_lines)
            for ln in lines:
                self.assertLessEqual(len(ln), PRESETS["broadcast"].max_chars)


class TestMarkerEDL(unittest.TestCase):
    def test_structure(self):
        edl = to_marker_edl(t_short(), 24.0)
        self.assertIn("TITLE: Scribe markers", edl)
        self.assertIn("001  001      V     C        01:00:00:12 01:00:00:13 "
                      "01:00:00:12 01:00:00:13", edl)
        self.assertIn("|C:ResolveColor", edl)
        self.assertIn("|M:Speaker 1: Hello there.", edl)
        self.assertIn("|D:1", edl)

    def test_speaker_colors_differ(self):
        edl = to_marker_edl(t_short(), 24.0)
        colors = {ln.split("|C:ResolveColor")[1].split(" ")[0]
                  for ln in edl.splitlines() if "|C:" in ln}
        self.assertEqual(len(colors), 2)


class TestSelectsEDL(unittest.TestCase):
    def test_record_tc_accumulates(self):
        edl = to_selects_edl(
            [Select(10.0, 12.0, "a"), Select(30.0, 31.0, "b")], 24.0,
            reel="SABBY", clip_name="interview.mov")
        self.assertIn("001  SABBY    V     C        00:00:10:00 00:00:12:00 "
                      "01:00:00:00 01:00:02:00", edl)
        self.assertIn("002  SABBY    V     C        00:00:30:00 00:00:31:00 "
                      "01:00:02:00 01:00:03:00", edl)
        self.assertIn("* FROM CLIP NAME: interview.mov", edl)

    def test_handles(self):
        edl = to_selects_edl([Select(10.0, 12.0)], 24.0, handles=0.5)
        self.assertIn("00:00:09:12 00:00:12:12", edl)


class TestTranscriptModel(unittest.TestCase):
    def test_json_roundtrip(self):
        t = t_short()
        back = Transcript.from_json(t.to_json())
        self.assertEqual(back.segments[0].words[1].w, "there.")
        self.assertEqual(back.segments[1].speaker, "Speaker 2")
        self.assertEqual(back.language, "en")

    def test_full_text_groups_speakers(self):
        txt = t_short().full_text()
        self.assertIn("Speaker 1:", txt)
        self.assertIn("Speaker 2:", txt)


if __name__ == "__main__":
    unittest.main()
