"""The web edition bake — canon twin, idempotence, structure, budgets.

Offline and hermetic: a tiny throwaway corpus.db is built with two meetings
and one cross-meeting issue, pressed to a temp dir, and checked. No network,
no real corpus, no suite server.
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from web import canon, tools

REPO = Path(__file__).resolve().parents[1]

# The golden table — the ONE truth both twins answer (web/canon.py and the
# canon() in web/static/app.js). specs/16 §P0.4.
GOLDEN = [
    ("https://www.youtube.com/watch?v=2YhgO14jXys", "youtube:2YhgO14jXys"),
    ("https://youtu.be/2YhgO14jXys?si=abcDEF", "youtube:2YhgO14jXys"),
    ("https://www.youtube.com/watch?v=2YhgO14jXys&list=PL&index=3", "youtube:2YhgO14jXys"),
    ("https://youtube.com/live/wAFa8pUa4IQ", "youtube:wAFa8pUa4IQ"),
    ("2YhgO14jXys", "youtube:2YhgO14jXys"),
    ("https://brooklinema.portal.civicclerk.com/event/1234/overview",
     "url:https://brooklinema.portal.civicclerk.com/event/1234/overview"),
    ("https://example.org/mtg?utm_source=x&feature=y", "url:https://example.org/mtg"),
    ("https://example.org/mtg#t=90", "url:https://example.org/mtg"),
    ("", ""),
]


class TestCanonTwin(unittest.TestCase):
    def test_python_canon_matches_golden(self):
        for url, want in GOLDEN:
            self.assertEqual(canon.canon(url), want, f"canon({url!r})")

    def test_js_twin_regexes_match_python(self):
        """A cheap structural guard: the strip-param set and the video-id host
        markers appear in both twins. (The rigorous check is
        test_js_canon_runs_the_golden_table, which executes the real reader
        code; JS regex literals escape '/' as '\\/', so a verbatim string
        compare would false-fail — this checks the slash-free parts.)"""
        js = (REPO / "web" / "static" / "app.js").read_text()
        py = (REPO / "web" / "canon.py").read_text()
        strip = r"(utm_[^=&]+|feature|si|list|index|t)=[^&]*"
        for token in (strip, "youtu", "shorts", "embed", r"([\w-]{11})"):
            self.assertIn(token, py, f"{token!r} missing from web/canon.py")
            self.assertIn(token, js, f"{token!r} drifted in web/static/app.js")

    def test_js_canon_runs_the_golden_table(self):
        """Actually execute the reader's canon() in node against the table —
        the real twin check, not just a structural one. Skips if node absent."""
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        js = (REPO / "web" / "static" / "app.js").read_text()
        # lift the three regexes + videoId + canon out of the IIFE
        grab = lambda name, pat: re.search(pat, js).group(0)
        body = "\n".join([
            re.search(r"const VIDEO_ID = .+?;", js).group(0),
            re.search(r"const BARE_ID = .+?;", js).group(0),
            re.search(r"const STRIP = .+?;", js).group(0),
            re.search(r"function videoId\(s\) \{.+?\n  \}", js, re.S).group(0),
            re.search(r"function canon\(url\) \{.+?\n  \}", js, re.S).group(0),
            "const T=" + json.dumps(GOLDEN) + ";",
            "for (const [u,w] of T){ if(canon(u)!==w){ "
            "console.log('FAIL',u,'->',canon(u),'want',w); process.exit(1);} }",
            "console.log('ok');",
        ])
        r = subprocess.run([node, "-e", body], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         f"JS canon disagreed with the golden table:\n{r.stdout}{r.stderr}")


class TestBakeEdition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.db = root / "corpus.db"
        cls._seed(cls.db)
        cls.out = root / "app"
        from web import bake
        cls.report = bake.bake(str(cls.db), str(cls.out), "9.9.9",
                               "https://example.org")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def _seed(db):
        from memory.store import Corpus
        c = Corpus(str(db))
        for mid, title, date in [("vid1", "Select Board — March", "2026-03-10"),
                                 ("vid2", "School Committee — June", "2026-06-18")]:
            segs = [{"start": i * 10.0, "end": i * 10 + 9, "speaker": "Chair",
                     "text": f"we discuss the budget override item {i} at length"}
                    for i in range(6)]
            c.replace_segments(mid, segs)
            c.upsert_meeting({"id": mid, "title": title, "date": date,
                              "town": "Testville", "body": "Board",
                              "source_kind": "youtube", "video_id": mid,
                              "url": f"https://youtube.com/watch?v={mid}",
                              "url_canon": f"youtube:{mid}", "duration": 60,
                              "n_segments": len(segs), "status": "live",
                              "summary": "A budget override was discussed.",
                              "analysis_json": json.dumps({"decisions": [
                                  {"t": 12.0, "text": "override passes", "outcome": "passed"}]})})
        # a cross-meeting issue by hand (both meetings share "budget override")
        c.upsert_issue({"id": "issue:testville:budget-override", "town": "Testville",
                        "name": "budget override", "status": "active",
                        "keywords": ["budget override"], "aliases": [], "related": []})
        for mid in ("vid1", "vid2"):
            rows = c.segments_of(mid)
            c.link_segments("issue:testville:budget-override",
                            [(r["id"], mid, 1.0, "alias") for r in rows[:3]])

    def _read(self, rel):
        return json.loads((self.out / rel).read_text())

    def test_manifest_and_counts(self):
        m = self._read("manifest.json")
        self.assertEqual(m["schema"], 1)
        self.assertEqual(m["version"], "9.9.9")
        self.assertEqual(m["counts"]["meetings"], 2)
        self.assertEqual(m["edition_date"], "2026-06-18")  # corpus-derived, not wall-clock
        self.assertTrue(m["corpus_hash"])

    def test_meeting_json_and_stub(self):
        mj = self._read("meetings/vid1.json")
        self.assertEqual(mj["title"], "Select Board — March")
        self.assertNotIn("segments", mj)  # transcript lives in the stub, not here
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn('property="og:title"', stub)
        self.assertIn("budget override item", stub)   # JS-off readable transcript
        self.assertIn('class="seg"', stub)
        # transcript .txt download exists
        self.assertTrue((self.out / "m" / "vid1" / "transcript.txt").exists())

    def test_issue_timeline(self):
        # find the issue file
        files = list((self.out / "issues").glob("*.json"))
        self.assertTrue(files)
        ij = json.loads(files[0].read_text())
        self.assertEqual(ij["name"], "budget override")
        self.assertEqual(ij["n_meetings"], 2)
        self.assertEqual(len(ij["timeline"]), 2)
        self.assertTrue(all(n["beads"] for n in ij["timeline"]))

    def test_urls_dedup_keys(self):
        urls = self._read("urls.json")
        self.assertEqual(urls.get("youtube:vid1"), "vid1")

    def test_search_index(self):
        shards = self._read("search/shards.json")
        self.assertGreater(shards["segments"], 0)
        segs = self._read("search/segs.json")
        # "budget" appears -> its prefix shard has it, pointing at real segments
        sh = self._read("search/t-b.json")
        self.assertIn("budget", sh)
        sid = sh["budget"][0]
        self.assertIn("budget", segs[sid][3].lower())

    def test_covenant_and_doors_present(self):
        self.assertTrue((self.out / "covenant" / "index.html").exists())
        # every desk tool has a door; memory (web surface) does not
        self.assertTrue((self.out / "t" / "stencil" / "index.html").exists())
        self.assertFalse((self.out / "t" / "memory").exists())
        door = (self.out / "t" / "stencil" / "index.html").read_text()
        self.assertIn("desk", door)
        self.assertIn("Get the desktop app", door)

    def test_feeds(self):
        self.assertTrue((self.out / "feeds" / "firehose.xml").exists())
        fh = (self.out / "feeds" / "firehose.xml").read_text()
        self.assertIn("<rss", fh)

    def test_within_budget(self):
        self.assertEqual(self.report["busts"], 0, "an edition busted its budget")

    def test_csp_on_every_stub(self):
        for stub in self.out.rglob("index.html"):
            html = stub.read_text()
            self.assertIn("Content-Security-Policy", html, f"{stub} lacks CSP")
            self.assertIn("script-src 'self'", html)


class TestIdempotence(unittest.TestCase):
    def test_same_corpus_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "c.db"
            TestBakeEdition._seed(db)
            from web import bake
            bake.bake(str(db), str(root / "a"), "1.0.0", "https://x.org")
            bake.bake(str(db), str(root / "b"), "1.0.0", "https://x.org")
            a = sorted((root / "a").rglob("*"))
            for p in a:
                if p.is_file():
                    rel = p.relative_to(root / "a")
                    self.assertEqual(p.read_bytes(), (root / "b" / rel).read_bytes(),
                                     f"{rel} differs between two bakes")


class TestRegistryMatchesDesk(unittest.TestCase):
    def test_web_accents_match_core_js(self):
        """The web registry re-declares the desk's accents; if core.js's
        values change, this catches the drift (specs/16 §8)."""
        core = (REPO / "suite" / "static" / "js" / "core.js").read_text()
        for t in tools.TOOLS:
            m = re.search(rf'--{t["id"]}\)', core)  # token reference exists
            # the accent hex must match app.css :root
        css = (REPO / "suite" / "static" / "app.css").read_text()
        for t in tools.TOOLS:
            want = re.search(rf'--{t["id"]}:\s*(#[0-9A-Fa-f]{{6}})', css)
            if want:
                self.assertEqual(t["accent"].lower(), want.group(1).lower(),
                                 f'{t["id"]} accent drifted from app.css')


if __name__ == "__main__":
    unittest.main()
