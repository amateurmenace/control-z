# PARALLEL.md — the two-lane agreement

Two Claude instances build the community wing (specs/12–15) in this repo at
the same time, on two machines. This file is the law between them. When a
question of "whose file is this" comes up, the answer is here; when it isn't,
the answer is **lane A's** — ask in a handoff note rather than editing.

Read order for either lane: this file → specs/12-community-program.md (the
big picture) → your product spec → README → specs/00, 08, 11 → CHANGELOG
(for the voice) → the code you'll sit beside.

## The lanes

**Lane A — the box, the shell, and the publish desk** (Stephen's primary
machine). Owns the suite shell and everything cross-cutting: the home page
redesign and workflow UX, nav/rail, shared css/js, czcore, the site, README,
CHANGELOG, specs/. Builds **Community Publisher** (specs/13) end to end, and
extracts Highlighter's moment detection into a callable engine (the shared
unlock in specs/12 §2). Wires every cross-tool integration: "Send to the
Record" buttons, the Prior-appearances panel, the workflow chains on Home.

**Lane B — the record** (the second machine). Builds **Community Memory**
(specs/14) end to end as a suite tool: ingest, pipeline, corpus store,
search, meeting pages, the long view, issue engine, submissions + context
endpoints. Later — by agreement at a wave boundary, never assumed —
Interpreter + Narrator (specs/15) as a pair.

## Ownership map

Lane B creates and exclusively owns:

- `memory/` — the whole package (engine, store, pipeline, adapters, HANDOFF.md)
- `suite/tools/memory.py` — its routes (`register_memory(app, jobs, frames)`)
- `suite/static/js/memory.js` — its page
- `tests/test_memory*.py`

Lane A owns everything else, including every file that exists today. The
sharp edges, spelled out: `czcore/` is A's (B imports, never edits);
`highlighter/`, `scribe/`, `grabber/` are A's (B imports read-only);
`home.js`, `app.js`, `core.js`, `app.css`, `index.html`, `server.py` are A's
**except** the single-line slots below; `site/`, `README.md`, `CHANGELOG.md`,
`specs/` are A's — B's changelog lines travel as fragments in HANDOFF.md.

## The single-line slots (B's only shared-file edits)

All four new tools are already on the rail as honest coming-pages
(`ready: false` in core.js — the coming.js mechanism does the rest). When
B's page first *works*, B makes exactly these edits, each one line, each in
a stable alphabetical slot, and nothing else:

1. `suite/server.py` — add `from .tools.memory import register_memory`
   (between kb and modelstore) and `register_memory(app, jobs, frames)`
   (same slot in the call block).
2. `suite/static/index.html` — add `<script src="/static/js/memory.js"></script>`
   after `kb.js`, before `queue.js`.
3. `suite/static/js/core.js` — flip `ready: false` → `ready: true` on the
   `memory` entry only. (coming.js only builds pages for not-ready tools,
   so the flip retires the placeholder and memory.js's page takes over.)

Same rule holds for A's tools (publisher now, interpreter/narrator with
whoever takes them). A never edits inside `memory/`; if A needs something
from B — or B from A — the ask goes in a handoff note and the owner makes
the change.

## Contracts (code to these, don't renegotiate them silently)

- **Store.** B's corpus lives under `czcore.paths.media_dir("memory")` —
  SQLite for the relational core, files beside it. The spec's
  Postgres/Qdrant/GCS is the hosted future, not this build (see
  "translation" below).
- **Jobs.** Every pipeline stage that takes real time runs through the
  suite's `JobManager` (`jobs.submit` from the register hook) so the Queue
  page and toasts show it. One queue is covenant.
- **ASR.** B never runs its own whisper: Scribe's engine and its
  `*.scribe.json` sidecar format are the transcript spine (see
  `scribe/`, `suite/tools/highlighter.py` `_sidecars()` for the shapes:
  `meeting.scribe.json`, `meeting.highlights.json`, `insight.json`).
- **Fetch.** Civic video arrives the way Grabber does it — `czcore.ytdlp`
  (nightly-check deal included) and Grabber's CivicClerk/Zoom patterns,
  imported, not reimplemented.
- **Detection seam.** A is extracting Highlighter's moment scoring into
  `czcore/moments.py` during the Publisher build. Until it lands, B needing
  detection wraps highlighter internals behind its own `memory/detect.py`
  adapter and swaps when A announces the landing (in "state of main" below).
- **LLM.** Generative passes go through `czcore/llm.py` (the guarded key,
  Anthropic or OpenAI by key shape) and every generative surface has an
  extractive fallback that stands alone without a key. No other network AI.
- **B's HTTP surface** (A builds UI against these, so they're stable once
  landed):
  - `POST /api/memory/submissions` — body `{url}` or `{path}` plus optional
    `{town, body, date}` → `{meeting_id, status: "exists"|"queued"}`, with
    the spec's dedupe (source URL → media hash → transcript similarity).
    This is what Highlighter's and Publisher's "Send to the Record" buttons
    call.
  - `POST /api/memory/context` — body `{texts: [...]}` (agenda items or
    transcript spans) → `{issues: [...], prior: [{meeting_id, ts, text,
    speaker}...], stats}`. This feeds the Prior-appearances panel.

## Translation (cloud spec → this suite)

The specs speak Cloud Run, Postgres, GCS, webhooks — the hosted, multi-station
future. In-a-Box v1 **is the suite**: local-only, no accounts, no telemetry,
covenant intact. Translate, keep the essence: Cloud Run Jobs → JobManager
jobs; Postgres → SQLite; Qdrant → local embeddings beside the store; GCS →
`media_dir`; webhooks → in-app events; "review queue UI" → a suite page;
auto-posting → export bundles and copy buttons (the spec's own v1 posture).
Every AI surface labeled, provenance shown, measurement on by default.

## Git ritual

- Lane A works on `main` and is the only lane that merges to it.
- Lane B works on `lane/memory`, merges `origin/main` into it at every
  session start and after any "state of main" announcement, commits small
  in the repo's voice (read `git log` first), pushes at every stopping
  point. Never pushes main.
- Wave boundaries: B finishes a coherent stage, updates HANDOFF.md, pushes;
  A merges `lane/memory` → main, folds changelog fragments, wires any
  integration asks, updates "state of main"; B re-merges main and continues.

## Handoff ritual

`memory/HANDOFF.md`, always current, in four short sections: **landed**
(what works, how to see it), **next** (what B starts after merge),
**asks** (changes wanted in A-owned files, exact and minimal), **fragments**
(changelog-ready lines in the house voice). A's side of the ledger is the
section below, updated on main.

## State of main (lane A updates this)

- 2026-07-17 (late) — **Detection seam LANDED: `czcore/moments.py`** —
  `score_segments`, `blend_energy`, `audio_energy`, `build_reel`, plus the
  VTT/transcript helpers (`parse_vtt`, `transcript_dict`).
  `highlighter/highlights.py` is now a re-export shim; import
  `czcore.moments` directly in new code (B: swap your adapter when
  convenient). Also landed: Home's wire (chain UX), and **cache-busted
  statics** — every include carries `?v={{v}}` substituted by the server,
  so hard-refresh rituals are dead; if you add your script tag, carry the
  `?v={{v}}` suffix like the others.
- 2026-07-17 — specs 12–15 committed; four community tools stubbed on the
  rail as coming-pages (core.js entries + accent vars); this agreement
  ratified. Publisher: in build (lane A). B is clear to begin Memory wave
  1 (ingest → pipeline → store → meeting pages → search, per specs/14 P0
  №1–3, 5).
