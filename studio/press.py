"""Press the edition from the cloud — the record, on paper, without us.

specs/17 §6.2 makes one promise and everything in this file serves it: **if
Cloud Run and Postgres both vanish, the record still reads.** The Studio is
allowed to be clever — semantic search needs a server, and that is the whole
reason there is one — but the reading of the record is not allowed to depend
on the Studio being alive. So on every corpus change, debounced, the same
specs/16 edition the desk presses is pressed here and pushed to a bucket
behind a CDN, and the reader shell talks to the API for exactly two things
(meaning-search and freshness) and to the bucket for everything else.

**The choice this module had to make.** `web.bake.bake()` takes a path to a
SQLite file, and a `PgCorpus` is not one. The tempting fix is to export the
Postgres record to a temporary `corpus.db` and bake that. Reading the code
says otherwise: `bake()` is a fourteen-line wrapper whose only real work is
`Corpus(corpus_db)`, and the press itself is the `Bake` class — which takes a
corpus *object* and was written against the store's methods, not against
SQLite. Every call it makes (`list_meetings`, `get_meeting`, `transcript`,
`votes_of`, `list_documents`, `list_issues`, `issue_appearances`,
`issue_paper`, `list_events`, `stats`, `all_votes` via `memory.votes`) is in
`memory.seam.CorpusStore`, and `PgCorpus` implements that interface — that is
what the seam was extracted for. So `Bake` is handed the corpus it already
knows how to read, and no copy of the record is written to a disk in order to
be read straight back off it.

That choice has a cost and it is carried in the open rather than hidden:
`press()` transcribes `bake()`'s orchestration — its nine stage calls, in
order — so a stage added to `web/bake.py` must be added here too or the
hosted edition quietly ships one plane fewer than the desk's. The alternative
was worse in a way that compounds: a corpus that will hold hundreds of
meetings, written out to `/tmp` in full on every press, so that a signature
could be satisfied.

**Two things the desk supplies that a container cannot.** `bake()` passes
`czcore.paths.media_dir`, which resolves `~/Movies` and *creates* directories
as a side effect of being asked where they are; `settings.py` already refuses
to import it for that reason. It is used for one purpose — finding the
Interpreter and Narrator sidecar tracks a desk wrote beside a meeting — and
the Studio has no sidecars, because nothing has ever transcribed or described
a meeting on this machine. So press passes a resolver that points at a path
that does not exist, the track scan finds nothing, and the pressed edition
carries no translated or described tracks. It says so: `sidecars` is False in
the return value. That is the honest shape of the gap until the drain
(specs/17 §6.4) posts tracks back.

**`edition_date` is the record's date, and must not become the press date.**
The bake derives it from `max(meeting date)` on purpose, and
`tests/test_web_bake.py::TestIdempotence` holds it there: the same corpus
presses byte-identical bytes, which is what makes a re-press free — the sync
below compares digests and uploads nothing when nothing moved. A hosted
record still owes the reader an answer to "is this current?", and that answer
is a *different* fact with a *different* name. It lives in `pressing.json`
beside the manifest, it carries a wall clock, and it is the only file in an
edition that does — which is exactly why it is a separate file and not a
field in `manifest.json`.

**The sync gzips, because nobody else will.** `web/bake.py` writes its JSON
plain and says why: GitHub Pages and Fastly gzip text on the wire, so the
reader is a plain fetch. GCS behind a Cloud Load Balancer does not do that by
default — it serves the bytes it was given. An edition of the live corpus is
about 29 MB raw and `search/segs.json` is fetched *in full* on every search,
so shipping it plain would move the entire cost of the covenant's "no
backend" onto the reader's phone. So the sync pre-compresses text objects and
sets `Content-Encoding: gzip` on them, and the origin is correct rather than
the CDN being lucky.

Nothing here calls a model. The press is the one pipeline stage with no AI in
it — deterministic, extractive, the record restated — so it writes no row to
the `spend` table, and a steward reading that ledger will correctly find the
nightly pressing absent from it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import mimetypes
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

# The freshness file. Deliberately not a key in manifest.json: the manifest is
# byte-idempotent by contract and this thing has a clock in it.
PRESSING = "pressing.json"

# Mirrors of the bake's own read limits (web/bake.py: list_meetings(2000),
# list_issues(500), list_events(40)). The fingerprint answers one question —
# "would a re-press differ?" — so it must read exactly what the press reads.
# A wider read would flag changes that never reach an edition; a narrower one
# would miss changes that do.
_MEETING_LIMIT = 2000
_ISSUE_LIMIT = 500
_EVENT_LIMIT = 40
_DOC_LIMIT = 2000

# Where the sidecar scan is pointed. It must be a path that does not exist and
# will not be created: `web.bake._sidecar_dirs` only ever calls `.is_dir()` on
# it, so a missing directory is a clean "no tracks here" rather than an error.
_NO_SIDECARS = Path("/var/empty/studio-has-no-sidecars")

# The object metadata key carrying the digest of the *plain* bytes. Comparing
# GCS's own md5 would compare the gzipped object against the local file and
# re-upload the whole edition every night; comparing what we put there
# ourselves compares like with like.
_SHA_KEY = "cz-sha256"

_NO_CACHE = "no-cache"
_IMMUTABLE = "public, max-age=31536000, immutable"
_REVALIDATE_SOON = "public, max-age=300"

_TYPES = {
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".xml": "application/rss+xml; charset=utf-8",
    ".vtt": "text/vtt; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}

# Suffixes worth compressing. Everything an edition ships is either text (all
# of it compresses 4–8×) or already-compressed pixels (JPEG/PNG, where gzip
# adds a header and buys nothing).
_GZIP_SUFFIXES = {".json", ".webmanifest", ".js", ".css", ".html", ".xml",
                  ".vtt", ".txt", ".svg"}

# Below this, the gzip header and the CDN's decompress cost outweigh the
# saving. Measured in bytes of the plain file.
_GZIP_FLOOR = 1024


# --------------------------------------------------------------------------
# the press
# --------------------------------------------------------------------------

def _no_sidecars(tool: str) -> Path:
    """Stand in for `czcore.paths.media_dir` in a container.

    The desk's resolver creates `~/Movies/...` on the way to answering, which
    is meaningless here and a surprise anywhere. This answers the same
    question — "where would a sidecar track for this tool be?" — with a
    truthful nowhere. A meeting imported from a desk may still carry a
    `media_path` pointing at that desk's disk; `_sidecar_dirs` tests it with
    `.exists()` and it will not, which is the same honest nothing.
    """
    return _NO_SIDECARS / tool


def press(corpus, out_dir: str, version: str = "",
          site_base: str = "") -> dict:
    """Press the specs/16 edition out of a store — here, a `PgCorpus`.

    This is `web.bake.bake()` with its two desk-shaped assumptions replaced:
    the corpus is handed in already open (rather than constructed from a
    SQLite path), and the sidecar resolver points at nothing (rather than at
    `~/Movies`). Everything between those two substitutions is the desk's
    press, unmodified and in its order — see this module's docstring for why
    that transcription exists and what it costs.

    Returns the bake's own report, plus `fingerprint`, `pressed_at`, `out`
    and `sidecars` — the last of which is False and means it: no edition
    pressed from the cloud carries translated or described tracks yet.
    """
    from web import bake as _bake
    from web import emit

    if not version:
        version = _suite_version()
    if not site_base:
        site_base = _site_base()

    out = Path(out_dir).resolve()
    if out.exists():
        # A clean press, as at the desk: the bake owns this directory whole,
        # and a leftover meeting from a previous pressing is a page that
        # 404s in the record's own index.
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    # The fingerprint is taken BEFORE the press, not after. It names the
    # corpus this edition was pressed from; taking it afterwards would name a
    # corpus that may have moved during the press and quietly certify an
    # edition as fresher than it is.
    fingerprint = corpus_fingerprint(corpus)

    b = _bake.Bake(corpus, out, version, _no_sidecars)

    print("pressing the edition…")
    meetings = b.bake_meetings()
    by_id = {m["id"]: m for m in meetings}
    issues = b.bake_issues(by_id)
    stats = b.bake_stats(meetings, issues)
    officials = b.bake_officials(meetings)
    analytics = b.bake_analytics(meetings)
    graph = b.bake_graph(issues)
    b.bake_urls(meetings)
    idx = b.bake_search(meetings)
    b.bake_feeds(meetings, issues, stats, site_base)
    manifest = b.bake_manifest(meetings, issues, stats)

    emit.emit_assets(out, version, manifest)
    emit.emit_stubs(out, meetings, issues, stats, manifest, site_base,
                    officials=officials, analytics=analytics, graph=graph)

    pressing = _write_pressing(out, manifest, fingerprint)

    print(f"  {len(meetings)} meetings · {len(issues)} issues · "
          f"{idx['segments']} segments indexed ({idx['terms']} terms) · "
          f"{stats['counts']['documents']} documents · "
          f"{stats['counts']['votes']} roll calls · "
          f"{len(officials)} officials")
    print("  no sidecar tracks: nothing has been translated or described on "
          "this machine (specs/17 §6.4 — the drain fills this in)")
    rep = b.report()
    print(f"edition pressed → {out}  (corpus {manifest['corpus_hash']}, "
          f"record {fingerprint})")
    return {"meetings": len(meetings), "issues": len(issues),
            "manifest": manifest, "out": str(out), "sidecars": False,
            "fingerprint": fingerprint,
            "pressed_at": pressing["pressed_at"], **rep}


def _write_pressing(out: Path, manifest: dict, fingerprint: str) -> dict:
    """The hosted record's freshness signal, kept apart from the manifest.

    Two dates live here and they are named for what they are, because
    conflating them is the mistake this file exists to avoid.
    `edition_date` is the record's own — the newest meeting in it — and is
    what the footer has always shown. `pressed_at` is when this pressing ran,
    which says nothing about whether the record moved and everything about
    whether the server is still tending it. A reader polling this file
    compares `fingerprint` against the one its cached shell was built from;
    an equal fingerprint with a newer `pressed_at` means the record is
    unchanged and the Studio is alive, which is a real and reassuring answer.
    """
    doc = {
        "fingerprint": fingerprint,
        "corpus_hash": manifest.get("corpus_hash", ""),
        "edition_date": manifest.get("edition_date", ""),
        "pressed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": manifest.get("version", ""),
        "schema": manifest.get("schema", 0),
        "counts": manifest.get("counts", {}),
        "sidecars": False,
    }
    (out / PRESSING).write_text(
        json.dumps(doc, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")), encoding="utf-8")
    return doc


def _suite_version() -> str:
    try:
        from suite import __version__ as version
        return str(version)
    except Exception:
        return "0"


def _site_base() -> str:
    try:
        from .settings import settings
        return settings.site_base
    except Exception:
        return "https://communityai.studio"


# --------------------------------------------------------------------------
# freshness: has the record moved?
# --------------------------------------------------------------------------

def corpus_fingerprint(corpus) -> str:
    """A stable hash over everything an edition would ship.

    Deliberately over-sensitive, and the asymmetry is the whole design: a
    false positive costs one idempotent press whose sync then uploads nothing
    (the bytes are identical, the digests match, the bucket is untouched); a
    false negative serves a stale record to every reader until the next real
    change. So a meeting flipping from `error` to `error` with a new message
    will trigger a press it did not need, and that is the cheap side of the
    trade.

    Every line below is a plane the bake reads: meetings, issues, documents,
    roll calls, resurfacing events, and the corpus totals. A plane the press
    reads but the fingerprint does not is a stale edition waiting to happen.
    Content within a row is covered transitively — `policy.merge_plan` stamps
    `updated_at` on every write — so the columns named here are the ones a
    deletion or a re-link would change without moving any single row's clock.

    Goes through the seam only, so it answers identically for the desk's
    SQLite `Corpus` and the Studio's `PgCorpus`. Timestamps are folded at
    one-second resolution: SQLite keeps them as REAL and Postgres as double
    precision, and float repr drift between the two would otherwise make the
    same record fingerprint differently on each store.
    """
    h = hashlib.sha256()

    s = corpus.stats()
    h.update(("n|%d|%d|%d|%d|%d\n" % (
        int(s.get("meetings", 0)), int(s.get("live", 0)),
        int(s.get("segments", 0)), int(s.get("issues", 0)),
        int(s.get("threads", 0)))).encode())

    newest = 0.0
    for m in sorted(corpus.list_meetings(limit=_MEETING_LIMIT),
                    key=lambda r: str(r.get("id", ""))):
        stamp = float(m.get("updated_at") or 0)
        newest = max(newest, stamp)
        # `or ""` everywhere a string is read, not `get(k, "")`: a column that
        # is NULL on one store and '' on the other hands back a key that
        # exists holding None, and the default never fires. That single
        # difference would make the two stores fingerprint the same record
        # differently, which is the one thing this function may not do.
        h.update(("m|%s|%s|%s|%d|%.0f\n" % (
            m.get("id") or "", m.get("status") or "", m.get("date") or "",
            int(m.get("n_segments") or 0), stamp)).encode())

    for i in sorted(corpus.list_issues(status="active", limit=_ISSUE_LIMIT),
                    key=lambda r: str(r.get("id", ""))):
        h.update(("i|%s|%s|%d|%d|%s\n" % (
            i.get("id") or "", i.get("name") or "",
            int(i.get("n_meetings") or 0), int(i.get("n_segments") or 0),
            ",".join(str(a) for a in (i.get("aliases") or [])))).encode())

    # Documents and roll calls hang off a meeting without touching its row, so
    # neither would show up in the meeting lines above. Both ship.
    for d in sorted(corpus.list_documents(limit=_DOC_LIMIT),
                    key=lambda r: str(r.get("id", ""))):
        stamp = float(d.get("updated_at") or 0)
        newest = max(newest, stamp)
        h.update(("d|%s|%s|%d|%.0f\n" % (
            d.get("id") or "", d.get("status") or "",
            int(d.get("n_chunks") or 0), stamp)).encode())

    votes = corpus.all_votes()
    h.update(("v|%d\n" % len(votes)).encode())
    for v in votes:
        stamp = float(v.get("updated_at") or 0)
        newest = max(newest, stamp)
        h.update(("v|%s|%.2f|%s|%s|%.0f\n" % (
            v.get("meeting_id") or "", float(v.get("t") or 0),
            v.get("outcome") or "", v.get("tally") or "", stamp)).encode())

    # The resurfacing feed on Home is the first forty events, newest first —
    # exactly this read, in `bake_stats`.
    for e in corpus.list_events(limit=_EVENT_LIMIT):
        h.update(("e|%s|%s\n" % (e.get("id") or "",
                                 e.get("kind") or "")).encode())

    h.update(("t|%.0f\n" % newest).encode())
    return h.hexdigest()[:16]


def needs_press(corpus, manifest_path: str) -> bool:
    """Would a press produce something different from what is already there?

    `manifest_path` may point at either the edition's `manifest.json` or its
    `pressing.json`; the fingerprint lives in the latter and is looked for in
    the sibling when the former does not carry it. An edition pressed by the
    desk's `web.bake` carries no fingerprint at all, and neither does an
    absent or truncated one — in every such case the answer is True. That is
    the safe direction: pressing when we did not need to costs one idempotent
    bake and no upload, while declining to press on an unreadable file means
    serving a record nobody can prove is current.
    """
    p = Path(manifest_path)
    rec = _read_json(p) or {}
    fp = str(rec.get("fingerprint") or "")
    if not fp and p.name != PRESSING:
        fp = str((_read_json(p.parent / PRESSING) or {}).get("fingerprint")
                 or "")
    if not fp:
        return True
    return fp != corpus_fingerprint(corpus)


def _read_json(p: Path) -> Optional[dict]:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


# --------------------------------------------------------------------------
# the push: a directory of files becomes a record behind a CDN
# --------------------------------------------------------------------------

def _content_type(rel: str) -> str:
    suffix = Path(rel).suffix.lower()
    if suffix in _TYPES:
        return _TYPES[suffix]
    guess, _enc = mimetypes.guess_type(rel)
    return guess or "application/octet-stream"


def _cache_control(rel: str) -> str:
    """specs/16 §8's caching law, translated to object metadata.

    `immutable` is a promise about a URL, so it is set only where the URL can
    keep it: the reader requests `app.js` and `app.css` with `?v={version}`
    and nothing else in an edition carries a version query, so nothing else
    may claim to be immutable. The data planes (`stats.json`, `meetings/*`,
    the search shards) are fetched at bare paths and are re-pressed whenever
    the record moves, so they get a short window and a revalidation rather
    than a year — long enough for the CDN to absorb a burst, short enough
    that a new pressing reaches a reader who never closes their tab.

    The three files that must never be stale are the two the reader uses to
    ask whether it is stale, and the worker that would otherwise pin an old
    shell in place.
    """
    if rel in ("app.js", "app.css"):
        return _IMMUTABLE
    if rel.endswith(".html") or rel in ("manifest.json", PRESSING, "sw.js"):
        return _NO_CACHE
    return _REVALIDATE_SOON


def _should_gzip(rel: str, size: int) -> bool:
    return Path(rel).suffix.lower() in _GZIP_SUFFIXES and size >= _GZIP_FLOOR


def sync_to_gcs(local_dir: str, bucket: str, prefix: str = "") -> dict:
    """Make a bucket hold exactly this directory — additions, changes, and
    the removals a re-press legitimately makes.

    Deletes are not optional. A meeting taken down under the takedown policy
    (specs/17 §7), a corpus re-import that renames an id, an issue merged
    away: each removes files from the pressed edition, and a sync that only
    ever uploads would leave those pages reachable at their old URLs forever
    — the record's own index would stop pointing at them while the CDN went
    on serving them. So anything under the prefix that the press did not
    write is removed.

    That makes an empty or half-written source directory catastrophic, so it
    is refused: `manifest.json` is the sentinel every successful press
    produces, and without it this returns `ok: False` and touches nothing. A
    press that produced no manifest is a bug, not an empty record.

    Uploads run before deletes, always. A sync that dies halfway through then
    leaves a *superset* of the record in the bucket, which reads; the other
    order leaves holes, which 404.

    Text objects are pre-compressed and marked `Content-Encoding: gzip` —
    see this module's docstring — and everything carries the digest of its
    plain bytes in object metadata, so the next night's sync uploads only
    what actually changed.

    `google-cloud-storage` is optional, as is having credentials. Without
    either, this returns `{"ok": False, "reason": ...}`; the edition is still
    on disk, and the caller is told plainly that it did not travel.
    """
    try:
        from google.cloud import storage
    except ImportError:
        return {"ok": False, "uploaded": 0, "deleted": 0, "skipped": 0,
                "reason": "google-cloud-storage is not installed; the edition "
                          "was pressed to disk and not uploaded"}

    root = Path(local_dir).resolve()
    if not (root / "manifest.json").is_file():
        return {"ok": False, "uploaded": 0, "deleted": 0, "skipped": 0,
                "reason": f"{root} holds no manifest.json, so it is not a "
                          "pressed edition; refusing to sync (a delete pass "
                          "against a half-written directory would empty the "
                          "record)"}

    prefix = prefix.strip("/")
    local = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        local[f"{prefix}/{rel}" if prefix else rel] = (p, rel)

    try:
        client = storage.Client()
        bkt = client.bucket(bucket)
        # The listing carries each object's metadata, so one call answers
        # "what is up there and what was it made from" for the whole edition.
        remote = {b.name: (b.metadata or {}).get(_SHA_KEY, "")
                  for b in client.list_blobs(
                      bucket, prefix=(prefix + "/") if prefix else None)}
    except Exception as exc:            # credentials, network, permissions
        return {"ok": False, "uploaded": 0, "deleted": 0, "skipped": 0,
                "reason": f"could not reach gs://{bucket}: {exc}"}

    uploaded = deleted = skipped = 0
    sent_bytes = 0
    gzipped = 0
    errors = []

    for name, (path, rel) in sorted(local.items()):
        try:
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            if remote.get(name) == sha:
                skipped += 1
                continue
            blob = bkt.blob(name)
            blob.cache_control = _cache_control(rel)
            blob.metadata = {_SHA_KEY: sha}
            body = data
            if _should_gzip(rel, len(data)):
                body = gzip.compress(data, mtime=0)
                blob.content_encoding = "gzip"
                gzipped += 1
            blob.upload_from_string(body, content_type=_content_type(rel))
            uploaded += 1
            sent_bytes += len(body)
        except Exception as exc:
            errors.append(f"upload {name}: {exc}")

    if not errors:
        for name in sorted(set(remote) - set(local)):
            try:
                bkt.blob(name).delete()
                deleted += 1
            except Exception as exc:
                errors.append(f"delete {name}: {exc}")
    elif set(remote) - set(local):
        # An upload failed, so the bucket is not yet a superset of this
        # edition; removing anything now could take away a page whose
        # replacement never landed. The stale objects stay and are named.
        errors.append(f"{len(set(remote) - set(local))} stale objects left in "
                      "place: deletes are skipped when an upload failed")

    out = {"ok": not errors, "bucket": bucket, "prefix": prefix,
           "uploaded": uploaded, "deleted": deleted, "skipped": skipped,
           "gzipped": gzipped, "bytes": sent_bytes, "errors": errors}
    if errors:
        out["reason"] = errors[0]
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="studio.press",
        description="Press the record's edition from Postgres and push it.")
    ap.add_argument("--out", default="",
                    help="output dir (default: STUDIO_EDITION_DIR)")
    ap.add_argument("--bucket", default="",
                    help="GCS bucket to sync into (default: "
                         "STUDIO_EDITION_BUCKET; omit to press to disk only)")
    ap.add_argument("--prefix", default="app",
                    help="object prefix inside the bucket (default: app)")
    ap.add_argument("--version", default="",
                    help="edition version (default: the suite's)")
    ap.add_argument("--base", default="",
                    help="site base URL for feeds + OG tags (default: "
                         "STUDIO_SITE_BASE)")
    ap.add_argument("--force", action="store_true",
                    help="press even when the record has not moved")
    args = ap.parse_args(argv)

    from .settings import settings
    from .store import PgCorpus

    out_dir = args.out or settings.edition_dir
    bucket = args.bucket or settings.edition_bucket

    corpus = PgCorpus()
    try:
        manifest_path = str(Path(out_dir) / PRESSING)
        if not args.force and not needs_press(corpus, manifest_path):
            print(f"the record has not moved since the last pressing "
                  f"({corpus_fingerprint(corpus)}) — nothing to press")
            return 0
        report = press(corpus, out_dir, args.version, args.base)
    finally:
        corpus.close()

    if not bucket:
        print("no bucket given — the edition stayed on disk")
        return 0

    sync = sync_to_gcs(out_dir, bucket, args.prefix)
    if not sync["ok"]:
        print(f"  ⚠ the edition did not travel: {sync['reason']}")
        for e in sync.get("errors", [])[1:6]:
            print(f"    {e}")
        return 1
    print(f"synced → gs://{bucket}/{sync['prefix']}: "
          f"{sync['uploaded']} uploaded ({sync['gzipped']} gzipped, "
          f"{sync['bytes']/1024:.0f} KB), {sync['skipped']} unchanged, "
          f"{sync['deleted']} removed")
    # A budget bust is loud (the bake already printed it) but it is not a
    # failed job. At the desk a nonzero exit blocks a human's push, which is
    # the right lever; here it tells a scheduler to retry, and retrying a
    # press cannot make an edition smaller. Only a record that failed to
    # reach its readers is a failure.
    if report.get("busts"):
        print("  ⚠ the edition busted a budget — pressed and pushed anyway; "
              "see the report above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
