"""The footage record: sidecar law, coverage, gaps, and the scoped rescan.

Probe is faked (scan reads real headers in life; tests care about the
catalog's bookkeeping, not ffprobe), but every sidecar on disk is real —
the law reads actual files.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from czcore import sidecars
from indexer.catalog import Catalog


def fake_probe(path):
    silent = "silent" in Path(path).name
    return SimpleNamespace(
        duration=60.0, audio_streams=0 if silent else 1,
        video=SimpleNamespace(fps=29.97, width=1920, height=1080,
                              codec="h264", nb_frames=1798))


class TestSidecarLaw(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-sclaw-")
        self.clip = Path(self.td.name) / "shoot.mp4"
        self.clip.write_bytes(b"x")

    def tearDown(self):
        self.td.cleanup()

    def test_collect_reads_what_sits_beside(self):
        self.clip.with_suffix(".scribe.json").write_text("{}")
        self.clip.with_suffix(".pivot.json").write_text("{}")
        found = sidecars.collect(self.clip)
        self.assertEqual(sidecars.kinds_present(found), ["words", "pivot"])

    def test_captions_take_the_newest_of_srt_and_vtt(self):
        srt = self.clip.with_suffix(".srt")
        vtt = self.clip.with_suffix(".vtt")
        srt.write_text("1")
        vtt.write_text("WEBVTT")
        os.utime(vtt, (time.time() + 60, time.time() + 60))
        found = sidecars.collect(self.clip)
        self.assertAlmostEqual(found["captions"], vtt.stat().st_mtime)

    def test_signature_moves_only_when_a_sidecar_does(self):
        self.clip.with_suffix(".scribe.json").write_text("{}")
        a = sidecars.signature(sidecars.collect(self.clip))
        b = sidecars.signature(sidecars.collect(self.clip))
        self.assertEqual(a, b)
        sc = self.clip.with_suffix(".scribe.json")
        os.utime(sc, (time.time() + 90, time.time() + 90))
        c = sidecars.signature(sidecars.collect(self.clip))
        self.assertNotEqual(a, c)

    def test_every_kind_names_a_tool(self):
        for kind, _sufs, tool in sidecars.KINDS:
            self.assertTrue(tool, f"{kind} has no owning tool")


class TestFootageRecord(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-desk-")
        self.root = Path(self.td.name)
        self.cat = Catalog(str(self.root / "cat.db"))
        self.footage = self.root / "footage"
        self.footage.mkdir()
        self.cat.add_folder(str(self.footage))
        self.a = self.footage / "a-interview.mp4"
        self.b = self.footage / "b-broll.mp4"
        self.silent = self.footage / "c-silent.mp4"
        for p in (self.a, self.b, self.silent):
            p.write_bytes(b"media")
        self.a.with_suffix(".scribe.json").write_text(json.dumps(
            {"segments": [{"start": 3.0, "end": 5.0,
                           "text": "the harvard street crosswalk"}]}))
        self.a.with_suffix(".highlights.json").write_text("{}")

    def tearDown(self):
        self.td.cleanup()

    def scan(self, **kw):
        with patch("czcore.media.probe", fake_probe):
            return self.cat.scan(**kw)

    def test_scan_records_what_each_clip_carries(self):
        st = self.scan()
        self.assertEqual(st["added"], 3)
        rows = {r["name"]: r for r in self.cat.search("")}
        self.assertEqual(rows["a-interview.mp4"]["carries"],
                         ["words", "moments"])
        self.assertEqual(rows["b-broll.mp4"]["carries"], [])
        self.assertNotIn("sidecars", rows["a-interview.mp4"])  # packed stays home

    def test_second_scan_is_quiet_until_a_sidecar_moves(self):
        self.scan()
        st = self.scan()
        self.assertEqual(st["added"] + st["updated"], 0)
        piv = self.b.with_suffix(".pivot.json")
        piv.write_text("{}")
        st = self.scan()
        self.assertEqual(st["updated"], 1)
        rows = {r["name"]: r for r in self.cat.search("")}
        self.assertEqual(rows["b-broll.mp4"]["carries"], ["pivot"])
        piv.unlink()  # the matte leaves; the row must stop claiming it
        st = self.scan()
        self.assertEqual(st["updated"], 1)
        rows = {r["name"]: r for r in self.cat.search("")}
        self.assertEqual(rows["b-broll.mp4"]["carries"], [])

    def test_coverage_and_the_wordless_gap(self):
        self.scan()
        s = self.cat.stats()
        self.assertEqual(s["coverage"]["words"], 1)
        self.assertEqual(s["coverage"]["moments"], 1)
        self.assertEqual(s["coverage"]["pivot"], 0)
        # b has sound and no words; the silent clip is not a gap — it has
        # nothing to transcribe, and listing it would be lying
        self.assertEqual(s["wordless"], 1)
        gaps = self.cat.gaps("words")
        self.assertEqual([g["name"] for g in gaps], ["b-broll.mp4"])

    def test_gaps_for_other_kinds_ignore_audio(self):
        self.scan()
        names = {g["name"] for g in self.cat.gaps("pivot")}
        self.assertEqual(names, {"a-interview.mp4", "b-broll.mp4",
                                 "c-silent.mp4"})

    def test_scoped_rescan_touches_only_its_paths(self):
        self.scan()
        self.b.with_suffix(".scribe.json").write_text(json.dumps(
            {"segments": [{"start": 1.0, "end": 2.0, "text": "b-roll pan"}]}))
        self.a.with_suffix(".pivot.json").write_text("{}")
        st = self.scan(only=[str(self.b)])
        self.assertEqual(st["updated"], 1)
        self.assertEqual(st["missing"], 0)  # a scoped pass never declares absence
        rows = {r["name"]: r for r in self.cat.search("")}
        self.assertEqual(rows["b-broll.mp4"]["carries"], ["words"])
        self.assertEqual(rows["a-interview.mp4"]["carries"],
                         ["words", "moments"])  # a's new pivot waits its turn
        st = self.scan()
        rows = {r["name"]: r for r in self.cat.search("")}
        self.assertEqual(rows["a-interview.mp4"]["carries"],
                         ["words", "moments", "pivot"])

    def test_search_by_what_was_said_still_lands_the_moment(self):
        self.scan()
        rows = self.cat.search("crosswalk")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matches"][0]["t"], 3.0)

    def test_old_catalogs_grow_the_column_without_ceremony(self):
        # a pre-1.8 db: build one, drop the new column, reopen
        import sqlite3
        db = str(self.root / "old.db")
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE folders (path TEXT PRIMARY KEY, "
                    "added_at REAL NOT NULL)")
        con.execute("CREATE TABLE clips (path TEXT PRIMARY KEY, folder TEXT "
                    "NOT NULL, name TEXT NOT NULL, size INTEGER, mtime REAL, "
                    "sidecar_mtime REAL, duration REAL, fps REAL, "
                    "width INTEGER, height INTEGER, codec TEXT, "
                    "audio INTEGER, transcript TEXT DEFAULT '', "
                    "scanned_at REAL, missing INTEGER DEFAULT 0)")
        con.commit()
        con.close()
        cat = Catalog(db)
        con2 = cat._con()
        try:
            cols = {r[1] for r in con2.execute(
                "PRAGMA table_info(clips)").fetchall()}
        finally:
            con2.close()
        self.assertIn("sidecars", cols)


if __name__ == "__main__":
    unittest.main()
