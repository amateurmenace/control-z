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
                    spec.archive_member,
                    f"{name} downloads a tarball but names no member to keep")

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


if __name__ == "__main__":
    unittest.main()
