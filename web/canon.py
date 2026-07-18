"""URL canonicalization — the Python twin of the reader's canon() in app.js.

specs/16 §P0.4: pasting a URL into "Add a meeting" must resolve to a meeting
already on the record. The reader canonicalizes client-side; the bake writes
urls.json keyed by the canonical form. Both sides MUST agree, so the logic
lives once here and once in app.js, and `tests/test_web_bake.py` pins the two
against one golden table (the same table this module and the JS both answer).

The canon mirrors memory/ingest.py exactly:
  - a YouTube URL/id  -> "youtube:<11-char id>"
  - any other URL     -> "url:" + the URL with tracking params + fragment stripped
This is deliberately the same shape ingest writes into meetings.url_canon, so
a resolved key is a real corpus key.
"""

from __future__ import annotations

import re

_VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})")
_BARE_ID = re.compile(r"^[\w-]{11}$")
# the tracking/params ingest._canon_url strips, in the same set
_STRIP = re.compile(r"[?&](utm_[^=&]+|feature|si|list|index|t)=[^&]*")


def video_id(url_or_id: str) -> str | None:
    """The 11-char YouTube id from a URL or a bare id — czcore.captions.video_id."""
    s = (url_or_id or "").strip()
    if _BARE_ID.match(s):
        return s
    m = _VIDEO_ID.search(s)
    return m.group(1) if m else None


def canon(url: str) -> str:
    """A pasted URL -> its corpus url_canon key. '' for empty input."""
    u = (url or "").strip()
    if not u:
        return ""
    vid = video_id(u)
    if vid:
        return f"youtube:{vid}"
    u = re.sub(r"#.*$", "", u)
    u = _STRIP.sub("", u)
    u = u.rstrip("/&?")
    return "url:" + u
