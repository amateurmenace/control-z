import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from czcore import proxy
from czcore.captions import parse_tracks, pick_track, video_id


class TestProxyURL(unittest.TestCase):
    def test_rotating_session_suffix_added(self):
        u = proxy.build_url("acct", "pw")
        self.assertTrue(u.startswith("http://acct-1:pw@"))

    def test_existing_suffix_kept(self):
        self.assertIn("acct-rotate:", proxy.build_url("acct-rotate", "pw"))
        self.assertIn("acct-1:", proxy.build_url("acct-1", "pw"))

    def test_credentials_url_encoded(self):
        u = proxy.build_url("us er", "p@ss#w", "h:80")
        self.assertIn("us%20er-1", u)
        self.assertIn("p%40ss%23w", u)
        self.assertTrue(u.endswith("@h:80/"))

    def test_default_host(self):
        self.assertIn("@p.webshare.io:80/", proxy.build_url("a", "b"))


class TestProxyConfig(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="cz-proxy-test-")
        patch_dir = mock.patch.object(
            proxy, "support_dir", lambda sub="": Path(self.td.name))
        patch_dir.start()
        self.addCleanup(patch_dir.stop)
        # a builder's baked-in account must never leak into these tests
        patch_house = mock.patch.object(
            proxy, "HOUSE_FILE", Path(self.td.name) / "house_proxy.json")
        patch_house.start()
        self.addCleanup(patch_house.stop)
        self.addCleanup(self.td.cleanup)
        # tests must not inherit a real environment configuration
        import os
        saved = {k: os.environ.pop(k, None)
                 for k in ("WEBSHARE_PROXY_USERNAME", "WEBSHARE_PROXY_PASSWORD",
                           "WEBSHARE_PROXY_HOST")}
        self.addCleanup(lambda: [os.environ.update({k: v})
                                 for k, v in saved.items() if v is not None])

    def test_unset_means_disabled(self):
        self.assertIsNone(proxy.proxy_url())
        st = proxy.status()
        self.assertFalse(st["enabled"])
        self.assertIsNone(st["source"])

    def test_file_roundtrip_and_masking(self):
        proxy.set_config("stationacct", "secretpw")
        st = proxy.status()
        self.assertTrue(st["enabled"])
        self.assertEqual(st["source"], "file")
        self.assertNotIn("secretpw", json.dumps(st))     # password never leaves
        self.assertIn("…", st["username_masked"])
        self.assertIn("stationacct-1:secretpw", proxy.proxy_url())

    def test_clear_with_empty_strings(self):
        proxy.set_config("a", "b")
        proxy.set_config("", "")
        self.assertIsNone(proxy.proxy_url())

    def test_env_wins_over_file(self):
        proxy.set_config("fileuser", "filepw")
        with mock.patch.dict("os.environ",
                             {"WEBSHARE_PROXY_USERNAME": "envuser",
                              "WEBSHARE_PROXY_PASSWORD": "envpw"}):
            c = proxy.get_config()
            self.assertEqual((c["username"], c["source"]), ("envuser", "env"))

    def test_relay_defaults_on_and_survives_credential_changes(self):
        self.assertTrue(proxy.relay_enabled())
        proxy.set_relay(False)
        proxy.set_config("acct", "pw")          # creds arrive
        self.assertFalse(proxy.relay_enabled())  # opt-out survives
        proxy.set_config("", "")                 # creds cleared
        self.assertFalse(proxy.relay_enabled())  # still opted out
        proxy.set_relay(True)
        self.assertTrue(proxy.relay_enabled())

    def test_status_carries_relay(self):
        self.assertIn("relay", proxy.status())

    # -- the switch + the built-in account (2026-09 fetch fixes) ---------------

    def test_house_account_is_off_until_switched_on(self):
        proxy.set_house("houseacct", "housepw")
        st = proxy.status()
        self.assertTrue(st["available"])
        self.assertEqual(st["source"], "house")
        self.assertFalse(st["switch"])
        self.assertFalse(st["enabled"])
        self.assertIsNone(proxy.proxy_url())          # default OFF
        proxy.set_enabled(True)
        self.assertIn("houseacct-1:housepw", proxy.proxy_url())
        self.assertTrue(proxy.status()["enabled"])
        proxy.set_enabled(False)
        self.assertIsNone(proxy.proxy_url())

    def test_house_file_is_not_plaintext(self):
        p = proxy.set_house("stationacct", "s3cretpw")
        raw = p.read_text()
        self.assertNotIn("stationacct", raw)
        self.assertNotIn("s3cretpw", raw)
        self.assertEqual(proxy._house()["username"], "stationacct")

    def test_house_status_never_names_the_account(self):
        proxy.set_house("stationacct", "s3cretpw")
        blob = json.dumps(proxy.status())
        self.assertNotIn("stationacct", blob)
        self.assertNotIn("s3cretpw", blob)

    def test_own_account_beats_house_and_saving_switches_on(self):
        proxy.set_house("houseacct", "housepw")
        proxy.set_config("mine", "minepw")
        self.assertEqual(proxy.status()["source"], "file")
        self.assertTrue(proxy.status()["enabled"])     # typing it in = on
        self.assertIn("mine-1:minepw", proxy.proxy_url())
        proxy.set_config("", "")                       # own account removed
        self.assertEqual(proxy.status()["source"], "house")
        # …and the switch goes OFF: traffic never lands on the built-in
        # account without the person choosing it
        self.assertFalse(proxy.status()["switch"])
        self.assertIsNone(proxy.proxy_url())

    def test_legacy_file_with_credentials_counts_as_on(self):
        # a proxy.json written before the switch existed
        (Path(self.td.name) / "proxy.json").write_text(
            json.dumps({"username": "old", "password": "pw"}))
        self.assertTrue(proxy.switch_on())
        self.assertIn("old-1:pw", proxy.proxy_url())

    def test_switch_survives_relay_changes(self):
        proxy.set_house("h", "p")
        proxy.set_enabled(True)
        proxy.set_relay(False)
        self.assertTrue(proxy.switch_on())
        self.assertFalse(proxy.relay_enabled())

    def test_test_without_account_says_so(self):
        r = proxy.test()
        self.assertFalse(r["ok"])
        self.assertIn("no proxy account", r["error"])


