"""Publicrecord's HTTP surface — and the promises it makes to a reader.

Three things are under test and they matter in this order.

**The covenant.** No public endpoint takes an identity, sets a cookie, or
changes because of who is asking. That is not a feature to regress quietly, so
it is asserted rather than assumed.

**Honest degradation.** Publicrecord is allowed to have a half missing — no
Gemini key, no steward console configured, no database — and it is never
allowed to hide that. A search with the neural half dark says so in the
response and returns the words it does have; a corpus that is gone returns 503
with a sentence, not an empty result that reads like "nothing was said about
that."

**Failing closed.** With auth unconfigured, every steward route returns 503.
The dangerous version of this bug is the one where the console falls *open*
because nobody set an environment variable.

Skips loudly without RECORD_TEST_PG_DSN.
"""

import os
import unittest
from unittest import mock

PG_DSN = os.environ.get("RECORD_TEST_PG_DSN", "").strip()

SELECT = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1",
     "text": "The chair calls the Select Board meeting to order."},
    {"start": 5.0, "end": 12.0, "speaker": "Speaker 1",
     "text": "First is the Harvard Street rezoning article."},
    {"start": 12.0, "end": 20.0, "speaker": "Speaker 2",
     "text": "I move to adopt the MBTA Communities zoning overlay as written."},
]
BOSTON = [
    {"start": 0.0, "end": 6.0, "speaker": "Speaker 1",
     "text": "The Council takes up the rezoning of the waterfront."},
]

STEWARD = {"email": "steward@example.org", "name": "A Steward", "sub": "1"}


@unittest.skipUnless(PG_DSN, "RECORD_TEST_PG_DSN unset — publicrecord's API is "
                             "UNPROVEN in this run")
class ApiTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from record.app import create_app
        from record.store import PgCorpus

        self.c = PgCorpus(dsn=PG_DSN)
        self.addCleanup(self.c.close)
        with self.c._con() as con:
            con.execute(
                "TRUNCATE meetings, segments, issues, issue_segments, threads, "
                "events, documents, doc_chunks, issue_documents, votes, "
                "submissions, asr_tasks, audit, spend, towns RESTART IDENTITY CASCADE")
        self.c.upsert_meeting({"id": "sel", "town": "Brookline", "status": "live",
                               "title": "Select Board", "date": "2026-05-19",
                               "body": "Select Board", "duration": 34.0,
                               "url": "https://www.youtube.com/watch?v=MIXnmQnw0gU",
                               "url_canon": "youtube:MIXnmQnw0gU"})
        self.c.replace_segments("sel", SELECT)
        self.c.upsert_meeting({"id": "bos", "town": "Boston", "status": "live",
                               "title": "City Council", "date": "2026-05-20"})
        self.c.replace_segments("bos", BOSTON)
        with self.c._con() as con:
            con.execute("INSERT INTO towns (slug, name, status) "
                        "VALUES ('Brookline','Brookline','live')")
        self.client = TestClient(create_app(corpus=self.c))

    # -- the covenant ------------------------------------------------------

    def test_public_endpoints_set_no_cookie_and_take_no_identity(self):
        """Readers are never logged in, counted, or followed. A Set-Cookie on
        any of these is the covenant breaking, whatever it was for."""
        for path, params in (("/api/health", {}),
                             ("/api/search", {"q": "rezoning"}),
                             ("/api/freshness", {}),
                             ("/api/towns", {})):
            r = self.client.get(path, params=params)
            self.assertNotIn("set-cookie", {k.lower() for k in r.headers})
            self.assertEqual(r.request.headers.get("cookie"), None)

    def test_search_is_identical_whoever_asks(self):
        a = self.client.get("/api/search", params={"q": "rezoning"}).json()
        b = self.client.get("/api/search", params={"q": "rezoning"},
                            headers={"Authorization": "Bearer whatever",
                                     "X-Forwarded-For": "10.0.0.1"}).json()
        self.assertEqual(a["hits"], b["hits"])

    # -- search ------------------------------------------------------------

    def test_search_returns_time_coded_hits_with_provenance(self):
        j = self.client.get("/api/search", params={"q": "rezoning"}).json()
        self.assertGreater(j["count"], 0)
        hit = j["hits"][0]
        self.assertIn("rezoning", hit["text"].lower())
        self.assertEqual(hit["t"], 5.0)
        self.assertIn(hit["why"], ("word", "related", "both", "meaning"))
        self.assertEqual(j["space"], "lexical")

    def test_search_scopes_to_a_town(self):
        j = self.client.get("/api/search",
                            params={"q": "rezoning", "town": "Brookline"}).json()
        self.assertEqual({h["town"] for h in j["hits"]}, {"Brookline"})
        j = self.client.get("/api/search",
                            params={"q": "rezoning", "town": "Boston"}).json()
        self.assertEqual({h["town"] for h in j["hits"]}, {"Boston"})

    def test_asking_for_meaning_without_a_key_says_so_and_still_answers(self):
        """The honest line specs/17 §8 asks for. The failure mode this guards
        is a search that silently returns lexical results while the UI claims
        to be searching meaning."""
        j = self.client.get("/api/search",
                            params={"q": "rezoning", "space": "neural"}).json()
        self.assertEqual(j["space"], "lexical")     # what actually happened
        self.assertIn("meaning-search needs publicrecord", j["note"])
        self.assertGreater(j["count"], 0)           # and the words still work

    def test_empty_query_is_not_an_error(self):
        j = self.client.get("/api/search", params={"q": "  "}).json()
        self.assertEqual(j["hits"], [])

    def test_search_rejects_an_unknown_space(self):
        r = self.client.get("/api/search", params={"q": "x", "space": "magic"})
        self.assertEqual(r.status_code, 422)

    # -- freshness ---------------------------------------------------------

    def test_freshness_changes_when_the_record_does(self):
        """Deliberately not the edition date — that is the newest meeting, not
        the moment of pressing, and it must stay that way so the bake is
        byte-idempotent."""
        before = self.client.get("/api/freshness").json()["fingerprint"]
        self.assertTrue(before)
        self.c.upsert_meeting({"id": "new", "town": "Brookline", "status": "live",
                               "date": "2026-06-01", "title": "Another"})
        after = self.client.get("/api/freshness").json()["fingerprint"]
        self.assertNotEqual(before, after)

    # -- submissions -------------------------------------------------------

    def test_a_known_meeting_is_recognised_through_a_tracking_link(self):
        """specs/16's acceptance: a youtu.be or `&si=` link of an ingested
        meeting resolves as already-on-the-record."""
        r = self.client.post("/api/submissions", json={
            "url": "https://www.youtube.com/watch?v=MIXnmQnw0gU&si=abc123"})
        self.assertEqual(r.json(), {"meeting_id": "sel", "status": "exists"})

    def test_a_new_url_lands_in_the_queue_not_in_the_record(self):
        """Nothing ingests on a stranger's POST. That is the whole point of
        having a queue."""
        r = self.client.post("/api/submissions", json={
            "url": "https://www.youtube.com/watch?v=BRANDNEW001",
            "town": "Brookline", "body": "Select Board", "date": "2026-07-01",
            "note": "you missed this one"})
        j = r.json()
        self.assertEqual(j["status"], "submitted")
        self.assertEqual(j["meeting_id"], "")
        self.assertIn("a steward reviews", j["note"])
        self.assertIsNone(self.c.get_meeting("BRANDNEW001"))

    def test_resubmitting_does_not_overrule_a_steward(self):
        url = "https://www.youtube.com/watch?v=BRANDNEW002"
        first = self.client.post("/api/submissions", json={"url": url}).json()
        with self.c._con() as con:
            con.execute("UPDATE submissions SET status='rejected' WHERE id=%s",
                        (first["submission_id"],))
        again = self.client.post("/api/submissions", json={"url": url}).json()
        self.assertEqual(again["status"], "rejected")

    def test_a_submission_without_a_url_is_refused_with_a_sentence(self):
        r = self.client.post("/api/submissions", json={"town": "Brookline"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("URL", r.json()["error"])

    # -- health ------------------------------------------------------------

    def test_health_reports_both_halves_not_just_a_green_light(self):
        j = self.client.get("/api/health").json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["record"]["meetings"], 2)
        self.assertIn("available", j["neural"])
        self.assertNotIn("record:record@", j["store"])   # never the password
        self.assertIn("***", j["store"])                 # and it says so


    # -- what the adversarial review found ---------------------------------

    def test_health_never_publishes_a_password_in_any_dsn_shape(self):
        """`redacted()` used to return the string verbatim for anything that
        was not clean URI form — and libpq also accepts keyword/value and a
        password in the query string. Both fell straight onto this anonymous
        endpoint. A redactor whose failure mode is "publish it" is worse than
        none."""
        from record.settings import Settings
        for dsn in (
            "postgresql://record:hunter2@localhost:5432/record",
            "host=localhost port=5432 dbname=record user=record password=hunter2",
            "postgresql://localhost/record?user=record&password=hunter2",
            "postgres://u:hunter2@h/db",
        ):
            out = Settings(dsn=dsn).redacted()
            self.assertNotIn("hunter2", out, f"leaked from {dsn!r} -> {out!r}")

    def test_search_reports_the_space_it_actually_searched(self):
        """`available()` sees a key and an importable SDK — it cannot see that
        the corpus was never embedded. Reporting `space: "neural"` over a
        purely lexical result is the exact dishonesty the note exists to
        prevent."""
        from unittest import mock

        from record import embed_neural
        with mock.patch.object(embed_neural, "available", lambda: True), \
             mock.patch.object(embed_neural, "embed_query", lambda *a, **k: None):
            j = self.client.get("/api/search",
                                params={"q": "rezoning", "space": "neural"}).json()
        self.assertEqual(j["space"], "lexical")     # nothing was embedded
        self.assertIn("words still work", j["note"])
        self.assertGreater(j["count"], 0)

    def test_public_search_withholds_a_meeting_that_is_not_live(self):
        """An un-approved submission's transcript was readable by anyone."""
        self.c.upsert_meeting({"id": "priv", "town": "Brookline",
                               "status": "queued", "title": "Executive Session"})
        self.c.replace_segments("priv", [
            {"start": 0.0, "end": 4.0, "text": "the rezoning article, privately"}])
        j = self.client.get("/api/search", params={"q": "rezoning"}).json()
        self.assertNotIn("priv", {h["meeting_id"] for h in j["hits"]})
        self.assertNotIn("Executive Session",
                         {h["title"] for h in j["hits"]})

    # -- the steward console fails closed ----------------------------------

    def test_every_steward_route_is_shut_when_auth_is_unconfigured(self):
        """The dangerous version of this bug is the one where the console falls
        OPEN because an environment variable was never set."""
        for method, path in (("get", "/api/steward/me"),
                             ("get", "/api/steward/submissions"),
                             ("get", "/api/steward/issues"),
                             ("get", "/api/steward/audit"),
                             ("get", "/api/steward/spend"),
                             ("post", "/api/steward/rebuild")):
            r = getattr(self.client, method)(path, **(
                {"json": {}} if method == "post" else {}))
            self.assertEqual(r.status_code, 503, f"{path} did not fail closed")
            self.assertIn("not configured", r.json()["error"])


@unittest.skipUnless(PG_DSN, "RECORD_TEST_PG_DSN unset — the steward console is "
                             "UNPROVEN in this run")
class StewardTest(unittest.TestCase):
    """The console with auth configured. The Google verifier is stubbed — what
    is under test is the allowlist and the verbs, not Google's RS256."""

    def setUp(self):
        from fastapi.testclient import TestClient

        from record import auth
        from record.app import create_app
        from record.settings import Settings
        from record.store import PgCorpus

        self.c = PgCorpus(dsn=PG_DSN)
        self.addCleanup(self.c.close)
        with self.c._con() as con:
            con.execute(
                "TRUNCATE meetings, segments, issues, issue_segments, threads, "
                "events, documents, doc_chunks, issue_documents, votes, "
                "submissions, asr_tasks, audit, spend, towns RESTART IDENTITY CASCADE")

        cfg = Settings(dsn=PG_DSN, google_client_id="test-client",
                       steward_allowlist=["steward@example.org"])
        p = mock.patch.object(auth, "settings", cfg, create=True)
        p.start(); self.addCleanup(p.stop)
        p2 = mock.patch("record.settings.settings", cfg)
        p2.start(); self.addCleanup(p2.stop)
        p3 = mock.patch.object(auth, "_HAVE_GOOGLE_AUTH", True)
        p3.start(); self.addCleanup(p3.stop)

        self.claims = {"iss": "https://accounts.google.com", "email_verified": True,
                       "email": "steward@example.org", "name": "A Steward",
                       "sub": "1"}
        self.verify = mock.patch.object(
            auth._g_id_token, "verify_oauth2_token",
            side_effect=lambda *a, **k: self.claims)
        self.verify.start(); self.addCleanup(self.verify.stop)

        self.c.upsert_meeting({"id": "sel", "town": "Brookline", "status": "live",
                               "title": "Select Board", "date": "2026-05-19"})
        self.c.replace_segments("sel", SELECT)
        segs = self.c.segments_of("sel")
        self.c.upsert_issue({"id": "i1", "town": "Brookline", "name": "City Realy",
                             "status": "active", "origin": "auto",
                             "aliases": ["city realy"], "keywords": ["city realy"]})
        self.c.link_segments("i1", [(segs[1]["id"], "sel", 1.0, "alias")])
        self.client = TestClient(create_app(corpus=self.c))
        self.hdr = {"Authorization": "Bearer good-token"}

    def test_a_signed_in_steward_is_recognised(self):
        j = self.client.get("/api/steward/me", headers=self.hdr).json()
        self.assertEqual(j["steward"], "steward@example.org")

    def test_a_verified_google_account_off_the_allowlist_gets_403_not_401(self):
        """403, because signing in again cannot help and the message should not
        send someone round a loop that has no exit."""
        self.claims = {**self.claims, "email": "stranger@example.org"}
        r = self.client.get("/api/steward/me", headers=self.hdr)
        self.assertEqual(r.status_code, 403)
        self.assertIn("is not a steward", r.json()["error"])

    def test_no_token_at_all_is_401(self):
        r = self.client.get("/api/steward/me")
        self.assertEqual(r.status_code, 401)

    def test_an_unverified_address_is_refused(self):
        self.claims = {**self.claims, "email_verified": False}
        self.assertEqual(
            self.client.get("/api/steward/me", headers=self.hdr).status_code, 403)

    def test_a_token_from_another_issuer_is_refused(self):
        self.claims = {**self.claims, "iss": "https://evil.example"}
        self.assertEqual(
            self.client.get("/api/steward/me", headers=self.hdr).status_code, 401)

    # -- the verbs ---------------------------------------------------------

    def test_rename_fixes_the_garbled_issue_and_says_who_did_it(self):
        """The verb the imported corpus needs first — `City Realy` is a caption
        garble the import deliberately carried across rather than quietly
        correcting."""
        r = self.client.post("/api/steward/issues/i1/rename", headers=self.hdr,
                             json={"name": "City Realty"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get_issue("i1")["name"], "City Realty")
        entry = self.client.get("/api/steward/audit", headers=self.hdr).json()["audit"][0]
        self.assertEqual(entry["verb"], "rename")
        self.assertEqual(entry["steward"], "steward@example.org")
        self.assertEqual(entry["payload"]["was"], "City Realy")
        self.assertEqual(entry["payload"]["now"], "City Realty")

    def test_rename_without_a_name_is_refused(self):
        r = self.client.post("/api/steward/issues/i1/rename", headers=self.hdr,
                             json={"name": "   "})
        self.assertEqual(r.status_code, 422)

    def test_forget_is_audited_before_the_row_is_gone(self):
        """The one destructive verb. The log has to outlive what it describes."""
        r = self.client.post("/api/steward/issues/i1/forget", headers=self.hdr)
        self.assertTrue(r.json()["forgotten"])
        self.assertIsNone(self.c.get_issue("i1"))
        entry = self.client.get("/api/steward/audit", headers=self.hdr).json()["audit"][0]
        self.assertEqual(entry["verb"], "forget")
        self.assertEqual(entry["payload"]["name"], "City Realy")

    def test_merge_leaves_a_tombstone_pointing_home(self):
        self.c.upsert_issue({"id": "i2", "town": "Brookline", "name": "Realty",
                             "status": "active"})
        r = self.client.post("/api/steward/issues/i1/merge", headers=self.hdr,
                             json={"src_ids": ["i2"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get_issue("i2")["status"], "merged")
        self.assertEqual(self.c.get_issue("i2")["merged_into"], "i1")

    def test_merge_with_nothing_to_merge_is_refused(self):
        r = self.client.post("/api/steward/issues/i1/merge", headers=self.hdr,
                             json={"src_ids": ["i1"]})       # itself only
        self.assertEqual(r.status_code, 422)

    def test_promote_keeps_the_links_the_candidate_queue_gave_it(self):
        self.c.upsert_issue({"id": "cand", "town": "Brookline", "name": "Maybe",
                             "status": "candidate", "origin": "auto"})
        segs = self.c.segments_of("sel")
        self.c.link_segments("cand", [(segs[0]["id"], "sel", 0.5, "related")])
        self.client.post("/api/steward/issues/cand/promote", headers=self.hdr)
        iss = self.c.get_issue("cand")
        self.assertEqual(iss["status"], "active")
        self.assertEqual(iss["origin"], "steward")
        self.assertEqual(iss["n_segments"], 1)          # unchanged, on purpose

    def test_a_verb_on_a_missing_issue_is_404(self):
        for path in ("/api/steward/issues/nope/rename",
                     "/api/steward/issues/nope/promote",
                     "/api/steward/issues/nope/forget"):
            r = self.client.post(path, headers=self.hdr, json={"name": "x"})
            self.assertEqual(r.status_code, 404, path)

    # -- the queue ---------------------------------------------------------

    def test_the_review_queue_approves_and_rejects_with_a_record(self):
        self.client.post("/api/submissions",
                         json={"url": "https://www.youtube.com/watch?v=QUEUED00001",
                               "town": "Brookline"})
        q = self.client.get("/api/steward/submissions", headers=self.hdr).json()
        self.assertEqual(len(q["submissions"]), 1)
        sub_id = q["submissions"][0]["id"]

        r = self.client.post(f"/api/steward/submissions/{sub_id}/approve",
                             headers=self.hdr)
        self.assertEqual(r.json()["status"], "approved")
        # approving marks it for the pipeline; it does not ingest inline
        self.assertIsNone(self.c.get_meeting("QUEUED00001"))

        verbs = [a["verb"] for a in
                 self.client.get("/api/steward/audit", headers=self.hdr).json()["audit"]]
        self.assertIn("approve", verbs)

    def test_rejecting_records_the_reason(self):
        self.client.post("/api/submissions",
                         json={"url": "https://www.youtube.com/watch?v=QUEUED00002"})
        sub_id = self.client.get("/api/steward/submissions",
                                 headers=self.hdr).json()["submissions"][0]["id"]
        r = self.client.post(f"/api/steward/submissions/{sub_id}/reject",
                             headers=self.hdr, json={"reason": "not a public body"})
        self.assertEqual(r.json()["reason"], "not a public body")
        left = self.client.get("/api/steward/submissions", headers=self.hdr).json()
        self.assertEqual(left["submissions"], [])       # gone from the queue

    def test_the_spend_ledger_is_visible_to_a_steward(self):
        """Every token attributed, on the console rather than in a bill nobody
        reads (specs/17 §6.6)."""
        import time
        with self.c._con() as con:
            con.execute("INSERT INTO spend (model, purpose, town, units, added_at) "
                        "VALUES ('gemini-embedding-001','embed','Brookline',1200,%s)",
                        (time.time(),))
        j = self.client.get("/api/steward/spend", headers=self.hdr).json()
        self.assertEqual(j["totals"][0]["units"], 1200)
        self.assertEqual(j["totals"][0]["model"], "gemini-embedding-001")


if __name__ == "__main__":
    unittest.main()
