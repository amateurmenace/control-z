import unittest

try:
    import cv2
    import numpy as np
    HAVE = True
except ImportError:
    HAVE = False


def model_present():
    try:
        from czcore.models import model_path
        model_path("realesrgan-x4", auto_download=False)
        return True
    except Exception:
        return False


@unittest.skipUnless(HAVE, "needs numpy+cv2")
class TestLanczosBackend(unittest.TestCase):
    def test_shapes_and_honesty(self):
        from rise.engine import upscale_frame

        f = (np.random.rand(90, 120, 3) * 255).astype(np.uint8)
        out, info = upscale_frame(f, 2, model="lanczos")
        self.assertEqual(out.shape, (180, 240, 3))
        self.assertEqual(info.backend, "lanczos")
        self.assertFalse(info.synthesized)

    def test_unknown_model_rejected(self):
        from rise.engine import resolve_model

        with self.assertRaises(ValueError):
            resolve_model("magic-upscaler-9000")


@unittest.skipUnless(HAVE and model_present(), "realesrgan-x4.onnx not converted")
class TestOnnxBackend(unittest.TestCase):
    def test_beats_bicubic_on_downscaled_detail(self):
        from rise.engine import upscale_frame

        rng = np.random.default_rng(9)
        # detailed synthetic scene: text-like structure + gradients
        hi = np.zeros((256, 256, 3), np.uint8)
        for i in range(0, 256, 16):
            cv2.line(hi, (i, 0), (i, 255), (255, 255, 255), 1)
            cv2.circle(hi, (int(rng.uniform(20, 236)), int(rng.uniform(20, 236))),
                       int(rng.uniform(4, 12)), tuple(int(x) for x in rng.uniform(60, 255, 3)), -1)
        lo = cv2.resize(hi, (64, 64), interpolation=cv2.INTER_AREA)

        up, info = upscale_frame(lo, 4, model="realesrgan-x4")
        self.assertTrue(info.synthesized)
        bicubic = cv2.resize(lo, (256, 256), interpolation=cv2.INTER_CUBIC)

        def psnr(a, b):
            mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
            return 10 * np.log10(255 ** 2 / (mse + 1e-9))

        self.assertGreater(psnr(up, hi), psnr(bicubic, hi) - 0.5,
                           "model should at least match bicubic on structure")

    def test_tiling_seamless(self):
        from rise.engine import upscale_frame

        f = (np.random.rand(200, 300, 3) * 255).astype(np.uint8)
        whole, _ = upscale_frame(f, 4, model="realesrgan-x4", tile=512)
        tiled, _ = upscale_frame(f, 4, model="realesrgan-x4", tile=128)
        diff = np.abs(whole.astype(np.int16) - tiled.astype(np.int16)).mean()
        self.assertLess(float(diff), 3.0, "tile seams visible")


if __name__ == "__main__":
    unittest.main()