WATCH_HTML = (
    'noise "captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext'
    '?v=x\\u0026lang=en","languageCode":"en","name":{"simpleText":"English"}},'
    '{"baseUrl":"https://www.youtube.com/api/timedtext?v=x\\u0026lang=en'
    '\\u0026kind=asr","languageCode":"en","kind":"asr"},'
    '{"baseUrl":"https://www.youtube.com/api/timedtext?v=x\\u0026lang=de",'
    '"languageCode":"de"}],"audioTracks" more noise')


class TestCaptionTracks(unittest.TestCase):
    def test_parse_tracks(self):
        t = parse_tracks(WATCH_HTML)
        self.assertEqual(len(t), 3)
        self.assertEqual(t[0]["lang"], "en")
        self.assertIn("&lang=en", t[0]["base_url"])      # \\u0026 unescaped
        self.assertEqual(t[1]["kind"], "asr")

    def test_pick_prefers_manual_english(self):
        t = parse_tracks(WATCH_HTML)
        best = pick_track(t, "en")
        self.assertEqual((best["lang"], best["kind"]), ("en", "manual"))

    def test_pick_falls_back_to_auto_then_other(self):
        t = [x for x in parse_tracks(WATCH_HTML) if x["kind"] == "asr"
             or x["lang"] == "de"]
        self.assertEqual(pick_track(t, "en")["kind"], "asr")
        self.assertEqual(pick_track([t[-1]], "en")["lang"], "de")

    def test_no_tracks(self):
        self.assertEqual(parse_tracks("<html>nothing here</html>"), [])
        self.assertIsNone(pick_track([], "en"))

    def test_video_id_forms(self):
        for s in ("https://www.youtube.com/watch?v=jNQXAC9IVRw",
                  "https://youtu.be/jNQXAC9IVRw?t=3",
                  "https://www.youtube.com/live/jNQXAC9IVRw",
                  "jNQXAC9IVRw"):
            self.assertEqual(video_id(s), "jNQXAC9IVRw", s)
        self.assertIsNone(video_id("https://example.com/x"))


if __name__ == "__main__":
    unittest.main()
