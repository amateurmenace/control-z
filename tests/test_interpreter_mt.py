"""Interpreter's engine math — cues, chunks, glossary constraints, the
N| protocol. No network, no key: the model is a fake with opinions."""

import unittest

from czcore import mt


def segs(*rows):
    return [{"start": s, "end": e, "text": t} for s, e, t in rows]


class TestCoalesce(unittest.TestCase):
    def test_rolling_fragments_join_and_break_at_sentence_end(self):
        cues = mt.coalesce(segs(
            (0.0, 2.0, "good evening and welcome to the"),
            (2.0, 4.0, "school committee meeting for June 18."),
            (4.2, 6.0, "We will begin with public comment."),
            (9.0, 11.0, "Thank you."),
        ))
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0]["start"], 0.0)
        self.assertEqual(cues[0]["end"], 4.0)
        self.assertTrue(cues[0]["text"].endswith("June 18."))
        self.assertEqual(cues[1]["text"], "We will begin with public comment.")
        # short closer stands alone rather than vanishing
        self.assertEqual(cues[2]["text"], "Thank you.")

    def test_max_chars_forces_a_break(self):
        a = "a" * 50
        b = "b" * 50
        cues = mt.coalesce(segs((0, 2, a), (2, 4, b)))
        self.assertEqual([c["text"] for c in cues], [a, b])

    def test_silence_gap_forces_a_break(self):
        cues = mt.coalesce(segs((0, 2, "before the pause"),
                                (5.0, 6.0, "after the pause")))
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[1]["start"], 5.0)

    def test_long_hold_breaks_at_max_dur(self):
        cues = mt.coalesce(segs((0, 4, "one thing"), (4, 8, "another thing"),
                                (8, 12, "a third thing")))
        self.assertGreater(len(cues), 1)

    def test_empty_fragments_are_skipped(self):
        cues = mt.coalesce(segs((0, 1, "  "), (1, 2, "words."),
                                (2, 3, "")))
        self.assertEqual(len(cues), 1)
        # timing belongs to the words, not the silence around them
        self.assertEqual(cues[0]["start"], 1.0)

    def test_timing_is_monotonic_and_carried(self):
        cues = mt.coalesce(segs((0, 2, "alpha beta"), (2, 4, "gamma delta."),
                                (4.1, 6, "epsilon zeta eta theta.")))
        for c in cues:
            self.assertLessEqual(c["start"], c["end"])
        starts = [c["start"] for c in cues]
        self.assertEqual(starts, sorted(starts))


class TestChunks(unittest.TestCase):
    def test_sizes_and_order(self):
        cues = [{"start": i, "end": i + 1, "text": str(i)} for i in range(95)]
        parts = mt.chunks(cues, per=40)
        self.assertEqual([len(p) for p in parts], [40, 40, 15])
        self.assertEqual(parts[2][-1]["text"], "94")

    def test_per_is_clamped_sane(self):
        self.assertEqual(len(mt.chunks([{"text": "x"}], per=0)), 1)


GLOSSARY = {
    "keep": ["Coolidge Corner", "Brookline"],
    "terms": {"override": {"es": {"text": "anulación del límite (override)",
                                  "status": "suggested"}}},
}


class TestGlossary(unittest.TestCase):
    def test_prompt_only_names_terms_present(self):
        block = mt.glossary_prompt(GLOSSARY, "es",
                                   "the override for Coolidge Corner")
        self.assertIn("Coolidge Corner", block)
        self.assertIn("anulación", block)
        self.assertNotIn("Brookline", block)

    def test_prompt_empty_when_nothing_applies(self):
        self.assertEqual(mt.glossary_prompt(GLOSSARY, "es", "hello there"), "")
        self.assertEqual(mt.glossary_prompt(None, "es", "override"), "")

    def test_check_kept_is_case_insensitive(self):
        self.assertEqual(mt.check_kept("Meet at COOLIDGE CORNER now",
                                       "nos vemos en la esquina",
                                       GLOSSARY["keep"]),
                         ["Coolidge Corner"])
        self.assertEqual(mt.check_kept("Meet at Coolidge Corner",
                                       "en coolidge corner",
                                       GLOSSARY["keep"]), [])


