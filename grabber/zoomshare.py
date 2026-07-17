"""Zoom recording share links, resolved with nothing but HTTP.

The original BIG Video Grabber drove a headless Chrome through the share
page. The page is just a shell around four requests, so we make them
directly — same flow yt-dlp uses for zoom.us, extended to **zoomgov.com**
(which yt-dlp doesn't match, and every Massachusetts town on Zoom for
Government needs):

  share URL → cookies + meetingId → share-info JSON → play page → fileId
  → play-info JSON → viewMp4Url (downloaded with the same cookie jar).

Zoom redecorates this flow every year or so; when it breaks, every step
here fails with a sentence naming the step, not a stack trace.
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SHARE_RE = re.compile(
    r"https?://(?P<host>[\w.-]*zoom(?:gov)?\.(?:us|com))/rec(?:ording)?/"
    r"(?:share|play)/(?P<token>[^?#]+)", re.I)


def is_zoom_share(url: str) -> bool:
    return bool(SHARE_RE.match(url or ""))


class _Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, url: str, referer: str = "", timeout: float = 30.0) -> bytes:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, **({"Referer": referer} if referer else {})})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read()


def _page_data(html: str, key: str) -> Optional[str]:
    m = re.search(rf"{key}\s*:\s*'([^']*)'", html)
    return m.group(1) if m else None


def resolve(url: str) -> dict:
    """Share URL -> {"clips": [{url, start_time}], "session", "base", "topic"}.

    Every failure names the step: Zoom redecorates, we say where.
    """
    m = SHARE_RE.match(url)
    if not m:
        raise RuntimeError("that isn't a Zoom recording share link")
    base = f"https://{m.group('host')}"
    s = _Session()
    try:
        html = s.get(url).decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"couldn't open the share page ({e})") from e
    play_url = url
    if "/rec/share/" in url or "/recording/share/" in url:
        meeting_id = _page_data(html, "meetingId")
        if not meeting_id:
            raise RuntimeError("the share page didn't carry a meetingId — "
                               "Zoom changed the page again")
        try:
            info = json.loads(s.get(
                f"{base}/nws/recording/1.0/play/share-info/"
                + urllib.parse.quote(meeting_id, safe=""), referer=url))
            redirect = (info.get("result") or {}).get("redirectUrl")
        except Exception as e:
            raise RuntimeError(f"the share-info call failed ({e})") from e
        if not redirect:
            raise RuntimeError("share-info answered without a redirectUrl — "
                               "the recording may need a passcode")
        play_url = urllib.parse.urljoin(base, redirect)
        html = s.get(play_url, referer=url).decode("utf-8", "replace")
    file_id = _page_data(html, "fileId")
    if not file_id:
        raise RuntimeError("the play page didn't carry a fileId — "
                           "Zoom changed the page again")

    clips: List[dict] = []
    topic = None
    start_time = ""
    for _ in range(30):  # multi-clip recordings chain by nextClipStartTime
        q = urllib.parse.urlencode({
            "canPlayFromShare": "true", "from": "share_recording_detail",
            "continueMode": "true", "componentName": "rec-play",
            **({"startTime": start_time} if start_time else {})})
        try:
            data = json.loads(s.get(
                f"{base}/nws/recording/1.0/play/info/"
                f"{urllib.parse.quote(file_id, safe='')}?{q}",
                referer=play_url))
        except Exception as e:
            raise RuntimeError(f"the play-info call failed ({e})") from e
        r = data.get("result") or {}
        mp4 = r.get("viewMp4Url")
        if not mp4:
            raise RuntimeError("play-info answered without a video URL — the "
                               "recording may be login-gated or expired")
        topic = topic or r.get("meetingTopic") or r.get("topic")
        clips.append({"url": mp4, "start_time": start_time})
        nxt = str(r.get("nextClipStartTime", -1))
        if nxt in ("-1", "", "None") or any(c["start_time"] == nxt for c in clips):
            break
        start_time = nxt
    return {"clips": clips, "session": s, "base": base, "play_url": play_url,
            "topic": topic or "zoom-recording"}


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\s.-]+", "", name).strip().replace("  ", " ")[:120]


def download(url: str, outdir: Path,
             progress: Optional[Callable[[float, str], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None,
             name: str = "") -> dict:
    """Fetch every clip of a share link. Returns {"path", "parts": [...]}.
    name (e.g. the portal's event name) beats Zoom's often-empty topic."""
    res = resolve(url)
    s: _Session = res["session"]
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    parts = []
    n = len(res["clips"])
    for k, clip in enumerate(res["clips"]):
        stem = _safe_name(name) or _safe_name(res["topic"]) or "zoom-recording"
        if n > 1:
            stem += f" part{k + 1}"
        dest = outdir / (stem + ".mp4")
        i = 1
        while dest.exists():
            i += 1
            dest = outdir / (stem + f" ({i}).mp4")
        req = urllib.request.Request(clip["url"], headers={
            "User-Agent": UA, "Referer": res["play_url"]})
        tmp = dest.with_suffix(".part")
        try:
            with s.opener.open(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    if cancelled and cancelled():
                        tmp.unlink(missing_ok=True)
                        raise RuntimeError("cancelled")
                    chunk = r.read(1024 * 512)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if progress and total:
                        frac = (k + got / total) / n
                        progress(frac, f"clip {k + 1}/{n} · "
                                       f"{got // (1024 * 1024)} MB")
        except RuntimeError:
            raise
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"the video download broke mid-stream ({e})") from e
        tmp.replace(dest)
        parts.append(str(dest))
    return {"path": parts[0], "parts": parts, "clips": n}
