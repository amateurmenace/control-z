"""Captions straight from YouTube — the player API's own track list.

The route that works (measured 2026-09-23): read the watch page once (the
metadata + the page's innertube key), ask the player API as the ANDROID
client for its captionTracks, fetch the track. The watch page's OWN
captionTracks carry `exp=xpe` now — a proof-of-origin token requirement —
so their timedtext URLs answer 200 with an EMPTY body from ANY address.
That empty body used to be read as "this IP is gated, set up a proxy",
which sent people to fix the wrong thing; it's a token wall, and the
ANDROID client's tracks don't have it. (The same route
youtube-transcript-api runs on.)

A proxy still matters when YouTube really does refuse this computer —
a bot check on the page, a 429, a LOGIN_REQUIRED from the player — and
CaptionError.blocked says exactly when, so the UI can offer the proxy
switch at that moment and not before.
"""

from __future__ import annotations

import html as _html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_TRACKS = re.compile(r'"captionTracks":(\[.*?\])[,}]')
_VIDEO_ID = re.compile(
    r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})")
_DETAILS = re.compile(r'"videoDetails":\s*({.*?})\s*,\s*"(?:annotations|'
                      r'playerConfig|storyboards|microformat)"', re.S)
_API_KEY = re.compile(r'"INNERTUBE_API_KEY":\s*"([\w-]+)"')
_CONSENT = re.compile(r'name="v" value="(.*?)"')
_UPLOAD = re.compile(r'"(?:uploadDate|publishDate)":"(\d{4})-(\d{2})-(\d{2})')

# the client whose caption URLs carry no proof-of-origin requirement
ANDROID_CLIENT = {"clientName": "ANDROID", "clientVersion": "20.10.38"}


class CaptionError(RuntimeError):
    """One caption route's failure, as a sentence — plus what the UI acts on.

    blocked: YouTube is refusing THIS computer (bot check, 429, sign-in
        wall) — the one case a proxy fixes. False for "no captions exist",
        network trouble, or a token wall a proxy can't open.
    meta: whatever the page told us before the failure (title, duration…),
        so a session keeps its name even when its words don't come.
    """

    def __init__(self, msg: str, blocked: bool = False,
                 meta: Optional[dict] = None, kind: str = ""):
        super().__init__(msg)
        self.blocked = blocked
        self.meta = meta or {}
        self.kind = kind


_YT_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


def video_id(url_or_id: str) -> Optional[str]:
    """The YouTube id in a YouTube link (or a bare id) — None for every
    other site. The host check matters: Facebook's `watch/?v=…` or a town
    site's `/live/council-meeting…` would otherwise yield a fake id and
    send the link down YouTube's road instead of yt-dlp's."""
    from urllib.parse import urlparse

    s = (url_or_id or "").strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    try:
        host = (urlparse(s if "//" in s else "https://" + s).hostname or "").lower()
    except ValueError:
        return None
    if not any(host == h or host.endswith("." + h) for h in _YT_HOSTS):
        return None
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


def player_tracks(player: dict) -> List[dict]:
    """captionTracks out of a player-API answer: [{lang, kind, base_url,
    name}] — the same shape parse_tracks gives for a watch page."""
    raw = (((player.get("captions") or {})
            .get("playerCaptionsTracklistRenderer") or {})
           .get("captionTracks") or [])
    out = []
    for t in raw:
        base = str(t.get("baseUrl") or "")
        if not base:
            continue
        name = t.get("name") or {}
        out.append({
            "lang": str(t.get("languageCode") or ""),
            "kind": str(t.get("kind") or "manual"),
            "base_url": base,
            "name": str(name.get("simpleText")
                        or (name.get("runs") or [{}])[0].get("text", "")),
        })
    return out


def player_meta(player: dict) -> dict:
    """Title / channel / length / description from the player answer's
    videoDetails — the same keys parse_video_details returns."""
    d = player.get("videoDetails") or {}
    out = {}
    for src, dst in (("title", "title"), ("author", "uploader"),
                     ("videoId", "id")):
        if d.get(src):
            out[dst] = str(d[src])
    if d.get("shortDescription"):
        out["description"] = str(d["shortDescription"])[:20000]
    try:
        out["duration"] = int(d.get("lengthSeconds") or 0) or None
    except (TypeError, ValueError):
        pass
    return out


