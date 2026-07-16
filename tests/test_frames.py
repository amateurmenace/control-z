"""Frame service: cache keying, decode-on-miss, pts-derived indices, EOF honesty.

Needs av + cv2 + numpy (skips cleanly without, like the other pipeline tests).
A tiny synthetic clip is encoded per test run — frame index is painted into
the pixels so frame-accuracy is checked against ground truth, not vibes.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

try:
    import av  # noqa: F401
    import cv2  # noqa: F401
    import numpy as np
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False

N_FRAMES = 48
W, H = 192, 108


def make_clip(path: str):
    """Gray levels encode the frame index: frame i is filled with i*5."""
    import av
    import numpy as np

    with av.open(path, "w") as out:
        v = out.add_stream("libx264", rate=24,
                           options={"crf": "10", "g": "12"})  # real GOPs: seeks matter
        v.width, v.height = W, H
        v.pix_fmt = "yuv420p"
        for i in range(N_FRAMES):
            img = np.full((H, W, 3), i * 5, dtype=np.uint8)
            for pkt in v.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                out.mux(pkt)
        for pkt in v.encode():
            out.mux(pkt)


def jpeg_level(path: Path) -> float:
    import cv2

    img = cv2.imread(str(path))
    return float(img.mean())


@unittest.skipUnless(HAVE_DEPS, "pipeline deps (av/cv2/numpy) not installed")
class TestFrameService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cz-frames-")
        cls.clip = str(Path(cls.tmp) / "clip.mp4")
        make_clip(cls.clip)
        # isolate the cache root
        import suite.frames as frames_mod
        cls.frames_mod = frames_mod
        cls.orig_root = frames_mod.cache_root
        cache = Path(cls.tmp) / "cache"
        cache.mkdir()
        frames_mod.cache_root = lambda: cache

    @classmethod
    def tearDownClass(cls):
        cls.frames_mod.cache_root = cls.orig_root
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def service(self):
        return self.frames_mod.FrameService(prefetch=0)

    def test_decode_and_cache(self):
        svc = self.service()
        f = svc.frame_path(self.clip, 10, height=54, prefetch=False)
        self.assertIsNotNone(f)
        self.assertTrue(f.exists())
        # frame 10 is gray level 50 (x264 crf10 keeps it within a couple of codes)
        self.assertAlmostEqual(jpeg_level(f), 50, delta=4)
        svc.close_all()

    def test_random_access_is_frame_accurate(self):
        svc = self.service()
        for idx in (37, 5, 23, 0, 47):  # backward + forward, across GOPs
            f = svc.frame_path(self.clip, idx, height=54, prefetch=False)
            self.assertIsNotNone(f, f"frame {idx} missing")
            self.assertAlmostEqual(jpeg_level(f), idx * 5, delta=4,
                                   msg=f"frame {idx} wrong content")
        svc.close_all()

    def test_past_eof_is_none_not_alias(self):
        svc = self.service()
        self.assertIsNone(svc.frame_path(self.clip, N_FRAMES + 5,
                                         height=54, prefetch=False))
        svc.close_all()

    def test_cache_key_changes_with_mtime(self):
        d1 = self.frames_mod.clip_cache_dir(self.clip, 54)
        import os
        st = os.stat(self.clip)
        os.utime(self.clip, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        d2 = self.frames_mod.clip_cache_dir(self.clip, 54)
        self.assertNotEqual(d1, d2)  # stale previews can never be served

    def test_heights_are_separate(self):
        svc = self.service()
        a = svc.frame_path(self.clip, 3, height=54, prefetch=False)
        b = svc.frame_path(self.clip, 3, height=96, prefetch=False)
        self.assertNotEqual(a, b)
        import cv2
        self.assertEqual(cv2.imread(str(a)).shape[0], 54)
        self.assertEqual(cv2.imread(str(b)).shape[0], 96)
        svc.close_all()

    def test_native_frame(self):
        svc = self.service()
        img = svc.native_frame(self.clip, 20)
        self.assertEqual(img.shape, (H, W, 3))
        self.assertAlmostEqual(float(img.mean()), 100, delta=4)
        svc.close_all()


if __name__ == "__main__":
    unittest.main()
