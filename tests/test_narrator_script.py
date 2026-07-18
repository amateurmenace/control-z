"""Narrator's sidecar, lint, mix graph and voice discovery — pure logic,
tmp dirs, no ffmpeg, no sherpa, no network."""

import tempfile
import unittest
from pathlib import Path

from czcore import tts
from narrator import script
from narrator.describe import draft_prompt, lint
from narrator.mix import build_graph


class TestScriptStore(unittest.TestCase):
    def test_paths_for_session_and_file(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "abc"
            d.mkdir()
            self.assertTrue(str(script.sidecar(str(d))).endswith(
                "/abc/meeting.narrator.json"))
        outs = script.out_paths("/lib/program.mp4")
        self.assertTrue(str(outs["vtt"]).endswith("/program.described.vtt"))
        self.assertTrue(str(outs["mix_video"]).endswith("/program.ad-mix.mp4"))

    def test_roundtrip_and_version_gate(self):
        with tempfile.TemporaryDirectory() as td:
            src = str(Path(td) / "p.mp4")
            Path(src).write_text("")
            s = script.new(src)
            s["cues"] = [{"start": 1, "end": 3, "text": "x",
                          "status": "accepted"}]
            script.save(src, s)
            self.assertEqual(script.load(src)["cues"][0]["text"], "x")
            script.sidecar(src).write_text('{"version": 99}')
            self.assertIsNone(script.load(src))

    def test_described_vtt_carries_only_reviewed_text(self):
        cues = [
            {"start": 0.0, "end": 2.0, "text": "A wide shot.",
             "status": "accepted"},
            {"start": 3.0, "end": 5.0, "text": "draft words",
             "status": "draft"},
            {"start": 6.0, "end": 8.0, "text": "", "status": "accepted"},
            {"start": 9.0, "end": 11.0, "text": "Edited words.",
             "status": "edited"},
        ]
        vtt = script.described_vtt(cues, note="audio description — beta")
        self.assertIn("A wide shot.", vtt)
        self.assertIn("Edited words.", vtt)
        self.assertNotIn("draft words", vtt)
        self.assertIn("NOTE\naudio description — beta", vtt)


class TestLint(unittest.TestCase):
    def test_clean_present_tense_passes(self):
        self.assertEqual(lint("A slide lists the FY27 budget totals.", 6.0),
                         [])

    def test_each_smell_is_named(self):
        self.assertIn("camera-talk", lint("We see a man at a podium.", 6.0))
        self.assertIn("interprets", lint("She seems happy with it.", 6.0))
        self.assertIn("past-tense", lint("He walked to the podium.", 6.0))
        self.assertIn("over-budget",
                      lint(" ".join(["word"] * 40), 3.0))
        self.assertEqual(lint("", 3.0), ["empty"])

    def test_prompt_carries_the_budget(self):
        self.assertIn("At most 12 words", draft_prompt("scene", 12))
        self.assertIn("transcript", draft_prompt("graphic", 0))
        self.assertIn("graphic", draft_prompt("graphic", 20).lower())


class TestMixGraph(unittest.TestCase):
    def test_graph_shape(self):
        g = build_graph([1500, 42000], duration=60.0)
        self.assertIn("[1:a]", g)
        self.assertIn("adelay=1500:all=1", g)
        self.assertIn("adelay=42000:all=1", g)
        self.assertIn("amix=inputs=2:duration=longest:normalize=0[ad]", g)
        self.assertIn("sidechaincompress", g)
        self.assertIn("apad=whole_dur=60.000", g)
        self.assertIn("[mixa]", g)
        self.assertIn("[mixv]", g)

    def test_zero_cues_refused(self):
        with self.assertRaises(ValueError):
            build_graph([], duration=10)


class TestVoiceDiscovery(unittest.TestCase):
    def test_voice_dir_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(tts._voice_dirs(root), [])
            v = root / "vits-ljs"
            v.mkdir()
            (v / "vits-ljs.onnx").write_bytes(b"x")
            self.assertEqual(tts._voice_dirs(root), [])   # tokens missing
            (v / "tokens.txt").write_text("a")
            (v / "lexicon.txt").write_text("a a")
            found = tts._voice_dirs(root)
            self.assertEqual([d.name for d in found], ["vits-ljs"])
            cfg = tts.voice_config(found[0])
            self.assertTrue(cfg["model"].endswith("vits-ljs.onnx"))
            self.assertTrue(cfg["lexicon"].endswith("lexicon.txt"))
            self.assertEqual(cfg["data_dir"], "")

    def test_bad_voice_dir_is_a_sentence(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError):
                tts.voice_config(Path(td))


if __name__ == "__main__":
    unittest.main()
