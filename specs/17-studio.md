# Community AI Studio
### The record, hosted — a civic memory that exists on its own

**Status:** v0.1 · **Stage:** **wave 1 built** (branch `lane/studio`; nothing provisioned — see `record/INFRA.md`) · **Owner:** Stephen Walter (Weird Machine / BIG) · **Family:** The Community AI Project · **Related:** Memory (specs/14 — the engine and the original cloud sketch this spec fulfills), the web app (specs/16 — becomes publicrecord's reader), Publisher (specs/13 §P2 — the same "separate networked product" lane), PARALLEL.md

> **The desk presses editions; publicrecord keeps the record.** Today the public
> record is a snapshot pressed from one Mac — brilliant, and stuck breathing
> through a human. Publicrecord is the record with its own heartbeat: meetings
> arrive nightly from the towns' own channels, the corpus lives in a real
> database, search understands meaning as well as words, and a steward can
> tend it from any browser. No Mac in the loop — and the reader still never
> logs in.

**On the name — superseded 2026-07-18.** This spec was written for a product
called *Community AI Studio*. The brand architecture has since split: the
umbrella is **communityai.studio** (R&D), the desktop suite is
**civicmedia.studio** (with control-z.org as its sub-brand), and *this* product —
the hosted record — is **publicrecord.studio**. The package is `record/`, not
`studio/`, because "studio" now names three brands and a directory, and one word
carrying four meanings had already confused two sessions. The spec's numbering
(`specs/17`) is unchanged so every citation to it still resolves.

**The original naming note.** The hosted product is **Community AI Studio** — and the domain
already exists: `communityai.studio` is owned and currently just redirects.
Recommendation: publicrecord lives AT `communityai.studio` (its own first-class
home, decoupled from any one host's DNS), the marketing page at
`community.weirdmachine.org` keeps the umbrella story and gains the big
two-button section (Open publicrecord · Get the desktop app), and
`community.weirdmachine.org/studio` redirects in. The desktop suite keeps its
name; publicrecord is the record's public house, not a rename of the desk.

---

## 1. Problem Statement

specs/16 opened the record; it did not free it. The edition is static, so it
goes stale unless a steward presses and pushes; the corpus lives in one
`corpus.db` on one machine; search on the web is lexical only (the desk's
semantic half never travels, because vectors need compute at query time);
towns are whoever that one Mac ingested; and curation — merge, split, rename,
correct — happens only at the desk. Every one of those is the same missing
piece: **the record has no home of its own.** specs/14 §9 sketched that home
(Cloud Run, managed Postgres, vectors, connectors) and PARALLEL.md translated
it *down* to the local suite for In-a-Box v1. This spec translates it back
up — with everything learned since: captions-first, phrase-anchored issues,
officials-only, editions as exports, provenance as UI.

## 2. Goals

1. **A record that feeds itself.** A town's configured sources (YouTube
   channels/playlists, CivicClerk portals) are polled nightly; a new meeting
   with captions is live in the corpus — segmented, embedded, issue-assigned —
   with **zero human steps and zero Macs**.
2. **Many towns, one instrument.** Town onboarding is configuration, not
   deployment. A resident picks their town once and the whole surface — home,
   search, issues, officials — scopes to it; the crosstown view (specs/14
   §P2.15) becomes real the day two corpora mature.
3. **Search that understands.** Semantic search over the whole corpus via
   real neural embeddings, blended with the existing lexical/FTS half, with
   the provenance line saying which found what. This is the feature the
   static envelope structurally cannot hold; it is publicrecord's reason to
   have a server at all.
4. **A steward's console.** Everything the desk's Memory page can curate —
   merge, split, rename, promote, forget, rebuild — plus ingest approval,
   town/roster config, corrections-that-annotate, and takedowns, from a
   browser, behind real auth, with an audit log.
5. **Resilient by construction.** The reader is static-first: publicrecord
   presses its own edition continuously, so if the API or database is down,
   yesterday's record still reads (and still works offline as a PWA). The
   database is managed Postgres with automated backups. Nothing about
   reading requires the backend to be healthy.
6. **The public covenant survives hosting.** Readers never log in, are never
   tracked, and can always leave with the data: the edition remains the
   anti-lock-in export, now pressed by the server. Accounts exist for
   stewards only. AGPL-3.0 keeps the network-use share-alike honest;
   In-a-Box becomes "run these same containers yourself."

## 3. Non-Goals (and the push-backs, recorded)

- **No Firebase.** Its pillars are auth, a document DB, and functions. The
  reader has no accounts by covenant; the data is join-heavy and relational
  (issues ↔ segments ↔ meetings ↔ votes — specs/14 flagged this against the
  Firestore house-default already); functions are Cloud Run's job here.
  Steward auth is Google Sign-In (one allowlisted account) — thirty lines,
  not a platform.
- **Not a wholesale Gemini migration.** The desk stays BYO-key + local-first —
  that's the "runs with no account, spends nothing" headline 1.9.0 shipped,
  and it stands. The **Studio's server-side** passes (embeddings, summaries,
  deltas, issue labels) run on Gemini under the project's own Google bill —
  that's the coherent version of "one Google bill": the server's spend is
  ours, the desk's is the user's, and every AI surface stays labeled with an
  extractive fallback.
