"""Export preset mapping: fallback order, alpha honesty, availability report.

Encoder availability is injected (no av import needed) so these run stdlib-only,
like the rest of the core tests.
"""

import unittest

from czcore import media


def fake_availability(available):
    """Pre-load the encoder cache so encoder_available never imports av."""
    media._encoder_ok.clear()
    all_encoders = set()
    for p in media.EXPORT_PRESETS.values():
        for c in p.candidates:
            all_encoders.add(c.codec)
    for name in all_encoders:
        media._encoder_ok[name] = name in available


class TestPresetMapping(unittest.TestCase):
    def tearDown(self):
        media._encoder_ok.clear()

    def test_hardware_prores_preferred(self):
        fake_availability({"prores_videotoolbox", "prores_ks"})
        spec = media.resolve_preset("prores-hq")
        self.assertEqual(spec["codec"], "prores_videotoolbox")
        self.assertTrue(spec["hardware"])
        self.assertEqual(spec["container"], "mov")

    def test_software_fallback(self):
        fake_availability({"prores_ks", "libx264", "libx265", "dnxhd"})
        spec = media.resolve_preset("prores-hq")
        self.assertEqual(spec["codec"], "prores_ks")
        self.assertFalse(spec["hardware"])
        self.assertEqual(spec["options"], {"profile": "3"})
        h264 = media.resolve_preset("h264")
        self.assertEqual(h264["codec"], "libx264")

    def test_4444_alpha_honored(self):
        fake_availability({"prores_ks"})
        spec = media.resolve_preset("prores-4444", alpha=True)
        self.assertEqual(spec["pix_fmt"], "yuva444p10le")
        self.assertTrue(spec["alpha"])

    def test_4444_without_alpha(self):
        fake_availability({"prores_ks"})
        spec = media.resolve_preset("prores-4444", alpha=False)
        self.assertEqual(spec["pix_fmt"], "yuv444p10le")
        self.assertFalse(spec["alpha"])

    def test_alpha_never_promised_on_non_alpha_preset(self):
        fake_availability({"prores_videotoolbox", "prores_ks"})
        spec = media.resolve_preset("prores-hq", alpha=True)
        self.assertFalse(spec["alpha"])  # ignored, not silently faked
        self.assertNotIn("a", spec["pix_fmt"].split("p")[0])

    def test_no_encoder_is_a_sentence(self):
        fake_availability(set())
        with self.assertRaises(RuntimeError) as ctx:
            media.resolve_preset("dnxhr-hqx")
        self.assertIn("dnxhd", str(ctx.exception))

    def test_unknown_preset_raises(self):
        with self.assertRaises(KeyError):
            media.resolve_preset("prores-9999")

    def test_report_shape(self):
        fake_availability({"prores_ks", "libx264"})
        report = media.presets_report()
        ids = {r["id"] for r in report}
        self.assertEqual(ids, set(media.EXPORT_PRESETS))
        by_id = {r["id"]: r for r in report}
        self.assertTrue(by_id["prores-hq"]["available"])
        self.assertEqual(by_id["prores-hq"]["encoder"], "prores_ks")
        self.assertFalse(by_id["dnxhr-hqx"]["available"])
        self.assertIsNone(by_id["dnxhr-hqx"]["encoder"])
        for r in report:
            self.assertTrue(r["note"])  # every preset explains itself


class TestColorTags(unittest.TestCase):
    def test_copy_and_report(self):
        class CC:
            color_primaries = 1
            color_trc = 1
            colorspace = 1
            color_range = 1

        src, dst = CC(), CC()
        dst.color_primaries = 2
        msg = media.copy_color_tags(src, dst)
        self.assertEqual(dst.color_primaries, 1)
        self.assertIn("bt709", msg)
        self.assertIn("passed through", msg)

    def test_no_tags_is_honest(self):
        class Empty:
            pass

        msg = media.copy_color_tags(Empty(), Empty())
        self.assertIn("none readable", msg)


if __name__ == "__main__":
    unittest.main()
