"""The Hush-core port: estimator accuracy, PSNR gates, no-ghosting, identity.

Synthetic scenes with known ground truth, matching the culture of Hush's own
test_denoise.cpp. Needs numpy + cv2 (skips cleanly without).
"""

import unittest

try:
    import cv2  # noqa: F401
    import numpy as np
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False

if HAVE_DEPS:
    from czcore.denoise import HushParams, denoise_trio, estimate_sigmas

W, H = 320, 200
SIGMA = 0.03  # signal units (0..1)


def make_clean():
    """Gradient + rectangles + a soft sinusoid: edges, flats, and texture."""
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    img = 0.25 + 0.5 * x * np.ones_like(y)
    img += 0.06 * np.sin(x * 40) * np.sin(y * 40)
    img[40:120, 40:120] = 0.75
    img[130:180, 180:290] = 0.2
    rgb = np.stack([img, img * 0.9 + 0.05, img * 0.8 + 0.1], axis=-1)
    return np.clip(rgb * 255, 0, 255).astype(np.uint8)


def add_noise(img_u8, sigma, seed):
    rng = np.random.RandomState(seed)
    noisy = img_u8.astype(np.float32) / 255.0 + rng.normal(0, sigma, img_u8.shape)
    return np.clip(noisy * 255, 0, 255).astype(np.uint8)


def psnr(a_u8, b_u8):
    d = (a_u8.astype(np.float32) - b_u8.astype(np.float32)) / 255.0
    mse = float((d * d).mean())
    return 99.0 if mse == 0 else -10.0 * np.log10(mse)


@unittest.skipUnless(HAVE_DEPS, "pipeline deps (numpy/cv2) not installed")
class TestEstimator(unittest.TestCase):
    def test_iid_sigma_recovered(self):
        clean = make_clean()
        noisy = add_noise(clean, SIGMA, 1)
        partner = add_noise(clean, SIGMA, 2)
        sig = estimate_sigmas(noisy, partner)
        self.assertTrue(sig.had_temporal)
        # temporal estimator is the primary one for video: tight tolerance
        self.assertAlmostEqual(sig.ty, SIGMA, delta=0.25 * SIGMA)
        # spatial-family estimate sits at/above the temporal (max with 0.85t)
        self.assertGreater(sig.sy, 0.6 * SIGMA)
        self.assertLess(sig.sy, 2.0 * SIGMA)

    def test_clean_input_reads_near_zero(self):
        sig = estimate_sigmas(make_clean())
        self.assertLess(sig.sy, 0.012)  # texture reads a little; noise none

    def test_gains_shape(self):
        sig = estimate_sigmas(add_noise(make_clean(), SIGMA, 3))
        self.assertEqual(len(sig.gain_y), 16)
        for g in sig.gain_y:
            self.assertTrue(0.6 <= g <= 2.2)


@unittest.skipUnless(HAVE_DEPS, "pipeline deps (numpy/cv2) not installed")
class TestDenoise(unittest.TestCase):
    def test_static_trio_improves_hard(self):
        """Static camera: temporal + NLM should buy well over 6 dB at sigma 3%."""
        clean = make_clean()
        prev = add_noise(clean, SIGMA, 11)
        cur = add_noise(clean, SIGMA, 12)
        nxt = add_noise(clean, SIGMA, 13)
        out, info = denoise_trio(prev, cur, nxt)
        gained = psnr(out, clean) - psnr(cur, clean)
        self.assertGreater(gained, 6.0, f"only +{gained:.2f} dB")
        self.assertEqual(info["backend"], "hush-core")
        self.assertGreater(info["eff_n_med"], 1.5)  # averaging actually engaged

    def test_spatial_only_improves(self):
        clean = make_clean()
        cur = add_noise(clean, SIGMA, 21)
        out, info = denoise_trio(None, cur, None)
        gained = psnr(out, clean) - psnr(cur, clean)
        self.assertGreater(gained, 2.5, f"only +{gained:.2f} dB")

    def test_motion_no_ghosting(self):
        """Neighbors shifted 12 px: the knee gate must reject them — output
        must NOT drift toward the shifted content (that's ghosting)."""
        clean = make_clean()
        shifted = np.roll(clean, 12, axis=1)
        prev = add_noise(shifted, SIGMA, 31)
        nxt = add_noise(shifted, SIGMA, 32)
        cur = add_noise(clean, SIGMA, 33)
        out, _ = denoise_trio(prev, cur, nxt)
        # where the shift moved content strongly, out must stay with cur
        moved = np.abs(clean.astype(np.float32) - shifted.astype(np.float32)).sum(-1) > 25
        self.assertGreater(int(moved.sum()), 500)  # scene actually moved
        d_cur = np.abs(out.astype(np.float32) - clean.astype(np.float32)).sum(-1)[moved].mean()
        d_shift = np.abs(out.astype(np.float32) - shifted.astype(np.float32)).sum(-1)[moved].mean()
        self.assertLess(d_cur, 0.5 * d_shift,
                        "output leans toward the shifted neighbors — ghosting")

    def test_edges_survive(self):
        """Preserve Detail: the hard rectangle edge must stay sharp."""
        clean = make_clean()
        cur = add_noise(clean, SIGMA, 41)
        out, _ = denoise_trio(None, cur, None)
        edge_col_in = clean[60, 38:43, 0].astype(np.float32)   # across the rect edge
        edge_col_out = out[60, 38:43, 0].astype(np.float32)
        swing_in = float(edge_col_in.max() - edge_col_in.min())
        swing_out = float(edge_col_out.max() - edge_col_out.min())
        self.assertGreater(swing_out, 0.65 * swing_in, "edge softened too far")

    def test_near_identity_on_clean(self):
        clean = make_clean()
        out, _ = denoise_trio(clean, clean, clean)
        d = np.abs(out.astype(np.int16) - clean.astype(np.int16))
        self.assertLessEqual(int(d.max()), 6)
        self.assertLess(float(d.mean()), 1.0)

    def test_deterministic(self):
        clean = make_clean()
        cur = add_noise(clean, SIGMA, 51)
        a, _ = denoise_trio(None, cur, None)
        b, _ = denoise_trio(None, cur, None)
        self.assertTrue(np.array_equal(a, b))


if __name__ == "__main__":
    unittest.main()
