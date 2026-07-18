"""The nightly poll — a town's channel, read the way a subscriber reads it.

A town publishes its meetings to its own YouTube channel and, without being
asked, publishes a machine-readable list of them beside it: the channel's Atom
feed. Fifteen entries, no API key, no quota, no binary, no scraping — the same
URL a podcast client would poll. That is the whole of this connector's
discovery surface, and the narrowing is deliberate.

specs/17 §14 asked whether yt-dlp's rate and ToS posture survives nightly-poll
volume. The answer taken here is to not find out. yt-dlp is a download tool
wearing a metadata tool's hat, and aiming it at every town every night is
precisely the traffic shape that gets a project's addresses walled — after
which the record stops arriving and nobody can say why. RSS is the polite
citizen's route: it exists in order to be polled. Discovery costs one GET per
body per night, and the only per-video request is the watch page whose caption
list the record genuinely needs.

**The connector does not ingest, and that is the design rather than a
limitation.** It files rows in `submissions` at status `submitted` and stops.
A steward approves; the pipeline ingests. specs/17 §5 made that a state
machine on purpose, because a poller that ingests whatever it finds is a
poller that can put the wrong town's budget hearing on the public record at
three in the morning with nobody awake to notice. The cost is bought
deliberately: a meeting waits in a queue for as long as a human takes, and the
spec accepts that latency in exchange for nothing ever landing unread.

**A video with no captions is reported, never skipped.** Silence is the one
failure mode a nightly job must not have — a body whose captions quietly
stopped would look, in a log of clean runs, exactly like a body that stopped
meeting. So the probe's verdict travels back in `errors` as a labeled entry
and into the submission's own note, where a steward will read it. And the
probe answers three ways, not two: captions found, captions definitively
absent, or *not known* — because a throttled fetch that reported "no captions"
would be a lie that costs a meeting.

What this connector will **not** do is write the `asr_tasks` row itself. An
ASR task is work queued against a meeting, and no meeting exists yet; filing
one here would be ingest through the back door, past the approval the
paragraph above exists to protect. That row belongs to the ingest stage, once
a human has said yes (specs/17 §6.4) — and it is a drain ticket, never a GPU
bill.

**Backoff is a value that surfaces, not a sleep that hides.** `Throttled`
carries the status, the attempt count and the wait; `discover` turns it into
an error entry rather than an exception; so the steward console can say *this
town's source is throttling* instead of showing a town that has mysteriously
stopped holding meetings.

Nothing here spends money. An Atom feed is free and captions are words the
town already published, so this connector writes no `spend` row — which keeps
the ledger meaning exactly what it says it means about the passes that do.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional

from memory import policy
from web.canon import canon

# A user agent that says who is calling and where to complain. An anonymous
# poller is indistinguishable from a scraper, and gets treated like one.
UA = ("CommunityAIStudio/0.1 (+https://communityai.studio; civic record; "
      "nightly meeting poll, one feed per body per night)")

FEED_BASE = "https://www.youtube.com/feeds/videos.xml"
WATCH_BASE = "https://www.youtube.com/watch?v="

# Politeness, spelled out. Four tries covers a routine 503; past that the
# source is saying no, and the honest move is to report it and come back
# tomorrow rather than to keep knocking through the night.
ATTEMPTS = 4
BACKOFF_BASE = 2.0          # seconds before the second try
BACKOFF_CAP = 60.0          # never sleep longer than this inside one poll
RETRY_CODES = {408, 425, 429, 500, 502, 503, 504}
SOURCE_GAP = 1.0            # a beat between a town's own feeds

# A hard read cap. `xml.etree` is not hardened against an entity-expansion
# bomb, and while this feed comes from youtube.com over TLS, "the far end is
# reputable" is not a memory limit. A channel feed is about 30 KB; a watch
# page about 2 MB.
MAX_FEED_BYTES = 4 << 20
MAX_PAGE_BYTES = 8 << 20

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"

_CHANNEL_ID = re.compile(r"UC[\w-]{22}")
_PLAYLIST_ID = re.compile(r"(?:PL|UU|FL|LL|OL|RD)[\w-]{10,}")
# The channel id as the handle page carries it, in either of the two shapes
# YouTube has used; both are checked because either alone has been wrong.
_PAGE_CHANNEL = re.compile(
    r'"(?:channelId|externalId|browseId)"\s*:\s*"(UC[\w-]{22})"'
    r'|/channel/(UC[\w-]{22})')

# A handle costs a page fetch to resolve, and a handle does not change between
# runs of the same nightly job — so it is resolved once per process.
_HANDLES: dict = {}


class Throttled(RuntimeError):
    """The source said slow down, and kept saying it.

    Carried rather than swallowed: the steward console's whole job here is to
    distinguish "this town held no meetings" from "we are being turned away",
    and only the connector knows which it saw."""

    def __init__(self, url: str, status: int, retry_after: Optional[float],
                 attempts: int):
        self.url = url
        self.status = status
        self.retry_after = retry_after
        self.attempts = attempts
        wait = (f"; it asked for {retry_after:.0f}s"
                if retry_after is not None else "")
        super().__init__(f"the source is throttling — HTTP {status} after "
                         f"{attempts} tries at {url}{wait}")


# --------------------------------------------------------------------------
# the network, politely
# --------------------------------------------------------------------------

def _pause(seconds: float) -> None:
    """Sleep with jitter. Every town's job is on the same Cloud Scheduler
    minute, so a fixed backoff would march them into the wall in lockstep."""
    time.sleep(max(0.0, min(BACKOFF_CAP, seconds)) * (0.8 + 0.4 * random.random()))


def _retry_after(headers) -> Optional[float]:
    """Honour Retry-After when it is a plain number of seconds. The HTTP-date
    form is not parsed: guessing at clock skew to shave a few seconds off a
    backoff we already have is not worth being wrong about."""
    raw = ""
    try:
        raw = (headers.get("Retry-After") or "").strip()
    except AttributeError:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _fetch(url: str, timeout: float = 20.0, attempts: int = ATTEMPTS,
           cap: int = MAX_FEED_BYTES, what: str = "") -> str:
    """One GET, with the backoff the spec requires and the sentence a steward
    needs when it fails. Raises `Throttled` when the far end kept refusing,
    `RuntimeError` for everything else — the caller tells those apart because
    they mean different things to a town."""
    what = what or url
    wait = BACKOFF_BASE
    for i in range(1, max(1, attempts) + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(cap).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in RETRY_CODES:
                if i >= attempts:
                    raise Throttled(url, e.code, _retry_after(e.headers),
                                    attempts) from e
                _pause(_retry_after(e.headers) or wait)
                wait = min(BACKOFF_CAP, wait * 2)
                continue
            raise RuntimeError(
                f"{what} answered HTTP {e.code} ({e.reason})") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if i >= attempts:
                raise RuntimeError(f"could not reach {what} ({e})") from e
            _pause(wait)
            wait = min(BACKOFF_CAP, wait * 2)
    raise RuntimeError(f"could not reach {what}")   # pragma: no cover


# --------------------------------------------------------------------------
# what a source is
# --------------------------------------------------------------------------

def _resolve_handle(page_url: str, timeout: float = 20.0) -> str:
    """A /@handle or /c/name page → the channel id the feed is keyed on.

    The feed endpoint speaks channel ids and playlist ids and nothing else, so
    a handle cannot be turned into a feed URL by string surgery — one fetch is
    the honest price. Memoised per process: a town's handle does not move
    between the feeds of one nightly run."""
    hit = _HANDLES.get(page_url)
    if hit:
        return hit
    html = _fetch(page_url, timeout=timeout, cap=MAX_PAGE_BYTES,
                  what=f"the channel page {page_url}")
    m = _PAGE_CHANNEL.search(html)
    cid = (m.group(1) or m.group(2)) if m else ""
    if not cid:
        raise RuntimeError(
            f"{page_url} did not name a channel id — either the handle is "
            "wrong or the page shape changed. Configure this source with its "
            "UC… channel id instead; the id never moves.")
    _HANDLES[page_url] = cid
    return cid


def channel_feed_url(source: str, timeout: float = 20.0) -> str:
    """A configured source → the RSS feed URL to poll.

    Accepts a bare channel id (`UC…`), a bare playlist id (`PL…`), a `@handle`,
    or any of the channel/playlist/handle URL shapes a steward will actually
    paste. RSS is the target because it needs neither an API key nor a binary,
    which is the whole reason this connector can run in a scale-to-zero
    container with no credentials in it.

    A video URL raises: a single meeting is a submission, not a source, and
    quietly polling the channel it happens to live on would subscribe a town
    to something nobody chose."""
    s = (source or "").strip()
    if not s:
        raise ValueError("no source given — expected a channel id, a playlist "
                         "id, a @handle, or a channel URL")
    if "/feeds/videos.xml" in s:
        return s                      # already a feed; a steward may pin one
    if s.startswith("@"):
        return (f"{FEED_BASE}?channel_id="
                f"{_resolve_handle('https://www.youtube.com/' + s, timeout)}")
    if _CHANNEL_ID.fullmatch(s):
        return f"{FEED_BASE}?channel_id={s}"
    if _PLAYLIST_ID.fullmatch(s):
        return f"{FEED_BASE}?playlist_id={s}"

    url = s if "://" in s else "https://" + s
    parts = urllib.parse.urlsplit(url)
    if "youtube.com" not in parts.netloc and "youtu.be" not in parts.netloc:
        raise ValueError(f"{s} is not a YouTube channel, playlist or handle")
    qs = urllib.parse.parse_qs(parts.query)
    if qs.get("v") or parts.netloc.endswith("youtu.be"):
        raise ValueError(
            f"{s} is a single video, not a source. Submit it as a meeting; a "
            "source is the channel or playlist a body posts to.")
    if qs.get("channel_id"):
        return f"{FEED_BASE}?channel_id={qs['channel_id'][0]}"
    if qs.get("playlist_id"):
        return f"{FEED_BASE}?playlist_id={qs['playlist_id'][0]}"
    if qs.get("list"):
        return f"{FEED_BASE}?playlist_id={qs['list'][0]}"
    path = parts.path
    m = re.search(r"/channel/(UC[\w-]{22})", path)
    if m:
        return f"{FEED_BASE}?channel_id={m.group(1)}"
    m = re.search(r"/user/([^/?#]+)", path)
    if m:
        return f"{FEED_BASE}?user={urllib.parse.quote(m.group(1))}"
    m = re.search(r"/(@[^/?#]+|c/[^/?#]+)", path)
    if m:
        page = "https://www.youtube.com/" + m.group(1).lstrip("/")
        return f"{FEED_BASE}?channel_id={_resolve_handle(page, timeout)}"
    raise ValueError(
        f"could not read a channel or playlist out of {s} — paste the UC… "
        "channel id or the playlist URL")


# --------------------------------------------------------------------------
# the feed
# --------------------------------------------------------------------------

def parse_feed(xml_text: str, limit: int = 25) -> List[dict]:
    """Atom → the connector's candidate shape, newest first.

    Kept apart from the fetch so the parse is testable against a saved feed
    with no network at all, which is the only way this stays honest about a
    schema YouTube can change under us."""
    root = ET.fromstring(xml_text)
    feed_author = ""
    fa = root.find(_ATOM + "author")
    if fa is not None:
        feed_author = (fa.findtext(_ATOM + "name") or "").strip()

    out: List[dict] = []
    for e in root.findall(_ATOM + "entry"):
        vid = (e.findtext(_YT + "videoId") or "").strip()
        href = ""
        link = e.find(_ATOM + "link")
        if link is not None:
            href = (link.get("href") or "").strip()
        if not vid and href:
            # A playlist feed has occasionally omitted yt:videoId; the link is
            # a watch URL either way, and canon() already knows how to read
            # one. Never a fourth copy of that regex.
            key = canon(href)
            vid = key.split(":", 1)[1] if key.startswith("youtube:") else ""
        if not vid:
            continue
        uploader = feed_author
        ea = e.find(_ATOM + "author")
        if ea is not None:
            uploader = (ea.findtext(_ATOM + "name") or "").strip() or feed_author
        out.append({
            "video_id": vid,
            "url": href or (WATCH_BASE + vid),
            "title": (e.findtext(_ATOM + "title") or "").strip(),
            "published": (e.findtext(_ATOM + "published") or "").strip(),
            "uploader": uploader,
        })
    # ISO-8601 sorts lexically, and the sort is stable, so an entry with no
    # published date keeps its feed position and lands at the end rather than
    # jumping the queue with an empty string.
    out.sort(key=lambda it: it["published"], reverse=True)
    return out[:max(0, limit)]


def poll(source: str, limit: int = 25, timeout: float = 20.0) -> List[dict]:
    """Fetch and parse one source's feed. Newest first, at most `limit`."""
    feed = channel_feed_url(source, timeout=timeout)
    xml_text = _fetch(feed, timeout=timeout, cap=MAX_FEED_BYTES,
                      what=f"the feed for {source}")
    try:
        return parse_feed(xml_text, limit=limit)
    except ET.ParseError as e:
        raise RuntimeError(
            f"the feed for {source} was not parseable XML ({e}) — YouTube "
            "sometimes answers a consent or error page with a 200") from e


