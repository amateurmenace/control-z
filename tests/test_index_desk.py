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

    def test_living_paths_lists_what_still_exists_under_a_folder(self):
        self.scan()
        allp = set(self.cat.living_paths())
        self.assertEqual(allp, {str(self.a), str(self.b), str(self.silent)})
        # scoped to the folder, and a vanished clip drops out
        self.assertEqual(set(self.cat.living_paths(str(self.footage))), allp)
        self.b.unlink()
        self.scan()
        self.assertNotIn(str(self.b), self.cat.living_paths())

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


class TestStandingOrders(unittest.TestCase):
    """A watched folder that tends itself: baseline the past, fire on what
    newly lands, mark each clip handled once, and say what it did. The road
    job itself is stubbed (jobs.start faked) so the test stays hermetic — what
    matters here is the bookkeeping, not the engines."""

    def setUp(self):
        from types import SimpleNamespace
        from unittest import mock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from czcore.appshell.jobs import JobManager
        from indexer.catalog import Catalog
        from suite.tools import indexer as ix

        self.td = tempfile.TemporaryDirectory(prefix="cz-standing-")
        root = Path(self.td.name)

        def sd(sub=""):
            d = root / sub if sub else root
            d.mkdir(parents=True, exist_ok=True)
            return d

        for mod in (ix, __import__("indexer.catalog", fromlist=["x"])):
            p = mock.patch.object(mod, "support_dir", sd)
            p.start(); self.addCleanup(p.stop)
        pp = mock.patch("czcore.media.probe", fake_probe)
        pp.start(); self.addCleanup(pp.stop)

        self.folder = root / "incoming"
        self.folder.mkdir()
        (self.folder / "a.mp4").write_bytes(b"media")

        app = FastAPI()
        self.jm = JobManager()
        # stub the queue: the road never actually runs; we assert on dispatch
        self.jobs_started = []

        def fake_start(kind, work, tool="", label=""):
            self.jobs_started.append({"kind": kind, "tool": tool, "label": label})
            return SimpleNamespace(id="fake", to_dict=lambda: {"id": "fake"})

        sp = mock.patch.object(self.jm, "start", fake_start)
        sp.start(); self.addCleanup(sp.stop)

        ix.register_indexer(app, self.jm, None)
        self.cl = TestClient(app)
        # seed the catalog the way life would: watch the folder, scan what's
        # here now, so a fresh standing order has a past to baseline against
        self.seed = Catalog()
        self.seed.add_folder(str(self.folder))
        self.seed.scan()

        self.addCleanup(self.td.cleanup)

    def _orders(self):
        return self.cl.get("/api/index/standing").json()["orders"]

    def test_baseline_then_fire_on_the_newly_landed(self):
        r = self.cl.post("/api/index/standing", json={
            "add": {"folder": str(self.folder), "stages": ["words"]}}).json()
        order = r["orders"][0]
        self.assertTrue(order["enabled"])
        self.assertIsNone(order["last_run"])
        # the clip already here is the order's past, not its work
        self.assertIn(str(self.folder / "a.mp4"), order["handled"])
        oid = order["id"]

        # a shoot lands overnight
        (self.folder / "b.mp4").write_bytes(b"media")
        before = len(self.jobs_started)
        r = self.cl.post("/api/index/standing", json={"run": oid}).json()
        order = r["orders"][0]
        self.assertEqual(len(self.jobs_started), before + 1)  # one road dispatched
        self.assertIn("standing order", self.jobs_started[-1]["label"])
        self.assertIn("1 clip sent down words", order["last_note"])
        self.assertIn(str(self.folder / "b.mp4"), order["handled"])

        # running again with nothing new is a sentence, not a job
        before = len(self.jobs_started)
        r = self.cl.post("/api/index/standing", json={"run": oid}).json()
        self.assertEqual(len(self.jobs_started), before)
        self.assertEqual(r["orders"][0]["last_note"], "watched · nothing new")

    def test_pause_and_remove(self):
        oid = self.cl.post("/api/index/standing", json={
            "add": {"folder": str(self.folder), "stages": ["words", "clear"]}}
        ).json()["orders"][0]["id"]
        r = self.cl.post("/api/index/standing", json={
            "update": {"id": oid, "patch": {"enabled": False}}}).json()
        self.assertFalse(r["orders"][0]["enabled"])
        r = self.cl.post("/api/index/standing", json={"remove": oid}).json()
        self.assertEqual(r["orders"], [])

    def test_an_order_needs_a_real_folder_and_a_stage(self):
        r = self.cl.post("/api/index/standing", json={
            "add": {"folder": "/no/such/place", "stages": ["words"]}})
        self.assertEqual(r.status_code, 422)
        r = self.cl.post("/api/index/standing", json={
            "add": {"folder": str(self.folder), "stages": []}})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self._orders(), [])


if __name__ == "__main__":
    unittest.main()


