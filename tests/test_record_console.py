"""The steward console as a *page* — and the two ways a page like this fails.

The API behind this console is tested elsewhere (`test_record_api.py`), and
those tests need a database. These do not: the console routes read three files
off disk and answer one question about configuration, which is exactly why they
are worth their own file. A console that will not serve is a console nobody
notices is broken until the night somebody needs it.

Three things are asserted, in the order they matter.

**It fails closed, and it says so in words.** With no `RECORD_GOOGLE_CLIENT_ID`
and no allowlist, `/steward/config.json` answers `configured: false` with the
server's own sentence naming the missing variable — and every steward API route
underneath still answers 503. The dangerous version of this bug is not the page
looking broken; it is the page looking fine.

**It leaks nothing on the way.** `config.json` is the one console route that
cannot require auth, because the page needs a client id before it can make an
authenticated call. A client id is public by Google's design. The allowlist is
not, and must never appear in that response.

**Its Content-Security-Policy is the narrow one it claims to be.** `/steward`
admits Google's sign-in script and nothing else; `script-src` keeps no
'unsafe-inline', so console.js remains the only code that can run on the page,
and no reader page's policy is touched by any of it. The page carrying an
inline <script> would silently defeat that, so the markup is checked too.
"""

import re
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "record" / "static"


def client(**settings_kw):
    """A TestClient with no database anywhere near it. The console routes
    never call `store()`, and `create_app(corpus=object())` proves it — if one
    of them ever does, the sentinel has no methods and the test says so."""
    from fastapi.testclient import TestClient

    from record.app import create_app
    return TestClient(create_app(corpus=object()))