# --------------------------------------------------------------------------
# captions — asked about, never assumed
# --------------------------------------------------------------------------

def captions_probe(video_id: str, timeout: float = 20.0) -> dict:
    """Does this video carry published captions?

    Returns `{"video_id", "captions", "tracks", "note"}` where `captions` is
    True, False, or **None for "could not tell"** — the third value is the
    point. A throttled fetch reported as "no captions" would send a meeting to
    the ASR drain that already has perfectly good words, and nothing
    downstream would ever question it.

    The watch page is fetched on this module's polite path and parsed by
    `czcore.captions`, which already knows the page's shapes and YouTube's
    empty-body tell. No second parser."""
    out: dict = {"video_id": video_id, "captions": None, "tracks": [],
                 "note": ""}
    try:
        from czcore import captions as ctext
    except ImportError as e:      # pragma: no cover - czcore is always present
        out["note"] = f"captions were not checked — czcore.captions is not importable ({e})"
        return out
    try:
        html = _fetch(WATCH_BASE + video_id, timeout=timeout,
                      cap=MAX_PAGE_BYTES, what=f"the watch page for {video_id}")
    except Throttled as e:
        out["note"] = f"captions were not checked — {e}"
        return out
    except RuntimeError as e:
        out["note"] = f"captions were not checked — {e}"
        return out
    if not html.strip():
        out["note"] = ("captions were not checked — YouTube answered the watch "
                       "page with an empty body, its tell for an address it "
                       "does not trust")
        return out
    details = ctext.parse_video_details(html)
    tracks = ctext.parse_tracks(html)
    if tracks:
        out["captions"] = True
        # The signed base_url expires within hours and is useless in a log or
        # a console; the language and whether it is auto-generated are what a
        # steward is actually deciding on.
        out["tracks"] = [{"lang": t["lang"], "kind": t["kind"],
                          "name": t["name"]} for t in tracks]
        out["note"] = "captions published: " + ", ".join(
            f"{t['lang'] or '?'}{'/auto' if t['kind'] == 'asr' else ''}"
            for t in out["tracks"])
        return out
    if details:
        # A real watch page that lists no tracks is a real answer.
        out["captions"] = False
        out["note"] = ("no published captions — this meeting needs a "
                       "transcript before it can join the record (the desk "
                       "drain, specs/17 §6.4)")
        return out
    out["note"] = ("captions were not checked — the watch page named neither "
                   "captions nor video details, so its shape changed or the "
                   "request was intercepted")
    return out


