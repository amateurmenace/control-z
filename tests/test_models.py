"""Model store: the registry's promises, and the archive-member path.

Downloads are stubbed — these must run offline and stdlib-only, like the rest
of the core suite.
"""

import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from czcore import models


class TestRegistry(unittest.TestCase):
    def test_every_entry_states_its_license_and_pins_its_hash(self):
        for name, spec in models.REGISTRY.items():
            self.assertTrue(spec.license, f"{name} has no license")
            self.assertTrue(spec.card, f"{name} has no card")
            self.assertTrue(spec.sha256, f"{name} ships without a pinned hash")
            self.assertEqual(len(spec.sha256), 64, f"{name}'s hash isn't sha256")

    def test_locally_built_models_say_how_to_build_them(self):
        for name, spec in models.REGISTRY.items():
            if spec.url is None:
                self.assertTrue(spec.hint,
                                f"{name} has no url and no hint — a dead end")

    def test_archive_entries_name_a_member(self):
        for name, spec in models.REGISTRY.items():
            if spec.url and ".tar" in spec.url:
                self.assertTrue(
                    spec.archive_member or spec.archive_dir,
                    f"{name} downloads a tarball but names nothing to keep")

    def test_diarization_pair_is_registered(self):
        """Scribe's speaker labels used to need two hand-placed files; the
        Models page could delete them but not bring them back."""
        for name in ("pyannote_seg", "speaker_embed"):
            self.assertIn(name, models.REGISTRY)
            self.assertIsNotNone(models.REGISTRY[name].url)


class TestArchiveMember(unittest.TestCase):
    """The pyannote weights only ship inside a tarball."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.payload = b"pretend onnx weights"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        inner = self.dir / "model.onnx"
        inner.write_bytes(self.payload)
        junk = self.dir / "LICENSE"
        junk.write_bytes(b"not the model")
        self.archive = self.dir / "bundle.tar.bz2"
        with tarfile.open(self.archive, "w:bz2") as tf:
            tf.add(inner, arcname="pkg/model.onnx")
            tf.add(junk, arcname="pkg/LICENSE")

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, member):
        return models.ModelSpec(
            name="t", filename="t.onnx", url="https://example/bundle.tar.bz2",
            sha256=self.digest, license="MIT", card="test",
            archive_member=member)

    def test_extracts_the_named_member(self):
        dest = self.dir / "kept.onnx"
        got = models._extract(self.archive, self._spec("pkg/model.onnx"), dest)
        self.assertEqual(got.read_bytes(), self.payload)
        self.assertEqual(hashlib.sha256(got.read_bytes()).hexdigest(), self.digest)

    def test_consumes_the_archive(self):
        dest = self.dir / "kept.onnx"
        models._extract(self.archive, self._spec("pkg/model.onnx"), dest)
        self.assertFalse(self.archive.exists(), "the tarball should not linger")

    def test_a_moved_member_is_a_sentence_not_a_keyerror(self):
        dest = self.dir / "kept.onnx"
        with self.assertRaises(RuntimeError) as ctx:
            models._extract(self.archive, self._spec("pkg/gone.onnx"), dest)
        msg = str(ctx.exception)
        self.assertIn("gone.onnx", msg)
        self.assertIn("code fix", msg)   # upstream moved it: retrying won't help

    def test_never_extracts_the_whole_archive(self):
        """A blanket extractall would let an archive write where it likes."""
        dest = self.dir / "kept.onnx"
        models._extract(self.archive, self._spec("pkg/model.onnx"), dest)
        self.assertFalse((self.dir / "pkg").exists())
        self.assertFalse((self.dir / "pkg" / "LICENSE").exists())


class TestArchiveDir(unittest.TestCase):
    """A voice is a directory — model + tokens + lexicon — so the store can
    keep a whole member directory, manifest-hashed like a single file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        src = self.dir / "src"
        (src / "sub").mkdir(parents=True)
        (src / "voice.onnx").write_bytes(b"pretend weights")
        (src / "tokens.txt").write_bytes(b"a b c")
        (src / "sub" / "lexicon.txt").write_bytes(b"HELLO HH")
        junk = self.dir / "outside.txt"
        junk.write_bytes(b"not part of the voice")
        self.archive = self.dir / "bundle.tar.bz2"
        with tarfile.open(self.archive, "w:bz2") as tf:
            tf.add(src / "voice.onnx", arcname="pkg/voice.onnx")
            tf.add(src / "tokens.txt", arcname="pkg/tokens.txt")
            tf.add(src / "sub" / "lexicon.txt", arcname="pkg/sub/lexicon.txt")
            tf.add(junk, arcname="elsewhere/outside.txt")
            tf.add(junk, arcname="pkg/../escape.txt")
        self.expected = models._sha256_dir(src)

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, member_dir="pkg"):
        return models.ModelSpec(
            name="t", filename="t", url="https://example/bundle.tar.bz2",
            sha256=self.expected, license="MIT", card="test",
            archive_dir=member_dir)

    def test_keeps_the_directory_and_its_manifest_hash(self):
        dest = self.dir / "kept"
        out = models._extract_dir(self.archive, self._spec(), dest)
        self.assertEqual((out / "voice.onnx").read_bytes(), b"pretend weights")
        self.assertEqual((out / "sub" / "lexicon.txt").read_bytes(), b"HELLO HH")
        self.assertEqual(models._sha256_dir(out), self.expected,
                         "the manifest hash must reproduce from the extraction")

    def test_leaves_everything_outside_the_prefix(self):
        dest = self.dir / "kept"
        out = models._extract_dir(self.archive, self._spec(), dest)
        self.assertFalse((out / "outside.txt").exists())
        self.assertFalse((self.dir / "elsewhere").exists())
        self.assertFalse((self.dir / "escape.txt").exists(),
                         "a ../ member name must never walk out")
        self.assertFalse((out.parent / "escape.txt").exists())

    def test_consumes_the_archive(self):
        models._extract_dir(self.archive, self._spec(), self.dir / "kept")
        self.assertFalse(self.archive.exists(), "the tarball should not linger")

    def test_a_moved_layout_is_a_sentence(self):
        with self.assertRaises(RuntimeError) as ctx:
            models._extract_dir(self.archive, self._spec("gone"),
                                self.dir / "kept")
        self.assertIn("code fix", str(ctx.exception))

    def test_manifest_hash_names_paths_not_just_bytes(self):
        """Same bytes under a different name is a different voice."""
        a = self.dir / "a"; a.mkdir(); (a / "x.onnx").write_bytes(b"w")
        b = self.dir / "b"; b.mkdir(); (b / "y.onnx").write_bytes(b"w")
        self.assertNotEqual(models._sha256_dir(a), models._sha256_dir(b))


if __name__ == "__main__":
    unittest.main()


class TestLicenceRuleIsCode(unittest.TestCase):
    """The permissive-only covenant, enforced at registry definition — not
    prose. The NLLB decision (CC-BY-NC) is the live case it exists for."""

    def test_every_registered_model_passes(self):
        for name, spec in models.REGISTRY.items():
            self.assertTrue(models._licence_is_permissive(spec.license),
                            f"{name}: {spec.license}")

    def test_a_noncommercial_card_refuses_at_definition(self):
        with self.assertRaises(ValueError):
            models.ModelSpec(
                name="nllb-200-distilled-600m", filename="nllb",
                url=None, sha256=None,
                license="CC-BY-NC-4.0 (Meta)", card="the tempting one")

    def test_gpl_refuses_too(self):
        with self.assertRaises(ValueError):
            models.ModelSpec(name="x", filename="x", url=None, sha256=None,
                             license="GPL-3.0", card="no")
