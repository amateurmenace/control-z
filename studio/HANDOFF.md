# studio/ — handoff

**Wave 1 of specs/17, on branch `lane/studio`.** Built and proven against a
local Postgres; **nothing is provisioned on GCP** and no bill has started.
`studio/INFRA.md` is the exact runbook for the day that changes.

---

## What landed

| Deliverable (specs/17 §13) | State |
|---|---|
| `studio/` package — FastAPI + PG schema | **done** — `app.py`, `store.py`, `auth.py`, `steward.py`, `settings.py`, `migrate.py`, `migrations/001_corpus.sql` |
| Store seam — one interface, two impls | **done** — `memory/seam.py` + `memory/policy.py`; 73 parity cases run against both stores |
| Connectors — nightly YouTube poll | **done** — `connectors/youtube.py`, RSS + captions-first, polite backoff. **Not scheduled** (no GCP) |
| Semantic search — blended, provenance chips | **API done**; neural half is a seam with no key. **Reader not wired** — see below |
| Steward console v1 | **API done** — Google Sign-In + allowlist, review queue, eight verbs, audit + spend ledgers. **No UI** |
| Press-from-cloud | **done** — presses from `PgCorpus` directly; GCS sync written, unexercised against real GCS |
| Import `corpus.db → studio` | **done** — run against the real record, verifies itself |
| `control-z.org/app/*` redirect stubs | **tool written, deliberately not run** — see below |

## The three honest gaps

**1. The reader's search field still uses the static index.** The API serves
blended search and the exact honest line specs/17 §8 asks for
(*"meaning-search needs the Studio; words still work"*), and returns it in
every response — but the baked reader does not call it yet. Its search page
still says *"(Vector search stays at the desk.)"*, which is true of a desk
edition and wrong of a Studio one. Wiring it means editing `web/static/app.js`,
which is copied into the edition **verbatim**, under a CSP of
`connect-src 'self'` — so it is a real change to the shared reader, affecting
the desk's edition too, and it wanted a decision rather than a quiet edit.
The API side is done and tested; the reader side is a wave-1 remainder.

**2. The GCS sync has never spoken to GCS.** `press.sync_to_gcs` was exercised
against a stub client (upload, skip-unchanged, delete-on-re-press, refuse a
directory with no manifest). `google-cloud-storage` is a guarded import and
returns `{"ok": False, "reason": …}` without it. First real run is step 6 of
INFRA.md.

**3. The connector has never fetched a live feed.** This venv has no CA bundle
(`SSL: CERTIFICATE_VERIFY_FAILED` — the repo's known open item;
`.claude/launch.json` works around it with `SSL_CERT_FILE` pointing at the
venv's certifi). The parse, the dedupe, the filing and the backoff are all
fixture-tested; the fetch is not. **Brookline's channel id is still unknown** —
the corpus records only the uploader name — so `towns.sources` needs a `UC…`
from Stephen before the nightly poll can run.

## Asks

1. **The DNS answer** (specs/17 §14, blocking): `communityai.studio` as the
   Studio's primary home, per the spec's assumption. It currently redirects to
   `community.weirdmachine.org` at Squarespace.
2. **Brookline's YouTube channel id** for `towns.sources`.
3. **AGPL on `studio/`.** specs/17 §9 asserts AGPL-3.0; the repo is MIT with no
   per-file headers anywhere, and specs/12 §9 still lists ratification as an
   open legal question. **Wave 1 ships under the repo licence and says so here
   rather than in silence.** When ratified it lands as its own commit —
   `studio/LICENSE`, a docstring line, a NOTICE entry — in the shape of *"The
   licence travels with the download."*
4. **The load balancer line.** INFRA.md §7 finds a cost specs/17 §10 did not
   count: an HTTPS LB is ~$18/mo, and the edition and API must share an origin
   because `emit.CSP` sets `connect-src 'self'`. Recommendation: serve the
   edition from Cloud Run at first and add the LB when traffic earns it.

## What B should know (this wave edited lane B's files)

`memory/store.py`, `memory/issues.py`, `memory/documents.py`, `memory/embed.py`
and `tests/test_memory_store.py` all changed. **No signature was removed and no
return shape changed**, and every pre-existing test passed without a line
edited — that was the design constraint for the seam commit and it is the
acceptance test. What is new:

- `forget()` now clears `issue_segments`. It never did, and `list_issues`
  counted the orphans while `issue_appearances` hid them.
- `Corpus` gained `linked_seg_ids`, `unlink_meeting`, `close`, `unit`.
  `issues.py`'s two `corpus._con()` escapes are closed.
- `search`/`semantic` gained a `town` argument, defaulting to today's behavior.
- `embed.as_vec` is now the only way to read an embedding back; `from_bytes`
  still works and is still what it delegates to on SQLite.
- The shared rules moved to `memory/policy.py`. `_loads`, `_dedupe_keep_order`,
  `_keyword_set` and `_MEETING_COLS` remain as aliases.

## Fragments (changelog-ready, house voice)

- **The record got its own address, and its own heartbeat.** `studio/` is the
  Studio: a Postgres store behind the same seam the desk uses, an HTTP surface
  small enough to reason about, connectors that poll the towns' own channels,
  and a steward console behind one Google sign-in. The engine is not forked —
  `memory/` is imported, so the hand-audited clustering produces the same
  record on both stores, and 73 parity cases prove it rather than assert it.

- **One engine, two stores.** `memory/seam.py` writes down what the engine may
  assume of a store — result ordering, that embeddings are opaque, that
  `speaker` is `None` and never `""`, that row ids may gap — and
  `memory/policy.py` holds the judgement calls that were previously spelled out
  three times inside one SQLite file. A store owns dialect; policy owns
  meaning.

- **Brookline arrived whole.** 16,443 segments, 41 issues, 392 links, nothing
  re-derived: the import transliterates rather than recomputes, because the
  record it carries was hand-audited and re-running the clusterer would produce
  *a* set of issues rather than *these*. It verifies itself — every table
  counted, vectors re-read bit-for-bit, rollups diffed between the two stores.

- **The record reads with the lights off.** Stop Postgres and the API returns
  honest 503s while the pressed edition still searches all 16,443 segments.
  That is specs/17 §6.2's promise, tested by literally stopping the database
  and walking the reader.
