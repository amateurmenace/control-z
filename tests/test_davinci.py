"""DaVinci Tools — the resources the page serves must actually exist.

The contract: every item names a file this repo carries (so a dev checkout
serves its own bytes), and a guide on control-z.org. If someone renames a
zip in grades/ or packs/, this is the test that says so.
"""

import unittest

from suite.tools.davinci import ITEMS, RAW, _repo_root


class TestDavinciResources(unittest.TestCase):
    def test_every_item_exists_in_the_repo(self):
        for key, it in ITEMS.items():
            p = _repo_root() / it["file"]
            self.assertTrue(p.is_file(), f"{key}: {it['file']} missing")
            self.assertGreater(p.stat().st_size, 1000, f"{key}: suspiciously small")

    def test_zips_are_zips(self):
        for key, it in ITEMS.items():
            p = _repo_root() / it["file"]
            self.assertEqual(p.read_bytes()[:2], b"PK", f"{key}: not a zip")

    def test_guides_live_on_the_site(self):
        for it in ITEMS.values():
            self.assertTrue(it["guide"].startswith("https://control-z.org/"))

    def test_raw_url_matches_repo_layout(self):
        self.assertIn("github.com/amateurmenace/control-z/raw/main/", RAW)


if __name__ == "__main__":
    unittest.main()
