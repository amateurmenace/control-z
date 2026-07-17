import unittest

from czcore.ytdlp import _PROG, asset_name, newer
from grabber.civicclerk import events_url, parse_events
from grabber.zoomshare import SHARE_RE, _page_data, _safe_name, is_zoom_share


class TestYtdlpManage(unittest.TestCase):
    def test_asset_per_platform(self):
        self.assertEqual(asset_name("darwin"), "yt-dlp_macos")
        self.assertEqual(asset_name("win32"), "yt-dlp.exe")
        self.assertEqual(asset_name("linux", "x86_64"), "yt-dlp_linux")
        self.assertEqual(asset_name("linux", "aarch64"), "yt-dlp_linux_aarch64")

    def test_nightly_version_compare_is_numeric(self):
        self.assertTrue(newer("2026.07.15.232840", "2026.7.9.010101"))
        self.assertFalse(newer("2026.07.15", "2026.07.15"))
        self.assertTrue(newer("2026.07.15", None))  # nothing installed yet

    def test_progress_line_parse(self):
        m = _PROG.search("[download]  45.2% of   50.25MiB at 2.05MiB/s ETA 00:23")
        self.assertAlmostEqual(float(m.group(1)), 45.2)
        self.assertIsNone(_PROG.search("[info] Writing video metadata"))


ZOOMGOV_EVENT = {
    "id": 9, "eventName": "Select Board Regular Meeting",
    "categoryName": "Select Board", "startDateTime": "2026-05-12T21:30:00Z",
    "externalMediaUrl": "https://brooklinema.zoomgov.com/rec/share/abc.def",
    "agendaName": "agenda", "youtubeVideoId": "",
}
YT_EVENT = {
    "id": 10, "eventName": "School Committee", "eventDate": "2026-05-01",
    "youtubeVideoId": "jNQXAC9IVRw",
}


class TestCivicClerk(unittest.TestCase):
    def test_events_url_shape(self):
        u = events_url("BrooklineMA", "2026-01-01", "2026-02-01")
        self.assertIn("brooklinema.api.civicclerk.com/v1/Events", u)
        self.assertIn("2026-01-01T00:00:00Z", u)
        self.assertNotIn(" ", u)

    def test_zoomgov_links_count_as_video(self):
        evs = parse_events({"value": [ZOOMGOV_EVENT]})
        links = evs[0]["links"]
        self.assertTrue(any(l["videoish"] for l in links))
        self.assertEqual(evs[0]["name"], "Select Board Regular Meeting")

    def test_bare_youtube_id_becomes_a_link(self):
        evs = parse_events({"value": [YT_EVENT]})
        urls = [l["url"] for l in evs[0]["links"]]
        self.assertIn("https://www.youtube.com/watch?v=jNQXAC9IVRw", urls)

    def test_garbage_payload_yields_no_events(self):
        self.assertEqual(parse_events({"weird": True}), [])
        self.assertEqual(parse_events({"value": ["not-a-dict", 42]}), [])


class TestZoomShare(unittest.TestCase):
    def test_share_url_matching(self):
        self.assertTrue(is_zoom_share(
            "https://brooklinema.zoomgov.com/rec/share/tok.en?startTime=1"))
        self.assertTrue(is_zoom_share("https://us02web.zoom.us/rec/play/abc"))
        self.assertFalse(is_zoom_share("https://youtube.com/watch?v=x"))
        self.assertFalse(is_zoom_share("https://zoom.example.com/rec/share/x"))

    def test_page_data_reads_the_quoted_fields(self):
        html = "meetingId: 'abc.def',\n fileId: '',\n"
        self.assertEqual(_page_data(html, "meetingId"), "abc.def")
        self.assertEqual(_page_data(html, "fileId"), "")
        self.assertIsNone(_page_data(html, "missing"))

    def test_safe_name_strips_the_dangerous(self):
        self.assertEqual(_safe_name("Select Board: 7/15 <LIVE>"),
                         "Select Board 715 LIVE")
        self.assertLessEqual(len(_safe_name("x" * 400)), 120)


if __name__ == "__main__":
    unittest.main()