- **No video hosting, still.** Embeds and transcripts; captions-first;
  nothing rehosted. Publicrecord makes the record *available*, not the tapes.
- **No person pages for private citizens** — officials-only aggregation is
  enforced in the same code path it is today (press-time and query-time).
- **Not a replacement for the desk.** The suite remains the craft surface
  (renders, reels, kits, AD mixes) and the sovereignty story. Publicrecord is
  the record's public house; the desk can still press and read editions.

## 4. Users

specs/14 §4's cast unchanged — resident-watcher, civic journalist,
official/staffer, Highlighter-as-client — plus the **steward** promoted to a
first-class authenticated role, and **the nightly scheduler** as an honorary
user (every pipeline stage must be runnable headless with machine-readable
failure).

## 5. System Model (delta from specs/14 §5)

| Object | Change |
|---|---|
| **Town** | Real table at last: name, slug, state, sources[] (channel/playlist/portal configs), roster refs, governance config, status (live/onboarding/requested) |
| **Meeting/Segment/Issue/Thread/Event** | Port as-is from `memory/store.py` — the schema already speaks this language |
| **Segment.emb** | BLOB → `vector` column (pgvector); dual-space: lexical vector kept for parity, neural embedding added beside it |
| **Steward** | New: Google identity, town scopes, audit log of every curation action |
| **Submission** | New state machine: `submitted → approved → queued → live / rejected` — public URL submissions land in a review queue instead of ingesting blind |
| **AsrTask** | New: a no-captions meeting parks here for the desk drain (§6.4) |

## 6. Architecture

**6.1 One engine, two stores.** `memory/` is already the civic-record engine
(ingest, issues, analyze, embed, votes, documents). It gains a thin store
seam: the current SQLite `Corpus` and a new Postgres-backed store implement
the same interface, so the issue engine, dedupe, vote reader — the measured,
hand-audited logic — run identically at the desk and in the cloud. No fork,
no rewrite: publicrecord service (`record/`, FastAPI, same house style) wraps
the same package the suite imports.