# --------------------------------------------------------------------------
# the submissions queue
# --------------------------------------------------------------------------

def _submission_for(corpus, url_canon: str) -> Optional[dict]:
    """Has this URL already been filed, by this poller or by a person?

    Reached through the store's own `_con()` rather than a fresh connection:
    that is what inherits the pool, the dict rows, and any `unit()` a caller
    has opened around the poll. `PgCorpus` has no submissions verb yet — the
    queue arrives with the steward console — and adding one from a connector
    would be writing another module's file."""
    if not url_canon:
        return None
    with corpus._con() as con:
        r = con.execute(
            "SELECT id, status FROM submissions WHERE url_canon=%s "
            "ORDER BY added_at LIMIT 1", (url_canon,)).fetchone()
    return dict(r) if r else None


def _file_submission(corpus, sub: dict) -> bool:
    """File one candidate at `submitted`. Returns whether a row was written.

    The id is derived from the canonical URL, so a feed that shows the same
    video for fifteen nights files it once, and a steward who has already
    rejected it is never overruled by the poller that found it again."""
    now = time.time()
    with corpus._con() as con:
        cur = con.execute(
            "INSERT INTO submissions (id, url, url_canon, town, body, date, "
            "note, status, added_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'submitted',%s,%s) "
            "ON CONFLICT (id) DO NOTHING",
            (sub["id"], sub["url"], sub["url_canon"], sub["town"],
             sub["body"], sub["date"], sub["note"], now, now))
        return bool(cur.rowcount)


