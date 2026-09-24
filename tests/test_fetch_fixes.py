"""The 2026-09 desk fixes: YouTube's caption route, fetches that can't lose
the video to a caption 429, the permanent job history, the Downloads
folder, honest cancels, and the kit folder."""

import json
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from czcore import captions as ct
from czcore import ytdlp


# -- the caption route -----------------------------------------------------------

PLAYER_OK = {
    "playabilityStatus": {"status": "OK"},
    "videoDetails": {"videoId": "8e2_uEe30pU", "title": "Select Board",
                     "author": "BIG", "lengthSeconds": "600",
                     "shortDescription": "0:00 Call to order"},
    "captions": {"playerCaptionsTracklistRenderer": {"captionTracks": [
        {"baseUrl": "https://www.youtube.com/api/timedtext?v=x&lang=en&kind=asr&fmt=srv3",
         "languageCode": "en", "kind": "asr",
         "name": {"runs": [{"text": "English (auto-generated)"}]}},
        {"baseUrl": "https://www.youtube.com/api/timedtext?v=x&lang=en",
         "languageCode": "en", "name": {"simpleText": "English"}},
    ]}},
}

WATCH = ('<html>"INNERTUBE_API_KEY":"AIzaFAKEKEY" "uploadDate":"2026-08-25T19:00:00" '
         '"videoDetails":{"videoId":"8e2_uEe30pU","title":"Select Board"},'
         '"annotations" </html>')

VTT = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n"
       "good evening &gt;&gt; everyone\n")


class _Resp:
    def __init__(self, body):
        self.body = body.encode() if isinstance(body, str) else body

    def read(self):
        return self.body


