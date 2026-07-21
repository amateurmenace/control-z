"""The shared-paper store — content-addressed, write-once, read-only.

specs/21 §6.2, the one server touch a curated paper can have. A paper is PUT
by the hash of its own canonical bytes, so the URL *is* the content: the same
paper always lands at the same address, a re-share is a no-op, and nothing at
this layer knows or asks who wrote or reads one. The store is **additive,
never load-bearing** — every paper also travels as a URL-encoded link and an
exportable ``paper.json``, so losing this bucket loses the shortness of the
short links and nothing else (specs/17 §6.2 holds whole).

The abuse posture, P1 (settled with Stephen 2026-07-21): the only free text a
stored paper may carry is its **title**, length-capped and control-char-free;
every other field is an exact-shaped reference into the record (a pid, a
slug, a clip's two timestamps). Validation is **strict, not corrective** — an
unknown key or a malformed block is a 422, never silently rewritten, because
a store that "helpfully" edits documents stores things nobody ever saw. (The
reader's own decoder is the opposite — total, malformed-degrades — and that
is the right split: a *link* must survive a mangling email client; a *store*
must refuse to hold what the client never meant.)

Canonical form is decided HERE and only here: keys sorted, separators tight,
ASCII-escaped, clip times snapped to the tenth-second grid with whole seconds
collapsed to ints (``12``, ``12.0`` and ``12.00`` are one clip, one hash).
The client never computes the hash — it POSTs the portable form and receives
the address back — so there is no cross-language byte contract to drift.

Takedown: there is no delete API on purpose. A steward removes the object
``p/<id>.json`` from the bucket by hand (``record/OPERATING.md`` §papers),
and the address goes honestly 404.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

SCHEMA = "publicrecord.paper/1"
MAX_BYTES = 64 * 1024        # the raw POST and the canonical form both
MAX_BLOCKS = 64
MAX_CLIPS = 100              # per reel block — matches the reader's cap
TITLE_MAX = 200

_REF = re.compile(r"^[A-Za-z0-9_-]{1,64}$")     # a pid or an issue slug
ID_RX = re.compile(r"^[0-9a-f]{16}$")           # a paper's content address


class PaperError(ValueError):
    """A document the store refuses — the message is the 422 body."""


def _t(x, what):
    """A clip time: a real JSON number, finite, >= 0, snapped to the
    tenth-second grid, whole seconds collapsed to int so 12 and 12.0 hash
    identically whichever a client sent."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise PaperError(f"{what} must be a number")
    v = round(float(x), 1)
    if not math.isfinite(v) or v < 0:
        raise PaperError(f"{what} must be a finite time from the tape's start")
    return int(v) if float(v).is_integer() else v


def _exact_keys(obj, want, what):
    got = set(obj)
    if got != want:
        raise PaperError(
            f"{what} must carry exactly {sorted(want)} (got {sorted(got)})")


def _block(b, i):
    what = f"block {i + 1}"
    if not isinstance(b, dict):
        raise PaperError(f"{what} is not an object")
    kind = b.get("kind")
    if kind == "story":
        story = b.get("story")
        if story == "meeting":
            _exact_keys(b, {"kind", "story", "pid"}, what)
            pid = b.get("pid")
            if not isinstance(pid, str) or not _REF.match(pid):
                raise PaperError(f"{what}: not a meeting id")
            return {"kind": "story", "story": "meeting", "pid": pid}
        if story == "issue":
            _exact_keys(b, {"kind", "story", "slug"}, what)
            slug = b.get("slug")
            if not isinstance(slug, str) or not _REF.match(slug):
                raise PaperError(f"{what}: not an issue slug")
            return {"kind": "story", "story": "issue", "slug": slug}
        raise PaperError(f"{what}: a story is a meeting or an issue")
    if kind == "reel":
        _exact_keys(b, {"kind", "clips"}, what)
        clips = b.get("clips")
        if not isinstance(clips, list) or not clips:
            raise PaperError(f"{what}: a reel carries a list of clips")
        if len(clips) > MAX_CLIPS:
            raise PaperError(f"{what}: more than {MAX_CLIPS} clips")
        out = []
        for j, c in enumerate(clips):
            cw = f"{what}, clip {j + 1}"
            if not isinstance(c, dict):
                raise PaperError(f"{cw} is not an object")
            _exact_keys(c, {"pid", "start", "end"}, cw)
            pid = c.get("pid")
            if not isinstance(pid, str) or not _REF.match(pid):
                raise PaperError(f"{cw}: not a meeting id")
            start, end = _t(c.get("start"), f"{cw} start"), _t(c.get("end"), f"{cw} end")
            if end <= start:
                raise PaperError(f"{cw}: ends before it starts")
            out.append({"pid": pid, "start": start, "end": end})
        return {"kind": "reel", "clips": out}
    raise PaperError(f"{what}: unknown kind {kind!r} — this store holds "
                     "stories and reels (charts and notes arrive later)")


