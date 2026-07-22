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


class TestMomentQualityGates(unittest.TestCase):
    """The newspaper's moment plane holds a higher bar than the shared
    analyzer (specs/20 §6 quality pass): stored decisions are re-validated on
    a word boundary, and soft tension words have to be *owned* to count."""

    def test_real_decisions_drops_the_substring_false_positives(self):
        from web.bake import _real_decisions
        stored = [
            {"t": 10.0, "text": "staff who have devoted three decades", "outcome": "discussed"},
            {"t": 20.0, "text": "I heard a commotion in the hallway", "outcome": "discussed"},
            {"t": 30.0, "text": "the motion carries, unanimous", "outcome": "passed"},
            {"t": 40.0, "text": "and the chair votes I", "outcome": "passed"},
        ]
        kept = _real_decisions(stored)
        texts = [d["text"] for d in kept]
        self.assertIn("the motion carries, unanimous", texts)   # real motion
        self.assertIn("and the chair votes I", texts)           # real roll call
        self.assertNotIn("staff who have devoted three decades", texts)
        self.assertNotIn("I heard a commotion in the hallway", texts)

    def test_weak_tension_keeps_the_felt_and_drops_the_incidental(self):
        from web.bake import _is_weak_tension
        felt = [
            ("I am deeply concerned about the plan", ["concern", "concerned"]),
            ("but I'm a little concerned that this fails kids", ["concern"]),
            ("we strongly oppose this cut", ["oppose", "opposed"]),
            ("the concern was that the language was vague", ["concern"]),
        ]
        incidental = [
            ("training to invent new things and solve problems", ["problem"]),
            ("as capable problem solvers", ["problem"]),
            ("my next question concerns equity", ["concern"]),
            ("fees as opposed to fines", ["oppose", "opposed"]),
            ("and there aren't crises on the finance side", ["concern"]),
            ("you don't concern yourself with opinion", ["concern"]),
        ]
        for text, words in felt:
            self.assertFalse(_is_weak_tension(text, words),
                             f"real pushback dropped: {text!r}")
        for text, words in incidental:
            self.assertTrue(_is_weak_tension(text, words),
                            f"incidental mention kept: {text!r}")

    def test_narrated_decisions_and_bare_vote_tokens_are_not_decisions(self):
        """A decision word inside narration (a death, a described process) or a
        lone roll-call token is not a decision made — the audit's finds."""
        from web.bake import _is_narrated_decision, _build_moments
        for narration in ("the original author passed away last spring",
                          "it is submitted and then approved by PSB Finance",
                          "signed by the superintendent and sent to DESE for approval",
                          "as we try to find resolutions we keep working"):
            self.assertTrue(_is_narrated_decision(narration),
                            f"narration read as a decision: {narration!r}")
        self.assertFalse(_is_narrated_decision("I move that we approve the budget"))
        # a bare "Aye." window is a vote cast, not a decision card
        segs = [{"start": 50.0, "end": 53.0, "text": "Aye."},
                {"start": 200.0, "end": 204.0, "text": "the board voted to adopt the budget"}]
        decisions = [{"t": 50.0, "text": "Aye.", "outcome": "discussed"},
                     {"t": 200.0, "text": "the board voted to adopt the budget",
                      "outcome": "passed"}]
        ms = _build_moments(segs, [], decisions, [], [])
        quotes = " || ".join(m["quote"] for m in ms if m["kind"] == "decision")
        self.assertNotIn("Aye", quotes)
        self.assertIn("adopt the budget", quotes)

    def test_moments_gate_procedural_roll_call_and_own_tension(self):
        """A decision that is pure roll-call mechanics ("how do you vote?")
        is procedure, not a moment; a tension word owned a segment away from
        its subject still lands, because the gate reads the windowed sentence."""
        from web.bake import _build_moments
        segs = [
            {"start": 100.0, "end": 103.0, "text": "Okay, want to vote?"},
            {"start": 200.0, "end": 203.0, "text": "we have a consent agenda to vote on"},
            {"start": 300.0, "end": 303.0, "text": "So, so I understand, but I'm a little"},
            {"start": 303.0, "end": 306.0, "text": "concerned that this eliminates a class."},
        ]
        decisions = [
            {"t": 100.0, "text": "Okay, want to vote?", "outcome": "discussed"},
            {"t": 200.0, "text": "we have a consent agenda to vote on", "outcome": "discussed"},
        ]
        tension = [{"t": 303.0, "text": "concerned that this eliminates a class.",
                    "words": ["concern", "concerned"]}]
        ms = _build_moments(segs, [], decisions, [], tension)
        quotes = " || ".join(m["quote"] for m in ms)
        self.assertNotIn("want to vote", quotes)                  # procedure gated
        self.assertIn("consent agenda", quotes)                   # real decision kept
        te = [m for m in ms if m["kind"] == "tension"]
        self.assertTrue(te, "owned tension one segment from its subject should land")
        self.assertIn("concerned", te[0]["quote"])


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

    def test_covenant_and_the_press_present(self):
        self.assertTrue((self.out / "covenant" / "index.html").exists())
        # the desk tools no longer own a door each; their URLs redirect to the
        # press, and memory (a web surface) never had one
        self.assertTrue((self.out / "t" / "stencil" / "index.html").exists())
        self.assertFalse((self.out / "t" / "memory").exists())
        stub = (self.out / "t" / "stencil" / "index.html").read_text()
        self.assertIn('http-equiv="refresh"', stub)
        self.assertIn("/app/press#stencil", stub)
        self.assertIn("Content-Security-Policy", stub)   # a real page, CSP intact
        # the press page is where they land: the tool, and the one download
        press = (self.out / "press" / "index.html").read_text()
        self.assertIn('id="stencil"', press)
        self.assertIn("Civic Media Studio", press)
        self.assertIn("Get the desktop app", press)
        self.assertIn("communityai.studio", press)   # the cross-link, done once

    def test_kits_plane_pressed_and_indexed(self):
        """Publisher's reading half (specs/20 §7.9 P2): a kit per meeting with a
        video and moments, as a real Publisher kit and an index that lists it."""
        kit = self._read("kits/vid1.json")
        self.assertEqual(kit["slug"], "vid1")
        self.assertEqual(kit["version"], 1)
        self.assertTrue(kit["clips"])
        self.assertIn("extractive", kit["copy"]["origin"])
        self.assertEqual(kit["files"], [])            # nothing rendered — desk work
        # the clip carries the reel model's identity (kind, t)
        self.assertTrue(all("kind" in c and "t" in c for c in kit["clips"]))
        idx = self._read("kits/index.json")
        slugs = {k["slug"] for k in idx["kits"]}
        self.assertEqual(slugs, {"vid1", "vid2"})
        self.assertTrue(all(k["n_clips"] >= 1 for k in idx["kits"]))

    def test_kit_page_reads_with_js_off_and_stays_at_the_desk(self):
        html = (self.out / "k" / "vid1" / "index.html").read_text()
        self.assertIn("publish kit", html)
        self.assertIn("mo-quote", html)                       # the clips render
        self.assertIn("/app/kits/vid1.json", html)            # the download
        self.assertIn("/app/r?v=1&amp;m=vid1&amp;c=", html)   # play-as-reel handoff
        # the covenant sentence: rendering stays at the desk, and it says so
        self.assertIn("Rendering the clips as video needs the desk", html)
        self.assertIn("Content-Security-Policy", html)        # a real page
        # the index lists both meetings' kits
        kidx = (self.out / "k" / "index.html").read_text()
        self.assertEqual(kidx.count('class="mcard"'), 2)

    def test_meeting_page_surfaces_its_kit_and_cross_meeting_reels(self):
        """The moments panel is the produce-zone: it links a meeting to its kit
        (P2-A) and says a reel can span meetings (P2-B), so both are findable."""
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn("/app/k/vid1", stub)
        self.assertIn("publish kit for this meeting", stub)
        self.assertIn("a reel can span the record", stub)

    def test_press_publisher_row_points_at_the_kits(self):
        """The door stays honest until kits press (specs/20 §6): this edition has
        kits, so Publisher's line now cross-links into /app/k."""
        press = (self.out / "press" / "index.html").read_text()
        self.assertIn("/app/k", press)
        self.assertIn("a publish kit for every meeting", press)

    def test_all_thirteen_door_urls_still_answer_as_stubs(self):
        """A citation never dies (specs/20 §5): every /app/t/<tool>/ URL the old
        doors answered is a redirect stub now — 200, CSP, pointed at the press."""
        doors = [t["id"] for t in tools.TOOLS if t["surface"] != "web"]
        self.assertEqual(len(doors), 13)
        press = (self.out / "press" / "index.html").read_text()
        for tid in doors:
            p = self.out / "t" / tid / "index.html"
            self.assertTrue(p.is_file(), f"/app/t/{tid}/ vanished")
            html = p.read_text()
            self.assertIn(f"/app/press#{tid}", html)
            self.assertIn('http-equiv="refresh"', html)
            self.assertIn(f'id="{tid}"', press, f"the press has no anchor for {tid}")

    def test_nothing_references_the_slides_that_never_travelled(self):
        """The broken door images leave this domain structurally (specs/20 §5):
        no pressed file references site/content/assets, and no /app/assets/slide
        survives anywhere — so there is no broken image on the domain."""
        for p in self.out.rglob("*"):
            if p.is_file() and p.suffix in (".html", ".css", ".js", ".json"):
                txt = p.read_text(errors="ignore")
                self.assertNotIn("site/content/assets", txt, str(p))
                self.assertNotIn("/app/assets/slide-", txt, str(p))

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

    # -- the coat: publicrecord's own face, drawn from brand/ (specs/20 §20.1) --

    def test_pressed_css_bans_the_desk_and_scopes_the_studio_pop(self):
        """publicrecord is the quietest property: neutrals + deep green, and no
        cream, oxblood, amber, or the lens hues may survive in the pressed
        stylesheet — not even as an unused variable (specs/20 §4, the law).

        The studio-mode amendment (specs/21 §6.1) is the one bounded exception:
        the two purples it uses — #a855f7 (surfaces/borders) and #7c3aed (text at
        AA) — may appear, but ONLY inside a rule scoped to html.cz-m-studio, so
        they light the editor's own chrome and can never reach the paper, the
        preview, or the shared masthead. Fuchsia is still forbidden everywhere —
        the amendment admitted purple, it did not repeal the fuchsia line.
        Comments are stripped first so a note does not count."""
        css = (self.out / "app.css").read_text()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S).lower()
        FORBIDDEN = [
            "#f3f0e7", "#8e4a55", "#a97a16", "#a97e22",   # cream, oxblood, amber
            "#d946ef",                                     # fuchsia — still nowhere
            "#7e5b8e", "#c77ba6", "#b0542d", "#3fa9d0",    # the lens hues
            "--cream", "--memory", "--amber", "--forest", "--ide-",
        ]
        for bad in FORBIDDEN:
            self.assertNotIn(bad, css, f"forbidden token {bad!r} in the pressed CSS")
        # the studio purples are admitted, but every occurrence must be
        # studio-mode-scoped: the governing selector (the text opening the rule it
        # sits in) names the mode.
        for purple in ("#a855f7", "#7c3aed"):
            at = -1
            while (at := css.find(purple, at + 1)) != -1:
                open_brace = css.rfind("{", 0, at)
                selector = css[css.rfind("}", 0, open_brace) + 1:open_brace]
                self.assertIn("cz-m-studio", selector,
                              f"purple {purple!r} appears outside a studio-mode "
                              f"rule (selector {selector.strip()!r}) — it must "
                              f"never reach the paper (specs/21 §6.1)")
        # the shared :root token block stays pure — no studio accent leaks upward
        root = css[css.index(":root{"):css.index("}", css.index(":root{"))]
        for pop in ("#a855f7", "#7c3aed", "#d946ef", "fuchsia", "purple"):
            self.assertNotIn(pop, root, f"{pop!r} leaked into the shared :root")
        # and the record's own accents ARE there
        for good in ("#052e16", "#059669", "#f8fafc"):
            self.assertIn(good, css, f"{good} (brand) missing from the pressed CSS")

    def test_the_studio_is_script_built_never_baked(self):
        """specs/21 P0: the three-mode studio is added by app.js at runtime, so
        the pressed pages stay byte-for-byte the specs/20 paper. No studio class
        and no mode class may appear in any baked stub — a reader with app.js
        removed gets exactly the reader, which is what 'paper mode never gets
        louder' and 'JS-off degrades to paper' require. The studio lives only in
        the shipped script and stylesheet."""
        MARKERS = ("cz-studio", "cz-m-", "cz-mode", "cz-panel", "cz-tab",
                   "cz-pill", "cz-enter")
        for stub in self.out.rglob("index.html"):
            html = stub.read_text()
            for m in MARKERS:
                self.assertNotIn(m, html,
                    f"{m!r} was baked into {stub.relative_to(self.out)} — the "
                    f"studio must be built by app.js, not pressed into the paper")
        self.assertIn("cz-m-studio", (self.out / "app.js").read_text())
        self.assertIn("cz-m-studio", (self.out / "app.css").read_text())

    def test_your_paper_stub_is_pressed(self):
        """specs/21 P1: /app/p is one static stub for every paper (the /app/r
        pattern) — the paper itself arrives in the link, the browser's draft,
        or a store id, so the stub must say honestly what JS-off cannot do and
        point at the record instead. And it stays paper-quiet: no studio class
        is baked (the guard above already sweeps it), and the rendered-paper
        rule — no studio hue — is CSS-scoped, so this page carries none."""
        stub = (self.out / "p" / "index.html").read_text()
        self.assertIn("A paper, edited from the record", stub)
        self.assertIn("needs JavaScript", stub)
        self.assertIn('href="/app/"', stub)          # the honest fallback
        self.assertIn('id="paperbody"', stub)        # the renderer's mount
        # the paper's own classes ship in the stylesheet the stub loads
        css = (self.out / "app.css").read_text()
        for cls in (".phead", ".ptitle", ".pb-gone", ".cz-ptitle", ".cz-prow"):
            self.assertIn(cls, css, f"{cls} missing from the pressed CSS")
        # the make surfaces belong to the offline shell (specs/21 §5: the
        # covenant's own case is composing with the servers gone) — the SW
        # precaches /app/p and /app/r beside the sibling stubs, in the
        # trailing-slash canonical form (the bare form 301s, and a cached
        # redirect served to a navigation is a browser error, not a page)
        sw = (self.out / "sw.js").read_text()
        for url in ('"/app/p/"', '"/app/r/"', '"/app/s/"'):
            self.assertIn(url, sw, f"{url} missing from the SW shell")
        self.assertNotIn('"/app/s",', sw, "a bare stub URL crept back into the shell")
        self.assertIn("!res.redirected", sw,
                      "the SW must never cache a redirected response")
        self.assertIn("url.pathname + '/'", sw,
                      "bare-path navigations must fall to the slash form offline")

    def test_the_ai_constitution_is_pressed_and_the_footer_names_it(self):
        """/app/ai says when a model touches the record, whose model it is,
        where it runs, and what stands without it — every claim checkable —
        and the footer on every page carries the recredit and the link; the
        about (covenant) and settings (town scope) surfaces carry the button.
        Interactivity is native (details/summary), so the page is complete
        with JavaScript off."""
        page = (self.out / "ai" / "index.html").read_text()
        for claim in ("Our AI Constitution", "gemini-embedding-001",
                      "Whisper-family", "no model at all",
                      "part of the Community AI Project", "communityai.studio",
                      "your machine only", "check it yourself",
                      "civicmedia.studio", "control-z.org", "/constitution"):
            self.assertIn(claim, page, f"{claim!r} missing from /app/ai")
        # the shareable spelling redirects, canonical intact
        alias = (self.out / "constitution" / "index.html").read_text()
        self.assertIn('url=/app/ai/', alias)
        self.assertIn('rel="canonical"', alias)
        self.assertIn("Our AI Constitution", alias)
        self.assertIn("<details>", page)
        self.assertIn("aria-label", page)      # the diagram speaks to AT
        home = (self.out / "index.html").read_text()
        for frag in ("weird machine", "brookline interactive group",
                     "Our AI Constitution", 'href="/app/ai"',
                     'class="scopeai"'):
            self.assertIn(frag, home, f"{frag!r} missing from the front page")
        self.assertNotIn("a Community AI Project tool", home,
                         "the old footer credit survived the recredit")
        cov = (self.out / "covenant" / "index.html").read_text()
        self.assertIn('href="/app/ai"', cov, "the about surface lost its button")
        self.assertIn('"/app/ai/"', (self.out / "sw.js").read_text(),
                      "the constitution should read offline too")

    def test_pressed_css_draws_its_tokens_from_brand(self):
        """The drift-guard, repointed at brand/ (specs/20 §8): the pressed
        :root carries the brand's own values, byte-faithful — the accent is
        green-deep, the state light is green-emerald, the page is off-white."""
        brand = (REPO / "brand" / "tokens" / "colors.css").read_text()
        val = lambda n: re.search(rf"--{n}:\s*(#[0-9A-Fa-f]{{6}})", brand).group(1)
        css = (self.out / "app.css").read_text()
        root = css[css.index(":root{"):css.index("}", css.index(":root{"))]
        for token, source in [("--accent", "green-deep"),
                              ("--state", "green-emerald"),
                              ("--surface-page", "offwhite"),
                              ("--text-primary", "ink"),
                              ("--text-secondary", "slate")]:
            self.assertIn(f"{token}:{val(source)}", root,
                          f"{token} drifted from brand --{source}")

    def test_fonts_are_vendored_and_within_budget(self):
        """Real Inter + JetBrains Mono, self-hosted (specs/20 §4): six subset
        woff2 with their OFL texts ship in the edition, the @font-face block is
        pressed, the CSP stays font-src 'self', and the whole face set is under
        its ~250 KB budget — thumbnails are remote, fonts are the only new
        bytes."""
        fonts = self.out / "fonts"
        faces = ["inter-400", "inter-500", "inter-700",
                 "jetbrains-mono-400", "jetbrains-mono-700", "jetbrains-mono-800"]
        total = 0
        for f in faces:
            p = fonts / f"{f}.woff2"
            self.assertTrue(p.is_file(), f"{f}.woff2 not vendored")
            total += p.stat().st_size
        self.assertTrue((fonts / "OFL-Inter.txt").is_file())
        self.assertTrue((fonts / "OFL-JetBrainsMono.txt").is_file())
        self.assertLess(total, 260_000, f"font set is {total//1024} KB (budget ~250)")
        css = (self.out / "app.css").read_text()
        self.assertIn("@font-face", css)
        self.assertIn("font-display:swap", css.replace(" ", ""))
        self.assertIn("/app/fonts/inter-400.woff2", css)
        home = (self.out / "index.html").read_text()
        self.assertIn("font-src 'self'", home)           # CSP unwidened
        self.assertIn('rel="preload"', home)             # critical faces preloaded
        self.assertNotIn("fonts.googleapis.com", home)   # nothing third-party
        self.assertNotIn("fonts.gstatic.com", css)

    def test_masthead_carries_the_brand_mark_byte_equal(self):
        """The keycap is read from brand/logos and never redrawn (specs/20 §4).
        Its three deep-green minute-lines, at their exact coordinates, appear in
        the masthead of every page and in the favicon."""
        mark = (REPO / "brand" / "logos" / "publicrecord-mark.svg").read_text().strip()
        line = '<rect x="22" y="28" width="52" height="8" fill="#052e16">'
        self.assertIn(line, mark, "the brand mark itself changed shape")
        home = (self.out / "index.html").read_text()
        self.assertIn(line, home, "the masthead mark is not the brand mark")
        self.assertEqual((self.out / "favicon.svg").read_text().strip(), mark)

    def test_front_page_is_a_newspaper(self):
        """The front page reads like a paper, not a dashboard: a lead story, a
        briefs column, by-the-numbers, the long view, the access ledger and the
        latest roll calls — all real HTML, so it reads linearly with JS off
        (specs/20 §5)."""
        home = (self.out / "index.html").read_text()
        for kicker in ("the latest meeting on the record", "also on the record",
                       "by the numbers", "the long view", "the access ledger",
                       "the latest roll calls"):
            self.assertIn(kicker, home, f"front page missing '{kicker}'")
        # the lead IS the latest meeting (vid2, June), as a real article
        self.assertIn('class="lead"', home)
        self.assertIn("School Committee — June", home)
        # briefs are the scope-filterable meeting cards
        self.assertIn('class="mcard"', home)
        # by-the-numbers, and every figure is a link (roll calls → the votes)
        self.assertIn('class="statband"', home)
        self.assertIn('<a class="statcell" href="/app/officials">', home)

    def test_front_page_pull_moments_link_into_the_tape(self):
        """The lead's pull-moments come from the moments plane and deep-link
        into the tape — nothing hand-typed."""
        home = (self.out / "index.html").read_text()
        self.assertIn('class="pull"', home)
        self.assertRegex(home, r'class="pull" href="/app/m/vid2#t\d+"')

    def test_meeting_carries_the_moments_plane(self):
        """Each meeting.json carries the pressed moments (specs/20 §6): a ranked,
        chronological list of {t, end, kind, score, reason, quote}. vid1 has a
        roll call, so it carries a VOTE moment scored above everything else."""
        mj = self._read("meetings/vid1.json")
        self.assertIn("moments", mj)
        ms = mj["moments"]
        self.assertTrue(ms, "vid1 should have moments")
        for mo in ms:
            self.assertEqual(set(mo),
                             {"t", "start", "end", "kind", "score", "reason", "quote"})
            # the anchor sits inside its own padded clip window
            self.assertLessEqual(mo["start"], mo["t"])
            self.assertGreaterEqual(mo["end"], mo["t"])
            self.assertGreaterEqual(mo["end"] - mo["start"], 6.0)   # min clip
        votes = [mo for mo in ms if mo["kind"] == "vote"]
        self.assertTrue(votes, "the roll call should press as a VOTE moment")
        self.assertGreaterEqual(votes[0]["score"], 0.9)
        # chronological
        self.assertEqual([mo["t"] for mo in ms], sorted(mo["t"] for mo in ms))

    def test_moments_window_the_sentence_and_gate_procedure(self):
        """specs/20 §6 P1 follow-up: a moment is the whole sentence around its
        anchor (padded into a watchable clip), and procedure is gated out — a
        reel is built from meaning, not from 'right, Betsy?'."""
        from web.bake import _build_moments
        segs = [
            {"start": 100.0, "end": 103.0, "text": "Right, Betsy?"},
            {"start": 200.0, "end": 203.0, "text": "How much will this override"},
            {"start": 203.0, "end": 206.0, "text": "cost the average household this year?"},
            {"start": 300.0, "end": 303.0, "text": "I am deeply concerned about the plan"},
            {"start": 303.0, "end": 306.0, "text": "to eliminate a kindergarten classroom."},
        ]
        questions = [
            {"t": 100.0, "text": "Right, Betsy?", "type": "information"},
            {"t": 200.0, "text": "How much will this override cost the average "
                                 "household this year?", "type": "budget"},
        ]
        tension = [{"t": 300.0, "text": "I am deeply concerned about the plan",
                    "words": ["concern"]}]
        ms = _build_moments(segs, [], [], questions, tension)
        quotes = " || ".join(m["quote"] for m in ms)
        self.assertNotIn("Right, Betsy", quotes)   # procedure gated out
        q = next(m for m in ms if m["kind"] == "question")
        self.assertIn("cost the average household", q["quote"])   # full sentence
        self.assertLessEqual(q["start"], q["t"])                  # padded clip
        self.assertGreaterEqual(q["end"] - q["start"], 6.0)
        te = next(m for m in ms if m["kind"] == "tension")
        self.assertIn("eliminate a kindergarten", te["quote"])    # fragment → sentence

    def test_search_is_instant_and_peeks_over_the_static_floor(self):
        """Instant search (debounced, never under three characters), hover peeks
        from the segs plane, and a `/` focus — all pure enhancement over the
        R1.6 static index, which stays untouched (specs/20 §4). The peek reads
        the plane the static path already loaded, so it never fetches and never
        burdens the live path."""
        js = (REPO / "web" / "static" / "app.js").read_text()
        self.assertIn("val.length < 3", js)             # no query under 3 chars
        self.assertIn('addEventListener("input"', js)   # instant
        self.assertIn("function wireSlashFocus", js)    # `/` focuses search
        self.assertIn("function selMove", js)           # j/k walk hits
        peek = re.search(r"function peek\(segs, id, mi\) \{.+?\n  \}",
                         js, re.S).group(0)
        for forbidden in ("fetch", "getJSON", "/api/", "askStudio"):
            self.assertNotIn(forbidden, peek,
                             f"the peek reached for {forbidden!r} — it must read "
                             "only the plane already in hand")

    def test_meeting_page_renders_moments_js_off(self):
        """The Moments panel is baked into the meeting stub, so it reads with
        JavaScript off (specs/20 §6 acceptance): scored cards, each a deep link
        into the transcript below, differing by a mono kicker not by colour."""
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn("the moments", stub)
        self.assertIn('class="moment"', stub)
        self.assertIn('class="mo-kind"', stub)
        self.assertRegex(stub, r'class="moment" href="#t\d+"')
        self.assertIn("salience", stub)   # the score bar is a measurement

    def test_moment_cards_carry_the_reel_composer_hooks(self):
        """Each moment card wraps in .mo-card and the anchor carries the whole
        moment (end, kind, quote), so the reel composer (specs/20 §6, P1) can
        cut a clip from a tick without a second fetch — and the card stays a
        plain deep link with JavaScript off."""
        stub = (self.out / "m" / "vid1" / "index.html").read_text()
        self.assertIn('class="mo-card"', stub)
        self.assertRegex(stub, r'class="moment"[^>]*data-end="[^"]+"[^>]*data-kind="')
        self.assertRegex(stub, r'data-quote="')

    def test_reel_viewer_stub_and_its_js_off_fallback(self):
        """/app/r is one static stub for every reel — the reel lives in the
        link, not the page (specs/20 §7). It has the mount points app.js
        hydrates, and a JS-off fallback that is honest about needing JavaScript
        and sends the reader to the record where the moments read in place."""
        stub = (self.out / "r" / "index.html").read_text()
        self.assertIn('id="reelstage"', stub)
        self.assertIn('id="reelcites"', stub)
        # honest JS-off degradation: it names the dependency and points home
        self.assertIn("needs JavaScript", stub)
        self.assertIn('href="/app/"', stub)
        # and it states the one desk-bound step plainly
        self.assertIn("needs the desk", stub)
        # the route exists in the reader
        js = (REPO / "web" / "static" / "app.js").read_text()
        self.assertIn(r"/\/app\/r$/.test(path)", js)

    def test_the_reel_path_touches_no_server(self):
        """The covenant, on the reel path: composing and playing a reel reach no
        backend (specs/20 §7 hard constraint). The viewer's only fetch is the
        meeting's own plane under /app/, and none of the reel code reaches the
        Studio helper."""
        js = (REPO / "web" / "static" / "app.js").read_text()
        # the reel path ends where the paper's own section (with its own
        # covenant test, TestPaper) begins
        block = js[js.index("THE REEL — compose here"):
                   js.index("YOUR PAPER — the curated document")]
        for forbidden in ("askStudio", "API +", "/api/", "http://", "run.app"):
            self.assertNotIn(forbidden, block,
                             f"the reel path reached for {forbidden!r}")
        # every plane the reel reads is a same-origin edition path
        for plane in re.findall(r"getJSON\(`([^`]+)`", block):
            self.assertTrue(plane.startswith("${BASE}/"),
                            f"{plane} is not an edition path")

    def test_the_thirteen_tool_doors_left_the_masthead(self):
        """The desk tools no longer share the record's masthead: the rail is
        gone and the section line is the paper's own (specs/20 §5). The tools
        live on /app/press now, reachable from the section nav and the footer."""
        home = (self.out / "index.html").read_text()
        self.assertNotIn('class="rail-item"', home)
        self.assertNotIn("civic media suite", home)   # the old rail heading
        self.assertIn('class="sectionnav"', home)
        self.assertIn('href="/app/press"', home)

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

    def test_votes_plane_restates_the_meetings_own_roll_calls(self):
        """specs/21 P2: votes.json gathers the roll calls the meeting planes
        already show — one date-ordered plane, one fetch at any corpus size,
        receipts by (pid, t). It must never disagree with the meeting pages
        (officials.json is per-member and deliberately different)."""
        plane = self._read("votes.json")
        self.assertEqual(plane["n_meetings"], 1)
        vs = plane["votes"]
        self.assertEqual(len(vs), self._read("manifest.json")["counts"]["votes"])
        v = vs[0]
        self.assertEqual(set(v), {"pid", "date", "body", "town", "t",
                                  "motion", "outcome", "tally"})
        self.assertEqual((v["outcome"], v["tally"]), ("passes", "3–0"))
        # the receipt resolves: the same vote, at the same second, on the
        # meeting page the dot links to
        m = self._read(f"meetings/{v['pid']}.json")
        self.assertIn(v["t"], [x["t"] for x in m["votes"]])
        self.assertEqual(v["motion"], m["votes"][0]["motion"])

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
        every readable page — so it is markup, not something script invents
        late. A door redirect stub is not a page the reader lands on, so it is
        the one exception (it carries a meta refresh instead)."""
        for stub in self.out.rglob("index.html"):
            html = stub.read_text()
            if 'http-equiv="refresh"' in html:
                continue
            self.assertIn('id="scopebanner"', html, str(stub))

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
        """The load-bearing property, stated more precisely than it used to be.

        This asserted that `/api/` appeared nowhere in the reader — a blanket
        rule that was exactly right while the reader had no server to call.
        specs/19 R1.6 gives it one, so the blanket rule would now have to be
        deleted or the feature abandoned, and neither is the point. The
        property worth keeping was never "no API string in the file"; it was
        **nothing on the path to reading the record depends on a server**.

        So: the edition's own planes are same-origin paths under /app/, the
        API's address is never hardcoded here (it arrives per-pressing from a
        meta tag, so a desk edition has no address to call), and the sole
        outbound call is funnelled through one guarded helper. That the search
        box actually falls back when that helper fails is proven by executing
        the code, in TestReaderDegradesToStatic.
        """
        js = (REPO / "web" / "static" / "app.js").read_text()
        self.assertIn("towns.json", js)
        self.assertNotIn("http://", js.replace("http://www.w3.org", ""))
        self.assertNotIn("localhost", js)
        self.assertTrue((self.out / "towns.json").exists())

        # No API host is baked into the reader. The address comes from the
        # pressing, which is what makes a desk edition serverless by default
        # rather than by everyone remembering.
        self.assertNotIn("run.app", js)
        self.assertNotIn("https://record-api", js)

        # Exactly the sanctioned outbound paths, every one guarded. The search
        # door is askStudio; specs/21 §6.2 added the paper store's two touches
        # — a POST behind the explicit "short link" button and a GET for `?p=`
        # addresses — both additive and both fail-soft (losing the store loses
        # short links, never a paper). Any other `/api/` would be a door
        # nobody wrote a fallback for.
        self.assertEqual(js.count("API + path"), 1)
        self.assertEqual(js.count("/api/papers"), 2,
                         "the paper store's two touches drifted")
        self.assertEqual(js.count("/api/"), 3, "an unsanctioned API call appeared")
        ask = re.search(r"  async function askStudio\(path\) \{.+?\n  \}",
                        js, re.S).group(0)
        self.assertIn("if (!API || API_DOWN) return null;", ask)
        # both store touches are timed, caught, and no-API-safe — executing
        # their fallbacks is TestPaper's and the browser's job; the shape is
        # pinned here beside the door count
        for fn in ("paperShortLink", "fetchStoredPaper"):
            src = re.search(rf"  async function {fn}\(.*?\n  \}}", js, re.S)
            self.assertTrue(src, f"{fn} moved")
            for guard in ("API_TIMEOUT_MS", "catch", "if (!API)"):
                self.assertIn(guard, src.group(0),
                              f"{fn} lost its {guard!r} guard")

        # Every edition plane the reader reads is a path under /app/.
        for plane in re.findall(r"getJSON\(`([^`]+)`", js):
            self.assertTrue(plane.startswith("${BASE}/"),
                            f"{plane} is not an edition path")


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

    def test_byte_identical_across_hash_seeds(self):
        """The rsync deploy re-uploads on any diff, and a real press runs in a
        fresh container process — so "press today == press tomorrow" spans
        Python hash seeds. The in-process test above shares one seed and cannot
        see set/dict-iteration order leaking into edition bytes; this presses
        the SAME corpus in two subprocesses with different PYTHONHASHSEED and
        byte-compares, which is the determinism the deploy actually needs."""
        import os
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "c.db"
            TestBakeEdition._seed(db)

            def press(dst, seed):
                r = subprocess.run(
                    [sys.executable, "-m", "web.bake", "--corpus", str(db),
                     "--out", str(root / dst), "--base", "https://x.org"],
                    cwd=str(REPO), env={**os.environ, "PYTHONHASHSEED": seed},
                    capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

            press("a", "0")
            press("b", "1")
            for p in sorted((root / "a").rglob("*")):
                if p.is_file():
                    rel = p.relative_to(root / "a")
                    self.assertEqual(
                        p.read_bytes(), (root / "b" / rel).read_bytes(),
                        f"{rel} differs across hash seeds — nondeterministic press")


class TestTombstones(unittest.TestCase):
    """A steward's forget leaves an explanation, not a bare 404 (specs/20 §6).
    The date comes from the audit ledger — stored state, never a wall clock —
    so the tombstone presses idempotently."""

    def test_press_writes_a_tombstone_with_the_audit_date(self):
        from memory.store import Corpus
        from web import bake
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "c.db"
            TestBakeEdition._seed(db)
            forget = [{"id": "issue:testville:gone-issue", "name": "a gone issue",
                       "town": "Testville", "date": "2026-05-01"}]
            # the desk store has no audit ledger; stand one in for this press so
            # the emission path is exercised end to end
            orig = Corpus.list_forgotten
            Corpus.list_forgotten = lambda self, limit=1000: list(forget)
            try:
                bake.bake(str(db), str(root / "app"), "1.0.0", "https://x")
            finally:
                Corpus.list_forgotten = orig
            p = root / "app" / "i" / "issue_testville_gone-issue" / "index.html"
            self.assertTrue(p.is_file(), "no tombstone was written")
            html = p.read_text()
            self.assertIn("removed from the record by a steward on 2026-05-01", html)
            self.assertIn("a gone issue", html)
            self.assertIn("Content-Security-Policy", html)   # a real page
            # the live issue's own page still stands, untouched
            self.assertTrue((root / "app" / "i" /
                             "issue_testville_budget-override" / "index.html").is_file())

    def test_a_live_issue_wins_its_old_grave(self):
        """A re-created issue must not be buried by its own tombstone: a slug a
        live issue occupies is never tombstoned."""
        from web import bake

        class Forgetful:
            def list_forgotten(self, limit=1000):
                return [{"id": "issue:x:thing", "name": "thing", "date": "2026-07-01"}]
        b = bake.Bake(Forgetful(), Path("/tmp/none"), "1.0.0", None)
        self.assertEqual(b.bake_tombstones({bake.islug("issue:x:thing")}), [])
        # but with no live claimant, the grave stands
        got = b.bake_tombstones(set())
        self.assertEqual(got[0]["slug"], bake.islug("issue:x:thing"))
        self.assertEqual(got[0]["date"], "2026-07-01")

    def test_the_desk_store_keeps_no_audit_ledger(self):
        from memory.store import Corpus
        with tempfile.TemporaryDirectory() as td:
            c = Corpus(str(Path(td) / "c.db"))
            self.assertEqual(c.list_forgotten(), [])


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


class TestLiveFirstEdition(unittest.TestCase):
    """`--api`: the one pressing that has a Studio behind it.

    Two promises are under test, and the second is the load-bearing one.

    **A desk edition does not change.** Press without `--api` and the bytes are
    what they were before the flag existed — no meta tag, no widened policy, no
    extra manifest key. The desk is the common case and it must not pay for a
    feature it does not have.

    **A Studio edition is still complete without its Studio.** The API is an
    upgrade on a static floor: every meeting, issue, timeline and the whole
    prebuilt lexical index are in the edition either way. This was proven once
    by stopping Postgres and walking the site, and it is asserted here so it
    stays true.
    """

    API = "https://record-api-907309358085.us-east1.run.app"

    def press(self, out, api=""):
        from web import bake
        return bake.bake(str(self.db), str(out), "1.0.0", "https://x.org",
                         api=api)

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.db = self.root / "c.db"
        TestBakeEdition._seed(self.db)
        # `emit` holds the API as module state; leaving it set would leak into
        # every later test in the process.
        from web import emit
        self.addCleanup(emit.set_api, "")

    # -- the desk pays nothing ---------------------------------------------

    def test_without_api_no_trace_of_one(self):
        out = self.root / "desk"
        self.press(out)
        html = (out / "s" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("record-api", html)
        self.assertIn("connect-src 'self';", html)
        self.assertNotIn("api", json.loads(
            (out / "manifest.json").read_text(encoding="utf-8")))

    def test_a_desk_press_is_byte_identical_either_side_of_a_studio_press(self):
        """The module-state trap: press with an API, then without, and the
        second must not inherit the first's."""
        a, b, c = self.root / "a", self.root / "b", self.root / "c"
        self.press(a)
        self.press(b, api=self.API)
        self.press(c)
        for p in sorted(a.rglob("*")):
            if p.is_file():
                rel = p.relative_to(a)
                self.assertEqual(p.read_bytes(), (c / rel).read_bytes(),
                                 f"{rel} changed after a Studio press")

    # -- the Studio edition -------------------------------------------------

    def test_with_api_the_address_and_the_permission_arrive_together(self):
        out = self.root / "studio"
        self.press(out, api=self.API)
        html = (out / "s" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'<meta name="record-api" content="{self.API}">', html)
        # the policy names exactly that origin, and nothing else moved
        self.assertIn(f"connect-src 'self' {self.API};", html)
        self.assertIn("script-src 'self';", html)
        self.assertIn("img-src 'self' https://i.ytimg.com data:;", html)

    def test_the_policy_names_an_origin_never_a_path(self):
        out = self.root / "path"
        self.press(out, api=self.API + "/some/path")
        html = (out / "s" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f"connect-src 'self' {self.API};", html)

    def test_the_manifest_records_which_studio_pressed_it(self):
        out = self.root / "m"
        self.press(out, api=self.API)
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man["api"], self.API)

    def test_the_search_note_stops_promising_what_it_cannot_do(self):
        """The sentence that was wrong for a month, both ways round."""
        desk, studio = self.root / "d2", self.root / "s2"
        self.press(desk)
        self.press(studio, api=self.API)
        self.assertIn("Meaning-search needs the Studio",
                      (desk / "s" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("two ways at once",
                      (studio / "s" / "index.html").read_text(encoding="utf-8"))

    # -- the covenant: complete without the Studio --------------------------

    def test_a_studio_edition_carries_the_whole_static_record_anyway(self):
        """If the API vanished, this edition still reads. Same files, same
        index, same meetings as a desk pressing — the API adds a way to ask,
        never a thing to hold."""
        desk, studio = self.root / "d3", self.root / "s3"
        self.press(desk)
        self.press(studio, api=self.API)
        names = lambda r: {str(p.relative_to(r)) for p in r.rglob("*")
                           if p.is_file()}
        self.assertEqual(names(desk), names(studio))
        for rel in ("search/segs.json", "search/meta.json", "stats.json",
                    "urls.json", "towns.json"):
            self.assertEqual((desk / rel).read_bytes(),
                             (studio / rel).read_bytes(), rel)

    def test_a_studio_press_is_idempotent_too(self):
        a, b = self.root / "i1", self.root / "i2"
        self.press(a, api=self.API)
        self.press(b, api=self.API)
        for p in sorted(a.rglob("*")):
            if p.is_file():
                rel = p.relative_to(a)
                self.assertEqual(p.read_bytes(), (b / rel).read_bytes(),
                                 f"{rel} differs between two Studio bakes")


class TestReaderDegradesToStatic(unittest.TestCase):
    """The reader's half of live-first, and the promise underneath it.

    specs/17 §6.2 is a covenant, not a preference: if Cloud Run and Postgres
    both vanish, the record still reads. So the interesting cases are not the
    ones where the Studio answers — they are the ones where it does not.
    """

    JS = (REPO / "web" / "static" / "app.js").read_text()

    def node(self, body):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        return subprocess.run([node, "-e", body], capture_output=True, text=True)

    def lift(self, pattern):
        m = re.search(pattern, self.JS, re.S)
        self.assertTrue(m, f"{pattern!r} not found in the reader — did it move?")
        return m.group(0)

    # -- structure: the fallback cannot be removed by accident -------------

    def test_search_falls_through_to_the_static_index(self):
        """`runSearch` may prefer the Studio; it must always be able to answer
        without one. If someone deletes the fallback, this fails rather than
        the record quietly needing a backend."""
        run = self.lift(r"  async function runSearch\(q\) \{.+?\n  \}")
        self.assertIn("staticSearch", run,
                      "runSearch no longer reaches the static index")
        self.assertIn("async function staticSearch", self.JS)

    def test_the_static_path_touches_no_api(self):
        """The prebuilt index answers from this origin and nowhere else."""
        static = self.lift(r"  async function staticSearch\(q, terms, box\) \{.+?\n  \}")
        for forbidden in ("askStudio", "API +", "/api/search"):
            self.assertNotIn(forbidden, static,
                             f"the static path reached for {forbidden!r}")

    def test_a_missing_meta_tag_means_a_desk_edition(self):
        """No tag, no API, no attempt — every desk edition's condition."""
        self.assertIn('$(\'meta[name="record-api"]\') || {}', self.JS)

    # -- behaviour: a dead Studio is one timed attempt, then silence -------

    def test_a_dead_studio_returns_null_and_is_not_asked_twice(self):
        body = "\n".join([
            "let calls = 0;",
            "const AbortController = globalThis.AbortController;",
            "const fetch = () => { calls++; return Promise.reject(new Error('down')); };",
            'const API = "https://api.example";',
            "const API_TIMEOUT_MS = 50;",
            "let API_DOWN = false;",
            self.lift(r"  async function askStudio\(path\) \{.+?\n  \}"),
            "(async () => {",
            "  const a = await askStudio('/api/search?q=x');",
            "  const b = await askStudio('/api/search?q=y');",
            "  if (a !== null || b !== null) { console.log('FAIL: returned a value'); process.exit(1); }",
            "  if (calls !== 1) { console.log('FAIL: asked ' + calls + ' times, want 1'); process.exit(1); }",
            "  if (!API_DOWN) { console.log('FAIL: API_DOWN not set'); process.exit(1); }",
            "  console.log('ok');",
            "})();",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"askStudio mishandled a dead Studio:\n{r.stdout}{r.stderr}")

    def test_a_slow_studio_is_abandoned_rather_than_waited_on(self):
        """A cold Cloud Run instance must not hold the reader hostage."""
        body = "\n".join([
            "const AbortController = globalThis.AbortController;",
            "const fetch = (u, o) => new Promise((res, rej) => {",
            "  o.signal.addEventListener('abort', () => rej(new Error('aborted')));",
            "});",
            'const API = "https://api.example";',
            "const API_TIMEOUT_MS = 60;",
            "let API_DOWN = false;",
            self.lift(r"  async function askStudio\(path\) \{.+?\n  \}"),
            "(async () => {",
            "  const t0 = Date.now();",
            "  const a = await askStudio('/api/search?q=x');",
            "  const dt = Date.now() - t0;",
            "  if (a !== null) { console.log('FAIL: returned a value'); process.exit(1); }",
            "  if (dt > 2000) { console.log('FAIL: waited ' + dt + 'ms'); process.exit(1); }",
            "  console.log('ok');",
            "})();",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"askStudio did not give up:\n{r.stdout}{r.stderr}")

    def test_no_reader_request_ever_carries_credentials(self):
        """Readers are never identified. The fetch says so explicitly rather
        than relying on the default, because the default is a thing that can
        change under you."""
        ask = self.lift(r"  async function askStudio\(path\) \{.+?\n  \}")
        self.assertIn('credentials: "omit"', ask)

    # -- the four chips -----------------------------------------------------

    def test_every_provenance_the_server_can_send_has_a_chip(self):
        """The vocabulary is set in two places and read in a third.

        `memory.policy.blend` emits `word` / `related` / `both`; the hosted
        store renames `related` to `meaning` when the neural half answered, so
        the reader can tell "a related word" from "what you meant". A value
        the reader has no chip for would render a blank badge, so the two ends
        are compared rather than trusted."""
        from memory import policy
        kw = [{"seg_id": 1, "score": 1.0}, {"seg_id": 2, "score": 0.9}]
        vec = [({"seg_id": 2, "score": 0.9}, 0.8), ({"seg_id": 3}, 0.7)]
        produced = {h["why"] for h in policy.blend(kw, vec, 10)}
        self.assertEqual(produced, {"word", "both", "related"})

        says = self.lift(r"  const WHY_SAYS = \{.+?\};")
        # `meaning` is the fourth, added by record/store.py in the neural space
        for w in produced | {"meaning"}:
            self.assertIn(f"{w}:", says, f"no chip for provenance {w!r}")
        self.assertIn('h["why"] = "meaning"',
                      (REPO / "record" / "store.py").read_text(),
                      "the hosted store no longer produces `meaning`")

    def test_an_unknown_provenance_renders_nothing_rather_than_an_empty_badge(self):
        body = "\n".join([
            "const esc = s => String(s == null ? '' : s);",
            self.lift(r"  const WHY_SAYS = \{.+?\};"),
            self.lift(r"  function why\(w\) \{.+?\n  \}"),
            "if (why('nonsense') !== '') { console.log('FAIL:', why('nonsense')); process.exit(1); }",
            "if (!why('meaning').includes('prov-meaning')) { console.log('FAIL: no class'); process.exit(1); }",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"why() mishandled an unknown value:\n{r.stdout}{r.stderr}")


class TestReel(unittest.TestCase):
    """The reel's client-only machinery (specs/20 §6/§7, P1), executed for real
    in node. A share link is a covenant with whoever you send it to: it must
    round-trip. So the encode/decode, the cite sheet, and the reel.json the desk
    opens are lifted from the reader and run — the same treatment canon() and
    resolve() get, and for the same reason.
    """

    JS = (REPO / "web" / "static" / "app.js").read_text()
    PRELUDE = "\n".join([
        'const BASE = "/app";',
        'const location = { origin: "https://publicrecord.studio" };',
    ])

    def node(self, body):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        return subprocess.run([node, "-e", body], capture_output=True, text=True)

    def lift(self, pattern):
        m = re.search(pattern, self.JS, re.S)
        self.assertTrue(m, f"{pattern!r} not found in the reader — did it move?")
        return m.group(0)

    def helpers(self):
        return "\n".join([
            self.lift(r"const hms = t => \{.+?\};"),
            self.lift(r"const REEL_V = .+?;"),
            self.lift(r"const REEL_VS = .+?;"),
            self.lift(r"const r1 = .+?;"),
            self.lift(r"const clipLen = .+?;"),
            self.lift(r"const reelRuntime = .+?;"),
            self.lift(r"const encodeClips = .+?;"),
            self.lift(r"const encodeClipsX = .+?;"),
            self.lift(r"function shareURL\(pid, clips\) \{.+?\n  \}"),
            self.lift(r"function reelShareURL\(clips\) \{.+?\n  \}"),
            self.lift(r"const reelPids = .+?;"),
            self.lift(r"function decodeReel\(search\) \{.+?\n  \}"),
            self.lift(r"function citeSheet\(meta, clips\) \{.+?\n  \}"),
            self.lift(r"function reelJSON\(meta, clips\) \{.+?\n  \}"),
        ])

    def test_share_link_round_trips(self):
        """encode → decode is the identity on a reel's clips, and a link that
        lost a character in an email degrades to fewer clips, never a throw."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "const clips = [{start:900.2,end:907.3},{start:1147.6,end:1151.2},{start:12.0,end:24.0}];",
            "const url = shareURL('2Yhg', clips);",
            "const back = decodeReel(url.slice(url.indexOf('?')));",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "if (back.v !== '1') fail('v='+back.v);",
            "if (back.pid !== '2Yhg') fail('pid='+back.pid);",
            "if (back.clips.length !== 3) fail('len='+back.clips.length);",
            "for (let i=0;i<3;i++){ if (back.clips[i].start!==clips[i].start || back.clips[i].end!==clips[i].end)",
            "  fail('clip'+i+' '+JSON.stringify(back.clips[i])); }",
            # 'garbage' has no pair; '5-3' has end<=start — both dropped, 2 remain
            "const bad = decodeReel('?v=1&m=x&c=1-2,garbage,5-3,7-9');",
            "if (bad.clips.length !== 2) fail('bad drop '+JSON.stringify(bad.clips));",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"reel round-trip failed:\n{r.stdout}{r.stderr}")

    def test_cite_sheet_carries_every_clip_with_a_deep_link(self):
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "const meta = {pid:'2Yhg', title:'Select Board — March', town:'Brookline', "
            "body:'Select Board', date:'2026-03-10'};",
            "const clips = [{start:900.2,end:907.3,kind:'vote',quote:'the override passes',speaker:'Chair:'},"
            "{start:12.0,end:24.0,kind:'question',quote:'how much is the levy'}];",
            "const s = citeSheet(meta, clips);",
            "function fail(m){ console.log('FAIL', m, '\\n', s); process.exit(1); }",
            "for (const n of ['Select Board — March','a reel of 2 moments','the override passes',"
            "'how much is the levy','https://publicrecord.studio/app/m/2Yhg#t900','#t12',"
            "'Select Board · Brookline · 2026-03-10','— Chair'])",
            "  if (!s.includes(n)) fail('missing '+JSON.stringify(n));",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"cite sheet malformed:\n{r.stdout}{r.stderr}")

    def test_reel_json_maps_onto_the_desk_renderer(self):
        """The reel.json's clips carry the {start,end} highlighter/reel.py's
        render_reel needs, in reel order, plus the media locator and the plain
        hand-off sentence. The one desk-bound step, made openable."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "const meta = {pid:'2Yhg', title:'Select Board — March', town:'Brookline', "
            "body:'Select Board', date:'2026-03-10', video_id:'2YhgO14jXys', "
            "url:'https://youtube.com/watch?v=2YhgO14jXys'};",
            "const clips = [{start:900.2,end:907.3,kind:'vote',quote:'passes',t:900.2},"
            "{start:12.0,end:24.0,kind:'question',quote:'how much',t:12.0}];",
            "const j = reelJSON(meta, clips);",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "if (j.schema !== 'publicrecord.reel/1') fail('schema '+j.schema);",
            "if (j.clips.length !== 2) fail('clips '+j.clips.length);",
            "if (j.clips[0].start !== 900.2 || j.clips[0].end !== 907.3) fail('clip0 '+JSON.stringify(j.clips[0]));",
            "if (j.clips[1].start !== 12 || j.clips[1].end !== 24) fail('clip1 '+JSON.stringify(j.clips[1]));",
            "if (j.meeting.video_id !== '2YhgO14jXys') fail('video_id '+j.meeting.video_id);",
            "if (typeof j.runtime !== 'number' || j.runtime <= 0) fail('runtime '+j.runtime);",
            "if (!/desk/i.test(j.note)) fail('note lacks the desk hand-off');",
            "if (!j.share.includes('/app/r?v=1&m=2Yhg')) fail('share '+j.share);",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"reel.json malformed:\n{r.stdout}{r.stderr}")

    def test_the_viewer_advances_clip_to_clip_even_out_of_order(self):
        """The acceptance's hard half, executed: the reel plays clip to clip
        (specs/20 §7). Clips play in reel order, not chronological, so the next
        clip can be *earlier* in the tape. A short clip reached by a backward
        seek is the trap: while the seek buffers, the facade repeats the old
        (past-the-clip) time, and TWO such stale reports must not arm-then-skip
        the clip. The `armed` gate — which arms only on a report inside the clip
        and before its end — is what proves the short clip actually plays."""
        adv = self.lift(r"  function reelAdvance\(t\) \{.+?\n  \}")
        rseek = self.lift(r"  function reelSeek\(c\) \{.+?\n  \}")
        body = "\n".join([
            "const seeks = [];",
            "const YT = {};",   # no player window → reelSeek falls to ytSeek
            "function ytSeek(t){ seeks.push(t); }",
            "function ytSend(){}",
            "function reelShow(){}",
            "const reelPids = clips => [...new Set(clips.map(c => c.pid).filter(Boolean))];",
            rseek,
            "function fail(m){ console.log('FAIL', m, 'seeks='+JSON.stringify(seeks),"
            " 'i='+REELPLAY.i, 'armed='+REELPLAY.armed, 'active='+REELPLAY.active); process.exit(1); }",
            # clip 1 is a 1s clip {19,20} placed AFTER {10,20}: reaching it is a
            # backward seek of 1s, so the two stale 20s sit inside the arm window.
            # all one meeting (video X) → reelSeek is a plain same-tape ytSeek.
            "let REELPLAY = { active:true, armed:false, i:0, vid:'X', clips:"
            "[{start:10,end:20,video_id:'X'},{start:19,end:20,video_id:'X'},{start:30,end:35,video_id:'X'}] };",
            adv,
            # play clip0 to its end, then TWO stale 20s while the seek to 19 buffers
            "[10,11,19,20, 20,20].forEach(t => reelAdvance(t));",
            # the fix holds here: still on clip1, NOT armed by a stale time, not skipped
            "if (REELPLAY.i !== 1) fail('a stale time skipped the short clip');",
            "if (REELPLAY.armed !== false) fail('a stale time armed the short clip');",
            "if (JSON.stringify(seeks) !== JSON.stringify([19])) fail('advanced too far on stale time');",
            # now the real clip1 times arrive and it plays through to clip2, then stops
            "[19,19.5,20, 20, 30,31,35].forEach(t => reelAdvance(t));",
            "if (JSON.stringify(seeks) !== JSON.stringify([19,30])) fail('wrong seeks');",
            "if (REELPLAY.active !== false) fail('did not stop after the last clip');",
            "if (REELPLAY.i !== 2) fail('final clip index');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"the seek engine misfired:\n{r.stdout}{r.stderr}")

    def test_a_cross_meeting_reel_carries_each_clips_own_meeting(self):
        """specs/20 §7.9 P2-B. A reel of one meeting stays the v1 link every
        existing share + kit page already carries; the moment it spans two, it
        becomes v2 (`<pid>:<start>-<end>`), and decode restores each clip's own
        meeting. v1 remains readable — its clips inherit the single `m=`."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            # one meeting → v1, byte-identical to before
            "const one = [{pid:'AAA',start:10,end:20},{pid:'AAA',start:30,end:40}];",
            "const u1 = reelShareURL(one);",
            "if (!u1.includes('/app/r?v=1&m=AAA&c=10-20,30-40')) fail('single-meeting not v1: '+u1);",
            # two meetings → v2, each clip prefixed with its meeting
            "const two = [{pid:'AAA',start:10,end:20},{pid:'B-b_9',start:5,end:9}];",
            "const u2 = reelShareURL(two);",
            "if (!u2.includes('/app/r?v=2&c=')) fail('cross-meeting not v2: '+u2);",
            "const d = decodeReel(u2.slice(u2.indexOf('?')));",
            "if (d.v !== '2') fail('v='+d.v);",
            "if (d.clips.length !== 2) fail('len='+d.clips.length);",
            "if (d.clips[0].pid !== 'AAA' || d.clips[1].pid !== 'B-b_9') fail('pids '+JSON.stringify(d.clips));",
            "if (d.clips[1].start !== 5 || d.clips[1].end !== 9) fail('range '+JSON.stringify(d.clips[1]));",
            # a v1 link still decodes, its clips inheriting the single m=
            "const v1 = decodeReel('?v=1&m=Z9&c=1-2,3-4');",
            "if (v1.clips.length !== 2 || v1.clips[0].pid !== 'Z9' || v1.clips[1].pid !== 'Z9') fail('v1 inherit '+JSON.stringify(v1.clips));",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"cross-meeting link failed:\n{r.stdout}{r.stderr}")

    def test_reel_seek_switches_the_tape_only_across_meetings(self):
        """The viewer plays clip to clip within one tape, and loads a new tape
        (loadVideoById) only when the next clip is from another meeting — so a
        cross-meeting reel actually crosses, and a same-meeting reel never
        needlessly reloads the player."""
        rseek = self.lift(r"  function reelSeek\(c\) \{.+?\n  \}")
        body = "\n".join([
            "const sent = []; const seeks = [];",
            "const YT = { win: {}, ready: true };",
            "function ytSend(kind, func, args){ sent.push([func, args]); }",
            "function ytSeek(t){ seeks.push(t); }",
            "let REELPLAY = { vid: 'AAA' };",
            rseek,
            "function fail(m){ console.log('FAIL', m, JSON.stringify({sent,seeks})); process.exit(1); }",
            # same meeting → a plain seek, no tape reload
            "reelSeek({video_id:'AAA', start:42});",
            "if (seeks.length !== 1 || seeks[0] !== 42) fail('same-tape should seek');",
            "if (sent.length !== 0) fail('same-tape must not reload');",
            # another meeting → loadVideoById at the clip start, vid updated
            "reelSeek({video_id:'BBB', start:7});",
            "if (sent.length !== 1 || sent[0][0] !== 'loadVideoById') fail('cross should loadVideoById');",
            "if (sent[0][1][0].videoId !== 'BBB' || sent[0][1][0].startSeconds !== 7) fail('bad load args '+JSON.stringify(sent[0]));",
            "if (REELPLAY.vid !== 'BBB') fail('vid not updated');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"reel tape-switch failed:\n{r.stdout}{r.stderr}")

    def test_a_tape_less_clip_is_skipped_never_played_on_the_wrong_tape(self):
        """A cross-meeting reel can include a clip whose meeting has no video
        (audio-only civic tape). It must NOT play on the previous meeting's tape
        under a label naming another — reelAdvance skips it to the next clip that
        has a tape, and reelSeek never falls back to the loaded video."""
        adv = self.lift(r"  function reelAdvance\(t\) \{.+?\n  \}")
        rseek = self.lift(r"  function reelSeek\(c\) \{.+?\n  \}")
        body = "\n".join([
            "const sent = []; const seeks = [];",
            "const YT = { win:{}, ready:true };",
            "function ytSend(kind, func, args){ sent.push([func, args]); }",
            "function ytSeek(t){ seeks.push(t); }",
            "function reelShow(){}",
            # clip1 has NO video_id (cite-only); clip2 is meeting Y
            "let REELPLAY = { active:true, armed:false, i:0, vid:'X', clips:"
            "[{start:10,end:20,video_id:'X'},{start:30,end:40},{start:5,end:9,video_id:'Y'}] };",
            rseek, adv,
            "function fail(m){ console.log('FAIL', m, JSON.stringify({i:REELPLAY.i,sent,seeks})); process.exit(1); }",
            # play clip0 to its end → advance must SKIP the tape-less clip1 → clip2
            "[10,15,20].forEach(t => reelAdvance(t));",
            "if (REELPLAY.i !== 2) fail('did not skip the tape-less clip');",
            "if (!sent.some(s => s[0]==='loadVideoById' && s[1][0].videoId==='Y')) fail('did not switch to the playable clip');",
            # reelSeek on a tape-less clip is a no-op — no seek onto the wrong tape
            "seeks.length = 0; sent.length = 0;",
            "reelSeek({start:30,end:40});",
            "if (seeks.length || sent.length) fail('a tape-less clip seeked the wrong tape');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"tape-less clip handling failed:\n{r.stdout}{r.stderr}")

    def test_a_clip_is_identified_by_kind_and_time_not_time_alone(self):
        """A contested roll call is emitted as two moments — a vote and a
        tension — anchored to the same segment start (web/bake.py dedups on
        `(kind, int(t))`, not time). The composer must tell them apart, or
        ticking one silently toggles the other. Its identity key must match the
        bake's, plus the meeting (P2-B): (meeting, kind, time)."""
        body = "\n".join([
            self.lift(r"const r1 = .+?;"),
            "const CREEL = { pid: 'M' };",   # a moment read off the page stands for this meeting
            self.lift(r"  const clipId = c => .+?;"),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const vote = {kind:'vote', t:100.0}, tension = {kind:'tension', t:100.0};",
            "if (clipId(vote) === clipId(tension)) fail('same-second twins collide');",
            # the same moment ticked twice is the same identity (toggle off works)
            "if (clipId(vote) !== clipId({kind:'vote', t:100.04})) fail('rounding split one moment in two');",
            # the same kind+second from two meetings is NOT the same clip (P2-B)
            "if (clipId({pid:'A',kind:'vote',t:100}) === clipId({pid:'B',kind:'vote',t:100})) fail('two meetings collided');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"clip identity is wrong:\n{r.stdout}{r.stderr}")


class TestPaper(unittest.TestCase):
    """specs/21 P1: the curated paper's client machinery, executed in node.
    A paper's link and its paper.json are covenants with whoever receives
    them — the codec must round-trip exactly, and a link that lost a
    character in an email must degrade to fewer blocks, never a throw
    (decodeReel's law, inherited by every decoder)."""

    JS = (REPO / "web" / "static" / "app.js").read_text()
    PRELUDE = "\n".join([
        'const BASE = "/app";',
        'const location = { origin: "https://publicrecord.studio" };',
    ])

    def node(self, body):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        return subprocess.run([node, "-e", body], capture_output=True, text=True)

    def lift(self, pattern):
        m = re.search(pattern, self.JS, re.S)
        self.assertTrue(m, f"{pattern!r} not found in the reader — did it move?")
        return m.group(0)

    def helpers(self):
        return "\n".join([
            self.lift(r"const hms = t => \{.+?\};"),
            self.lift(r"const REEL_V = .+?;"),
            self.lift(r"const REEL_VS = .+?;"),
            self.lift(r"const r1 = .+?;"),
            self.lift(r"const clipLen = .+?;"),
            self.lift(r"const reelRuntime = .+?;"),
            self.lift(r"const encodeClips = .+?;"),
            self.lift(r"const encodeClipsX = .+?;"),
            self.lift(r"function shareURL\(pid, clips\) \{.+?\n  \}"),
            self.lift(r"function reelShareURL\(clips\) \{.+?\n  \}"),
            self.lift(r"const reelPids = .+?;"),
            self.lift(r"const PAPER_V = .+?;"),
            self.lift(r"const PAPER_VS = .+?;"),
            self.lift(r"const PAPER_TITLE_MAX = .+?;"),
            self.lift(r"const PAPER_MAX_BLOCKS = .+?;"),
            self.lift(r"const PAPER_MAX_CLIPS = .+?;"),
            self.lift(r"const PAPER_REF = .+?;"),
            self.lift(r"const PAPER_NOTE_MAX = .+?;"),
            self.lift(r"const PAPER_CHARTS = .+?;"),
            self.lift(r"const paperV = .+?;"),
            self.lift(r"const cut = .+?;"),
            self.lift(r"const noteText = .+?;"),
            self.lift(r"function chartRecordURL\(b\) \{.+?\n  \}"),
            self.lift(r"function normalizePaper\(p\) \{.+?\n  \}"),
            self.lift(r"function normalizeBlock\(b\) \{.+?\n  \}"),
            self.lift(r"function portablePaper\(p\) \{.+?\n  \}"),
            self.lift(r"function encodePaperQS\(p\) \{.+?\n  \}"),
            self.lift(r"function paperShareURL\(p\) \{.+?\n  \}"),
            self.lift(r"function decodePaper\(search\) \{.+?\n  \}"),
            self.lift(r"function paperJSON\(p\) \{.+?\n  \}"),
        ])

    DRAFT = ('{ title: "Overrides, watched", blocks: ['
             '{kind:"story",story:"meeting",pid:"vid1",title:"Select Board",'
             'date:"2026-03-10",town:"Testville"},'
             '{kind:"story",story:"issue",slug:"budget-override",'
             'name:"budget override",n_meetings:2},'
             '{kind:"reel",clips:[{pid:"vid1",start:900.2,end:907.3,'
             'kind:"vote",quote:"the override passes"},'
             '{pid:"vid2",start:12,end:24}]}]}')

    def test_the_link_round_trips_the_whole_paper(self):
        """portable(decode(encode(p))) === portable(p): the link carries the
        paper exactly — title and all three block kinds — and carries no
        ride-along meta (a paper may not assert what the record's planes
        would not)."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            f"const draft = {self.DRAFT};",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const url = paperShareURL(draft);",
            "if (url.indexOf('https://publicrecord.studio/app/p?') !== 0) fail('url '+url);",
            "if (url.includes('+') || url.includes(' ')) fail('unsafe chars in '+url);",
            "if (url.includes('Select')) fail('ride-along meta leaked into the link');",
            "const back = decodePaper(url.slice(url.indexOf('?')));",
            "if (back.v !== '1') fail('v='+back.v);",
            "if (back.id !== '') fail('id='+back.id);",
            "if (back.title !== 'Overrides, watched') fail('title='+back.title);",
            "const a = JSON.stringify(portablePaper(draft));",
            "const b = JSON.stringify(portablePaper({title: back.title, blocks: back.blocks}));",
            "if (a !== b) fail('round-trip drifted:\\n'+a+'\\n'+b);",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"paper round-trip failed:\n{r.stdout}{r.stderr}")

    def test_a_mangled_link_degrades_and_never_throws(self):
        """Hostile queries → fewer blocks, never an exception. The exact table
        a forwarding email client would write."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const CASES = [",
            "  ['?v=1&b=,,,,', 0],",
            "  ['?v=1&b=m.', 0],",
            "  ['?v=1&b=x.abc', 0],",
            "  ['?v=1&b=m.has%20space', 0],",
            "  ['?v=1&b=m.%E0%A4%A', 0],",          # bad URI escape → dropped
            "  ['?v=1&b=r.', 0],",
            "  ['?v=1&b=r.vid1:5-3', 0],",           # end <= start
            "  ['?v=1&b=r.vid1:9-x', 0],",
            "  ['?v=1&b=r.vid1:-2-4', 0],",          # negative start
            "  ['?v=1&b=m.vid1,garbage,i.slug-ok,r.vid1:1-2~junk', 3],",
            "  ['', 0],",
            "  [null, 0],",
            "];",
            "for (const [q, want] of CASES) {",
            "  let got;",
            "  try { got = decodePaper(q).blocks.length; }",
            "  catch (e) { fail('THREW on '+JSON.stringify(q)+': '+e); }",
            "  if (got !== want) fail(JSON.stringify(q)+' -> '+got+' blocks, want '+want);",
            "}",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"decodePaper is fragile:\n{r.stdout}{r.stderr}")

    def test_normalize_is_total_and_caps_hold(self):
        """Whatever localStorage or a stored paper hands over leaves as a
        valid paper: junk drops, the title truncates at its cap, block and
        clip counts clamp."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "for (const junk of [null, 7, 'hi', [], {title: 9},",
            "     {blocks: 'no'}, {title: null, blocks: [null, 3, {}, {kind:'x'}]}]) {",
            "  const p = normalizePaper(junk);",
            "  if (p.title !== '' || p.blocks.length !== 0)",
            "    fail('junk survived: '+JSON.stringify(junk)+' -> '+JSON.stringify(p));",
            "}",
            "const long = normalizePaper({title: 'x'.repeat(999), blocks: []});",
            "if (long.title.length !== PAPER_TITLE_MAX) fail('title cap '+long.title.length);",
            "const many = normalizePaper({blocks: Array.from({length: 99},",
            "  (_, i) => ({kind:'story',story:'meeting',pid:'m'+i}))});",
            "if (many.blocks.length !== PAPER_MAX_BLOCKS) fail('block cap '+many.blocks.length);",
            "const fat = normalizeBlock({kind:'reel', clips: Array.from({length: 999},",
            "  (_, i) => ({pid:'vid1', start:i, end:i+1}))});",
            "if (fat.clips.length !== PAPER_MAX_CLIPS) fail('clip cap '+fat.clips.length);",
            "const meta = normalizeBlock({kind:'story',story:'meeting',pid:'vid1',",
            "  title:'kept', evil:'<script>'});",
            "if (meta.title !== 'kept') fail('ride-along meta lost');",
            "if ('evil' in meta) fail('unknown keys must not survive normalize');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"normalizePaper is leaky:\n{r.stdout}{r.stderr}")

    def test_a_store_address_decodes_as_an_id_and_nothing_else(self):
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const good = decodePaper('?p=0123456789abcdef');",
            "if (good.id !== '0123456789abcdef') fail('id lost: '+good.id);",
            "if (good.blocks.length) fail('an id link carries no blocks');",
            "for (const bad of ['?p=xyz', '?p=0123456789ABCDEF', '?p=0123',",
            "     '?p=0123456789abcdef0']) {",
            "  if (decodePaper(bad).id !== '') fail('accepted '+bad);",
            "}",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"store-id decode wrong:\n{r.stdout}{r.stderr}")

    def test_real_length_refs_survive_the_link(self):
        """The bake mints pids to 80 chars and issue slugs to 96 — the link
        codec must carry what the record actually names (the 64-char cap a
        review lens caught would have dropped real adds with a success
        toast)."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const pid80 = 'p'.repeat(80), slug96 = 's'.repeat(96);",
            "const draft = { title: '', blocks: [",
            "  {kind:'story',story:'meeting',pid:pid80},",
            "  {kind:'story',story:'issue',slug:slug96},",
            "  {kind:'reel',clips:[{pid:pid80,start:1,end:2}]}]};",
            "const port = portablePaper(draft);",
            "if (port.blocks.length !== 3) fail('normalize dropped a real ref: '+JSON.stringify(port.blocks));",
            "const url = paperShareURL(draft);",
            "const back = decodePaper(url.slice(url.indexOf('?')));",
            "if (JSON.stringify(portablePaper({title:'',blocks:back.blocks})) !== JSON.stringify(port))",
            "  fail('long refs did not round-trip');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"long refs dropped:\n{r.stdout}{r.stderr}")

    def test_paper_json_is_the_receipt_the_desk_can_trust(self):
        """schema pinned, the share link included, every story with its record
        URL, every reel with its play link (v1 for one meeting — byte-shaped
        like every reel link already in the wild)."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            f"const draft = {self.DRAFT};",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const j = paperJSON(draft);",
            "if (j.schema !== 'publicrecord.paper/1') fail('schema '+j.schema);",
            "if (j.share !== paperShareURL(draft)) fail('share drifted');",
            "if (j.blocks.length !== 3) fail('blocks '+j.blocks.length);",
            "if (j.blocks[0].url !== 'https://publicrecord.studio/app/m/vid1') fail('story url '+j.blocks[0].url);",
            "if (j.blocks[1].url !== 'https://publicrecord.studio/app/i/budget-override') fail('issue url');",
            "const play = j.blocks[2].play;",
            "if (!play.includes('/app/r?v=2&c=vid1')) fail('cross-meeting reel must be v2: '+play);",
            "const one = paperJSON({title:'', blocks:[{kind:'reel',",
            "  clips:[{pid:'vid1',start:1,end:2},{pid:'vid1',start:5,end:9}]}]});",
            "if (!one.blocks[0].play.includes('/app/r?v=1&m=vid1')) fail('one-meeting reel must stay v1: '+one.blocks[0].play);",
            "if (one.blocks[0].runtime !== 5) fail('runtime '+one.blocks[0].runtime);",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"paperJSON malformed:\n{r.stdout}{r.stderr}")

    P2_DRAFT = ('{ title: "P2, watched", blocks: ['
                '{kind:"chart",chart:"votes"},'
                '{kind:"chart",chart:"framing"},'
                '{kind:"chart",chart:"framing",pid:"vid1",title:"Select Board"},'
                '{kind:"chart",chart:"reach",slug:"budget-override",name:"budget override"},'
                '{kind:"chart",chart:"topics"},'
                '{kind:"note",text:"Watch the tally, not the speeches. '
                '100% real — plus+comma, dots. ¿unicode?\\nSecond line."}]}')

    def test_p2_blocks_round_trip_the_link(self):
        """Charts and notes travel in the link like every other block — the
        note twice-encoded so its own commas and percents survive
        URLSearchParams's early decode, and no ride-along label leaks."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            f"const draft = {self.P2_DRAFT};",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const url = paperShareURL(draft);",
            "if (url.includes('Select') || url.includes('budget%20override'))",
            "  fail('ride-along meta leaked into the link: '+url);",
            "const back = decodePaper(url.slice(url.indexOf('?')));",
            "if (back.blocks.length !== 6) fail('blocks '+back.blocks.length);",
            "const a = JSON.stringify(portablePaper(draft));",
            "const b = JSON.stringify(portablePaper({title: back.title, blocks: back.blocks}));",
            "if (a !== b) fail('round-trip drifted:\\n'+a+'\\n'+b);",
            "const note = back.blocks[5];",
            "if (note.kind !== 'note') fail('note lost');",
            "if (!note.text.includes('plus+comma,')) fail('note text mangled: '+note.text);",
            "if (!note.text.includes('100%')) fail('percent mangled: '+note.text);",
            "if (!note.text.includes('¿unicode?')) fail('unicode mangled');",
            "if (!note.text.includes('\\nSecond line')) fail('newline lost');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"P2 round-trip failed:\n{r.stdout}{r.stderr}")

    def test_mangled_p2_links_degrade_and_never_throw(self):
        """decodeReel's law, extended to charts and notes: a lost character
        reads as fewer blocks, never a crash — and a chart shape the record
        never writes (a bare reach, a reffed votes) is a mangle, dropped."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const CASES = [",
            "  ['?v=1&b=n.', 0],",
            "  ['?v=1&b=n.%2520', 0],",           # a lone space — trims away
            "  ['?v=1&b=n.%E0%A4%A', 0],",        # bad escape at the 2nd decode
            "  ['?v=1&b=c.', 0],",
            "  ['?v=1&b=c.sparkline', 0],",
            "  ['?v=1&b=c.reach', 0],",           # reach needs its issue
            "  ['?v=1&b=c.votes.vid1', 0],",      # votes carries no ref
            "  ['?v=1&b=c.topics.vid1', 0],",
            "  ['?v=1&b=c.framing.', 0],",        # an empty ref is a mangle
            "  ['?v=1&b=c.framing.has%2520space', 0],",
            "  ['?v=1&b=c.votes,n.hi,garbage', 2],",
            "];",
            "for (const [q, want] of CASES) {",
            "  let got;",
            "  try { got = decodePaper(q).blocks.length; }",
            "  catch (e) { fail('THREW on '+JSON.stringify(q)+': '+e); }",
            "  if (got !== want) fail(JSON.stringify(q)+' -> '+got+' blocks, want '+want);",
            "}",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"P2 decodePaper is fragile:\n{r.stdout}{r.stderr}")

    def test_note_normalize_is_total_and_the_empty_note_is_draft_only(self):
        """The client cleans (total); the store refuses (strict) — and the
        one place an empty note may live is the draft being typed into:
        portablePaper and paperJSON carry none."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const long = normalizeBlock({kind:'note', text: 'a'.repeat(9999)});",
            "if (long.text.length !== PAPER_NOTE_MAX) fail('cap '+long.text.length);",
            "const ctl = normalizeBlock({kind:'note', text: 'a\\u0000b\\rc\\td'});",
            "if (ctl.text !== 'ab\\ncd') fail('control clean: '+JSON.stringify(ctl.text));",
            "if (normalizeBlock({kind:'note', text: 7}) !== null) fail('non-string note');",
            "const empty = normalizeBlock({kind:'note', text: ''});",
            "if (!empty || empty.text !== '') fail('the draft must keep an empty note');",
            "const p = {title:'', blocks:[{kind:'note',text:'  '},{kind:'note',text:'kept'}]};",
            "if (portablePaper(p).blocks.length !== 1) fail('portable must drop empty notes');",
            "if (paperJSON(p).blocks.length !== 1) fail('paperJSON must drop empty notes');",
            "if (normalizeBlock({kind:'chart', chart:'sparkline'}) !== null) fail('junk chart');",
            "if (normalizeBlock({kind:'chart', chart:'reach'}) !== null) fail('bare reach');",
            "if (normalizeBlock({kind:'chart', chart:'framing', pid:'has space'}) !== null) fail('bad pid');",
            "const stray = normalizeBlock({kind:'chart', chart:'votes', slug:'x'});",
            "if (JSON.stringify(stray) !== '{\"kind\":\"chart\",\"chart\":\"votes\"}')",
            "  fail('stray ref survived: '+JSON.stringify(stray));",
            "const keep = normalizeBlock({kind:'chart', chart:'reach', slug:'ok', name:'N', junk:1});",
            "if (keep.junk !== undefined || keep.name !== 'N') fail('ride-along wrong');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"P2 normalize leaky:\n{r.stdout}{r.stderr}")

    def test_p2_papers_travel_as_v2_and_p1_papers_stay_byte_stable(self):
        """A paper carrying kinds the shipped v1 reader cannot represent
        (notes, charts) must not travel under v=1 — the old reader would
        silently render a mutilated paper instead of its honest
        newer-version message (a review catch). And a stories+reels paper
        must keep encoding EXACTLY as P1 did, byte for byte — every P1 link
        and address in the wild depends on it."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            f"const p1 = {self.DRAFT};",
            f"const p2 = {self.P2_DRAFT};",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const q1 = encodePaperQS(p1);",
            "if (!q1.startsWith('v=1&')) fail('P1 paper drifted off v=1: '+q1.slice(0,20));",
            "const expect = 'v=1&t=Overrides%2C%20watched'",
            "  + '&b=m.vid1,i.budget-override,r.vid1:900.2-907.3~vid2:12-24';",
            "if (q1 !== expect) fail('P1 bytes drifted:\\n'+q1+'\\n'+expect);",
            "const q2 = encodePaperQS(p2);",
            "if (!q2.startsWith('v=2&')) fail('P2 paper must travel as v=2: '+q2.slice(0,20));",
            "if (!PAPER_VS.includes('2')) fail('the new reader must accept v=2');",
            "const back = decodePaper('?' + q2);",
            "if (back.v !== '2' || back.blocks.length !== 6) fail('v=2 decode broke');",
            "// an empty-note-only draft has nothing traveling — it stays v=1",
            "if (paperV(portablePaper({title:'', blocks:[{kind:'note',text:'  '}]})) !== '1')",
            "  fail('an empty note must not force v=2');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"version gate broken:\n{r.stdout}{r.stderr}")

    def test_chart_votes_never_draws_an_outcome_the_record_does_not_hold(self):
        """The record mints more than passes/fails (tabled, tied; desk
        imports carry their own words). A binarized chart drew a tabled
        motion as a FAILED one (a review catch): now passes = filled dot,
        fails = hollow dot, anything else = the half-tone square, with the
        exact word in the tooltip and the legend naming the third class only
        when it appears."""
        extra = "\n".join([
            'const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,',
            '  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", \'"\': "&quot;" }[c]));',
            self.lift(r"function chartShell\(kicker, sub, body, twin, src\) \{.+?\n  \}"),
            self.lift(r"const chartUnfetched = .+?;"),
            self.lift(r"const chartDay = .+?;"),
            self.lift(r"function chartVotes\(plane\) \{.+?\n  \}"),
        ])
        body = "\n".join([
            self.PRELUDE, self.helpers(), extra,
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const mixed = chartVotes({ n_meetings: 1, votes: [",
            "  {pid:'vid1', date:'2026-03-10', t:10, motion:'a', outcome:'passes', tally:'3–0'},",
            "  {pid:'vid1', date:'2026-03-10', t:20, motion:'b', outcome:'fails', tally:'0–3'},",
            "  {pid:'vid1', date:'2026-03-10', t:30, motion:'c', outcome:'tabled', tally:''},",
            "]});",
            "if ((mixed.match(/<circle/g) || []).length !== 2) fail('two circles expected');",
            "if (!/fill=\"#ffffff\" stroke=\"#052e16\"/.test(mixed)) fail('fails must stay hollow');",
            "if (!/<rect[^>]*fill-opacity=\"\\.5\"/.test(mixed)) fail('tabled must be the half-tone square');",
            "if (!mixed.includes('other outcomes')) fail('legend must name the third class');",
            "if (!mixed.includes('tabled')) fail('the exact word must ride the twin/tooltip');",
            "if (!mixed.includes('role=\"group\"')) fail('role=img would hide every receipt from AT');",
            "if (!mixed.includes('pb-twinwrap')) fail('the twin needs its scroll container');",
            "const plain = chartVotes({ n_meetings: 1, votes: [",
            "  {pid:'vid1', date:'2026-03-10', t:10, motion:'a', outcome:'passes', tally:'3–0'},",
            "]});",
            "if (plain.includes('other outcomes')) fail('no third class → no third legend entry');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"chartVotes outcomes broken:\n{r.stdout}{r.stderr}")

    def test_a_cap_cut_never_strands_half_an_emoji(self):
        """PAPER_NOTE_MAX and PAPER_TITLE_MAX count UTF-16 units; a bare
        slice at the cap can split a surrogate pair, and encodeURIComponent
        THROWS on the stranded half — a copy-link click would die on a
        paper whose emoji landed on the boundary. cut() gives the pair up
        instead (decodeReel's law: never a throw)."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const noted = { title: '', blocks: [",
            "  {kind:'note', text: 'x'.repeat(PAPER_NOTE_MAX - 1) + '\\u{1F600}'}]};",
            "const titled = { title: 'y'.repeat(PAPER_TITLE_MAX - 1) + '\\u{1F600}',",
            "  blocks: [] };",
            "let url;",
            "try { url = paperShareURL(noted); }",
            "catch (e) { fail('note at the cap THREW: ' + e); }",
            "try { url = paperShareURL(titled); }",
            "catch (e) { fail('title at the cap THREW: ' + e); }",
            "const back = decodePaper('?v=1&t=' + 'z'.repeat(300));",
            "if (back.title.length !== PAPER_TITLE_MAX) fail('title cap ' + back.title.length);",
            "const n = normalizeBlock({kind:'note', text: 'x'.repeat(PAPER_NOTE_MAX - 1) + '\\u{1F600}'});",
            "if (n.text.length !== PAPER_NOTE_MAX - 1) fail('the pair must be given up whole: ' + n.text.length);",
            "// a hand-edited draft can hold a lone surrogate ANYWHERE (JSON",
            "// round-trips it) — the encoders must survive that too",
            "for (const dirty of ['a\\uDC00b', 'a\\uD800b', '\\uDC00', 'ok \\uD800'])",
            "  try {",
            "    const u = paperShareURL({ title: dirty, blocks: [{kind:'note', text: dirty}] });",
            "    if (/%ED/i.test(u)) fail('a lone half leaked into the link: '+u);",
            "  } catch (e) { fail('interior lone surrogate THREW: '+e); }",
            "if (cut('a\\uDC00b\\uD800c', 99) !== 'abc') fail('lone halves must drop: '+JSON.stringify(cut('a\\uDC00b\\uD800c', 99)));",
            "if (cut('a\\u{1F600}b', 99) !== 'a\\u{1F600}b') fail('a whole pair must survive cut');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"surrogate cut broken:\n{r.stdout}{r.stderr}")

    def test_paper_json_charts_carry_their_record_urls(self):
        """Provenance for a chart is the page a reader can recount it on —
        every chart block in the receipt names its record page."""
        body = "\n".join([
            self.PRELUDE, self.helpers(),
            f"const draft = {self.P2_DRAFT};",
            "function fail(m){ console.log('FAIL', m); process.exit(1); }",
            "const j = paperJSON(draft);",
            "const urls = j.blocks.filter(b => b.kind === 'chart').map(b => b.url);",
            "const want = ['https://publicrecord.studio/app/officials',",
            "  'https://publicrecord.studio/app/analytics',",
            "  'https://publicrecord.studio/app/m/vid1',",
            "  'https://publicrecord.studio/app/i/budget-override',",
            "  'https://publicrecord.studio/app/analytics'];",
            "if (JSON.stringify(urls) !== JSON.stringify(want))",
            "  fail('chart urls drifted: '+JSON.stringify(urls));",
            "const note = j.blocks[5];",
            "if (note.kind !== 'note' || !note.text.includes('tally')) fail('note lost from receipt');",
            "if ('url' in note) fail('a note has no record URL — it is the editor’s words');",
            "console.log('ok');",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"paperJSON P2 malformed:\n{r.stdout}{r.stderr}")

    def test_the_caps_and_kinds_match_the_store(self):
        """One cap, one enum, two languages — the reader's constants must
        equal the store's or a paper the panel accepts gets a 422 at share."""
        from record.papers import CHARTS, NOTE_MAX
        m = re.search(r"const PAPER_NOTE_MAX = (\d+);", self.JS)
        self.assertTrue(m and int(m.group(1)) == NOTE_MAX,
                        "PAPER_NOTE_MAX drifted from record.papers.NOTE_MAX")
        m = re.search(r"const PAPER_CHARTS = \[(.+?)\];", self.JS)
        self.assertEqual(tuple(re.findall(r'"(\w+)"', m.group(1))), CHARTS,
                         "PAPER_CHARTS drifted from record.papers.CHARTS")

    def test_the_paper_make_path_touches_no_api(self):
        """The covenant, extended to P1 (specs/21 §5): composing, arranging,
        encoding and exporting a paper read localStorage, strings and the
        record's own static planes — never the API. The store appears only
        past the PART 2 marker, behind the explicit share actions."""
        block = self.JS[self.JS.index("YOUR PAPER — the curated document"):
                        self.JS.index("PART 2: SHARING")]
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "/api/",
                          "askStudio", "API_TIMEOUT", "document.cookie",
                          "new Image("):
            self.assertNotIn(forbidden, block,
                             f"the paper's make path reached for {forbidden!r} "
                             f"— composing must not touch a server (specs/21 §5)")
        # and the draft is localStorage, the same private preference the mode is
        self.assertIn("localStorage.setItem(PAPER_KEY", block)

    def test_the_paper_markers_are_present(self):
        """The drift guard, extended: the pieces the stylesheet, the stub and
        the studio panel lean on keep their names."""
        for token in ("function paper(", 'const PAPER_KEY = "cz-paper"',
                      "function refreshPaperSummary(",
                      "function paperShortLink(", "function decodePaper(",
                      'test(path)) paper()'):
            self.assertIn(token, self.JS, f"{token!r} drifted in app.js")


class TestStudioFootprint(unittest.TestCase):
    """specs/21 P0: the studio's mode state is the reader's own — localStorage and
    nothing else, defaulting to preview, validated on the way in, and NEVER a
    server call. Lifted from app.js and executed in node, the same treatment
    resolve() and decodeReel() get, and for the same reason."""

    JS = (REPO / "web" / "static" / "app.js").read_text()

    def node(self, body):
        import shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        return subprocess.run([node, "-e", body], capture_output=True, text=True)

    def lift(self, pattern):
        m = re.search(pattern, self.JS, re.S)
        self.assertTrue(m, f"{pattern!r} not found in the reader — did it move?")
        return m.group(0)

    def test_read_mode_defaults_to_preview_and_validates(self):
        """Absent, empty, or unknown → preview (the quiet default the resident
        gets). Only an exact one of the three modes is honoured — no coercion, so
        a corrupted value can never silently open the loud studio."""
        cases = [
            [None, "preview"], ["preview", "preview"], ["studio", "studio"],
            ["paper", "paper"], ["", "preview"], ["cockpit", "preview"],
            ["STUDIO", "preview"], [" studio", "preview"],
        ]
        body = "\n".join([
            "let STORE = null;",
            "const localStorage = { getItem: () => STORE };",
            self.lift(r'const MODE_KEY = .+?;'),
            self.lift(r"const MODES = .+?;"),
            self.lift(r'const readMode = .+?catch \{ return "preview"; \} \};'),
            "const CASES = " + json.dumps(cases) + ";",
            "let bad = 0;",
            "for (const [stored, want] of CASES) {",
            "  STORE = stored;",
            "  const got = readMode();",
            "  if (got !== want) { console.log('FAIL', JSON.stringify(stored), '->', got, 'want', want); bad++; }",
            "}",
            "process.exit(bad ? 1 : 0);",
        ])
        r = self.node(body)
        self.assertEqual(r.returncode, 0,
                         f"readMode is wrong:\n{r.stdout}{r.stderr}")

    def test_the_studio_path_touches_no_server(self):
        """The make path stays client-only: the studio's own functions read and
        write localStorage and compose pure links, and never reach a network —
        the covenant, and a test that proves it (specs/21 §5)."""
        block = self.JS[self.JS.index("THE STUDIO — the three-mode footprint"):
                        self.JS.index("SCOPE: the town")]
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "/api/",
                          "askStudio", "document.cookie", "new Image("):
            self.assertNotIn(forbidden, block,
                             f"the studio reached for {forbidden!r} — the make "
                             f"path must never touch a server (specs/21 §5)")
        # the mode is stored in localStorage, the same private preference the town
        # scope keeps — no cookie, no account, no sync
        self.assertIn("localStorage.setItem(MODE_KEY", block)

    def test_the_studio_markers_are_present(self):
        """A cheap drift guard: the pieces the stylesheet and the P0 contract lean
        on are present under their expected names."""
        for token in ("function initStudio(", "function markMode(",
                      'classList.toggle("cz-m-"', 'const MODE_KEY = "cz-studio-mode"',
                      "function refreshReelSummary(", "function setMode("):
            self.assertIn(token, self.JS, f"{token!r} drifted in app.js")
