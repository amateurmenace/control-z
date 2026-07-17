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