class TestTranslateCues(unittest.TestCase):
    CUES = [{"start": 0.0, "end": 2.0, "text": "Good evening."},
            {"start": 2.0, "end": 4.0, "text": "Welcome to Brookline."}]

    def test_lines_map_back_with_timing_and_source(self):
        def fake(prompt, system, max_tokens):
            return "\n".join(f"{k}|linea {k}" for k in range(2))
        out = mt.translate_cues(self.CUES, "es", complete=fake)
        self.assertEqual(out[0]["text"], "linea 0")
        self.assertEqual(out[1]["src"], "Welcome to Brookline.")
        self.assertEqual(out[1]["start"], 2.0)
        self.assertNotIn("fallback", out[0])

    def test_dropped_line_falls_back_and_says_so(self):
        def fake(prompt, system, max_tokens):
            return "0|buenas noches"
        out = mt.translate_cues(self.CUES, "es", complete=fake)
        self.assertNotIn("fallback", out[0])
        self.assertTrue(out[1]["fallback"])
        self.assertEqual(out[1]["text"], "Welcome to Brookline.")

    def test_failed_chunk_keeps_english_for_every_line(self):
        def fake(prompt, system, max_tokens):
            raise RuntimeError("rate limited by the API (429)")
        out = mt.translate_cues(self.CUES, "es", complete=fake)
        self.assertTrue(all(c.get("fallback") for c in out))

    def test_lost_keep_term_is_marked_for_review(self):
        def fake(prompt, system, max_tokens):
            return "0|buenas noches\n1|bienvenidos al pueblo"
        out = mt.translate_cues(self.CUES, "es", glossary=GLOSSARY,
                                complete=fake)
        self.assertEqual(out[1]["miss"], ["Brookline"])
        self.assertNotIn("miss", out[0])

    def test_prompts_carry_protocol_and_language(self):
        seen = {}

        def fake(prompt, system, max_tokens):
            seen["prompt"], seen["system"] = prompt, system
            return "0|x\n1|y"
        mt.translate_cues(self.CUES, "es", glossary=GLOSSARY, complete=fake)
        self.assertIn("0|Good evening.", seen["prompt"])
        self.assertIn("Spanish", seen["system"])
        self.assertIn("N| prefix", seen["system"])
        # Brookline appears in the chunk, so the constraint rides along
        self.assertIn("Brookline", seen["system"])

    def test_simple_english_is_a_rewrite_not_a_translation(self):
        seen = {}

        def fake(prompt, system, max_tokens):
            seen["system"] = system
            return "0|x\n1|y"
        mt.translate_cues(self.CUES, "simple", complete=fake)
        self.assertIn("Simple English", seen["system"])
        self.assertIn("plain language", seen["system"].lower())

    def test_chunking_covers_every_cue_in_order(self):
        cues = [{"start": i, "end": i + 1, "text": f"line {i}"}
                for i in range(7)]

        def fake(prompt, system, max_tokens):
            return "\n".join(f"{k}|ok {ln.split('|', 1)[1]}"
                             for k, ln in enumerate(prompt.splitlines()))
        out = mt.translate_cues(cues, "es", complete=fake, per=3)
        self.assertEqual(len(out), 7)
        self.assertEqual(out[6]["text"], "ok line 6")

    def test_progress_and_cancel_hooks_run(self):
        ticks = []

        def fake(prompt, system, max_tokens):
            return "0|a"

        class Stop(Exception):
            pass

        def cancel():
            if ticks:
                raise Stop()
        mt.translate_cues([{"start": 0, "end": 1, "text": "x"}], "es",
                          complete=fake,
                          progress=lambda f, m: ticks.append((f, m)))
        self.assertEqual(ticks[-1][0], 1.0)
        with self.assertRaises(Stop):
            mt.translate_cues(
                [{"start": 0, "end": 1, "text": "x"}] * 90, "es",
                complete=fake, per=40,
                progress=lambda f, m: ticks.append((f, m)),
                check_cancel=cancel)

    def test_unknown_language_is_a_sentence(self):
        with self.assertRaises(RuntimeError):
            mt.translate_cues(self.CUES, "klingon", complete=lambda **k: "")


class TestLanguages(unittest.TestCase):
    def test_the_seven_panel_languages(self):
        codes = [l["code"] for l in mt.LANGUAGES]
        self.assertEqual(codes, ["es", "simple", "zh", "pt", "ht", "vi", "ru"])
        self.assertEqual(mt.lang("ht")["name"], "Kreyòl Ayisyen")
        self.assertIsNone(mt.lang("xx"))
        # simple english rides the en srclang for the player
        self.assertEqual(mt.lang("simple")["srclang"], "en")


if __name__ == "__main__":
    unittest.main()
