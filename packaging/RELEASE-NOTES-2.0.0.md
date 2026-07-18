# Civic Media Studio 2.0.0 — release notes

**A new signed identity.** `bundle_identifier` moved from `org.control-z.suite`
to `org.civicmedia.studio`. macOS treats that as a different application: it
installs *beside* 1.9.0 rather than replacing it, Gatekeeper has never seen it
before, and the notarization is fresh rather than an update to an existing
record. Operators upgrading should expect to drag the new app over and remove
the old one by hand — and to tell users the same, because nothing will do it
for them.

**Supersedes 1.9.0**, which was the last signed DMG.

---

## What is in it, since 1.9.0

**The suite is Civic Media Studio.** The app, its icon, its window title and its
home page carry civicmedia.studio. Control-Z survives as its own brand *inside*
the suite — free pro production tools for Resolve, still at control-z.org, for
an audience that may never care about the civic half. `brand/` vendors all four
identities (communityai, publicrecord, civicmedia, control-z) with their marks,
tokens, clearspace rules and minimum sizes, so no surface redraws a logo.

**The public record is publicrecord.studio.** Reader mark, page titles, feeds
and the web manifest. The pressed edition is branding-only against 1.9.0 — same
`corpus_hash`, all 216 issue pages and every deep link intact.

**`record/` — the hosted record** (specs/17 wave 1). Postgres + pgvector behind
the same store seam the desk uses; a FastAPI service carrying only what a static
edition structurally cannot (semantic search, freshness, submissions, the
steward console); nightly YouTube connectors; a press job. **Nothing is
provisioned and no bill has started** — `record/INFRA.md` is the runbook.
Deliberately **not** in this DMG: no Postgres driver, no cloud SDK, no
`record/` in `suite.spec`. A signed desktop app has no business carrying a
server.

**The drain** (specs/17 §6.4, gated). A desk can lend itself to the record: a
meeting without captions parks as a task any station Mac can transcribe on its
own hardware. That is how ASR stays at marginal zero instead of becoming a GPU
bill, and it is off unless a steward turns it on.

**The desk's fifth wave.** Rise joins the road, presets name their work, the
coherence pass across all eight desk pages, and the Models page grew local
cards for MT and vision.

---

## Build notes for the signing operator

- **Two version truths must agree**: `pyproject.toml` and `suite/__init__.py`
  are both `2.0.0`. The statics cache-bust off the latter.
- **The venv changed.** `pyproject` gained a `record` extra (psycopg, pgvector,
  fastapi, google-auth[requests]) and registered the `brand` and `record`
  packages. The `record` extra is **not** part of `suite`, and `record/` is
  deliberately absent from `packaging/suite.spec` — if a future edit adds it,
  that is the bug, not a feature.
- **`brand/logos/*.svg` and `brand/tokens/*.css` are package-data now.** They
  were not registered on the branch that introduced them, so a wheel would have
  shipped without them. If `build_suite.sh` reports a missing brand asset, that
  guard is doing its job.
- **`tests/test_packaging.py` must report six tests and no skips.** A skip there
  is a gate that lost its inputs, not routine: an unbuilt vendor FFmpeg skips
  one, but a missing `otool` silently skips all four GPL-linkage gates and the
  run looks clean.
- The **FFmpeg posture is unchanged**: LGPL-2.1, no `--enable-gpl`, no x264/x265,
  H.264 and HEVC through VideoToolbox. `NOTICE.txt` and the LGPL text ride in
  the DMG beside the app.

## The ritual (run on the signing Mac)

    git pull
    .venv/bin/pip install -e '.[packaging]'
    .venv/bin/pip install -r requirements.txt
    RECORD_TEST_PG_DSN=... .venv/bin/python -m unittest discover -s tests -t .
    #   685 tests. Without the DSN the record's Postgres half skips loudly (39)
    #   — fine for a desktop release, since none of it ships in the DMG.
    packaging/build_ffmpeg.sh   # only if vendor/ffmpeg is not already built
    packaging/build_suite.sh    # freezes onedir; fails loudly on a missing asset
    packaging/sign_suite.sh     # Developer ID, hardened runtime, zero entitlements
    packaging/notarize_suite.sh # staples the app, builds + notarizes the DMG

Then the gate that **cannot** run on a dev machine (specs/09 §7): `spctl -a -vvv`
on a Mac that has never seen a developer certificate or Homebrew. Only after
that verdict: GitHub release **v2.0.0**, DMG attached, this file as the body.

**This release especially needs that loaner check.** The identity is new, so
Gatekeeper's verdict on 1.9.0 tells you nothing about 2.0.0 — it is the first
time this bundle id has ever been presented to a machine that does not know you.
