"""Captions the way the web app gets them: the watch page's own track list.

yt-dlp's player-API caption routes are walled one by one lately (android_vr
lists no tracks, web wants a PO token, tv trips DRM experiments) — but the
watch page still names its captionTracks, and the timedtext URL they carry
still serves VTT… to IPs YouTube trusts. Through the user's residential
proxy this is exactly the path community-highlighter has run on for months.

YouTube's tell for a gated IP is an HTTP 200 with an EMPTY body — this
module refuses to call that success and says what it means instead.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import List, Optional

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_TRACKS = re.compile(r'"captionTracks":(\[.*?\])[,}]')
_VIDEO_ID = re.compile(
    r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})")
_DETAILS = re.compile(r'"videoDetails":\s*({.*?})\s*,\s*"(?:annotations|'
                      r'playerConfig|storyboards|microformat)"', re.S)


def video_id(url_or_id: str) -> Optional[str]:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    m = _VIDEO_ID.search(s)
    return m.group(1) if m else None


def parse_tracks(html: str) -> List[dict]:
    """captionTracks out of a watch page: [{lang, kind, base_url, name}]."""
    m = _TRACKS.search(html)
    if not m:
        return []
    try:
        raw = json.loads(m.group(1))
    except ValueError:
        return []
    out = []
    for t in raw:
        base = str(t.get("baseUrl") or "").replace("\\u0026", "&")
        if not base:
            continue
        out.append({
            "lang": str(t.get("languageCode") or ""),
            "kind": str(t.get("kind") or "manual"),   # "asr" = auto-generated
            "base_url": base,
            "name": str((t.get("name") or {}).get("simpleText")
                        or (t.get("name") or {}).get("runs", [{}])[0].get("text", "")),
        })
    return out


def parse_video_details(html: str) -> dict:
    """Title, duration, channel out of the watch page itself — the same
    HTML the caption fetch already paid for, so the fast path needs no
    second metadata request. Empty dict when the page shape changed."""
    m = _DETAILS.search(html)
    if not m:
        return {}
    try:
        d = json.loads(m.group(1))
    except ValueError:
        return {}
    out = {}
    if d.get("title"):
        out["title"] = str(d["title"])
    if d.get("author"):
        out["uploader"] = str(d["author"])
    if d.get("videoId"):
        out["id"] = str(d["videoId"])
    if d.get("shortDescription"):
        # the description often carries the agenda as timestamp lines —
        # keep it so a fast-path session can show one
        out["description"] = str(d["shortDescription"])[:20000]
    try:
        out["duration"] = int(d.get("lengthSeconds") or 0) or None
    except (TypeError, ValueError):
        pass
    return out


def pick_track(tracks: List[dict], lang: str = "en") -> Optional[dict]:
    """Manual captions in the language beat auto; auto beats other-language
    manual; anything beats nothing."""
    def rank(t: dict):
        exact = t["lang"] == lang or t["lang"].startswith(lang + "-")
        manual = t["kind"] != "asr"
        return (exact, manual)

    ranked = sorted(tracks, key=rank, reverse=True)
    return ranked[0] if ranked else None


def _opener(proxy: Optional[str]):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def fetch_vtt(url_or_id: str, lang: str = "en",
              proxy: Optional[str] = None, timeout: float = 25.0) -> dict:
    """Watch page → captionTracks → timedtext VTT.

    Returns {"vtt": text, "track": {…}, "meta": {title, duration, uploader}}
    — the metadata rides along free because the watch page was already
    fetched. Raises RuntimeError with a sentence for every distinct way this
    fails — including YouTube's empty-200 gate, which names the Settings fix.
    """
    vid = video_id(url_or_id)
    if not vid:
        raise RuntimeError("that doesn't look like a YouTube URL or id")
    op = _opener(proxy)
    via = "via your Webshare proxy" if proxy else "from this IP"
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={vid}",
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        html = op.open(req, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"couldn't reach the watch page {via} ({e})") from e
    meta = parse_video_details(html)
    tracks = parse_tracks(html)
    if not tracks:
        # the page answered, so hand the metadata to the caller even though
        # the captions didn't — a session deserves its title either way
        err = RuntimeError("the watch page lists no caption tracks — this "
                           "video has no captions (or the page shape changed)")
        err.meta = meta
        raise err
    track = pick_track(tracks, lang)
    try:
        req = urllib.request.Request(track["base_url"] + "&fmt=vtt",
                                     headers={"User-Agent": UA})
        body = op.open(req, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"the caption fetch broke {via} ({e})") from e
    if not body.strip():
        err = RuntimeError(
            "YouTube answered the caption request with an empty body — its "
            "tell for a gated IP. " +
            ("Even through the proxy; try again (rotating pool) or check the "
             "Webshare account." if proxy else
             "Configure your Webshare proxy in Settings → fetch network and "
             "retry."))
        err.meta = meta
        raise err
    return {"vtt": body, "track": track, "meta": meta}


# -- the community caption service ------------------------------------------

RELAY_URL = "https://community-highlighter.onrender.com/api/transcript"


def fetch_vtt_relay(url: str, relay: str = RELAY_URL,
                    timeout: float = 75.0) -> dict:
    """Captions via the community-highlighter web app's own public transcript
    engine — BIG's deployment, which fetches through its residential proxy.

    This is the zero-setup path for download users: no credentials ship in
    this app and none are needed; the request carries only the public video
    URL. Users who prefer full independence turn it off in Settings, or set
    their own Webshare account. The long timeout is honest: free-tier Render
    cold-starts in ~30 s.
    """
    vid = video_id(url)
    if not vid:
        raise RuntimeError("that doesn't look like a YouTube URL or id")
    body = json.dumps({"url": f"https://www.youtube.com/watch?v={vid}"}).encode()
    req = urllib.request.Request(
        relay, data=body, method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout) \
            .read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # the service answers per-video failures as HTTP errors with a JSON
        # sentence — read it; "didn't answer" would blame the wrong thing
        try:
            detail = json.loads(e.read().decode("utf-8", "replace"))
            detail = detail.get("error") or detail.get("detail") or f"HTTP {e.code}"
        except Exception:
            detail = f"HTTP {e.code}"
        raise RuntimeError("the community caption service couldn't get this "
                           f"one — {detail}") from e
    except Exception as e:
        raise RuntimeError(
            f"the community caption service didn't answer ({e}) — it runs on "
            "a free tier and sleeps; a retry usually lands") from e
    text = resp.strip()
    if text.startswith("WEBVTT"):
        return {"vtt": resp, "track": {"lang": "en", "kind": "relay"}}
    # the service answers errors as JSON sentences — pass the sentence on
    try:
        err = json.loads(text)
        detail = err.get("error") or err.get("detail") or text[:200]
    except ValueError:
        detail = text[:200] or "an empty answer"
    raise RuntimeError(f"the community caption service couldn't get this "
                       f"one — {detail}")