class FakeOpener:
    """Routes requests by URL; records what was asked."""

    def __init__(self, player=PLAYER_OK, vtt=VTT, xml=None, fail=None):
        self.player, self.vtt, self.xml, self.fail = player, vtt, xml, fail
        self.urls = []

    def open(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if self.fail and self.fail[0] in url:
            raise urllib.error.HTTPError(url, self.fail[1], "x", {}, None)
        if "/watch?" in url:
            return _Resp(WATCH)
        if "/youtubei/v1/player" in url:
            return _Resp(json.dumps(self.player))
        if "timedtext" in url and "fmt=vtt" in url:
            return _Resp(self.vtt)
        if "timedtext" in url:
            return _Resp(self.xml or "")
        raise AssertionError(url)


class TestCaptionRoute(unittest.TestCase):
    def fetch(self, opener, **kw):
        with mock.patch.object(ct, "_opener", lambda proxy: opener):
            return ct.fetch_vtt("https://www.youtube.com/watch?v=8e2_uEe30pU",
                                **kw)

    def test_player_route_prefers_manual_and_strips_fmt(self):
        op = FakeOpener()
        got = self.fetch(op)
        self.assertEqual(got["route"], "player API")
        self.assertEqual(got["track"]["kind"], "manual")
        self.assertTrue(got["vtt"].startswith("WEBVTT"))
        cap = [u for u in op.urls if "timedtext" in u][0]
        self.assertEqual(cap.count("fmt="), 1)             # srv3 stripped
        self.assertIn("key=AIzaFAKEKEY", [u for u in op.urls if "player" in u][0])

    def test_meta_rides_along_with_upload_date(self):
        got = self.fetch(FakeOpener())
        self.assertEqual(got["meta"]["title"], "Select Board")
        self.assertEqual(got["meta"]["upload_date"], "20260825")
        self.assertEqual(got["meta"]["duration"], 600)

    def test_xml_fallback_when_vtt_is_empty(self):
        xml = ('<?xml version="1.0"?><transcript><text start="1.5" dur="2">'
               'It&amp;#39;s the <i>vote</i></text></transcript>')
        got = self.fetch(FakeOpener(vtt="", xml=xml))
        self.assertIn("It's the vote", got["vtt"])
        self.assertIn("00:00:01.500 --> 00:00:03.500", got["vtt"])

    def test_token_walled_track_is_not_called_blocked(self):
        player = json.loads(json.dumps(PLAYER_OK))
        for t in player["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"]:
            t["baseUrl"] += "&exp=xpe"
        with self.assertRaises(ct.CaptionError) as cm:
            self.fetch(FakeOpener(player=player))
        self.assertFalse(cm.exception.blocked)     # a proxy wouldn't help

    def test_bot_wall_is_blocked(self):
        player = {"playabilityStatus": {
            "status": "LOGIN_REQUIRED",
            "reason": "Sign in to confirm you're not a bot"}}
        with self.assertRaises(ct.CaptionError) as cm:
            self.fetch(FakeOpener(player=player))
        self.assertTrue(cm.exception.blocked)
        self.assertEqual(cm.exception.meta.get("title"), "Select Board")

    def test_429_is_blocked(self):
        with self.assertRaises(ct.CaptionError) as cm:
            self.fetch(FakeOpener(fail=("timedtext", 429)))
        self.assertTrue(cm.exception.blocked)
        self.assertEqual(cm.exception.kind, "rate_limited")

    def test_no_tracks_is_final_not_blocked(self):
        player = {"playabilityStatus": {"status": "OK"},
                  "videoDetails": {"title": "x"}}
        with self.assertRaises(ct.CaptionError) as cm:
            self.fetch(FakeOpener(player=player))
        self.assertEqual(cm.exception.kind, "no_captions")
        self.assertFalse(cm.exception.blocked)

    def test_xml_segments_keep_styled_words(self):
        segs = ct.xml_to_segments(
            '<transcript><text start="0" dur="1">a <b>bold</b> move'
            '</text><text start="2">x</text></transcript>')
        self.assertEqual(segs[0]["text"], "a bold move")
        self.assertEqual(segs[1]["end"], 4.0)          # missing dur → 2 s

    def test_age_gate_and_private_are_not_blocked(self):
        for reason in ("This video may be inappropriate for some users.",
                       "Private video"):
            player = {"playabilityStatus": {"status": "LOGIN_REQUIRED",
                                            "reason": reason}}
            with self.assertRaises(ct.CaptionError) as cm:
                self.fetch(FakeOpener(player=player))
            self.assertFalse(cm.exception.blocked, reason)   # no proxy opens it
            self.assertEqual(cm.exception.kind, "unavailable")

    def test_video_id_only_for_youtube_hosts(self):
        self.assertEqual(ct.video_id("https://m.youtube.com/live/jNQXAC9IVRw"),
                         "jNQXAC9IVRw")
        self.assertIsNone(ct.video_id(
            "https://www.facebook.com/watch/?v=1234567890123456"))
        self.assertIsNone(ct.video_id("https://town.gov/live/council-meeting-2026"))

    def test_player_tracks_read_runs_names(self):
        tr = ct.player_tracks(PLAYER_OK)
        self.assertEqual(tr[0]["name"], "English (auto-generated)")
        self.assertEqual(tr[1]["name"], "English")


class _Flaky:
    """An opener that raises the queued errors first, then answers."""

    def __init__(self, *errors):
        self.errors, self.calls = list(errors), 0

    def open(self, req, timeout=None):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return _Resp("ok")


def _tunnel(code="502 Bad Gateway"):
    return urllib.error.URLError(OSError(f"Tunnel connection failed: {code}"))


class TestProxyHiccup(unittest.TestCase):
    """The residential exit drops → CONNECT 502. Seen live on the built-in
    account; one quiet retry, then it's an honest network failure."""

    def read(self, op):
        req = urllib.request.Request("https://www.youtube.com/watch?v=x")
        with mock.patch.object(ct, "_HICCUP_PAUSE", 0):
            return ct._read(op, req, 5, "through the proxy", "watch page")

    def test_one_hiccup_is_retried_quietly(self):
        op = _Flaky(_tunnel())
        self.assertEqual(self.read(op), "ok")
        self.assertEqual(op.calls, 2)

    def test_two_hiccups_are_a_network_failure_not_a_block(self):
        op = _Flaky(_tunnel("503 Service Unavailable"), _tunnel())
        with self.assertRaises(ct.CaptionError) as cm:
            self.read(op)
        self.assertEqual(op.calls, 2)
        self.assertEqual(cm.exception.kind, "network")
        self.assertFalse(cm.exception.blocked)

    def test_other_failures_are_not_retried(self):
        for err in (urllib.error.URLError("nodename nor servname provided"),
                    _tunnel("407 Proxy Authentication Required")):
            op = _Flaky(err)
            with self.assertRaises(ct.CaptionError):
                self.read(op)
            self.assertEqual(op.calls, 1, err)


# -- the quality chooser: what a video really offers ------------------------------

def _yt_info():
    """A YouTube-shaped probe: h264 to 1080p (each rung twice — a sized
    https file and an unsized HLS twin with a higher bitrate), AV1/VP9 above
    it, a dubbed video's audio in two languages, and a storyboard."""
    F = [{"format_id": "sb0", "vcodec": "none", "acodec": "none", "ext": "mhtml"}]

    def v(fid, h, vc, size, tbr, proto="https", fps=24, ext="mp4"):
        F.append({"format_id": fid, "height": h, "vcodec": vc, "acodec": "none",
                  "ext": ext, "filesize": size, "tbr": tbr, "fps": fps,
                  "protocol": proto})

    def a(fid, ext, size, abr, lang_pref):
        F.append({"format_id": fid, "vcodec": "none", "acodec": "mp4a.40.2",
                  "ext": ext, "filesize": size, "abr": abr,
                  "language_preference": lang_pref})

    v("134", 360, "avc1.4d401e", 11_000_000, 380)
    v("136", 720, "avc1.64001f", 43_000_000, 1480)
    v("232", 720, "avc1.64001f", None, 2450, proto="m3u8_native")
    v("137", 1080, "avc1.640028", 79_000_000, 2716)
    v("270", 1080, "avc1.640028", None, 5152, proto="m3u8_native")
    v("400", 1440, "av01.0.12M.08", 150_000_000, 5000)
    v("401", 2160, "av01.0.12M.08", 300_000_000, 10000)
    v("313", 2160, "vp9", 280_000_000, 9000, ext="webm")
    a("140-0", "m4a", 3_777_507, 129, -1)        # a dub
    a("140-20", "m4a", 3_776_005, 129, 10)       # the original
    a("251", "webm", 3_900_000, 135, -1)
    return {"duration": 233, "formats": F}


class TestQualityOptions(unittest.TestCase):
    def test_the_ladder_is_what_you_would_really_get(self):
        opts = ytdlp.quality_options(_yt_info())
        self.assertEqual([o["label"] for o in opts],
                         ["1080p", "720p", "360p", "audio only"])
        # 4K/1440p exist only as AV1/VP9 — the h264 ladder can't reach them,
        # so they collapse into 1080p instead of being promised
        self.assertEqual([o["quality"] for o in opts], ["1080", "720", "480", "audio"])

    def test_sizes_follow_the_file_yt_dlp_takes(self):
        top = ytdlp.quality_options(_yt_info())[0]
        # the SIZED https 1080p (not its unsized HLS twin), plus the
        # original-language audio — measured: 83.0 MB estimate vs 83.0 MB file
        self.assertEqual(top["bytes"], 79_000_000 + 3_776_005)

    def test_probe_reports_the_ceiling_above_the_ladder(self):
        with mock.patch.object(ytdlp, "_run_json", return_value=[
                {**_yt_info(), "id": "x", "title": "t", "webpage_url": "u"}]):
            got = ytdlp.probe_url("https://www.youtube.com/watch?v=x")
        self.assertEqual(got["max_height"], 2160)
        self.assertEqual(got["options"][0]["label"], "1080p")
        self.assertFalse(got["live"])

    def test_size_from_bitrate_when_the_site_wont_say(self):
        info = {"duration": 100, "formats": [
            {"format_id": "hls-720", "height": 720, "vcodec": "avc1.64001f",
             "acodec": "mp4a.40.2", "ext": "mp4", "tbr": 2000, "fps": 60}]}
        (o,) = ytdlp.quality_options(info)
        self.assertEqual(o["label"], "720p60")
        self.assertEqual(o["bytes"], 25_000_000)          # 2000 kbit/s × 100 s

    def test_a_bare_file_link_is_as_published(self):
        info = {"formats": [{"format_id": "0", "ext": "mp4",
                             "url": "https://town.gov/meeting.mp4"}]}
        self.assertEqual(ytdlp.quality_options(info), [
            {"quality": "best", "label": "as published", "height": 0,
             "bytes": None}])

    def test_unknown_height_passes_every_cap(self):
        # a strict [height<=720] fails a format whose height is unknown —
        # every rung but "best" then errored "Requested format is not available"
        self.assertIn("[height<=?720]", ytdlp.FORMATS["720"])
        self.assertNotIn("[height<=720]", ytdlp.FORMATS["720"])


# -- yt-dlp: search rows, blocked sentences, cancel cleanup ----------------------

class TestYtdlp(unittest.TestCase):
    def test_search_drops_channels_and_playlists(self):
        rows = [
            {"id": "UCtl_u3j2UDQMXK-G6QD5g_w", "ie_key": "YoutubeTab",
             "url": "https://www.youtube.com/channel/UCtl_u3j2UDQMXK-G6QD5g_w"},
            {"id": "PLabcdefghijklmnop", "url": "https://www.youtube.com/playlist?list=PL"},
            {"id": "8e2_uEe30pU", "ie_key": "Youtube",
             "url": "https://www.youtube.com/watch?v=8e2_uEe30pU"},
        ]
        self.assertEqual([r["id"] for r in rows if ytdlp.is_video(r)],
                         ["8e2_uEe30pU"])

    def test_blocked_sentences_name_the_proxy(self):
        why = "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests"
        self.assertTrue(ytdlp.looks_blocked(why))
        self.assertIn("proxy", ytdlp._explain(why))
        self.assertFalse(ytdlp.looks_blocked("ERROR: Video unavailable"))
        self.assertNotIn("proxy", ytdlp._explain("ERROR: Video unavailable"))

    def test_sweep_partials_only_removes_this_videos_fragments(self):
        with tempfile.TemporaryDirectory() as td:
            import os
            d = Path(td)
            t0 = time.time() + 5          # everything "before" this run
            old = d / "earlier [abcdefghijk].mp4.part"
            old.write_text("x")
            os.utime(old, (t0 - 100, t0 - 100))
            keep = d / "finished [abcdefghijk].mp4"
            keep.write_text("x")
            stranger = d / "firefox-download.zip.part"   # a shared Downloads
            frag = d / "meeting [abcdefghijk].f137.mp4"
            part = d / "meeting [abcdefghijk].mp4.part"
            info = d / "meeting [abcdefghijk].info.json"
            for f in (frag, part, info, stranger):
                f.write_text("x")
                os.utime(f, (t0, t0))
            ytdlp._sweep_partials(d, t0, "")           # no id → touch nothing
            self.assertTrue(part.exists())
            ytdlp._sweep_partials(d, t0, "abcdefghijk")
            self.assertTrue(old.exists())       # not this run's
            self.assertTrue(keep.exists())      # a real file
            self.assertTrue(stranger.exists())  # not this video's
            self.assertFalse(frag.exists())
            self.assertFalse(part.exists())
            self.assertFalse(info.exists())     # its video never landed

    def test_js_runtime_found_or_none(self):
        rt = ytdlp.js_runtime()
        self.assertTrue(rt is None or (rt[0] in ("deno", "node", "bun")
                                       and Path(rt[1]).exists()))
        args = ytdlp._js_args()
        self.assertTrue(args == [] or args[0] == "--js-runtimes")


class TestSidecarCaptions(unittest.TestCase):
    def test_caption_failure_never_raises(self):
        with tempfile.TemporaryDirectory() as td:
            v = Path(td) / "meeting [8e2_uEe30pU].mp4"
            v.write_bytes(b"x")
            err = ct.CaptionError("YouTube is rate-limiting", blocked=True,
                                  kind="rate_limited")
            with mock.patch.object(ct, "fetch_vtt", side_effect=err), \
                    mock.patch.object(ytdlp, "fetch_captions",
                                      side_effect=RuntimeError("429")):
                r = ytdlp.sidecar_captions(
                    "https://www.youtube.com/watch?v=8e2_uEe30pU", v)
            self.assertEqual(r["captions"], "failed")
            self.assertTrue(r["blocked"])

    def test_captions_land_beside_the_video(self):
        with tempfile.TemporaryDirectory() as td:
            v = Path(td) / "meeting [8e2_uEe30pU].mp4"
            v.write_bytes(b"x")
            with mock.patch.object(ct, "fetch_vtt", return_value={
                    "vtt": VTT, "route": "player API"}):
                r = ytdlp.sidecar_captions(
                    "https://www.youtube.com/watch?v=8e2_uEe30pU", v)
            self.assertEqual(r["captions"], "fetched")
            self.assertTrue((Path(td) / "meeting [8e2_uEe30pU].en.vtt").exists())


# -- the job history + honest cancels ------------------------------------------

def wait_for(pred, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return False


class TestJobHistory(unittest.TestCase):
    def test_history_outlives_clear_finished(self):
        from czcore.appshell.jobs import JobManager
        with tempfile.TemporaryDirectory() as td:
            jm = JobManager(db_path=str(Path(td) / "jobs.db"), queued=True)
            a = jm.start("render", lambda j: {"out": "/tmp/reel.mp4"},
                         tool="highlighter", label="reel one")
            self.assertTrue(wait_for(lambda: a.status == "done"))
            time.sleep(0.1)
            self.assertEqual(jm.clear_finished(), 1)
            self.assertEqual(len(jm.list()), 0)
            h = jm.history()
            self.assertEqual(h["total"], 1)
            self.assertEqual(h["rows"][0]["label"], "reel one")
            self.assertEqual(h["rows"][0]["result"]["out"], "/tmp/reel.mp4")

    def test_history_backfills_and_filters(self):
        from czcore.appshell.jobs import JobManager
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "jobs.db")
            jm = JobManager(db_path=db, queued=True)
            ok = jm.start("x", lambda j: 1, tool="grabber", label="fetch a")

            def boom(j):
                raise RuntimeError("nope")
            bad = jm.start("x", boom, tool="publisher", label="kit b")
            self.assertTrue(wait_for(lambda: bad.status == "error"
                                     and ok.status == "done"))
            time.sleep(0.1)
            jm2 = JobManager(db_path=db, queued=True)   # a relaunch
            self.assertEqual(jm2.history()["total"], 2)
            self.assertEqual(jm2.history(tool="grabber")["total"], 1)
            self.assertEqual(jm2.history(status="error")["rows"][0]["label"], "kit b")
            self.assertEqual(jm2.history(q="kit")["total"], 1)

    def test_legacy_cancelled_sentence_reads_as_cancelled(self):
        from czcore.appshell.jobs import JobManager
        jm = JobManager()

        def loop(j):
            while True:
                if j.cancel_requested:
                    raise RuntimeError("cancelled")   # the older render loops
                time.sleep(0.01)
        job = jm.start("render", loop)
        time.sleep(0.05)
        jm.cancel(job.id)
        self.assertTrue(wait_for(lambda: job.status in ("cancelled", "error")))
        self.assertEqual(job.status, "cancelled")
        self.assertIsNone(job.error)


# -- where downloads land -----------------------------------------------------------

class TestDownloadsFolder(unittest.TestCase):
    def setUp(self):
        from czcore import paths
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        p = mock.patch.object(paths, "support_dir",
                              lambda sub="": Path(self.td.name))
        p.start()
        self.addCleanup(p.stop)
        self.paths = paths

    def test_default_is_the_downloads_folder_unconfirmed(self):
        r = self.paths.downloads_root()
        self.assertEqual(r, Path.home() / "Downloads" / "Civic Media Studio")
        self.assertFalse(self.paths.downloads_chosen())

    def test_choice_and_confirmation_persist(self):
        target = Path(self.td.name) / "fetches"
        self.paths.set_downloads_root(str(target))
        self.assertEqual(self.paths.downloads_root(), target)
        self.assertTrue(self.paths.downloads_chosen())
        self.paths.set_downloads_root("")              # back to default…
        self.assertTrue(self.paths.downloads_chosen())  # …still a choice
        self.assertEqual(self.paths.downloads_root().name, "Civic Media Studio")

    def test_media_root_and_downloads_share_a_file_without_clobbering(self):
        self.paths.set_downloads_root(str(Path(self.td.name) / "dl"))
        self.paths.set_media_root(str(Path(self.td.name) / "out"))
        self.assertEqual(self.paths.downloads_root().name, "dl")
        self.paths.set_media_root("")
        self.assertEqual(self.paths.downloads_root().name, "dl")


# -- the full recording vs its clips --------------------------------------------------

ROLLING_VTT = ("WEBVTT\n\n"
               "00:00:01.000 --> 00:00:03.000\n \nGood<00:00:01.500><c> evening</c>\n\n"
               "00:00:03.000 --> 00:00:03.010\nGood evening\n \n\n"
               "00:00:03.010 --> 00:00:05.000\nGood evening\nthe<00:00:03.500><c> motion</c>\n")


class TestCaptionReread(unittest.TestCase):
    """Words read from captions by the old parse_vtt doubled every rolling
    line; they re-read their caption file once. Scribe's words never do."""

    def test_old_caption_words_reread_once_and_scribe_is_left_alone(self):
        from czcore.moments import VTT_PARSE_V
        from suite.tools import highlighter as hl
        with tempfile.TemporaryDirectory() as td:
            sess = Path(td) / "abcdefghijk"
            sess.mkdir()
            (sess / "meeting.en.vtt").write_text(ROLLING_VTT)
            doubled = {"version": 1, "model": "captions:meeting.en.vtt",
                       "segments": [{"start": 1, "end": 3, "text": "Good evening"}] * 2}
            side = sess / "meeting.scribe.json"
            side.write_text(json.dumps(doubled))
            t, origin = hl._load_transcript(str(sess))
            self.assertEqual(origin, "captions")
            self.assertEqual([s["text"] for s in t["segments"]], ["Good evening", "the motion"])
            self.assertEqual(json.loads(side.read_text())["parse_v"], VTT_PARSE_V)

            scribe = {"version": 1, "model": "large-v3-turbo",
                      "segments": [{"start": 1, "end": 3, "text": "Scribe heard this"}]}
            side.write_text(json.dumps(scribe))
            t, origin = hl._load_transcript(str(sess))
            self.assertEqual(origin, "scribe")
            self.assertEqual(t["segments"][0]["text"], "Scribe heard this")

    def test_a_translation_beside_it_never_replaces_the_words(self):
        # the Highlighter writes meeting.<language>.srt beside the meeting;
        # "arabic" sorts before "en" — the re-read must take the file the
        # words came FROM, and a fresh read must take the English one
        from suite.tools import highlighter as hl
        with tempfile.TemporaryDirectory() as td:
            sess = Path(td) / "abcdefghijk"
            sess.mkdir()
            (sess / "meeting.en.vtt").write_text(ROLLING_VTT)
            (sess / "meeting.arabic.srt").write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nمساء الخير\n")
            side = sess / "meeting.scribe.json"
            side.write_text(json.dumps({"version": 1, "model": "captions:meeting.en.vtt",
                                        "segments": [{"start": 1, "end": 3, "text": "Good evening"}] * 2}))
            t, _ = hl._load_transcript(str(sess))
            self.assertEqual([s["text"] for s in t["segments"]], ["Good evening", "the motion"])
            side.unlink()
            self.assertEqual(hl._captions_for(sess).name, "meeting.en.vtt")
            t, _ = hl._load_transcript(str(sess))
            self.assertEqual(t["segments"][0]["text"], "Good evening")

    def test_words_with_nothing_to_reread_stand(self):
        # a transcript borrowed from its twin (no caption file beside it)
        # keeps its words — it is never swapped for another caption file
        from suite.tools import highlighter as hl
        with tempfile.TemporaryDirectory() as td:
            sess = Path(td) / "abcdefghijk"
            sess.mkdir()
            (sess / "meeting.spanish.srt").write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nBuenas noches\n")
            kept = {"version": 1, "model": "captions:meeting.en.vtt",
                    "segments": [{"start": 1, "end": 3, "text": "Good evening"}]}
            (sess / "meeting.scribe.json").write_text(json.dumps(kept))
            t, origin = hl._load_transcript(str(sess))
            self.assertEqual((origin, t["segments"][0]["text"]), ("captions", "Good evening"))
            self.assertNotIn("parse_v", json.loads((sess / "meeting.scribe.json").read_text()))


class TestFullRecording(unittest.TestCase):
    def test_only_the_full_recording_counts(self):
        from suite.tools import highlighter as hl
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            names = ["Mtg [abcdefghijk].mp4", "Mtg [abcdefghijk] [600-630].mp4",
                     "Mtg [abcdefghijk].reel.mp4"]
            for n in names:
                (d / n).write_bytes(b"x" * (999 if "reel" in n else 10))
            with mock.patch.object(hl, "fetched_videos", lambda: list(d.iterdir())):
                self.assertEqual(hl.full_video_for("abcdefghijk").name, names[0])

    def test_a_section_clip_never_borrows_the_meetings_words(self):
        from suite.tools import highlighter as hl
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            sess = d / ".meetings" / "abcdefghijk"
            sess.mkdir(parents=True)
            (sess / "meeting.scribe.json").write_text(json.dumps(
                {"model": "captions:x", "segments": [
                    {"start": 900.0, "end": 901.0, "text": "meeting time"}]}))
            clip = d / "Mtg [abcdefghijk] [600-630].mp4"
            clip.write_bytes(b"x")
            full = d / "Mtg [abcdefghijk].mp4"
            full.write_bytes(b"x")
            with mock.patch.object(hl, "_meetings_dir", lambda: d / ".meetings"):
                t, _ = hl._load_transcript(str(clip))
                self.assertIsNone(t)                   # its own timeline
                t, _ = hl._load_transcript(str(full))
                self.assertEqual(t["segments"][0]["text"], "meeting time")


class TestFolderChoice(unittest.TestCase):
    def test_bad_folders_are_refused_before_saving(self):
        from suite.tools.settings import usable_folder
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "a-file"
            f.write_text("x")
            self.assertIn("isn't a full folder path", usable_folder("relative/dir"))
            self.assertIn("is a file", usable_folder(str(f)))
            self.assertIsNone(usable_folder(str(Path(td) / "new" / "place")))
            self.assertTrue((Path(td) / "new" / "place").is_dir())


class TestSessionToRecord(unittest.TestCase):
    def test_a_session_folder_goes_to_the_record_as_its_link(self):
        from suite.tools.memory import _session_to_url
        with tempfile.TemporaryDirectory() as td:
            sess = Path(td) / "abcdefghijk"
            sess.mkdir()
            (sess / "meeting.info.json").write_text(json.dumps(
                {"webpage_url": "https://www.youtube.com/watch?v=abcdefghijk"}))
            out = _session_to_url({"path": str(sess), "town": "x"})
            self.assertEqual(out, {"url": "https://www.youtube.com/watch?v=abcdefghijk",
                                   "town": "x"})
            f = Path(td) / "clip.mp4"
            f.write_bytes(b"x")
            self.assertEqual(_session_to_url({"path": str(f)}), {"path": str(f)})


# -- the kit folder -------------------------------------------------------------------

class TestKitFolder(unittest.TestCase):
    def test_renders_inside_the_kit_stay_put(self):
        from publisher import bundle
        with tempfile.TemporaryDirectory() as td:
            kit = {"meta": {"title": "Select Board", "date": "2026-08-25"},
                   "copy": {"origin": "extractive"}, "clips": []}
            kdir = bundle.kit_dir(kit, td)
            self.assertEqual(kdir.name, "2026-08-25-select-board-kit")
            (kdir / "clips").mkdir(parents=True)
            clip = kdir / "clips" / "2026-08-25-select-board-clip01.16x9.mp4"
            clip.write_bytes(b"v")
            outside = Path(td) / "older.16x9.mp4"
            outside.write_bytes(b"v")
            with mock.patch.object(bundle, "transcript_text", lambda s: ""):
                out = bundle.assemble("/nowhere", kit,
                                      [{"path": str(clip), "ratio": "16x9"},
                                       {"path": str(outside), "ratio": "16x9"}],
                                      [], out_root=td)
            self.assertIn(str(clip), out["files"])        # not duplicated
            self.assertEqual(len(list((kdir / "clips").iterdir())), 2)
            self.assertTrue(Path(out["zip"]).exists())
            self.assertTrue((kdir / "copy.md").exists())

    def test_two_meetings_with_one_title_get_two_folders(self):
        from publisher import bundle
        with tempfile.TemporaryDirectory() as td:
            kit = {"meta": {"title": "Select Board", "date": "2026-08-25"}}
            a = bundle.kit_dir(kit, td, "/m/a")
            bundle.claim(a, "/m/a")
            b = bundle.kit_dir(kit, td, "/m/b")
            self.assertNotEqual(a, b)
            bundle.claim(b, "/m/b")
            self.assertEqual(bundle.kit_dir(kit, td, "/m/a"), a)   # stable
            self.assertEqual(bundle.kit_dir(kit, td, "/m/b"), b)


if __name__ == "__main__":
    unittest.main()