class TestRoadPlan(unittest.TestCase):
    """The road's bookkeeping: who runs what, every skip a sentence."""

    def rows(self):
        return [
            {"path": "/f/a.mp4", "name": "a.mp4", "audio": 1, "width": 1920,
             "missing": 0, "carries": ["words"]},
            {"path": "/f/b.mp4", "name": "b.mp4", "audio": 1, "width": 1920,
             "missing": 0, "carries": []},
            {"path": "/f/c-silent.mp4", "name": "c-silent.mp4", "audio": 0,
             "width": 1920, "missing": 0, "carries": []},
            {"path": "/f/d.wav", "name": "d.wav", "audio": 1, "width": None,
             "missing": 0, "carries": []},
            {"path": "/f/e.mp4", "name": "e.mp4", "audio": 1, "width": 1920,
             "missing": 1, "carries": []},
        ]

    def plan(self, stages):
        from suite.tools.indexer import _road_plan
        return _road_plan(self.rows(), stages)

    def test_stages_run_in_road_order_regardless_of_ask(self):
        p = self.plan(["pivot", "words", "clear"])
        self.assertEqual(p["stages"], ["words", "clear", "pivot"])

    def test_done_work_is_skipped_with_the_reason_said(self):
        p = self.plan(["words"])
        names = [i["name"] for i in p["plan"]]
        self.assertEqual(names, ["b.mp4", "d.wav"])
        self.assertIn("a.mp4 · words: already done", p["skips"])

    def test_a_clip_offers_only_what_it_can_carry(self):
        p = self.plan(["words", "clear", "pivot"])
        by = {i["name"]: i["stages"] for i in p["plan"]}
        self.assertEqual(by["b.mp4"], ["words", "clear", "pivot"])
        self.assertEqual(by["c-silent.mp4"], ["pivot"])  # picture, no sound
        self.assertEqual(by["d.wav"], ["words", "clear"])  # sound, no picture
        self.assertNotIn("e.mp4", by)  # unplugged drives never join the road
        self.assertIn("e.mp4 · words: drive unplugged?", p["skips"])
        self.assertIn("c-silent.mp4 · words: no audio track", p["skips"])
        self.assertIn("d.wav · reframe 9:16: no picture", p["skips"])

    def test_rise_lifts_sd_and_leaves_hd_alone(self):
        rows = [
            {"path": "/f/sd.mp4", "name": "sd.mp4", "audio": 1, "width": 720,
             "height": 480, "missing": 0, "carries": []},
            {"path": "/f/hd.mp4", "name": "hd.mp4", "audio": 1, "width": 1920,
             "height": 1080, "missing": 0, "carries": []},
            {"path": "/f/720.mp4", "name": "720.mp4", "audio": 1, "width": 1280,
             "height": 720, "missing": 0, "carries": []},
            {"path": "/f/a.wav", "name": "a.wav", "audio": 1, "width": None,
             "height": None, "missing": 0, "carries": []},
        ]
        from suite.tools.indexer import _road_plan
        p = _road_plan(rows, ["rise"])
        names = [i["name"] for i in p["plan"]]
        self.assertEqual(names, ["sd.mp4"])           # only the SD clip lifts
        self.assertIn("hd.mp4 · to HD: already 1080p — Rise's craft, not the "
                      "road's", p["skips"])
        self.assertIn("720.mp4 · to HD: already 720p — Rise's craft, not the "
                      "road's", p["skips"])
        self.assertIn("a.wav · to HD: no picture", p["skips"])

    def test_rise_respects_an_existing_lift(self):
        from suite.tools import indexer as ix
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "sd.mp4"
            src.write_bytes(b"x")
            ix._rise_out(str(src)).write_bytes(b"lifted")
            rows = [{"path": str(src), "name": "sd.mp4", "audio": 1,
                     "width": 720, "height": 480, "missing": 0, "carries": []}]
            p = ix._road_plan(rows, ["rise"])
            self.assertEqual(p["plan"], [])
            self.assertIn("sd.mp4 · to HD: already lifted", p["skips"])

    def test_presets_name_only_real_stages(self):
        from suite.tools.indexer import ROAD_PRESETS, ROAD_STAGES
        known = {s["id"] for s in ROAD_STAGES}
        for preset in ROAD_PRESETS:
            self.assertTrue(set(preset["stages"]) <= known,
                            f"{preset['id']} names an unknown stage")
            self.assertTrue(preset["label"] and preset["hint"])

    def test_existing_pivot_render_is_respected(self):
        from suite.tools import indexer as ix
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "b.mp4"
            src.write_bytes(b"x")
            ix._pivot_out(str(src)).write_bytes(b"done")
            rows = [{"path": str(src), "name": "b.mp4", "audio": 1,
                     "width": 1920, "missing": 0, "carries": []}]
            p = ix._road_plan(rows, ["pivot"])
            self.assertEqual(p["plan"], [])
            self.assertIn("b.mp4 · reframe: already rendered", p["skips"])
