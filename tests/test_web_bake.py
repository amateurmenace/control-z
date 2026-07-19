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

from web import canon, emit, tools

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


class TestScopeResolution(unittest.TestCase):
    """The reader's `resolve()` decides which town every page obeys, and it is
    the one place specs/17 §14's trap is either sprung or defused. So it is
    executed for real in node against a table, rather than trusted to reading
    — the same treatment canon() gets, for the same reason."""

    # (label, edition towns, stored choice, query string, expected fields)
    TABLE = [
        ("two towns, first visit: nothing is presumed",
         ["Brookline", "Boston"], None, "", {"town": "", "from": "none"}),
        ("the stored choice governs",
         ["Brookline", "Boston"], "Brookline", "", {"town": "Brookline", "from": "stored"}),
        ("a ?town= link overrides the choice WITHOUT replacing it",
         ["Brookline", "Boston"], "Brookline", "?town=Boston",
         {"town": "Boston", "from": "link", "stored": "Brookline"}),
        ("the link's town is matched case-insensitively",
         ["Brookline", "Boston"], None, "?town=bOsToN",
         {"town": "Boston", "from": "link"}),
        ("a ?town= naming a town this edition lacks scopes to nothing, "
         "rather than to a town that looks close",
         ["Brookline", "Boston"], "Brookline", "?town=Cambridge",
         {"town": "", "from": "link", "stored": "Brookline"}),
        ("one town: scoped without ever being asked",
         ["Brookline"], None, "", {"town": "Brookline", "from": "only"}),
        ("a stored town this pressing dropped is reported, not obeyed",
         ["Boston"], "Brookline", "", {"town": "", "lost": "Brookline"}),
        ("?town= empty means the whole record for this visit",
         ["Brookline", "Boston"], "Brookline", "?town=",
         {"town": "", "from": "link-all"}),
        ("the body filter rides alongside the town",
         ["Brookline"], None, "?body=Select+Board",
         {"town": "Brookline", "body": "Select Board"}),
    ]

    def test_resolve_runs_in_node(self):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        js = (REPO / "web" / "static" / "app.js").read_text()
        fn = re.search(r"  function resolve\(ed\) \{.+?\n  \}", js, re.S)
        self.assertTrue(fn, "resolve() not found in the reader — did it move?")
        cases = [{"label": l, "towns": t, "stored": s, "qs": q, "want": w}
                 for l, t, s, q, w in self.TABLE]
        body = "\n".join([
            "let STORED = null, QS = '';",
            "const readTown = () => STORED || '';",
            "const location = { get search() { return QS; } };",
            fn.group(0),
            "const CASES = " + json.dumps(cases) + ";",
            "let bad = 0;",
            "for (const c of CASES) {",
            "  STORED = c.stored; QS = c.qs;",
            "  const ed = { towns: c.towns.map(t => ({ town: t })) };",
            "  const got = resolve(ed);",
            "  for (const [k, v] of Object.entries(c.want)) {",
            "    if ((got[k] || '') !== v) {",
            "      console.log('FAIL [' + c.label + '] ' + k + ' = ' +",
            "        JSON.stringify(got[k]) + ' want ' + JSON.stringify(v));",
            "      bad++; } } }",
            "process.exit(bad ? 1 : 0);",
        ])
        r = subprocess.run([node, "-e", body], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         f"the reader's scope resolution is wrong:\n{r.stdout}{r.stderr}")

    def test_an_override_never_writes_the_choice(self):
        """The rule that keeps a shared link from silently re-homing a reader:
        only chooseTown() may touch storage, and it is only ever called from a
        click. resolve() and banner() must never write."""
        js = (REPO / "web" / "static" / "app.js").read_text()
        # Walk back from each call site to the thing that owns it. Only a
        # deliberate act of choosing may reach storage.
        ALLOWED = {"const writeTown", "function chooseTown", "b.onclick"}
        sites = [m.start() for m in re.finditer(r"writeTown\(", js)]
        self.assertTrue(sites, "writeTown disappeared")
        for at in sites:
            before = js[:at]
            owner = max(
                ((before.rfind(k), k) for k in
                 ("const writeTown", "function chooseTown", "b.onclick",
                  "function resolve", "function banner", "function paintScope",
                  "function initScope", "function runSearch")),
                key=lambda kv: kv[0])[1]
            self.assertIn(owner, ALLOWED,
                          f"writeTown reached from {owner} — the choice must "
                          f"only be written when the reader makes one")
        # and resolve() itself is pure over (edition, location, storage)
        fn = re.search(r"  function resolve\(ed\) \{.+?\n  \}", js, re.S).group(0)
        for forbidden in ("writeTown", "localStorage.setItem", "fetch("):
            self.assertNotIn(forbidden, fn,
                             f"resolve() must not {forbidden} — it is read-only")


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

    def test_covenant_explains_the_licence_and_links_the_source(self):
        """The covenant page named AGPL-3.0 for a year while the repository was
        MIT — a claim nobody could check because the page never said where to
        look. Both licences are named, both are explained in words a resident
        reads without a lawyer, and the source and LICENSING.md are one click
        away. A regression back to the bare word fails here."""
        cov = (self.out / "covenant" / "index.html").read_text()
        self.assertIn("AGPL-3.0", cov)
        self.assertIn("CC BY-SA 4.0", cov)
        # the consequence, not the mechanism: what a resident actually gets
        self.assertIn("run their own copy", cov)
        self.assertIn("owes those people the changed program", cov)
        # the record and the code are told apart, and the town's own record
        # is not claimed by either
        self.assertIn("The meetings belong to the town", cov)
        # a claim with a dead link behind it is worse than no claim
        self.assertIn(f'href="{emit.SOURCE_REPO}"', cov)
        self.assertIn(f'href="{emit.LICENSING_DOC}"', cov)
        self.assertIn("LICENSING.md", cov)
        # it must read with JavaScript off, like the rest of the edition: the
        # prose is baked into the document, not injected by app.js, and nothing
        # holds it back with hidden
        body = cov.split('<section class="covpage">')[1].split("</section>")[0]
        self.assertIn("The software is AGPL-3.0", body)
        self.assertNotIn("hidden", body)

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

    # -- the analytical eye: framing, analytics, the graph (wave 3) --------

    def test_meeting_carries_the_analyzer_read(self):
        mj = self._read("meetings/vid1.json")
        an = mj["analysis"]
        # framing lenses + questions computed at press time from the transcript
        self.assertIn("framing", an)
        self.assertIn("questions", an)
        self.assertIsInstance(an["framing"].get("lenses"), list)
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn("eight civic lenses", stub)   # JS-off readable

    def test_analytics_plane_and_page(self):
        a = self._read("analytics.json")
        self.assertIn("framing", a)         # meetings × lenses matrix
        self.assertIn("lens_order", a)
        self.assertEqual(len(a["framing"]), 2)   # one row per live meeting
        self.assertTrue((self.out / "analytics" / "index.html").exists())
        page = (self.out / "analytics" / "index.html").read_text()
        self.assertIn("The record, drawn", page)

    def test_graph_plane_and_page(self):
        g = self._read("graph.json")
        self.assertIn("nodes", g)
        self.assertIn("edges", g)
        # our two seeded meetings share the budget-override issue, but a single
        # shared issue across 2 meetings is real co-occurrence data
        self.assertTrue((self.out / "graph" / "index.html").exists())
        page = (self.out / "graph" / "index.html").read_text()
        self.assertIn("The issue graph", page)
        # the SVG is inline (no external lib — CSP holds) and has a table twin
        self.assertIn("<svg", page)
        self.assertIn("the same, as a table", page)


    # -- the scope plane: towns and bodies (specs/17 §8) -------------------

    def test_towns_plane_is_observed_not_configured(self):
        """towns.json is derived from the pressed meetings. The steward's
        source rules can name a body that has never met; the reader's filter
        must not, because an option that always returns nothing is a promise a
        static edition has no way to explain."""
        t = self._read("towns.json")
        self.assertEqual([x["town"] for x in t["towns"]], ["Testville"])
        town = t["towns"][0]
        self.assertEqual(town["meetings"], 2)
        self.assertEqual(town["first"], "2026-03-10")
        self.assertEqual(town["last"], "2026-06-18")
        self.assertEqual([b["body"] for b in town["bodies"]], ["Board"])
        self.assertEqual(town["bodies"][0]["meetings"], 2)
        self.assertEqual([b["body"] for b in t["bodies"]], ["Board"])
        self.assertEqual(t["bodies"][0]["towns"], ["Testville"])
        self.assertEqual(t["untowned"], 0)      # every seeded meeting has a town

    def test_search_meta_carries_town_for_scoping(self):
        """A scoped search filters its own hits from the meta plane; without
        town on each meeting it would have to fetch a document per hit."""
        meta = self._read("search/meta.json")
        self.assertTrue(all(m["town"] == "Testville" for m in meta))
        self.assertTrue(all(m["body"] == "Board" for m in meta))

    def test_coverage_carries_town_body_cells(self):
        """The strip has to be redrawable under a scope, or it contradicts the
        scoped list beside it."""
        s = self._read("stats.json")
        cov = s["coverage"]
        self.assertTrue(cov)
        for month in cov:
            self.assertIn("cells", month)
            self.assertEqual(sum(month["cells"].values()), month["total"])
        self.assertIn("Testville␟Board", cov[0]["cells"])
        # the home rail's cards carry their town, so the filter needs no fetch
        self.assertTrue(all("town" in m for m in s["new"]))

    def test_single_town_edition_names_it_and_does_not_nag(self):
        """One town is not a question. The bar states it; there is no picker,
        no prompt, and nothing that blocks the page."""
        home = (self.out / "index.html").read_text()
        self.assertIn('class="scope one"', home)
        self.assertIn("the only town on this edition", home)
        self.assertNotIn('class="scopetown"', home)
        self.assertNotIn("scopelink", home)      # no footer re-chooser either
        # and the picker is on every page, not just home
        for rel in ("s/index.html", "m/vid1/index.html", "officials/index.html"):
            self.assertIn('id="scope"', (self.out / rel).read_text(), rel)

    def test_scope_banner_slot_on_every_page(self):
        """The un-trapping banner lands above what the reader came for, on
        every page — so it is markup, not something script invents late."""
        for stub in self.out.rglob("index.html"):
            self.assertIn('id="scopebanner"', stub.read_text(), str(stub))

    def test_body_filter_degrades_to_a_readable_sentence(self):
        """JS-off there is no dead control: the filter rail is empty and
        hidden, and the same fact ships as prose with checkable counts."""
        home = (self.out / "index.html").read_text()
        self.assertIn('id="bodyfilter"', home)
        self.assertIn('hidden', home)
        self.assertRegex(home, r'class="bodylist"[^>]*>Board <b>2</b>')
        self.assertIn("With JavaScript off this page lists the whole record",
                      home)
        # every card carries what the filter needs
        self.assertIn('data-body="Board"', home)
        self.assertIn('data-town="Testville"', home)

    def test_meeting_stub_declares_its_town(self):
        """The deep-link trap without a query string: a meeting from another
        town. The banner needs the meeting's own town in the markup."""
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn('data-town="Testville"', stub)
        self.assertIn('data-body="Board"', stub)

    def test_officials_cards_carry_town(self):
        page = (self.out / "officials" / "index.html").read_text()
        self.assertIn('class="offcard" data-town="Testville"', page)

    def test_search_filters_appear_only_when_they_can_do_something(self):
        """One town and one body: a select with a single option is a control
        that cannot change anything, so it is not emitted."""
        page = (self.out / "s" / "index.html").read_text()
        self.assertNotIn('id="townsel"', page)
        self.assertNotIn('id="bodysel"', page)

    def test_reader_still_reads_with_the_backend_dark(self):
        """The load-bearing property: nothing added here reaches for a server.
        The scope planes are files in the edition, and the only fetches the
        reader makes are same-origin paths under /app/."""
        js = (REPO / "web" / "static" / "app.js").read_text()
        self.assertIn("towns.json", js)
        self.assertNotIn("http://", js.replace("http://www.w3.org", ""))
        for host in ("/api/", "localhost"):
            self.assertNotIn(host, js)
        self.assertTrue((self.out / "towns.json").exists())


