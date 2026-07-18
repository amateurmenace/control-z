"""The local translation runtime — discovery, the N| adapter, glossary
protection, and the Simple-English exclusion. No model, no ctranslate2 needed:
the translator is faked, exactly as the key-path tests fake `complete`.
"""

import tempfile
import unittest
from pathlib import Path

from czcore import mt, mt_local


class DiscoveryTest(unittest.TestCase):
    def test_no_model_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            got = mt_local.available(root=Path(td))
            self.assertIsNone(got["engine"])
            self.assertIn("no local translation model", got["sentence"])

    def test_discovers_a_ct2_shaped_directory(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "mt" / "nllb200"
            d.mkdir(parents=True)
            (d / "model.bin").write_bytes(b"\x00")
            (d / "tokenizer.json").write_text("{}")
            self.assertEqual(mt_local.model_name(root=Path(td)), "nllb200")
            # engine is only 'local' when ctranslate2 also imports; the shape is
            # found regardless, and the sentence stays honest either way
            got = mt_local.available(root=Path(td))
            self.assertIn(got["engine"], (None, "local"))


class AdapterTest(unittest.TestCase):
    def test_flores_mapping_covers_the_panel(self):
        for code in ("es", "zh", "pt", "ht", "vi", "ru"):
            self.assertIn(code, mt_local.FLORES)
        self.assertNotIn("simple", mt_local.FLORES)   # NLLB has no Simple English

    def test_adapter_honors_the_numbered_protocol(self):
        # a fake translate_lines: upper-cases, so we can see it ran
        real = mt_local.translate_lines
        mt_local.translate_lines = lambda texts, code, keep=None, root=None: \
            [t.upper() for t in texts]
        try:
            complete = mt_local.adapter("es")
            out = complete(prompt="0|hello there\n1|second line")
            lines = dict(ln.split("|", 1) for ln in out.splitlines())
            self.assertEqual(lines["0"], "HELLO THERE")
            self.assertEqual(lines["1"], "SECOND LINE")
        finally:
            mt_local.translate_lines = real

    def test_translate_cues_prefers_local_when_available(self):
        # patch the whole local path: available() says local, adapter upper-cases
        real_avail = mt_local.available
        real_adapter = mt_local.adapter
        mt_local.available = lambda root=None: {"engine": "local", "model": "fake"}
        mt_local.adapter = lambda code, glossary=None, root=None: (
            lambda prompt="", system="", max_tokens=0:
            "\n".join(f"{ln.split('|',1)[0]}|{ln.split('|',1)[1].upper()}"
                      for ln in prompt.splitlines() if "|" in ln))
        try:
            cues = [{"start": 0, "end": 1, "text": "hello"}]
            out = mt.translate_cues(cues, "es")     # no `complete` passed
            self.assertEqual(out[0]["text"], "HELLO")
            self.assertFalse(out[0].get("fallback"))
        finally:
            mt_local.available = real_avail
            mt_local.adapter = real_adapter

    def test_simple_english_never_uses_the_local_engine(self):
        # even with a local model present, 'simple' must fall to the key path
        real_avail = mt_local.available
        mt_local.available = lambda root=None: {"engine": "local", "model": "fake"}
        try:
            captured = {}

            def fake_complete(prompt="", system="", max_tokens=0):
                captured["system"] = system
                return "\n".join(f"{ln.split('|',1)[0]}|simplified"
                                 for ln in prompt.splitlines() if "|" in ln)
            cues = [{"start": 0, "end": 1, "text": "The aforementioned article."}]
            # passing complete= means we drive the key path deliberately; the
            # point is the local adapter is not silently substituted for simple
            out = mt.translate_cues(cues, "simple", complete=fake_complete)
            self.assertIn("Simple English", captured["system"])
            self.assertEqual(out[0]["text"], "simplified")
        finally:
            mt_local.available = real_avail


class GlossaryProtectionTest(unittest.TestCase):
    def test_keep_terms_are_protected_and_restored(self):
        seen = {}

        def fake_ct2_translate(texts, code, keep=None, root=None):
            # the "model" would mangle a name; the placeholder shields it
            seen["texts"] = texts
            return [t.replace("beta", "translated") for t in texts]
        real = mt_local.translate_lines

        def wrapped(texts, code, keep=None, root=None):
            # exercise _protect/_restore around a fake core
            outs = []
            for t in texts:
                prot, holds = mt_local._protect(t, keep or [])
                res = prot.replace("beta", "translated")
                outs.append(mt_local._restore(res, holds))
            return outs
        mt_local.translate_lines = wrapped
        try:
            complete = mt_local.adapter("es", {"keep": ["Harvard Street"]})
            out = complete(prompt="0|beta on Harvard Street")
            # the keep-term survives verbatim; the rest is 'translated'
            self.assertIn("Harvard Street", out)
            self.assertIn("translated", out)
        finally:
            mt_local.translate_lines = real


if __name__ == "__main__":
    unittest.main()
