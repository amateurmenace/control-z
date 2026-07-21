"""The shared-paper store (specs/21 §6.2) — canonical bytes, strict refusal,
idempotent addresses, honest failure.

The store's whole contract lives in `record/papers.py`: one canonical
serialization decided server-side (so there is no cross-language byte contract
for the reader to drift against), a hash that IS the address, and validation
that refuses rather than rewrites — the only free text a stored paper may
carry is its title. The endpoints are thin; these tests hold the contract.

None of this needs a database (`create_app(corpus=object())` proves the
routes never touch the corpus) or a bucket (`MemPapers` is the same two
methods the GCS backend keeps).
"""

import json
import unittest
from pathlib import Path

from record.papers import (SCHEMA, TITLE_MAX, MemPapers, PaperError,
                           canonical, paper_id)

REPO = Path(__file__).resolve().parents[1]


def portable(title="Overrides, watched", blocks=None):
    """A well-formed portable paper — the exact shape the reader POSTs."""
    return {"schema": SCHEMA, "title": title,
            "blocks": blocks if blocks is not None else [
                {"kind": "story", "story": "meeting", "pid": "2YhgO14jXys"},
                {"kind": "story", "story": "issue", "slug": "the-override"},
                {"kind": "reel", "clips": [
                    {"pid": "2YhgO14jXys", "start": 900.2, "end": 907.3},
                    {"pid": "abc_def-123", "start": 12, "end": 24.0},
                ]},
            ]}


class TestCanonicalForm(unittest.TestCase):
    def test_canonical_is_deterministic_and_key_order_blind(self):
        a = canonical(portable())
        scrambled = json.loads(json.dumps(portable()))
        scrambled = {k: scrambled[k] for k in ("blocks", "schema", "title")}
        self.assertEqual(a, canonical(scrambled))

    def test_whole_second_times_collapse_to_one_address(self):
        """12, 12.0 and 12.00 are the same clip; a client's int and another's
        float must not mint two addresses for one paper."""
        ints = portable(blocks=[{"kind": "reel", "clips": [
            {"pid": "abc", "start": 12, "end": 24}]}])
        floats = portable(blocks=[{"kind": "reel", "clips": [
            {"pid": "abc", "start": 12.0, "end": 24.00}]}])
        self.assertEqual(paper_id(canonical(ints)), paper_id(canonical(floats)))
        self.assertIn('"start":12}', canonical(ints))

    def test_times_snap_to_the_tenth_second_grid(self):
        a = portable(blocks=[{"kind": "reel", "clips": [
            {"pid": "abc", "start": 1.23, "end": 4.56}]}])
        b = portable(blocks=[{"kind": "reel", "clips": [
            {"pid": "abc", "start": 1.2, "end": 4.6}]}])
        self.assertEqual(canonical(a), canonical(b))

    def test_canonical_round_trips_through_itself(self):
        """canonical(parse(canonical(x))) == canonical(x) — the stored bytes
        are a fixed point, so a re-share of a fetched paper re-mints its own
        address."""
        c = canonical(portable())
        self.assertEqual(c, canonical(json.loads(c)))

    def test_the_id_is_sixteen_hex_characters(self):
        pid = paper_id(canonical(portable()))
        self.assertRegex(pid, r"^[0-9a-f]{16}$")

    def test_a_title_only_paper_stores(self):
        canonical({"schema": SCHEMA, "title": "just a name", "blocks": []})

    def test_refusals_name_their_reason(self):
        """Strict, not corrective: every malformed document is a PaperError
        whose message a reader could act on — never a silent rewrite."""
        cases = [
            ("not even an object", [], "json object"),
            ({"schema": "publicrecord.reel/1", "title": "x", "blocks": []},
             None, "schema"),
            ({"schema": SCHEMA, "title": "x", "blocks": [], "author": "me"},
             None, "unknown keys"),
            ({"schema": SCHEMA, "title": 7, "blocks": []}, None, "string"),
            ({"schema": SCHEMA, "title": "a" * (TITLE_MAX + 1), "blocks": []},
             None, "longer"),
            ({"schema": SCHEMA, "title": "a\x00b", "blocks": []},
             None, "control"),
            ({"schema": SCHEMA, "title": "", "blocks": []}, None, "empty"),
            (portable(blocks=[{"kind": "note", "text": "hi"}]), None,
             "unknown kind"),
            (portable(blocks=[{"kind": "story", "story": "meeting",
                               "pid": "has space"}]), None, "meeting id"),
            (portable(blocks=[{"kind": "story", "story": "meeting",
                               "pid": "ok", "title": "smuggled"}]), None,
             "exactly"),
            (portable(blocks=[{"kind": "reel", "clips": []}]), None, "clips"),
            (portable(blocks=[{"kind": "reel", "clips": [
                {"pid": "abc", "start": 9, "end": 3}]}]), None, "ends before"),
            (portable(blocks=[{"kind": "reel", "clips": [
                {"pid": "abc", "start": "9", "end": 12}]}]), None, "number"),
            (portable(blocks=[{"kind": "reel", "clips": [
                {"pid": "abc", "start": True, "end": 12}]}]), None, "number"),
            (portable(blocks=[{"kind": "reel", "clips": [
                {"pid": "abc", "start": -1, "end": 12}]}]), None, "finite"),
            (portable(blocks=[{"kind": "reel", "clips": [
                {"pid": "abc", "start": 1, "end": 2, "quote": "free text"}]}]),
             None, "exactly"),
        ]
        for doc, _, fragment in cases:
            with self.assertRaises(PaperError, msg=repr(doc)) as cm:
                canonical(doc)
            self.assertIn(fragment, str(cm.exception).lower(),
                          f"for {doc!r} got: {cm.exception}")

    def test_the_reader_never_computes_the_hash(self):
        """The canonical form is decided HERE — app.js must not grow its own
        (a client-side hash would be a cross-language byte contract waiting
        to drift; the client POSTs and receives the address)."""
        js = (REPO / "web" / "static" / "app.js").read_text()
        for token in ("sha256", "SHA-256", "crypto.subtle", "digest("):
            self.assertNotIn(token, js,
                             f"app.js grew {token!r} — the store's canonical "
                             "bytes are server-side only (record/papers.py)")


class TestPaperEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from record.app import create_app
        self.mem = MemPapers()
        # corpus=object(): these routes must never touch the record itself
        self.client = TestClient(create_app(corpus=object(), papers=self.mem))

    def test_post_answers_the_address_and_get_serves_the_bytes(self):
        r = self.client.post("/api/papers", json=portable())
        self.assertEqual(r.status_code, 200, r.text)
        pid = r.json()["id"]
        self.assertRegex(pid, r"^[0-9a-f]{16}$")
        self.assertEqual(r.json()["path"], f"/api/papers/{pid}")
        g = self.client.get(f"/api/papers/{pid}")
        self.assertEqual(g.status_code, 200)
        self.assertEqual(g.json()["schema"], SCHEMA)
        self.assertEqual(g.json()["title"], "Overrides, watched")
        # the address is the content, so the cache may say forever
        self.assertIn("immutable", g.headers.get("cache-control", ""))

    def test_the_same_paper_cannot_have_two_addresses(self):
        a = self.client.post("/api/papers", json=portable())
        b = self.client.post("/api/papers", json=portable())
        self.assertEqual(a.json()["id"], b.json()["id"])
        self.assertEqual(len(self.mem._d), 1)

    def test_stored_bytes_are_canonical_not_the_wire_bytes(self):
        """However the client spelled it (key order, 12.0), the store holds
        the one canonical form."""
        doc = portable(blocks=[{"kind": "reel", "clips": [
            {"end": 24.0, "start": 12, "pid": "abc"}]}])
        pid = self.client.post("/api/papers", json=doc).json()["id"]
        self.assertEqual(self.mem.get(pid).decode(), canonical(doc))

    def test_invalid_documents_are_422_with_the_reason(self):
        r = self.client.post("/api/papers",
                             json={"schema": SCHEMA, "title": "x",
                                   "blocks": [], "author": "me"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("unknown keys", r.json()["error"])
        r = self.client.post("/api/papers", content=b"not json{",
                             headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_oversize_is_413_before_parsing(self):
        blob = b"x" * (64 * 1024 + 1)
        r = self.client.post("/api/papers", content=blob,
                             headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 413)

    def test_absent_papers_are_honest_404s(self):
        r = self.client.get("/api/papers/0123456789abcdef")
        self.assertEqual(r.status_code, 404)
        self.assertIn("no paper at this address", r.json()["error"])
        # a malformed id is a 404 too, not a 500 and not a probe surface
        self.assertEqual(self.client.get("/api/papers/xyz").status_code, 404)
        self.assertEqual(
            self.client.get("/api/papers/AAAAAAAAAAAAAAAA").status_code, 404)

    def test_without_a_bucket_the_store_says_so(self):
        """papers=None and no RECORD_PAPERS_BUCKET → 503 with the covenant
        line, not a crash and not a silent success."""
        from fastapi.testclient import TestClient

        from record.app import create_app
        from record.settings import settings
        if settings.papers_bucket:
            self.skipTest("RECORD_PAPERS_BUCKET is set in this environment")
        bare = TestClient(create_app(corpus=object()))
        r = bare.post("/api/papers", json=portable())
        self.assertEqual(r.status_code, 503)
        self.assertIn("full link", r.json()["error"])
        self.assertEqual(bare.get("/api/papers/0123456789abcdef").status_code,
                         503)

    def test_the_store_takes_no_identity(self):
        """No cookie is set and nothing about the caller is stored — the
        object is the canonical document bytes and only that."""
        r = self.client.post("/api/papers", json=portable())
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers})
        pid = r.json()["id"]
        stored = json.loads(self.mem.get(pid))
        self.assertEqual(set(stored), {"schema", "title", "blocks"})


if __name__ == "__main__":
    unittest.main()