def discover(corpus, town: str, body: str, source: str, limit: int = 25,
             check_captions: bool = True) -> dict:
    """Poll one source and file what the record has never seen.

    Dedupe is tier one only — the canonical URL — and deliberately so: tiers
    two and three (media hash, transcript shingles) need the words, and the
    words are what approval unlocks. A duplicate that slips past the URL tier
    meets the other two inside ingest, where `memory.ingest` already runs them.

    Returns `{"polled", "known", "filed", "errors"}` with the source's own
    labels alongside. Every entry in `errors` is a dict with a `kind`, because
    the nightly scheduler is an honorary user (specs/17 §4) and an honorary
    user reads machine-readable failure."""
    out: dict = {"source": source, "town": town, "body": body,
                 "polled": 0, "known": 0, "filed": 0, "errors": []}
    try:
        items = poll(source, limit=limit)
    except Throttled as e:
        out["errors"].append({"kind": "throttled", "source": source,
                              "status": e.status, "retry_after": e.retry_after,
                              "detail": str(e)})
        return out
    except (ValueError, RuntimeError) as e:
        out["errors"].append({"kind": "unreachable", "source": source,
                              "detail": str(e)})
        return out

    out["polled"] = len(items)
    for it in items:
        key = canon(it["url"])
        if not key:
            out["errors"].append({"kind": "uncanonical", "url": it["url"],
                                  "detail": "no canonical key for this entry"})
            continue
        if corpus.find_by_url_canon(key) or _submission_for(corpus, key):
            out["known"] += 1
            continue

        notes = [it["title"] or "(untitled)"]
        if it["published"]:
            # The feed's date is the day the town *posted* the video, which is
            # often not the day it met. It rides in the note, where it informs
            # a steward, rather than in `date`, where it would be an assertion
            # about the meeting that nobody checked. Ingest derives the real
            # meeting day from the title.
            notes.append(f"published {it['published']}")
        if check_captions:
            probe = captions_probe(it["video_id"])
            notes.append(probe["note"])
            if probe["captions"] is False:
                out["errors"].append({
                    "kind": "no_captions", "video_id": it["video_id"],
                    "url": it["url"], "title": it["title"],
                    "detail": probe["note"]})
            elif probe["captions"] is None:
                out["errors"].append({
                    "kind": "captions_unknown", "video_id": it["video_id"],
                    "url": it["url"], "title": it["title"],
                    "detail": probe["note"]})
        notes.append(f"found by the nightly poll of {source}")

        try:
            filed = _file_submission(corpus, {
                "id": "sub:" + key, "url": it["url"], "url_canon": key,
                "town": town, "body": body, "date": "",
                "note": " · ".join(n for n in notes if n)})
        except Exception as e:
            out["errors"].append({"kind": "not_filed", "url": it["url"],
                                  "detail": str(e)})
            continue
        if filed:
            out["filed"] += 1
        else:
            out["known"] += 1     # someone filed it between the check and now
    return out


