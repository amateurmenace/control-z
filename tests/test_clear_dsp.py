import unittest

try:
    import numpy as np
    import scipy  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False

SR = 48000


def band_power(x, sr, f0, width=2.0):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    band = (freqs > f0 - width) & (freqs < f0 + width)
    return float(spec[band].sum())


@unittest.skipUnless(HAVE, "needs numpy+scipy")
class TestDehum(unittest.TestCase):
    def _hummy(self, base=60.0, seconds=4.0):
        rng = np.random.default_rng(1)
        t = np.arange(int(SR * seconds)) / SR
        speech = rng.standard_normal(len(t)) * 0.05  # broadband stand-in
        hum = sum(0.1 / k * np.sin(2 * np.pi * base * k * t) for k in (1, 2, 3))
        return (speech + hum).astype(np.float32)

    def test_detects_60(self):
        from clear.dsp import detect_hum

        self.assertEqual(detect_hum(self._hummy(60.0), SR), 60.0)

    def test_detects_50(self):
        from clear.dsp import detect_hum

        self.assertEqual(detect_hum(self._hummy(50.0), SR), 50.0)

    def test_clean_audio_no_false_positive(self):
        from clear.dsp import detect_hum

        rng = np.random.default_rng(2)
        clean = (rng.standard_normal(SR * 4) * 0.05).astype(np.float32)
        self.assertIsNone(detect_hum(clean, SR))

    def test_notch_kills_20db_and_spares_speech_band(self):
        from clear.dsp import dehum

        x = self._hummy(60.0)
        y = dehum(x, SR, 60.0)
        for f in (60.0, 120.0, 180.0):
            drop = 10 * np.log10(band_power(x, SR, f) / (band_power(y, SR, f) + 1e-18))
            self.assertGreater(drop, 20.0, f"only {drop:.1f} dB at {f} Hz")
        keep = 10 * np.log10(band_power(x, SR, 1000, 200) /
                             (band_power(y, SR, 1000, 200) + 1e-18))
        self.assertLess(abs(keep), 1.0, "speech band damaged")


@unittest.skipUnless(HAVE, "needs numpy+scipy")
class TestDeclick(unittest.TestCase):
    def test_clicks_removed_signal_kept(self):
        from clear.dsp import declick

        t = np.arange(SR * 2) / SR
        x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        rng = np.random.default_rng(3)
        clicks = rng.choice(len(x) - 100, 12, replace=False) + 50
        y = x.copy()
        y[clicks] += rng.choice([-0.9, 0.9], len(clicks)).astype(np.float32)
        fixed, n = declick(y, SR)
        self.assertGreater(n, 0)
        err_before = float(np.abs(y - x).max())
        err_after = float(np.abs(fixed - x).max())
        self.assertLess(err_after, err_before / 5)

    def test_clean_untouched(self):
        from clear.dsp import declick

        t = np.arange(SR) / SR
        x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        fixed, n = declick(x, SR)
        self.assertTrue(np.allclose(fixed, x, atol=1e-4))


@unittest.skipUnless(HAVE, "needs numpy+scipy")
class TestRoomtone(unittest.TestCase):
    def test_generated_tone_matches_profile(self):
        from clear.roomtone import generate, profile

        rng = np.random.default_rng(4)
        # "room": low-passed noise (HVAC-ish)
        from scipy.signal import butter, sosfilt
        sos = butter(2, 400, "lowpass", fs=SR, output="sos")
        room = sosfilt(sos, rng.standard_normal(SR * 3)).astype(np.float32) * 0.02
        prof = profile(room, SR)
        tone = generate(prof, 3.0)
        p2 = profile(tone, SR)
        # log-spectral distance in the band that matters
        band = (prof["freqs"] > 30) & (prof["freqs"] < 4000)
        d = np.abs(10 * np.log10(prof["psd"][band]) -
                   10 * np.log10(p2["psd"][band])).mean()
        self.assertLess(d, 3.0, f"spectral distance {d:.2f} dB")
        rms_ratio = float(np.sqrt((tone ** 2).mean()) /
                          np.sqrt((room ** 2).mean()))
        self.assertAlmostEqual(rms_ratio, 1.0, delta=0.25)


@unittest.skipUnless(HAVE, "needs numpy+scipy+pyloudnorm")
class TestLoudness(unittest.TestCase):
    def test_normalize_hits_target(self):
        try:
            import pyloudnorm  # noqa: F401
        except ImportError:
            self.skipTest("pyloudnorm missing")
        from clear.loudness import measure_lufs, normalize

        rng = np.random.default_rng(5)
        x = (rng.standard_normal(SR * 6) * 0.02).astype(np.float32)
        y, report = normalize(x, SR, -24.0)
        self.assertAlmostEqual(measure_lufs(y, SR), -24.0, delta=0.5)
        self.assertFalse(report["limited_by_peak"])


if __name__ == "__main__":
    unittest.main()
