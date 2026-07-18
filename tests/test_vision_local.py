"""Local vision for Narrator — discovery by shape, the availability probe, and
the local-first hook in narrator/describe.py. No ONNX model, no onnxruntime
call: the vision engine is faked, so the plumbing and the fallback are what get
checked, not a model's arithmetic.
"""

import tempfile
import unittest
from pathlib import Path

from czcore import vision


class DiscoveryTest(unittest.TestCase):
    def test_no_model_is_honest(self):
        with tempfile.TemporaryDirectory() as td:
            got = vision.available(root=Path(td))
            self.assertFalse(got["ok"])
            self.assertIn("no on-device vision model", got["sentence"])

    def test_discovers_a_vlm_shaped_directory(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "vlm" / "moondream"
            d.mkdir(parents=True)
            (d / "vision_encoder.onnx").write_bytes(b"\x00")
            (d / "text_decoder.onnx").write_bytes(b"\x00")
            (d / "tokenizer.json").write_text("{}")
            self.assertEqual(vision.model_name(root=Path(td)), "moondream")

    def test_vlm_namespace_is_separate_from_tts_voices(self):
        # a VLM under models_dir()/vlm/ must NOT be seen by tts's top-level
        # voice discovery (the collision the vlm/ namespace exists to prevent)
        from czcore import tts
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "vlm" / "moondream"
            d.mkdir(parents=True)
            (d / "vision_encoder.onnx").write_bytes(b"\x00")
            (d / "text_decoder.onnx").write_bytes(b"\x00")
            (d / "tokenizer.json").write_text("{}")
            # tts scans top-level dirs for *.onnx + tokens.txt — vlm/ has neither
            self.assertEqual(tts._voice_dirs(root=root), [])


class DescribeFrameHookTest(unittest.TestCase):
    """narrator/describe.py tries local first, falls back to the key, and
    labels each draft by what actually drew it."""

    def test_local_first_returns_local_origin(self):
        from narrator import describe
        real_avail, real_desc = vision.available, vision.describe
        vision.available = lambda root=None: {"ok": True, "model": "moondream"}
        vision.describe = lambda *a, **k: "A board sits at a long table."
        vision.model_name = lambda root=None: "moondream"
        try:
            text, origin = describe.describe_frame(b"jpegbytes", "scene", 8)
            self.assertEqual(text, "A board sits at a long table.")
            self.assertTrue(origin.startswith("local:"))
        finally:
            vision.available, vision.describe = real_avail, real_desc

    def test_falls_back_to_key_when_no_local_model(self):
        from czcore import llm
        from narrator import describe
        real_v, real_enabled, real_cv, real_status = (
            vision.available, llm.enabled, llm.complete_vision, llm.status)
        vision.available = lambda root=None: {"ok": False, "model": None}
        llm.enabled = lambda: True
        llm.status = lambda: {"model": "claude-x", "enabled": True}
        llm.complete_vision = lambda *a, **k: "A described scene."
        try:
            text, origin = describe.describe_frame(b"jpegbytes", "scene", 8)
            self.assertEqual(text, "A described scene.")
            self.assertTrue(origin.startswith("ai:"))
        finally:
            (vision.available, llm.enabled, llm.complete_vision,
             llm.status) = real_v, real_enabled, real_cv, real_status

    def test_no_engine_raises_a_sentence(self):
        from czcore import llm
        from narrator import describe
        real_v, real_enabled = vision.available, llm.enabled
        vision.available = lambda root=None: {"ok": False, "model": None}
        llm.enabled = lambda: False
        try:
            with self.assertRaises(RuntimeError) as cm:
                describe.describe_frame(b"jpegbytes", "scene", 8)
            self.assertIn("Models page", str(cm.exception))
        finally:
            vision.available, llm.enabled = real_v, real_enabled


if __name__ == "__main__":
    unittest.main()
