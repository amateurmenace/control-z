import unittest

from czcore.media import parse_probe

FIXTURE = {
    "format": {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "12.512500",
        "tags": {"timecode": "01:00:00;00"},
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "prores",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv422p10le",
            "avg_frame_rate": "24000/1001",
            "nb_frames": "300",
            "tags": {},
        },
        {"codec_type": "audio", "codec_name": "pcm_s16le"},
        {"codec_type": "audio", "codec_name": "pcm_s16le"},
    ],
}


class TestParseProbe(unittest.TestCase):
    def test_fields(self):
        info = parse_probe("/x/clip.mov", FIXTURE)
        self.assertEqual(info.video.width, 1920)
        self.assertEqual(info.video.height, 1080)
        self.assertAlmostEqual(info.video.fps, 24000 / 1001, places=6)
        self.assertEqual(info.video.nb_frames, 300)
        self.assertEqual(info.audio_streams, 2)
        self.assertEqual(info.timecode, "01:00:00;00")
        self.assertAlmostEqual(info.duration, 12.5125)

    def test_no_video(self):
        info = parse_probe("/x/a.wav", {"format": {"duration": "3.0"}, "streams": [
            {"codec_type": "audio"}]})
        self.assertIsNone(info.video)
        self.assertEqual(info.audio_streams, 1)

    def test_bad_rate_handled(self):
        data = {"format": {}, "streams": [{"codec_type": "video", "width": 10,
                "height": 10, "avg_frame_rate": "0/0", "r_frame_rate": "25/1"}]}
        self.assertAlmostEqual(parse_probe("x", data).video.fps, 25.0)


if __name__ == "__main__":
    unittest.main()