def canonical(doc) -> str:
    """Validate a portable paper strictly and return its one canonical
    serialization — the bytes that get hashed and stored. Raises PaperError
    with a sayable message on anything malformed."""
    if not isinstance(doc, dict):
        raise PaperError("a paper is a JSON object")
    extra = set(doc) - {"schema", "title", "blocks"}
    if extra:
        raise PaperError(
            f"unknown keys {sorted(extra)} — send the portable form "
            "(schema, title, blocks of refs); the enriched paper.json is "
            "a receipt, not an upload")
    if doc.get("schema") != SCHEMA:
        raise PaperError(f"schema must be {SCHEMA!r}")
    title = doc.get("title", "")
    if not isinstance(title, str):
        raise PaperError("the title must be a string")
    if len(title) > TITLE_MAX:
        raise PaperError(f"the title is longer than {TITLE_MAX} characters")
    if any(ord(ch) < 0x20 for ch in title):
        raise PaperError("the title carries control characters")
    blocks = doc.get("blocks", [])
    if not isinstance(blocks, list):
        raise PaperError("blocks must be a list")
    if len(blocks) > MAX_BLOCKS:
        raise PaperError(f"more than {MAX_BLOCKS} blocks")
    if not blocks and not title:
        raise PaperError("an empty paper has nothing to store — the link "
                         "already carries it")
    clean = {"schema": SCHEMA, "title": title,
             "blocks": [_block(b, i) for i, b in enumerate(blocks)]}
    out = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    if len(out) > MAX_BYTES:
        raise PaperError("this paper is too large to store — share it as a "
                         "paper.json file instead")
    return out


def paper_id(canonical_form: str) -> str:
    """The content address: sixteen hex characters of the canonical bytes'
    SHA-256. Idempotent by construction — the same paper cannot have two."""
    return hashlib.sha256(canonical_form.encode("utf-8")).hexdigest()[:16]


# -- backends ---------------------------------------------------------------
# One method pair, two homes. `put_new` must be create-only (an existing
# object is left byte-identical — content addressing makes overwrite and
# no-op indistinguishable anyway); `get` returns bytes or None.

class MemPapers:
    """The store in a dict — tests, and any run without a bucket."""

    def __init__(self):
        self._d = {}

    def put_new(self, pid: str, data: bytes) -> None:
        self._d.setdefault(pid, data)

    def get(self, pid: str):
        return self._d.get(pid)


class GcsPapers:
    """The store in a private GCS bucket, `p/<id>.json` per paper.
    `if_generation_match=0` makes the write create-only at the bucket, so
    even a raced double-POST stores one object once. The client library is
    imported lazily — importing this module must never need credentials."""

    def __init__(self, bucket_name: str):
        self._name = bucket_name
        self._bucket = None

    def _b(self):
        if self._bucket is None:
            from google.cloud import storage
            self._bucket = storage.Client().bucket(self._name)
        return self._bucket

    def put_new(self, pid: str, data: bytes) -> None:
        from google.api_core.exceptions import PreconditionFailed
        blob = self._b().blob(f"p/{pid}.json")
        try:
            blob.upload_from_string(data, content_type="application/json",
                                    if_generation_match=0)
        except PreconditionFailed:
            pass    # the same bytes are already there — that is the point

    def get(self, pid: str):
        from google.api_core.exceptions import NotFound
        blob = self._b().blob(f"p/{pid}.json")
        try:
            return blob.download_as_bytes()
        except NotFound:
            return None