class TestScopeOnTwoTowns(unittest.TestCase):
    """A second town changes the shape of the chrome, and only a second town
    can exercise the trap specs/17 §14 leaves open — so it gets its own
    pressing rather than a bolt-on to the single-town corpus."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        db = root / "two.db"
        TestBakeEdition._seed(db)
        from memory.store import Corpus
        c = Corpus(str(db))
        segs = [{"start": i * 10.0, "end": i * 10 + 9, "speaker": "Chair",
                 "text": f"the zoning appeal item {i}"} for i in range(4)]
        c.replace_segments("vid3", segs)
        c.upsert_meeting({"id": "vid3", "title": "Zoning Board — July",
                          "date": "2026-07-02", "town": "Otherville",
                          "body": "Zoning Board of Appeals",
                          "source_kind": "youtube", "video_id": "vid3",
                          "url": "https://youtube.com/watch?v=vid3",
                          "url_canon": "youtube:vid3", "duration": 60,
                          "n_segments": len(segs), "status": "live"})
        # a meeting the record never learned a town for — it must not vanish
        c.replace_segments("vid4", segs)
        c.upsert_meeting({"id": "vid4", "title": "Unknown provenance",
                          "date": "2026-07-03", "town": "", "body": "",
                          "source_kind": "youtube", "video_id": "vid4",
                          "url": "https://youtube.com/watch?v=vid4",
                          "url_canon": "youtube:vid4", "duration": 60,
                          "n_segments": len(segs), "status": "live"})
        cls.out = root / "app"
        from web import bake
        bake.bake(str(db), str(cls.out), "9.9.9", "https://example.org")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _read(self, rel):
        return json.loads((self.out / rel).read_text())

    def test_untowned_meeting_is_counted_never_filed_under_a_town(self):
        t = self._read("towns.json")
        self.assertEqual([x["town"] for x in t["towns"]],
                         ["Otherville", "Testville"])
        self.assertEqual(t["untowned"], 1)
        self.assertEqual(t["meetings"], 4)
        # it belongs to no town, so it is in no town's bucket
        self.assertEqual(sum(x["meetings"] for x in t["towns"]), 3)
        # but its (empty) body is still a real filter option
        self.assertIn("", [b["body"] for b in t["bodies"]])

    def test_picker_offers_every_town_plus_the_whole_record(self):
        home = (self.out / "index.html").read_text()
        self.assertIn('data-town="Testville"', home)
        self.assertIn('data-town="Otherville"', home)
        self.assertIn("the whole record", home)
        self.assertNotIn("the only town on this edition", home)
        # re-choosable from the footer, and the anchor works JS-off
        self.assertIn('class="scopelink" href="#scope"', home)

    def test_search_gets_real_filters_when_there_is_a_choice(self):
        page = (self.out / "s" / "index.html").read_text()
        self.assertIn('<select name="town" id="townsel"', page)
        self.assertIn('<select name="body" id="bodysel"', page)
        self.assertIn("every town", page)
        self.assertIn("no body recorded", page)   # the untowned meeting's body

    def test_bodies_are_per_town_not_a_flat_list(self):
        t = self._read("towns.json")
        other = next(x for x in t["towns"] if x["town"] == "Otherville")
        self.assertEqual([b["body"] for b in other["bodies"]],
                         ["Zoning Board of Appeals"])
        test = next(x for x in t["towns"] if x["town"] == "Testville")
        self.assertEqual([b["body"] for b in test["bodies"]], ["Board"])

    def test_coverage_cells_separate_the_towns(self):
        cov = self._read("stats.json")["coverage"]
        july = next(m for m in cov if m["month"] == "2026-07")
        self.assertEqual(july["cells"]["Otherville␟Zoning Board of Appeals"], 1)
        self.assertEqual(july["cells"]["␟"], 1)   # the untowned meeting
        self.assertEqual(july["total"], 2)

    def test_two_town_edition_presses_idempotently(self):
        """The scope plane is derived from the corpus; nothing in it may vary
        between two pressings of the same record."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "two.db"
            TestBakeEdition._seed(db)
            from memory.store import Corpus
            c = Corpus(str(db))
            c.replace_segments("vid3", [{"start": 0.0, "end": 9, "text": "zoning"}])
            c.upsert_meeting({"id": "vid3", "title": "Zoning Board — July",
                              "date": "2026-07-02", "town": "Otherville",
                              "body": "Zoning Board of Appeals",
                              "source_kind": "youtube", "video_id": "vid3",
                              "url_canon": "youtube:vid3", "duration": 60,
                              "n_segments": 1, "status": "live"})
            from web import bake
            bake.bake(str(db), str(root / "a"), "1.0.0", "https://x.org")
            bake.bake(str(db), str(root / "b"), "1.0.0", "https://x.org")
            for p in sorted((root / "a").rglob("*")):
                if p.is_file():
                    rel = p.relative_to(root / "a")
                    self.assertEqual(p.read_bytes(), (root / "b" / rel).read_bytes(),
                                     f"{rel} differs between two bakes")


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