class ConsolePageTest(unittest.TestCase):
    def setUp(self):
        self.c = client()

    # -- it serves ---------------------------------------------------------

    def test_the_console_page_serves(self):
        r = self.c.get("/steward")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        self.assertIn("publicrecord", r.text)
        self.assertIn("/steward/console.js", r.text)
        self.assertIn("/steward/console.css", r.text)

    def test_the_trailing_slash_serves_the_same_page(self):
        """A steward types one or the other and neither is a 404."""
        self.assertEqual(self.c.get("/steward/").text, self.c.get("/steward").text)

    def test_the_static_assets_are_reachable(self):
        css = self.c.get("/steward/console.css")
        self.assertEqual(css.status_code, 200)
        self.assertIn("text/css", css.headers["content-type"])
        js = self.c.get("/steward/console.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])
        self.assertIn("/api/steward/preview", js.text)

    def test_nothing_outside_the_console_is_reachable_through_it(self):
        """An allowlist of three names, not a directory mount — so there is no
        path expression to get wrong."""
        for path in ("/steward/app.py", "/steward/../app.py",
                     "/steward/console.html", "/steward/settings.py"):
            self.assertEqual(self.c.get(path).status_code, 404, path)

    # -- the covenant ------------------------------------------------------

    def test_the_console_sets_no_cookie_either(self):
        """Stewards sign in; nobody gets a session. The ID token lives in a
        variable in the page and there is no server-side session to set."""
        for path in ("/steward", "/steward/console.js", "/steward/config.json"):
            r = self.c.get(path)
            self.assertNotIn("set-cookie", {k.lower() for k in r.headers}, path)

    def test_the_page_asks_not_to_be_indexed(self):
        self.assertIn('name="robots"', self.c.get("/steward").text)

    # -- the CSP -----------------------------------------------------------

    def test_the_console_csp_admits_google_and_nothing_else(self):
        csp = self.c.get("/steward").headers["content-security-policy"]
        self.assertIn("script-src 'self' https://accounts.google.com/gsi/client;", csp)
        self.assertIn("connect-src 'self' https://accounts.google.com/gsi/;", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        # No CDN, no font host, no analytics beacon rode in behind Google.
        hosts = set(re.findall(r"https://[a-z0-9.\-]+", csp))
        self.assertEqual(hosts, {"https://accounts.google.com"})

    def test_script_src_keeps_no_inline_escape_hatch(self):
        """'unsafe-inline' on script-src would make the whole policy
        decorative — corpus data reaches this page, and municipal video titles
        come from the internet."""
        csp = self.c.get("/steward").headers["content-security-policy"]
        script = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
        self.assertNotIn("unsafe-inline", script)
        self.assertNotIn("unsafe-eval", script)

    def test_the_assets_carry_the_policy_too(self):
        for path in ("/steward/console.css", "/steward/console.js"):
            self.assertIn("content-security-policy",
                          {k.lower() for k in self.c.get(path).headers}, path)

    def test_the_page_has_no_inline_script_to_be_blocked(self):
        """The CSP forbids it, so an inline <script> would not fail loudly —
        it would just silently not run. Catch it here instead."""
        html = self.c.get("/steward").text
        for tag in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S):
            self.assertEqual(tag.strip(), "", "the console has an inline script")

    def test_the_assets_reference_no_third_party_at_all(self):
        """Google is admitted on the page, for the sign-in tag. Neither the
        stylesheet nor the script is allowed to reach anywhere: pure stdlib on
        the server, vanilla JS in the browser, no CDN, no build step."""
        for name in ("console.css", "console.js"):
            text = (STATIC / name).read_text()
            found = re.findall(r"https?://[^\s'\"<>)]+", text)
            self.assertEqual(found, [], f"{name} reaches out to {found}")

    # -- configuration, honestly -------------------------------------------

    def test_an_unconfigured_console_says_which_variable_is_missing(self):
        """Not a broken UI, not a blank page: a sentence naming the switch."""
        j = self.c.get("/steward/config.json").json()
        self.assertFalse(j["configured"])
        self.assertEqual(j["client_id"], "")
        self.assertTrue(j["why"])
        self.assertRegex(j["why"], r"RECORD_GOOGLE_CLIENT_ID|RECORD_STEWARD_ALLOWLIST"
                                   r"|google-auth")

    def test_an_unconfigured_console_still_answers_200(self):
        """"There is no console here" is a true and successful answer to the
        question the page asked. Failing closed happens on the API below,
        where it changes what somebody can do."""
        self.assertEqual(self.c.get("/steward/config.json").status_code, 200)

    def test_the_api_underneath_still_fails_closed_while_the_page_serves(self):
        """The pairing that matters: a page that renders is not a console that
        is open. No database is touched proving it, because `steward_of` raises
        before anything reaches the store."""
        self.assertEqual(self.c.get("/steward").status_code, 200)
        for path in ("/api/steward/me", "/api/steward/towns",
                     "/api/steward/submissions", "/api/steward/audit",
                     "/api/steward/spend"):
            r = self.c.get(path)
            self.assertEqual(r.status_code, 503, f"{path} did not fail closed")
            self.assertIn("not configured", r.json()["error"])

    def test_a_configured_console_hands_over_the_client_id_and_nothing_else(self):
        """The client id is public by Google's design — it is in the markup of
        every page that renders a sign-in button. The allowlist is not, and a
        page has no business knowing who the other stewards are."""
        from record import auth
        from record.settings import Settings

        cfg = Settings(google_client_id="1234-abc.apps.googleusercontent.com",
                       steward_allowlist=["steward@example.org",
                                          "another@example.org"])
        with mock.patch("record.settings.settings", cfg), \
             mock.patch.object(auth, "_HAVE_GOOGLE_AUTH", True), \
             mock.patch("record.app.settings", cfg):
            j = client().get("/steward/config.json").json()
        self.assertTrue(j["configured"])
        self.assertEqual(j["client_id"], "1234-abc.apps.googleusercontent.com")
        self.assertEqual(j["why"], "")
        body = repr(j)
        self.assertNotIn("steward@example.org", body)
        self.assertNotIn("another@example.org", body)


class ConsoleCoversTheSpecTest(unittest.TestCase):
    """specs/17 §7 names what this console is for. These are shallow checks —
    a string in a file is not a working screen — but they catch the regression
    where a verb quietly loses its button and nobody notices for a month."""

    def setUp(self):
        self.js = (STATIC / "console.js").read_text()
        self.html = (STATIC / "console.html").read_text()

    def test_every_verb_the_api_allows_has_a_caller(self):
        from record.steward import VERBS

        for v in VERBS:
            self.assertIn(v, self.js, f"the console cannot {v}")

    def test_the_intake_screen_reaches_all_four_intake_routes(self):
        for route in ("/api/steward/towns", "/api/steward/preview",
                      "/sources", "/poll"):
            self.assertIn(route, self.js, route)

    def test_the_preview_renders_all_three_lists_and_the_cost(self):
        for key in ("would_cost", "unmatched", "excluded", "suggestions"):
            self.assertIn(key, self.js, key)

    def test_the_ledgers_are_read(self):
        self.assertIn("/api/steward/spend", self.js)
        self.assertIn("/api/steward/audit", self.js)

    def test_the_page_says_what_it_needs_when_scripts_are_off(self):
        """The reader's pages degrade to real HTML because a resident must be
        able to read the record without scripts. A curation console genuinely
        cannot — so it says so rather than showing an empty frame."""
        self.assertIn("<noscript>", self.html)

    def test_publicrecord_takes_zero_pop_colour(self):
        """The quiet brand. Fuchsia and purple belong to communityai and
        civicmedia; a steward console is still publicrecord, and this is the
        rule most likely to be broken by someone reaching for a 'danger' red
        or an 'active' accent."""
        # Comments are stripped first: the file argues at length about why
        # there is no fuchsia here, and the rule is about declarations.
        css = re.sub(r"/\*.*?\*/", "", (STATIC / "console.css").read_text(),
                     flags=re.S).lower()
        for banned in ("#d946ef", "#a855f7", "fuchsia", "purple", "magenta"):
            self.assertNotIn(banned, css, f"{banned} has no place in publicrecord")


if __name__ == "__main__":
    unittest.main()