**6.2 The read path is static-first.** Publicrecord presses the specs/16
edition on every corpus change (debounced) into GCS behind the CDN — same
stubs, same JS-off readability, same offline PWA. The reader shell calls the
API for exactly three things: semantic search, freshness ("a newer pressing
exists"), and nothing else unless authenticated. **If Cloud Run and Postgres
both vanish, the record still reads.** This is the resilience answer and the
cost answer in one move.

**6.3 The services.**
- **Cloud Run `studio-api`** — FastAPI: search (semantic+lexical blend),
  submissions, steward console API, freshness. Scale-to-zero, min 0.
- **Cloud Run Jobs `studio-pipeline`** — connectors (YouTube poll,
  CivicClerk poll), ingest (captions-first, port of `memory/ingest.py`),
  embed, issue-assign, document fetch, vote read, press-the-edition.
  Triggered by Cloud Scheduler (nightly per town) and by approval events.
- **Cloud SQL Postgres + pgvector** — the corpus. FTS via `tsvector`
  (mirroring the FTS5 queries), vectors via HNSW index.
- **GCS** — pressed editions (served via CDN), fetched documents (PDFs),
  connector work dirs. No video, ever.
- **Auth** — Google Sign-In on `/steward/*` only, server-side allowlist of
  steward identities. (IAP is the graduation path if steward count grows;
  it's config, not code.)

**6.4 ASR without an ASR bill — the drain.** Captions cover most civic
YouTube; those meetings cost pennies (embedding + analysis) and no GPU. A
meeting *without* captions parks as an `AsrTask`. Any desk running the suite
can volunteer as a drain: it polls the queue, transcribes locally with
Scribe's engine (the station's own hardware, the climate-justice posture
specs/14 §8 already commits to), and posts the transcript back over the
steward-scoped API. Cloud GPU ASR remains a priced, deliberate later option —
never the silent default. **This is the hybrid that removes the
host-computer dependency for the common case while keeping marginal cost at
zero for the hard case.**

**6.5 Embeddings — the seam pays off.** `memory/embed.py` declared itself a
seam ("swap the body here and every caller inherits it"). Publicrecord swaps
in **Gemini text embeddings** server-side (batched at ingest; pennies per
meeting), stored beside — not instead of — the lexical vector. Search blends:
FTS (exact) + lexical (related words) + neural (meaning), and the results
UI keeps saying which is which. The desk keeps lexical-offline as its
default and its fallback; an edition never depends on the neural column.

**6.6 Analysis passes.** Summaries, resurfacing deltas, issue labels run on
**Gemini Flash** under the project bill, labeled ("AI-generated — verify
against the official record" continues), extractive fallback always present.
The AI-audit ledger pattern from the desk ports to the server: every token
attributed, spend visible on the steward console.

## 7. The Steward Console

Parity first, then growth: the eight desk curation verbs (`rename / merge /
split / promote / forget / rebuild`, plus follow/thread tools) exposed at
`/steward` with the same honest surfaces; the submission review queue (the
public "Add a meeting" finally POSTs live instead of composing a GitHub
issue — the specs/16 contract shape unchanged); town onboarding (sources,
roster seed, glossary seed); corrections that annotate; takedown workflow
with the public policy page; the audit log; the spend ledger. Every action
writes who/when/what — the record remembers its own edits (specs/14 §8).

## 8. Reader Surface (delta from specs/16)

- **Town picker** — first visit chooses (stored in localStorage, never an
  account); every page scopes; `?town=` deep links override.
- **Semantic search** — one search field, blended results, provenance chips
  per hit; when the API is unreachable the field degrades to lexical-static
  with one honest line ("meaning-search needs publicrecord; words still work").
- **Freshness** — the footer's edition date gains "a newer record exists —
  reload" when the pressed edition advances.
- Everything else — meeting pages, the long view, ledgers, officials,
  analytics, graph, watching, offline — is already built and rides along
  unchanged.

## 9. Covenant, translated up

The In-a-Box translation (PARALLEL.md) ran the cloud spec down to the desk;
this is the inverse, and the same table keeps it honest: readers get **no
accounts, no cookies-for-tracking, no analytics, no fingerprinting** — the
server logs what Cloud Run logs (operational, rotated, never product data).
Follows stay in localStorage. The edition remains downloadable-whole
(anti-lock-in as a URL). Provenance is UI everywhere AI touched anything.
Officials-only aggregation enforced server-side. Corrections annotate.
AGPL-3.0 on `record/` — anyone can run the same record for their town, and
In-a-Box v2 is literally `docker compose up` of these containers.

## 10. Costs (honest, monthly, at launch scale)

| Line | Est. |
|---|---|
| Cloud Run api + jobs (scale-to-zero, low traffic) | $0–5 |
| Cloud SQL Postgres (smallest prod tier) | $10–30 |
| GCS + CDN (editions, documents) | $1–5 |
| Gemini embeddings + Flash passes (~50 meetings/mo) | $1–5 |
| Scheduler, logging | ~$0 |
| **Steady state** | **~$15–45/mo** |
| One-time backfill (300 meetings, captions-first) | ~$5–15 |
| ASR | $0 via the drain; cloud GPU only as a priced decision |

The grant categories specs/12 names (press infrastructure, language access,
disability equity) are exactly what this line item belongs to.

## 11. Migration & Reuse

1. Store seam in `memory/store.py` (interface extraction, SQLite impl
   unchanged) — the one refactor the desk absorbs; lane-law note required.
2. `record/` package: PG store impl, FastAPI app, connectors (port
   `memory/ingest.py` resolve/dedupe/captions paths), press job (calls
   `web.bake` — already parameterized by base URL).
3. `corpus.db → studio` import command (the two real Brookline meetings and
   41 issues arrive day one; nothing is re-derived that was hand-audited).
4. DNS: `communityai.studio` → publicrecord (today it redirects to the
   marketing page); `control-z.org/app/*` → redirect stubs into publicrecord
   so every civic citation minted so far survives.
5. The desk's "Publish the record" learns the third target: press locally
   (kiosk), push gh-pages (legacy), or POST to publicrecord (steward key).

## 12. Success Metrics

Corpus freshness (≤72h from publication, now measurable per town);
towns live (≥3 within a quarter of launch); semantic-search share of
searches with a click-through; submissions approved per month; steward
actions per meeting trending **down** (quality proxy); edition download
count (the anti-lock-in metric the covenant lets us count); uptime of the
*read* path measured independently of the API (target: boring).

## 13. Phasing

- **Wave 1 — the record moves in.** ✅ **BUILT 2026-07-18** (branch
  `lane/studio`; **nothing provisioned** — `record/INFRA.md` is the runbook,
  and the whole wave was proven against `docker compose up`). `record/`
  service + PG schema + store seam; Brookline imported (16,443 segments, 41
  issues, nothing re-derived); nightly YouTube connector written (RSS,
  captions-first — **not scheduled**, and Brookline's channel id is still
  owed); semantic search live as an API with the neural half pinned to
  `gemini-embedding-001@768` behind a seam; the edition presses from
  Postgres; steward auth + submission queue + audit and spend ledgers.
  *The record exists on its own.*

  **Three remainders, named rather than quietly carried:** the reader's search
  field still uses its static index and its specs/16 copy — the API serves the
  blend and §8's honest line, but wiring `web/static/app.js` (copied verbatim,
  under `connect-src 'self'`) is a change to the shared reader that wanted a
  decision; `press.sync_to_gcs` has only ever spoken to a stub; and the
  connector has never fetched a live feed (this venv has no CA bundle). The
  `control-z.org/app/*` redirect stubs are written and **deliberately not
  run** — pointing a working edition at a Studio that does not exist yet would
  break every civic citation minted so far.
- **Wave 2 — many towns, one steward.** Town onboarding UI, CivicClerk
  connector port, rosters/glossaries per town, town picker, the drain
  (AsrTask + desk volunteer mode), audit log + spend ledger. *Boston joins
  without a deploy.*
- **Wave 3 — the wide record.** Crosstown views, per-town RSS/digests,
  Highlighter/Publisher "Send to the Record" pointed at publicrecord,
  In-a-Box v2 (compose file), IAP graduation if stewards multiply.

## 14. Open Questions

- **(Stephen, blocking wave 1 DNS)** `communityai.studio` as publicrecord's
  primary home (recommended) vs `community.weirdmachine.org/studio` as
  primary with the .studio domain redirecting — either works; the spec
  assumes the former.
- **(Stephen)** GCP project/billing account to create — nothing in this
  spec has been provisioned; wave 1 starts with `gcloud` from a clean
  project so the bill is legible from day one.
- ~~**(Eng)** Embedding model + dimension pin~~ — **decided:**
  `gemini-embedding-001` at `output_dimensionality=768`, stored *beside* the
  256-dim lexical vector, pinned in four places the way models.py pins hashes
  (`record/settings.py`, the `vector(768)` column, a CHECK constraint, and
  `meta('embed_neural')` asserted at connect time). It is MRL-truncatable, so
  1536 or 3072 is a re-embed away rather than a code change. Note the model
  does **not** normalise below 3072 dimensions and `memory.embed.cosine()` is
  a bare dot product — `record/embed_neural.py` L2-normalises on the way in,
  and that is load-bearing.
- **(Eng)** Postgres FTS parity with FTS5's bm25 ranking — port the desk's
  ranking behavior or accept ts_rank; measure on the real corpus before
  choosing.
- **(Eng)** yt-dlp on Cloud Run for caption fetch: confirm rate/ToS posture
  at nightly-poll volume; the connector must back off politely and say so
  in the steward console when a town's source throttles.
- **(Design)** The reader's town picker for the person who arrives via a
  deep link from another town — never trap them in the wrong scope.