def xml_to_segments(xml_text: str) -> List[dict]:
    """YouTube's timedtext XML (<text start dur>…</text>) -> [{start, end,
    text}]. The text arrives entity-escaped twice over (&amp;#39;); the XML
    parser takes one layer and html.unescape the other."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    segs = []
    for el in root.iter("text"):
        try:
            start = float(el.attrib.get("start", "0"))
            dur = float(el.attrib.get("dur", "0") or 0)
        except ValueError:
            continue
        # itertext: styling tags (<i>, <b>) are child elements to the
        # parser — .text alone would drop every word inside them
        text = _html.unescape("".join(el.itertext()))
        text = re.sub(r"<[^>]*>", "", text).replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            segs.append({"start": start, "end": start + (dur or 2.0),
                         "text": text})
    return segs


def _vtt_ts(s: float) -> str:
    s = max(0.0, s)
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}.{int(round((s % 1) * 1000)) % 1000:03d}"


def segments_to_vtt(segs: List[dict]) -> str:
    cues = [f"{_vtt_ts(s['start'])} --> {_vtt_ts(s['end'])}\n{s['text']}"
            for s in segs]
    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"


# A residential exit that drops mid-session makes the proxy's CONNECT answer
# 502/503/504 — the gateway's hiccup, not YouTube's refusal. Seen live on the
# built-in account; the very next request goes through.
_TUNNEL_HICCUP = re.compile(r"Tunnel connection failed: 50[234]")
_HICCUP_PAUSE = 1.5


def _read(op, req, timeout: float, via: str, what: str) -> str:
    """One request, every failure a CaptionError that knows whether YouTube
    was refusing THIS computer (429) or the network simply broke. A proxy
    gateway hiccup gets one quiet retry before it counts as broken."""
    for attempt in (1, 2):
        try:
            return op.open(req, timeout=timeout).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise CaptionError(
                    f"YouTube is rate-limiting {via} (HTTP 429 on the {what}) — "
                    "it has seen too many requests from here",
                    blocked=True, kind="rate_limited") from e
            if e.code == 403:
                raise CaptionError(f"YouTube refused the {what} {via} (HTTP 403)",
                                   blocked=True, kind="blocked") from e
            raise CaptionError(f"the {what} failed {via} (HTTP {e.code})",
                               kind="network") from e
        except Exception as e:
            if attempt == 1 and _TUNNEL_HICCUP.search(str(e)):
                time.sleep(_HICCUP_PAUSE)
                continue
            raise CaptionError(f"couldn't reach YouTube's {what} {via} "
                               f"({e.__class__.__name__}: {str(e)[:120]})",
                               kind="network") from e


def _watch_html(op, vid: str, timeout: float, via: str) -> str:
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    url = f"https://www.youtube.com/watch?v={vid}"
    html = _read(op, urllib.request.Request(url, headers=headers), timeout,
                 via, "watch page")
    if 'action="https://consent.youtube.com/s"' in html:
        # the EU consent interstitial: answer it once, as a browser would
        m = _CONSENT.search(html)
        if m:
            headers["Cookie"] = f"CONSENT=YES+{m.group(1)}"
            html = _read(op, urllib.request.Request(url, headers=headers),
                         timeout, via, "watch page")
    if 'class="g-recaptcha"' in html:
        raise CaptionError(
            f"YouTube is showing {via} a robot check instead of the video "
            "page — it has flagged this address",
            blocked=True, kind="blocked")
    return html


def fetch_transcript(url_or_id: str, lang: str = "en",
                     proxy: Optional[str] = None,
                     timeout: float = 25.0) -> dict:
    """Watch page → player API (ANDROID client) → caption track → VTT.

    Returns {"vtt", "track", "meta", "route"}. The VTT keeps YouTube's
    word-timing tags when the track serves them (follow-along karaoke);
    when it doesn't, the plain XML becomes clean cues. Raises CaptionError
    — .blocked True only when a proxy would plausibly help.
    """
    vid = video_id(url_or_id)
    if not vid:
        raise CaptionError("that doesn't look like a YouTube link",
                           kind="bad_url")
    op = _opener(proxy)
    via = "through the proxy" if proxy else "from this computer"
    html = _watch_html(op, vid, timeout, via)
    meta = parse_video_details(html)
    up = _UPLOAD.search(html)
    if up:
        meta["upload_date"] = "".join(up.groups())
    key = _API_KEY.search(html)
    body = json.dumps({"context": {"client": ANDROID_CLIENT},
                       "videoId": vid}).encode()
    purl = ("https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
            + (f"&key={key.group(1)}" if key else ""))
    try:
        player = json.loads(_read(op, urllib.request.Request(
            purl, data=body, method="POST",
            headers={"User-Agent": UA, "Content-Type": "application/json"}),
            timeout, via, "player API"))
    except CaptionError as e:
        e.meta = meta
        raise
    except ValueError as e:
        raise CaptionError("YouTube's player API answered with something "
                           "that isn't JSON", meta=meta,
                           kind="network") from e
    for k, v in player_meta(player).items():
        if v and not meta.get(k):    # fill gaps (a None duration counts)
            meta[k] = v
    ps = player.get("playabilityStatus") or {}
    status = str(ps.get("status") or "")
    if status and status != "OK":
        reason = str(ps.get("reason") or "") or status
        low = reason.lower()
        # ONLY bot/traffic wording means "this address": an age gate ("may be
        # inappropriate for some users") or a private video is also
        # LOGIN_REQUIRED, and no proxy opens those
        bot = ("not a bot" in low or "confirm you" in low
               or "unusual traffic" in low or "automated" in low)
        raise CaptionError(
            f"YouTube won't serve this video {via}: {reason}"
            + (" — it has flagged this address" if bot else
               " (it needs a sign-in — age-restricted or private)"
               if status == "LOGIN_REQUIRED" else ""),
            blocked=bot, meta=meta, kind="blocked" if bot else "unavailable")
    tracks = player_tracks(player)
    if not tracks:
        raise CaptionError(
            "this video has no captions on YouTube — download it and let "
            "Scribe transcribe it on this computer", meta=meta,
            kind="no_captions")
    track = pick_track(tracks, lang)
    base = re.sub(r"&fmt=[^&]*", "", track["base_url"])
    if "exp=xpe" in base:
        raise CaptionError("YouTube asked for a proof-of-origin token on "
                           "this caption track", meta=meta, kind="po_token")
    headers = {"User-Agent": UA}
    try:
        vtt = _read(op, urllib.request.Request(base + "&fmt=vtt",
                                               headers=headers),
                    timeout, via, "caption file")
    except CaptionError as e:
        if e.blocked:
            e.meta = meta
            raise
        vtt = ""
    if vtt.lstrip().startswith("WEBVTT") and "-->" in vtt:
        return {"vtt": vtt, "track": track, "meta": meta,
                "route": "player API"}
    # the plain XML form — every track serves it
    try:
        xml = _read(op, urllib.request.Request(base, headers=headers),
                    timeout, via, "caption file")
    except CaptionError as e:
        e.meta = meta
        raise
    segs = xml_to_segments(xml)
    if not segs:
        # an empty 200 is most often a token wall, not this address — so it
        # is NOT "blocked" (that would send people to the proxy for nothing)
        raise CaptionError(
            "YouTube sent an empty caption file — try again in a minute; the "
            "other caption routes are tried next", meta=meta, kind="empty")
    return {"vtt": segments_to_vtt(segs), "track": track, "meta": meta,
            "route": "player API"}


def fetch_vtt(url_or_id: str, lang: str = "en",
              proxy: Optional[str] = None, timeout: float = 25.0) -> dict:
    """The caption fetch every tool calls. The player-API route first; the
    watch page's own track list only as a fallback for the rare track that
    isn't token-walled. Returns {"vtt", "track", "meta", "route"}; raises
    CaptionError (a RuntimeError) with a sentence and .blocked/.meta."""
    try:
        return fetch_transcript(url_or_id, lang=lang, proxy=proxy,
                                timeout=timeout)
    except CaptionError as first:
        if first.blocked or first.kind in ("bad_url", "no_captions",
                                           "unavailable"):
            raise
        vid = video_id(url_or_id)
        op = _opener(proxy)
        via = "through the proxy" if proxy else "from this computer"
        try:
            html = _watch_html(op, vid, timeout, via)
        except CaptionError:
            raise first
        tracks = [t for t in parse_tracks(html)
                  if "exp=xpe" not in t["base_url"]]
        if not tracks:
            raise first
        track = pick_track(tracks, lang)
        try:
            body = _read(op, urllib.request.Request(
                track["base_url"] + "&fmt=vtt", headers={"User-Agent": UA}),
                timeout, via, "caption file")
        except CaptionError:
            raise first
        if not body.strip():
            raise first
        meta = {**first.meta, **parse_video_details(html)}
        return {"vtt": body, "track": track, "meta": meta,
                "route": "watch page"}


# -- the community caption service ------------------------------------------

RELAY_URL = "https://community-highlighter.onrender.com/api/transcript"


def fetch_vtt_relay(url: str, relay: str = RELAY_URL,
                    timeout: float = 75.0) -> dict:
    """Captions via the community-highlighter web app's own public transcript
    engine — BIG's deployment, which fetches through its residential proxy.

    The zero-setup last resort: no account needed on this machine; the
    request carries only the public video URL. Users who prefer full
    independence turn it off in Settings (the proxy switch is the other
    road around a refusing YouTube). The long timeout is honest: free-tier
    Render cold-starts in ~30 s.
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