def poll_town(corpus, town_row: dict, limit: int = 25) -> dict:
    """Every YouTube source a town has configured, one town's whole night.

    `town_row` is a row from `towns`, whose `sources` JSONB is
    `[{kind, url, body}, …]`. Non-YouTube sources are passed over in silence
    rather than reported — a CivicClerk portal is not this connector's failure
    (it is wave 2's), and reporting it nightly would train a steward to ignore
    the error list, which is the only thing standing between the record and a
    body that quietly stopped publishing."""
    # `meetings.town` holds a display name on the desk corpus that arrives day
    # one, and a submission becomes a meeting — so the submission carries the
    # name and falls back to the slug. There is no foreign key here to keep
    # the two honest, which is exactly why the choice is written down.
    town = str(town_row.get("name") or town_row.get("slug") or "").strip()
    sources = town_row.get("sources") or []
    if isinstance(sources, (str, bytes)):
        sources = policy.loads(sources) or []

    out: dict = {"town": town, "slug": str(town_row.get("slug") or ""),
                 "sources": 0, "polled": 0, "known": 0, "filed": 0,
                 "errors": [], "results": []}
    first = True
    for src in sources:
        if not isinstance(src, dict):
            out["errors"].append({"kind": "bad_source", "detail": repr(src)[:120]})
            continue
        if str(src.get("kind", "")).strip().lower() != "youtube":
            continue
        url = str(src.get("url", "") or "").strip()
        if not url:
            out["errors"].append({"kind": "bad_source",
                                  "detail": "a youtube source with no url"})
            continue
        if not first:
            _pause(SOURCE_GAP)      # a beat between one town's own feeds
        first = False
        r = discover(corpus, town, str(src.get("body", "") or ""), url,
                     limit=limit)
        out["sources"] += 1
        for k in ("polled", "known", "filed"):
            out[k] += r[k]
        out["errors"].extend(r["errors"])
        out["results"].append(r)
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_run(r: dict) -> None:
    print(f"  polled {r['polled']} · known {r['known']} · filed {r['filed']}")
    for e in r["errors"]:
        print(f"  [{e['kind']}] {e.get('title') or e.get('url') or e.get('source', '')}")
        print(f"      {e['detail']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="studio.connectors.youtube",
        description="Poll a town body's YouTube channel and file what is new.")
    ap.add_argument("--source", required=True,
                    help="channel id (UC…), playlist id (PL…), @handle, or URL")
    ap.add_argument("--town", default="", help="town the meetings belong to")
    ap.add_argument("--body", default="",
                    help="the body that meets (e.g. 'Select Board')")
    ap.add_argument("--limit", type=int, default=25,
                    help="most recent entries to consider (default 25)")
    ap.add_argument("--no-captions", action="store_true",
                    help="skip the per-video caption probe (one GET each)")
    ap.add_argument("--dry-run", action="store_true",
                    help="poll and print; touch no database at all")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.dry_run:
        # Nothing is imported that could write: no store, no DSN, no pool.
        try:
            items = poll(args.source, limit=args.limit)
        except (ValueError, RuntimeError) as e:
            print(f"could not poll {args.source}: {e}")
            return 1
        rows = []
        for it in items:
            row = {**it, "url_canon": canon(it["url"])}
            if not args.no_captions:
                p = captions_probe(it["video_id"])
                row["captions"] = p["captions"]
                row["captions_note"] = p["note"]
            rows.append(row)
        if args.json:
            print(json.dumps({"source": args.source, "dry_run": True,
                              "items": rows}, indent=2))
            return 0
        print(f"{len(rows)} entries from {args.source} (nothing written)")
        for row in rows:
            cap = row.get("captions")
            mark = {True: "captions", False: "NO CAPTIONS",
                    None: "captions unknown"}.get(cap, "not checked")
            print(f"  {row['published'][:10] or '??????????'}  {row['url_canon']}"
                  f"  [{mark}]  {row['title'][:70]}")
        return 0

    if not args.town:
        print("note: no --town given; these submissions will be filed "
              "town-less and a steward will have to say where they belong")
    from studio.store import PgCorpus

    corpus = PgCorpus()
    try:
        r = discover(corpus, args.town, args.body, args.source,
                     limit=args.limit, check_captions=not args.no_captions)
    finally:
        corpus.close()
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"{args.source} → {args.town or '(no town)'}"
              f"{' / ' + args.body if args.body else ''}")
        _print_run(r)
    return 1 if any(e["kind"] in ("throttled", "unreachable", "not_filed")
                    for e in r["errors"]) else 0


if __name__ == "__main__":
    sys.exit(main())
