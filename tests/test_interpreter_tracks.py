"""Interpreter's writers, sidecars, glossary store and review queue —
pure logic, tmp dirs, no app support touched."""

import json
import tempfile
import unittest
from pathlib import Path

from interpreter import glossary as gl
from interpreter import kit
from interpreter.tracks import to_srt, to_vtt

CUES = [
    {"start": 0.0, "end": 2.5, "text": "Buenas noches."},
    {"start": 2.5, "end": 9.0,
     "text": "Bienvenidos a la reunión del Comité Escolar de Brookline, "
             "una noche importante para las escuelas."},
]


class TestWriters(unittest.TestCase):
    def test_srt_golden(self):
        srt = to_srt(CUES)
        self.assertIn("1\n00:00:00,000 --> 00:00:02,500\nBuenas noches.",
                      srt)
        self.assertIn("2\n00:00:02,500 --> 00:00:09,000\n", srt)

    def test_vtt_has_header_and_note(self):
        vtt = to_vtt(CUES, note="AI translation — beta · es")
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertIn("NOTE\nAI translation — beta · es", vtt)
        self.assertIn("00:00:00.000 --> 00:00:02.500", vtt)

    def test_long_lines_wrap_to_two(self):
        block = to_srt(CUES).split("\n\n")[1].rstrip("\n")
        lines = block.split("\n")[2:]
        self.assertEqual(len(lines), 2)

    def test_text_cannot_impersonate_timing(self):
        srt = to_srt([{"start": 0, "end": 1, "text": "a --> b\nc"}])
        self.assertEqual(srt.count("-->"), 1)   # the real cue arrow only


class TestSidecarPaths(unittest.TestCase):
    def test_session_and_file_shapes(self):
        with tempfile.TemporaryDirectory() as td:
            session = Path(td) / "abc123"
            session.mkdir()
            tp = kit.track_paths(str(session), "es")
            self.assertTrue(str(tp["srt"]).endswith(
                "/abc123/meeting.translated.es.srt"))
        tp2 = kit.track_paths("/lib/program.mp4", "zh")
        self.assertTrue(str(tp2["vtt"]).endswith(
            "/program.translated.zh.vtt"))
        self.assertTrue(str(kit.sidecar("/lib/program.mp4")).endswith(
            "/program.interpreter.json"))

    def test_english_still_wins_the_caption_sort(self):
        """Highlighter's no-transcript fallback grabs the first caption file
        in the folder, sorted. Our tracks live beside the meeting, so `en`
        must sort ahead of every translated track — pin it."""
        session = sorted(["meeting.translated.es.vtt", "meeting.en.vtt",
                          "meeting.translated.zh.vtt"])
        self.assertEqual(session[0], "meeting.en.vtt")
        local = sorted(["program.translated.es.srt", "program.srt"])
        self.assertEqual(local[0], "program.srt")

    def test_kit_and_cues_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            src = str(Path(td) / "program.mp4")
            Path(src).write_text("")
            k = kit.new_kit(src)
            k["languages"]["es"] = {"engine": "key", "n_cues": 2}
            kit.save_kit(src, k)
            back = kit.load_kit(src)
            self.assertEqual(back["languages"]["es"]["n_cues"], 2)
            kit.save_cues(src, "es", CUES)
            self.assertEqual(kit.load_cues(src, "es")[1]["end"], 9.0)
            self.assertEqual(kit.load_cues(src, "zh"), [])


class TestGlossaryStore(unittest.TestCase):
    def test_seed_loads_and_scaffold_stands_in(self):
        g = gl.load("brookline")
        self.assertGreaterEqual(g["version"], 1)
        self.assertIn("Coolidge Corner", g["keep"])
        self.assertEqual(g["terms"]["School Committee"]["es"]["status"],
                         "suggested")
        empty = gl.load("nowhere-ville")
        self.assertEqual(empty["version"], 0)
        self.assertEqual(empty["terms"], {})

    def test_save_bumps_version_and_scrubs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = gl.save("brookline", {
                "keep": [" Coolidge Corner ", ""],
                "terms": {
                    "override": {"es": {"text": "anulación", "status": "vetted"},
                                 "zh": {"text": "", "status": "vetted"},
                                 "pt": "anulação"},
                    "": {"es": {"text": "x"}},
                },
            }, root=root)
            self.assertEqual(out["version"], gl.load("brookline")["version"] + 1)
            self.assertEqual(out["keep"], ["Coolidge Corner"])
            self.assertEqual(out["terms"]["override"]["es"]["status"], "vetted")
            # a bare string render is honest but unvetted
            self.assertEqual(out["terms"]["override"]["pt"]["status"],
                             "suggested")
            self.assertNotIn("zh", out["terms"]["override"])
            self.assertNotIn("", out["terms"])
            again = gl.save("brookline", out, root=root)
            self.assertEqual(again["version"], out["version"] + 1)
            # the working copy wins the next load
            self.assertEqual(gl.load("brookline", root=root)["version"],
                             again["version"])

    def test_towns_marks_edited_copies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = {r["town"]: r for r in gl.towns(root=root)}
            self.assertFalse(rows["brookline"]["edited"])
            gl.save("brookline", gl.load("brookline"), root=root)
            rows = {r["town"]: r for r in gl.towns(root=root)}
            self.assertTrue(rows["brookline"]["edited"])

    def test_town_slug_is_strict(self):
        with self.assertRaises(ValueError):
            gl.load("///")


class TestReviewQueue(unittest.TestCase):
    def test_flag_updates_and_unflag_removes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kit.flag_line("/m/a", "Meeting A", "es", 4, "hello", "hola",
                          note="wrong tone", root=root)
            kit.flag_line("/m/a", "Meeting A", "es", 9, "bye", "adios",
                          root=root)
            items = kit.read_queue(root)
            self.assertEqual(len(items), 2)
            # re-flagging the same line replaces, never duplicates
            kit.flag_line("/m/a", "Meeting A", "es", 4, "hello", "hola",
                          note="better note", root=root)
            items = kit.read_queue(root)
            self.assertEqual(len(items), 2)
            self.assertEqual(
                next(r["note"] for r in items if r["i"] == 4), "better note")
            kit.flag_line("/m/a", "Meeting A", "es", 9, "", "", on=False,
                          root=root)
            self.assertEqual(len(kit.read_queue(root)), 1)

    def test_resolve_drops_the_item(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kit.flag_line("/m/a", "A", "ht", 2, "s", "t", root=root)
            kit.resolve_item("/m/a", "ht", 2, root=root)
            self.assertEqual(kit.read_queue(root), [])


if __name__ == "__main__":
    unittest.main()
