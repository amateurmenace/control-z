"""Extractive cleanup: filler strip + silence tightening.

Pure over the words Scribe wrote — no media touched. The route proposes the
pull-list, and on write leaves a CMX3600 cut list of what survives; the source
is never edited.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scribe import tighten as tt
from scribe.transcript import Segment, Transcript, Word


def _t(segs, duration=10.0):
    return Transcript(source="clip.mp4", language="en", duration=duration,
                      segments=segs)


class TestFillerStrip(unittest.TestCase):
    def test_finds_disfluencies_keeps_real_words(self):
        seg = Segment(0.0, 3.0, "Um so the crosswalk, uh, passed", words=[
            Word("Um", 0.0, 0.4), Word("so", 0.5, 0.8),
            Word("the", 0.9, 1.1), Word("crosswalk,", 1.2, 2.0),
            Word("uh,", 2.1, 2.4), Word("passed", 2.5, 3.0)])
        rem = tt.filler_removals(_t([seg]))
        self.assertEqual([r.text for r in rem], ["Um", "uh,"])
        self.assertTrue(all(r.kind == "filler" for r in rem))
        # "so" is never treated as filler — removing it would change meaning
        self.assertNotIn("so", [r.text.lower() for r in rem])

    def test_caller_can_add_its_own_fillers(self):
        seg = Segment(0.0, 2.0, "like basically done", words=[
            Word("like", 0.0, 0.3), Word("basically", 0.4, 1.0),
            Word("done", 1.1, 1.6)])
        base = tt.filler_removals(_t([seg]))
        self.assertEqual(base, [])                      # neither is a default
        more = tt.filler_removals(_t([seg]), extra=["like", "basically"])
        self.assertEqual([r.text for r in more], ["like", "basically"])

    def test_no_word_timings_yields_no_filler_spans(self):
        seg = Segment(0.0, 3.0, "um the whole thing", words=[])
        self.assertEqual(tt.filler_removals(_t([seg])), [])


class TestSilenceTighten(unittest.TestCase):
    def test_gap_over_threshold_becomes_a_padded_removal(self):
        segs = [Segment(0.0, 2.0, "one", words=[Word("one", 0.0, 2.0)]),
                Segment(5.0, 6.0, "two", words=[Word("two", 5.0, 6.0)])]
        rem = tt.silence_removals(_t(segs), min_gap=0.7, pad=0.1)
        self.assertEqual(len(rem), 1)
        self.assertEqual(rem[0].kind, "silence")
        self.assertAlmostEqual(rem[0].start, 2.1)       # padded off the tail
        self.assertAlmostEqual(rem[0].end, 4.9)         # padded off the onset

    def test_short_gaps_are_left_alone(self):
        segs = [Segment(0.0, 2.0, "one", words=[Word("one", 0.0, 2.0)]),
                Segment(2.3, 3.0, "two", words=[Word("two", 2.3, 3.0)])]
        self.assertEqual(tt.silence_removals(_t(segs), min_gap=0.7), [])

    def test_falls_back_to_segments_without_word_timings(self):
        segs = [Segment(0.0, 2.0, "one", words=[]),
                Segment(6.0, 7.0, "two", words=[])]
        rem = tt.silence_removals(_t(segs), min_gap=0.7, pad=0.0)
        self.assertEqual(len(rem), 1)
        self.assertAlmostEqual(rem[0].start, 2.0)
        self.assertAlmostEqual(rem[0].end, 6.0)


class TestKeepRanges(unittest.TestCase):
    def test_inverts_and_merges_overlaps(self):
        rem = [tt.Removal(1.0, 2.0, "filler"), tt.Removal(1.5, 3.0, "silence")]
        keeps = tt.keep_ranges(10.0, rem)
        self.assertEqual([(s.start, s.end) for s in keeps],
                         [(0.0, 1.0), (3.0, 10.0)])      # 1.0–3.0 merged out

    def test_no_removals_keeps_the_whole_clip(self):
        keeps = tt.keep_ranges(10.0, [])
        self.assertEqual([(s.start, s.end) for s in keeps], [(0.0, 10.0)])

    def test_summary_adds_up_and_never_exceeds_duration(self):
        rem = [tt.Removal(0.0, 4.0, "silence"), tt.Removal(3.0, 12.0, "filler")]
        s = tt.summarize(10.0, rem)
        self.assertEqual(s["kept_seconds"], 0.0)        # clamped, never negative
        self.assertEqual((s["n_fillers"], s["n_silences"]), (1, 1))


class TestTightenRoute(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from czcore.appshell.jobs import JobManager
        from suite.tools import scribe as scribetool

        self.td = tempfile.TemporaryDirectory(prefix="cz-tighten-")
        self.clip = Path(self.td.name) / "meeting.mp4"
        self.clip.write_bytes(b"not real media")   # probe fails → fps falls to 24
        app = FastAPI()
        scribetool.register_scribe(app, JobManager(), None)
        self.cl = TestClient(app)
        self.addCleanup(self.td.cleanup)

    def _sidecar(self):
        segs = [{"start": 0.0, "end": 2.0, "text": "um the vote",
                 "words": [{"w": "um", "s": 0.0, "e": 0.4},
                           {"w": "the", "s": 0.5, "e": 0.7},
                           {"w": "vote", "s": 0.8, "e": 2.0}]},
                {"start": 6.0, "end": 7.0, "text": "passed",
                 "words": [{"w": "passed", "s": 6.0, "e": 7.0}]}]
        self.clip.with_suffix(".scribe.json").write_text(json.dumps(
            {"source": str(self.clip), "language": "en", "duration": 8.0,
             "segments": segs}))

    def test_preview_lists_removals_and_writes_nothing(self):
        self._sidecar()
        r = self.cl.post("/api/scribe/tighten",
                         json={"path": str(self.clip)}).json()
        kinds = sorted({x["kind"] for x in r["removals"]})
        self.assertEqual(kinds, ["filler", "silence"])
        self.assertEqual(r["n_fillers"], 1)
        self.assertEqual(r["n_silences"], 1)
        self.assertFalse(self.clip.with_name("meeting.tighten.edl").exists())

    def test_write_leaves_a_cut_list_and_never_touches_source(self):
        self._sidecar()
        before = self.clip.read_bytes()
        r = self.cl.post("/api/scribe/tighten",
                         json={"path": str(self.clip), "write": True}).json()
        edl = Path(r["out"])
        self.assertTrue(edl.exists() and edl.name == "meeting.tighten.edl")
        self.assertIn("TITLE: Scribe selects", edl.read_text())
        self.assertEqual(self.clip.read_bytes(), before)   # source untouched

    def test_no_sidecar_is_a_sentence(self):
        r = self.cl.post("/api/scribe/tighten", json={"path": str(self.clip)})
        self.assertEqual(r.status_code, 409)

    def test_nothing_to_tighten_refuses_to_write(self):
        # a clean transcript: no fillers, no long gaps
        self.clip.with_suffix(".scribe.json").write_text(json.dumps(
            {"source": str(self.clip), "language": "en", "duration": 2.0,
             "segments": [{"start": 0.0, "end": 2.0, "text": "the vote passed",
                           "words": [{"w": "the", "s": 0.0, "e": 0.6},
                                     {"w": "vote", "s": 0.7, "e": 1.3},
                                     {"w": "passed", "s": 1.4, "e": 2.0}]}]}))
        r = self.cl.post("/api/scribe/tighten",
                         json={"path": str(self.clip), "write": True})
        self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()
