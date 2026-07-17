import json
import tempfile
import unittest
from pathlib import Path

from indexer.catalog import Catalog


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-index-test-")
        self.cat = Catalog(str(Path(self.td.name) / "cat.db"))

    def tearDown(self):
        self.td.cleanup()

    def test_add_and_remove_folder(self):
        d = Path(self.td.name) / "footage"
        d.mkdir()
        self.cat.add_folder(str(d))
        self.assertEqual(len(self.cat.folders()), 1)
        self.cat.remove_folder(str(d))
        self.assertEqual(self.cat.folders(), [])

    def test_add_missing_folder_is_a_sentence(self):
        with self.assertRaises(ValueError):
            self.cat.add_folder(str(Path(self.td.name) / "nope"))

    def test_fts_query_quotes_prefix_terms(self):
        q = Catalog._fts_query('crosswalk "vote"  7/15')
        self.assertIn('"crosswalk"*', q)
        self.assertIn('"vote"*', q)
        self.assertNotIn("/", q)

    def test_search_finds_manual_rows_and_sidecar_hits(self):
        # bypass probe (needs media on disk): insert a row directly, but keep
        # the sidecar real so time-coded hits go through the real reader
        clip = Path(self.td.name) / "meeting.mp4"
        clip.write_bytes(b"")
        sc = clip.with_suffix(".scribe.json")
        sc.write_text(json.dumps({"segments": [
            {"start": 12.0, "end": 15.0, "text": "the crosswalk vote passes"}]}))
        with self.cat._con() as con:
            con.execute(
                "INSERT INTO clips VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(clip), self.td.name, "meeting.mp4", 0, 0.0, 1.0, 30.0,
                 29.97, 1920, 1080, "h264", 1, "the crosswalk vote passes",
                 0.0, 0))
            if self.cat.fts:
                con.execute("INSERT INTO clips_fts VALUES (?,?,?,?)",
                            (str(clip), "meeting.mp4", self.td.name,
                             "the crosswalk vote passes"))
            con.commit()
        rows = self.cat.search("crosswalk")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "meeting.mp4")
        self.assertEqual(rows[0]["matches"][0]["t"], 12.0)
        self.assertNotIn("transcript", rows[0])  # full text stays out of payloads

    def test_empty_query_lists_recent(self):
        self.assertEqual(self.cat.search(""), [])

    def test_stats_shape(self):
        s = self.cat.stats()
        for key in ("clips", "seconds", "transcribed", "missing", "folders", "fts"):
            self.assertIn(key, s)


if __name__ == "__main__":
    unittest.main()
