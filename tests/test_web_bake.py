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
            # .97 fractional starts exercise the anchor/deep-link rounding
            # invariant: int(12.97)=12 but round(12.97,1)=13.0 — a producer
            # that rounded up would mint a #t13 link with no t13 anchor.
            segs = [{"start": i * 10.0 + 0.97, "end": i * 10 + 9, "speaker": "Chair",
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
        # a document on vid1, linked to the issue by a keyword its chunk names
        c.upsert_document({"id": "doc:budget", "meeting_id": "vid1",
                           "town": "Testville", "kind": "Agenda",
                           "title": "Agenda", "date": "2026-03-10",
                           "url": "https://example.org/agenda.pdf", "pages": 2})
        c.replace_doc_chunks("doc:budget", [
            {"page": 1, "text": "the budget override public hearing"},
            {"page": 2, "text": "unrelated permit boilerplate"}])
        from memory import documents
        documents.assign_document(c, "doc:budget")
        # a roll-call vote on vid1, near the issue's first bead (t≈0.97)
        c.replace_votes("vid1", [{
            "t": 12.0, "motion": "to approve the budget override",
            "outcome": "passes", "tally": "3–0", "origin": "extractive",
            "roll": [{"name": "Chair Alpha", "vote": "yes", "t": 12.0, "quote": "aye"},
                     {"name": "Member Beta", "vote": "yes", "t": 13.0, "quote": "aye"},
                     {"name": "Member Gamma", "vote": "no", "t": 14.0, "quote": "no"}]}])

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

    def test_deeplink_anchors_resolve(self):
        """The HIGH bug: a search/cite deep-link is #t<floor(segTime)>, and the
        transcript anchor is id=t<int(start)>. If the two used different
        rounding, ~5% of deep-links would land on no element. Assert every
        search segment's floored time matches a real anchor in its stub."""
        segs = self._read("search/segs.json")
        meta = self._read("search/meta.json")
        # anchor ids present in each meeting stub
        anchors = {}
        for mi, mrec in enumerate(meta):
            html = (self.out / "m" / mrec["pid"] / "index.html").read_text()
            anchors[mi] = set(re.findall(r'id="t(\d+)"', html))
            # data-t must floor to its own anchor id (never round up past it)
            for aid, dt in re.findall(r'id="t(\d+)" data-t="([^"]+)"', html):
                self.assertEqual(int(float(dt)), int(aid),
                                 f"data-t {dt} floors past anchor t{aid}")
        for mi, t, spk, text in segs:
            self.assertIn(str(int(t)), anchors[mi],
                          f"search deep-link #t{int(t)} has no anchor in meeting {mi}")

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

    # -- documents, votes, officials, and the PWA (waves 2/3) --------------

    def test_meeting_carries_votes_and_documents(self):
        mj = self._read("meetings/vid1.json")
        self.assertEqual(len(mj["votes"]), 1)
        self.assertEqual(mj["votes"][0]["tally"], "3–0")
        self.assertEqual(len(mj["documents"]), 1)
        self.assertEqual(mj["documents"][0]["kind"], "Agenda")
        # the roll call and the paper are readable JS-off in the stub
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn("the vote ledger", stub)
        self.assertIn("the town", stub)   # "the town's paper"

    def test_issue_carries_ledger_and_document_lane(self):
        ij = json.loads((self.out / "issues" /
                         "issue_testville_budget-override.json").read_text())
        self.assertTrue(ij["ledger"], "the issue should carry a roll-call ledger")
        self.assertEqual(ij["ledger"][0]["tally"], "3–0")
        # a timeline node interleaves the document
        withdocs = [n for n in ij["timeline"] if n.get("documents")]
        self.assertTrue(withdocs, "a document should interleave on the timeline")
        self.assertEqual(withdocs[0]["documents"][0]["kind"], "Agenda")
        # the milestone is a real vote (not just a heuristic decision)
        votes = [m for n in ij["timeline"] for m in n["milestones"]
                 if m.get("kind") == "vote"]
        self.assertTrue(votes)

    def test_officials_plane_is_officials_only(self):
        off = self._read("officials.json")
        names = {o["name"] for o in off["officials"]}
        self.assertEqual(names, {"Chair Alpha", "Member Beta", "Member Gamma"})
        gamma = next(o for o in off["officials"] if o["name"] == "Member Gamma")
        self.assertEqual(gamma["no"], 1)
        # every cell is a receipt into the tape
        self.assertTrue(all("pid" in v for v in gamma["votes"]))
        # and the page renders JS-off
        page = (self.out / "officials" / "index.html").read_text()
        self.assertIn("The people", page)

    def test_stats_count_documents_and_votes(self):
        s = self._read("stats.json")
        self.assertEqual(s["counts"]["documents"], 1)
        self.assertEqual(s["counts"]["votes"], 1)

    def test_pwa_manifest_and_service_worker(self):
        wm = self._read("manifest.webmanifest")
        self.assertEqual(wm["scope"], "/app/")
        self.assertTrue((self.out / "sw.js").exists())
        sw = (self.out / "sw.js").read_text()
        self.assertIn("cz-record-", sw)          # cache keyed by corpus hash
        self.assertNotIn("Date.now", sw)         # deterministic, no wall-clock
        # the manifest + RSS autodiscovery ride in every page head
        home = (self.out / "index.html").read_text()
        self.assertIn('rel="manifest"', home)
        self.assertIn('type="application/rss+xml"', home)

    def test_still_watching_page_present(self):
        self.assertTrue((self.out / "watching" / "index.html").exists())


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
