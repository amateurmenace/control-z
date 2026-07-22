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
endpoints.

**Lane C — seen and heard** (a third session; on lane A's machine it works
in a git worktree, never lane A's checkout). Builds **Community
Interpreter + Community Narrator** (specs/15) as the adjacent pair they
are: translated caption tracks in the seven panel languages + Simple
English with per-town glossaries, then the VOD audio-description
pipeline with its review timeline and the meeting-graphics wedge.

Lane C creates and exclusively owns: `interpreter/` and `narrator/`
(HANDOFF.md lives in `interpreter/`), `suite/tools/interpreter.py`,
`suite/tools/narrator.py`, `suite/static/js/interpreter.js`,
`suite/static/js/narrator.js`, `tests/test_interpreter*.py`,
`tests/test_narrator*.py` — plus, as the one czcore exception, the NEW
files `czcore/mt.py` and `czcore/tts.py` (translation and speech
engines the whole wing will eventually share; stdlib-guarded imports
per the house convention). Its single-line slots work exactly like B's:
import/register pairs in server.py (alphabetical), script tags in
index.html after publisher.js, ready flips on its own two core.js
entries. Everything else follows the lane B rules verbatim — branch
`lane/access`, merge main in at every session start, A merges you,
asks via HANDOFF.

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
- **Store seam.** `memory/store.py` grew an interface (`memory/seam.py`, the
  `CorpusStore` Protocol) and a policy module (`memory/policy.py`) so the desk's
  SQLite `Corpus` and publicrecord's Postgres store (specs/17) run the same
  engine. The SQLite implementation is unchanged in behavior and every existing
  `tests/test_memory*.py` passes untouched — that is the acceptance test, not a
  hope. Nobody reaches through `corpus._con()` any more: the two escapes in
  `memory/issues.py` became `linked_seg_ids()` and `unlink_meeting()`. An
  embedding is opaque across the seam — read it only through `embed.as_vec()`,
  never `from_bytes()`, because pgvector hands back an array where SQLite hands
  back bytes.
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

- 2026-07-22 (latest) — **specs/21 is DONE: P3 — templates, featured
  papers, the radiogroup — LIVE at v2.1.10 (image r32).** Templates write
  pre-shaped drafts client-side (empty-draft-only, confirm-gated, the note
  joins empty). Featured papers are built AT PRESS TIME in
  `emit.featured_papers` — computed inside `emit_stubs` from arguments
  bake and press already pass identically, so parity is structural — and
  travel as ordinary `/app/p?v=2` links; the Python codec twin
  (`_js_euc`/`_paper_qs`) is pinned byte-for-byte to `encodePaperQS` by a
  node parity test (decode → re-encode → identical, v= by `paperV`'s
  rule). The mode control is a real radiogroup with a roving tabindex —
  and it describes the PAINTED mode (`shownMode`/`shownRail` read the
  html classes; storage is the fallback), because a storage-blocked
  browser's radios must not claim "preview" over a visibly open studio.
  New laws worth knowing: a state-attribute migration must move the CSS
  selector WITH it (the review's HIGH: `[aria-pressed="true"]` styled a
  state the JS no longer writes — the pair is now test-pinned); a bare
  `var(--focus-ring)` without the `var(--state)` fallback resolves to
  outline:none and silently kills the global focus ring (the sheet
  documents it — believe it); links in pressed prose need underlines
  (G183: ink vs slate is 2.36:1); `n_of()` for every counted noun the
  bake prints. Namespaces now minted: `pf-` (featured cards), `.featline`,
  `cz-tpl*`. 903 tests. Two review passes folded 12+3. Live-verified
  2026-07-22: manifest 2.1.10, SW `cz-record-2.1.10-66c05a9544c70585`,
  API revision 00022-cl6 (r32, health ok/neural/steward), Pages commit
  5d9f6d4; the pressed featured papers are the real record's (the roll
  calls · Capital Improvement Projects across 10 meetings · the June 18
  School Committee) and the roll-calls link renders live with the real
  27 votes; both prod store papers (88ba5977746282f1, aab17fcb26e41b50)
  serve unregressed. specs/22 — the cutting room — is DRAFTED
  (`specs/22-cutting-room.md`) and awaits Stephen's settlement of §6
  (preview vs the /app/r singleton, named reels, make-this-yours, P0
  scope) before any surface builds.
- 2026-07-22 — **specs/21 P2: charts + notes — LIVE at v2.1.9
  (image r31).** A paper now carries pictures and its editor's own words:
  four chart kinds (votes over time on the NEW `votes.json` plane —
  `bake_votes` in BOTH web/bake.py and record/press.py, the parity test
  names it; an issue's reach; the framing lenses; recurring topics), all
  computed client-side from the pressed planes, paper palette, table twins,
  receipts under every mark. Notes: the editor's words, labeled at render;
  the store accepts them as the second and last free text (strict — 2,000
  UTF-16 units, newlines only; the checkpoint 2026-07-22). P2 papers travel
  as **v=2** (the shipped v1 reader degrades honestly); stories+reels
  papers stay byte-identical v=1 — links AND store addresses. Two
  adversarial passes folded 16 + 1 findings. New house laws worth knowing:
  free text in the `b=` param rides TWICE-encoded (URLSearchParams decodes
  once before the comma split); every free-text cap goes through `cut()`
  (lone surrogates make encodeURIComponent throw); check CSS class names
  against the whole sheet before minting (`.lensbar` was the meeting
  page's 9px pill and silently squashed the chart rows → `pb-` namespace).
  898 tests. Live-verified: store round-trip on prod (P2 paper
  88ba5977746282f1 with the real 27 roll calls), P1 paper aab17fcb
  unregressed, SW cache `cz-record-2.1.9`. P3 (templates + featured papers
  + the radiogroup nit) still owed; then specs/22 — the cutting room
  (`specs/22-session-prompt.md` is the orientation).
- 2026-07-21 — **specs/21 P1: your paper + the share store, AND the
  AI constitution. SHIPPED + LIVE, edition v2.1.7, image r29.** The making
  surface: a curated paper (schema `publicrecord.paper/1` — story blocks by
  pid/slug, reel blocks reusing the clip encoding, a title) edited in the
  studio panel (context adds, ↑ ↓ ✕, share row), rendered at the new `/app/p`
  stub (the `/app/r` pattern; `page_paper` in the shared `emit_stubs`, so
  press parity is free), traveling the three covenant ways (`cz-paper` draft /
  whole-paper link `?v=1&t=…&b=…` / `paper.json`) plus the content-addressed
  store **checkpointed with Stephen before the write path existed**:
  `POST/GET /api/papers` on record-api, strict validation (title = the ONLY
  free text; refs fullmatch `[\w-]{1,128}` — the bake mints pids to 80 and
  slugs to 96), server-side canonical bytes (tenth-second grid, sorted keys)
  hashed to a 16-hex address in the private `publicrecord-papers` bucket
  (us-east1; SA objectAdmin; `RECORD_PAPERS_BUCKET` env; ~$0/mo; takedown =
  steward removes the object — OPERATING §5/§6). Two adversarial workflow
  passes folded 23 + 13 confirmed findings; the re-review repaired a
  **pre-P1 live SW bug** (bare stub URLs precached redirected responses —
  offline navigation to /app/s etc. was broken; the shell now precaches
  slash-canonical forms, navigations slash-normalize, redirects never cache).
  The same pressing ships Stephen's mid-flight request: **`/app/ai` — the AI
  constitution** (eight checkable articles, the when/whose/where/without-it
  ledger — `gemini-embedding-001` search, labeled Gemini summaries/names,
  Whisper-family ASR on own hardware, no-model rows, the desk's local-only
  models — the Community AI Project band, resources; native interactivity,
  JS-off complete) and the **footer recredit** (weird machine + brookline
  interactive group + the constitution link; covenant/about + town-scope/
  settings buttons). Local `.claude/rules/branding.md` records the amendment.
  885 tests. **Next: P2 data viz + analyses (v2.1.8/r30).**
- 2026-07-20 — **specs/21 P0: the studio — be the editor of your own
  paper (the footprint shell). SHIPPED + LIVE, edition v2.1.6, image r28.** The
  reader can now become an editor: a three-mode footprint it controls — **preview**
  (a compact, non-blocking corner pill inviting you in), **studio** (a full left
  sidebar, the one place publicrecord's volume goes up), **paper** (the studio
  recedes to a tab; the specs/20 reader, untouched). The mode is a class on
  `<html>` kept in `localStorage` (`cz-studio-mode`, default preview); the existing
  `cz-reel` make-loop is surfaced (a count on the pill, a play/share/clear panel in
  studio), not rebuilt. Covenant-clean, byte-idempotent, JS-off/mobile → paper.
  Two adversarial passes folded in. **855 green.**
  - **`web/static/app.js` CHANGED** — a new "THE STUDIO" section (initStudio,
    markMode/setMode/readMode, the pill/tab/panel, refreshReelSummary reading the
    global `cz-reel`); `saveReel()` and `wireComposer()` now also call
    refreshReelSummary; `toast()` moved to the `.cz-toast` class. **Any lane
    touching the reader: the studio is script-built and appended as `<body>`'s
    FIRST child; a new `<html>` mode class (`cz-m-preview|studio|paper`) + optional
    `cz-rail` govern a body padding-left in studio mode. localStorage keys added:
    `cz-studio-mode`, `cz-studio-rail`.**
  - **`web/static/app.web.css` CHANGED** — a studio block at the end. The
    **branding amendment (specs/21 §6.1) is now live**: two purples (`#a855f7`
    surfaces/borders, `#7c3aed` text at AA) + `#22c55e` (non-text), all under
    `html.cz-m-studio` ONLY; paper/preview/masthead stay quiet; zero fuchsia.
  - **`tests/test_web_bake.py` CHANGED** — the pressed-CSS palette guard now
    admits the two purples *only* in a studio-scoped rule (still bans fuchsia +
    the desk palette everywhere); new `test_the_studio_is_script_built_never_baked`
    (paper stays byte-clean); new `TestStudioFootprint` (readMode validation +
    make-path-touches-no-server, run in node).
  - **`web/emit.py` UNCHANGED** — P0 is client-only; the pressed HTML is identical
    to v2.1.5 except the `?v=` bump. (No bake/press-stage change → parity holds.)
  - **Deployed** — code-only reader change, so image `r28` + version bump `2.1.6`
    (SW cache) + press + Pages rsync/gunzip. Live verified (headless Chrome desktop
    + 390px). **Next: specs/21 P1 (the curated-paper document model + the
    content-addressed share store, behind a checkpoint).**

- 2026-07-20 — **specs/20 P2-B/C: cross-meeting reels + per-issue RSS —
  P2 (and the spec) finished.** A reel can now span meetings and years, still
  client-only and living entirely in its link; per-issue feeds gained head-level
  discovery + dated items. Dark mode declined for the reader (Q3 → "never,"
  revisitable). Covenant-clean, v1 links byte-identical, **849 green.**
  - **`web/static/app.js` CHANGED** — the reel model spans meetings: `REEL_VS`
    (v1+v2), `decodeReel` returns `clips:[{pid,start,end}]` (v1 clip inherits
    `m=`, v2 clip is `<pid>:<start>-<end>`), `reelShareURL` picks v1/v2 by span; a
    single global `cz-reel` tray (was per-meeting) with each clip tagged by
    meeting + a one-time migration; the viewer fetches every meeting the reel
    touches and switches tape with `loadVideoById` at a boundary. reel.json stays
    single-meeting (cross-meeting render is a future desk step). **Any lane
    touching the reader's reel: the share link is now v1-or-v2 and the composer
    key is global (`cz-reel`), not `cz-reel-<pid>`.**
  - **`web/static/app.web.css` CHANGED** — `.rt-from`/`.rc-from`/`.rt-other`/
    `.rn-from` (the meeting labels; tokens only).
  - **`web/emit.py`, `web/bake.py` CHANGED (P2-C)** — `_feed_link` + `head`/`shell`
    grow an optional `feed=` (per-issue `<link rel=alternate>` discovery, before
    the firehose); `page_reel` lede reworded (one meeting or several); `_rfc822` +
    `<pubDate>` on feed items (deterministic, no wall-clock). No existing plane
    changed; the per-issue feeds already existed.
  - **`tests/test_web_bake.py` CHANGED** — TestReel gains v1↔v2 round-trip, the
    (meeting,kind,time) identity, and the tape-switch (loadVideoById only across
    meetings); the P1 seek-engine + reel.json + cite proofs hold unchanged.
  - **Deploying** — a code-only reader change (no new data plane), so image `r26`
    + version bump `2.1.4` (SW cache) + press + Pages rsync/gunzip.

- 2026-07-20 — **specs/20 P2-A: the kit plane — Publisher's reading
  half moves in.** `/app/k` pages a read-only publish kit for every meeting with
  a video and moments: the clips worth cutting (from the `moments` plane) + draft
  copy assembled from the transcript, no model. The `kit.json` is a real
  Publisher kit a producer opens at the desk to render; rendering stays there and
  the page says so. Auto-derive + quiet, per Stephen's call. Covenant-clean (no
  server call, `connect-src 'self'`, JS-off readable), byte-idempotent, palette
  quiet. Five-lens adversarial review folded in. **847 green.**
  - **`czcore/kit.py` NEW, `publisher/kit.py` CHANGED** — the pure copy writer
    (`copy_extractive`, `kit_from_parts`, the small text helpers) moved to shared
    core so desk + record kits can't drift; `publisher.kit` re-imports the old
    names, surface unchanged. **Lane B/C: the desk's kit copy now lives in
    `czcore.kit`, not `publisher.kit`.**
  - **`web/kit.py` NEW** — `kit_from_meeting` derives a kit from a pressed
    meeting (gates: no video or no moments → no kit).
  - **`web/bake.py`, `record/press.py` CHANGED** — a `bake_kits` stage in both,
    writing `kits/<pid>.json` + `kits/index.json`; **`tests/test_press_parity.py`
    NEW** holds the bake/press stage sequences equal (the drift press.py warns of).
  - **`web/emit.py`, `web/static/app.web.css` CHANGED** — `page_kits_index` +
    `page_kit` (`/app/k`), the Publisher press-row flip (only when kits pressed).
    New reader URLs: `/app/k`, `/app/k/<pid>`, `/app/kits/<pid>.json`,
    `/app/kits/index.json` — additive, no existing plane touched.
  - **`record/Dockerfile` CHANGED** — cold-start import check now names
    `web.bake`/`web.emit`/`web.kit` (the press's lazy kit chain).
  - **`tests/test_web_kit.py` NEW, `tests/test_web_bake.py` CHANGED** — the plane,
    the pages, the press-row flip, and a **cross-process idempotence guard** (two
    presses under different `PYTHONHASHSEED` must be byte-identical).
  - **Deploying** — a new data plane + reader, so a full container reship:
    image `r25`, version bump `2.1.3` (the SW must not serve cached JS), press,
    Pages rsync + gunzip. Verify live on the real corpus (headless Chrome + 375px).

- 2026-07-20 — **specs/20 P1 follow-up: the moment labels earn their
  kicker.** The moments plane read a celebration as a `DECISION` because the
  shared analyzer matched keywords as bare substrings (`voted` inside
  "de**voted**", `motion` inside "e**motion**"), and `TENSION` fired on any bare
  "concern"/"problem". `czcore.moments.hits_in` now matches word-like keywords
  on a *leading* word boundary (votes/voted/unanimously survive; deVOTEd/eMOTION
  don't; `$`/`[applause]` stay substring) — a correctness fix inherited by
  `score_segments` and `insight.decisions`/`disagreements`/`dynamics`. The paper
  holds a bar above Highlighter's recall, all in `web/bake.py`: stored decisions
  re-validated on the boundary + gated for narration ("passed away", "sent … for
  approval"), soft tension words gated unless *owned*, roll-call mechanics gated.
  Verified against the 10 real transcripts (~70 keyword FPs drop, as many real
  moments rise) + an independent judge/blast-radius panel. 832 green.
  - **`czcore/moments.py`, `highlighter/highlights.py`, `highlighter/insight.py`
    CHANGED** — `hits_in` (leading-boundary matcher, re-exported by
    `highlights.py`); `decisions`/`disagreements`/`dynamics` route through it;
    `KEYWORD_CLASSES` gains `disapprove`/`disapproval` (decision) and
    `unfunded`/`underfunded` (money). **The shared-analyzer change touches every
    czcore consumer** — audited net-positive, but lane B/C should know the match
    is now leading-boundary, not substring. **`web/bake.py` CHANGED** —
    `_real_decisions`, `_is_weak_tension`, `_is_narrated_decision`, the
    procedural + narration decision gates; `_build_moments` recomputes nothing
    it didn't already, it re-validates the stored decisions it reads.
    **`tests/test_highlights.py`, `tests/test_web_bake.py` CHANGED** — the
    boundary matcher (inflections kept, substrings dropped, symbols intact) and
    the newspaper gates.
  - **Shipped as v2.1.2 / image r24** (2026-07-20, after Stephen reviewed the
    before/after artifact) — a code-only edition change with a version bump so
    the service worker didn't serve returning readers the cached JS; same P0/P1
    deploy flow (image rebuild → job updates → press → Pages rsync + gunzip);
    verified live (no celebration-decision, real tension). No new data plane.

- 2026-07-20 — **specs/20 P1: the reel composer + the `/app/r`
  viewer.** Highlighter's composing half, moved into the browser — client-only,
  over the `moments` plane P0 presses. On every meeting page, a tick on each
  Moments card builds a reel tray (reorder, trim to segment bounds, live
  runtime) with three outputs: a **share link** (`/app/r?v=1&m=<pid>&c=<t>-<end>,…`,
  state in the URL + localStorage, no server), a **cite sheet**, and a
  **`reel.json`** the desk Highlighter opens to render (mapped onto
  `highlighter/reel.py`'s `render_reel`). `/app/r` decodes a shared link, fetches
  the meeting's own plane, and plays the sequence clip to clip through the
  youtube-nocookie facade. Verified on a local press (real video → real
  playback) + 822 tests green.
  - **`web/static/app.js`, `web/static/app.web.css`, `web/emit.py` CHANGED** —
    the composer + viewer + `page_reel` stub (written in `emit_stubs`, so
    `record/press.py` mirrors it for free); Moment cards wrap in `.mo-card` and
    carry `data-end/kind/quote`. **No new `/api/`, no new server call**: the
    reel path's only fetch is the meeting plane under `/app/`, and the R1.6
    degradation proofs still pass (`js.count("/api/")==1`). **`tests/test_web_bake.py`
    CHANGED** — a `TestReel` class runs the round-trip / cite sheet / reel.json /
    seek-engine in node, plus the stub + JS-off fallback + the reel-path
    covenant. Tidy: the undated coverage-strip label (`ed` → `—`).
  - **Deploy**: same flow as P0 (`record/OPERATING.md` §5) — image rebuild
    (`record/api:r22`), `record-press` + `record-api` job updates, press, Pages
    rsync + gunzip-in-place. No new data plane, so no new bake stage.

- 2026-07-19 — **specs/20 P0: the record gets its own face.**
  publicrecord.studio now serves an ink-on-white newspaper, pressed from the
  cloud (image `record/api:r21`, corpus `66c05a95`) and live. The edition takes
  publicrecord's own tokens from `brand/` (the single source for this product;
  no cream/oxblood/amber/fuchsia survives the press) with self-hosted Inter +
  JetBrains Mono; a newspaper front page (lead story, briefs, by-the-numbers,
  the long view, access ledger, roll-calls teaser); a Moments panel + minimap +
  sticky header on every meeting; instant search with hover peeks and keyboard
  paths; one `/app/press` page with the thirteen doors quiet as redirect stubs;
  and tombstones for forgotten issues. 816 tests green.
  - **`web/emit.py`, `web/bake.py`, `web/static/app.web.css`, `web/static/app.js`
    CHANGED** — the whole edition restyled; a moments plane pressed per meeting
    (`czcore.moments.score_segments`, idempotent); the press page + door stubs;
    `page_tombstone`. **`web/static/fonts/` NEW** (6 subset woff2 + OFL). The
    R1.6 live-first/static-always machine is untouched; its degradation proofs
    still pass. **`brand/` joins the Dockerfile COPY**; the dead
    `suite/static/app.css` copy leaves.
  - **`record/store.py`, `memory/store.py`, `memory/seam.py` CHANGED** —
    `list_forgotten()` on the seam (audit ledger on Postgres, `[]` at the desk),
    powering tombstones. **`record/press.py` CHANGED** — mirrors the bake's new
    `bake_tombstones` stage, so the hosted press emits tombstones too.
  - **Deploy**: `record/OPERATING.md` §5 corrected — this gcloud version's
    `storage rsync` uses `--delete-unmatched-destination-objects` (not `-d`) and
    downloads the bucket's gzip objects RAW, so the Pages sync must decompress
    in place before pushing. Both `record-api` (rev 00010) and `record-press`
    now run `r21`.

- 2026-07-19 — **publicrecord R1: the record breathes.** The wave-1
  backend went from deployed to alive. Live on Cloud Run in project
  `publicrecord-studio`: 11 meetings, 80,856 segments, the neural half embedded,
  the console signing a steward in, hosted ingest having carried one meeting end
  to end, and a nightly poll+ingest per town. On `main`, 801 tests green (Postgres
  cases skip without `RECORD_TEST_PG_DSN`).
  - **`record/pipeline.py` NEW** — drains the approved submissions queue through
    `memory/ingest` (store-agnostic; the parity suite is what lets it reuse the
    desk's engine). Files `asr_tasks` for caption-less meetings; embeds the one
    new meeting, never the town.
  - **`record/store.py`, `record/app.py`, `web/emit.py`, `web/bake.py`,
    `web/static/app.js` CHANGED** — live-first search. The bake takes `--api`;
    the reader calls it and falls back to its static index when it is dark;
    `/api/search` gained `body` and CORS (`RECORD_READER_ORIGINS`, allowlist, no
    credentials). A desk edition stays byte-identical. Vector search moved into
    a segments-only subquery so the HNSW index is actually used (45s → 0.4s).
  - **`record/connectors/youtube.py` CHANGED** — the poll now applies the intake
    rules it never called (default-deny restored), and gained `--all-towns` for
    the nightly scheduler.
  - **Cloud Run jobs**: `record-pipeline`, `record-poll`, `record-embed`,
    `record-press` created; `record-nightly-poll`/`-ingest` schedulers.

  **R1.7 landed — publicrecord.studio is live.** Not by the specs/18 site-move
  (which needs `control-z-tools` public) but by a second public repo,
  `amateurmenace/publicrecord`, with its own Pages+CNAME serving the cloud-pressed
  live-first edition. control-z.org never moved and never went dark; both verified
  in a browser. Refresh flow in `record/OPERATING.md` §5. **R1.8 (the split + the
  full control-z.org→tools reorganisation) is still deferred** — repo surgery plus
  the signing machine for the DMG proof.

  **Two facts to carry forward.** The record shows 215 active issues because
  Stephen deleted one through the console (audited `forget`), not because the
  import was short (it arrived whole at 216); the console works end to end, and
  hosted ingest carried two meetings, one Stephen approved himself. And the R1.7
  shortcut leaves the tombstone question open — `control-z.org/app` still carries
  the deleted issue's page while publicrecord.studio does not, so a citation to it
  wants a tombstone, not a 404.

- 2026-07-18 — **publicrecord, wave 1: the record moves in.
  `record/` joins the tree; `memory/` grows a store seam. 648 tests green
  (39 skip without a Postgres).** On branch `lane/studio`, not yet merged.
  Nothing is provisioned on GCP and no bill has started — the whole wave was
  built and proven against a local Postgres, and `record/INFRA.md` is the
  runbook for the day that changes.
  - **`memory/seam.py` + `memory/policy.py` NEW — the store seam.** One
    interface, two implementations: the desk's SQLite `Corpus` and
    `record/store.py`'s `PgCorpus`. `tests/test_record_store_parity.py`
    states 73 guarantees once and runs them against both.
  - **`record/` NEW — the hosted record.** FastAPI (`app.py`), Postgres +
    pgvector (`store.py`, `migrations/`), Google Sign-In on an allowlist
    (`auth.py`), the eight curation verbs with an audit log (`steward.py`),
    the nightly YouTube poll (`connectors/youtube.py`), the press
    (`press.py`), the neural search seam (`embed_neural.py`), and the
    `corpus.db → studio` import (`import_desk.py`).
  - **`docker-compose.yml` + `record/Dockerfile` NEW.** In-a-Box v2's shape,
    and how wave 1 was proven.
  - **`pyproject.toml`** gains the `studio` package, its `migrations/*.sql`
    package-data, and a server-only `studio` extra. **Deliberately NOT added
    to `packaging/suite.spec`** — a signed desktop DMG has no business
    carrying a Postgres driver, and a silent omission is the bug the 1.9.0
    audits taught us to name.

  **B: your paths changed, for the first time.** `memory/store.py` gained
  `linked_seg_ids()`, `unlink_meeting()`, `close()` and `unit()`; its shared
  rules moved to the new `memory/policy.py` (with `_loads`,
  `_dedupe_keep_order`, `_keyword_set`, `_MEETING_COLS` kept as aliases);
  `search()`/`semantic()` gained a `town` argument defaulting to today's
  behavior; and `forget()` now clears `issue_segments` — it never did, and
  `list_issues` counted the orphans while `issue_appearances` hid them.
  `memory/issues.py` lost its two `corpus._con()` escapes and
  `memory/documents.py` reads embeddings through `embed.as_vec()`.
  **No signature was removed, no return shape changed, and every
  `tests/test_memory*.py` passed untouched.** Re-merge main before your next
  wave; if you were mid-flight on either file, say so in HANDOFF and A will
  rebase you.

- 2026-07-18 — **1.9.0: the record, drawn — the desk's
  analytical eye goes public. 500 tests green; both version truths at
  1.9.0.** The public edition (`web/`) grew the desk's Highlighter-analyzer
  and Library reads, all baked (pure-view, deterministic, CSP-clean):
  - **Meeting pages** now carry the eight civic **framing lenses** (with
    first/second-half drift), the **questions** asked typed by kind, and
    tension moments — computed at press time via `insight.framing`/
    `questions`/`disagreements` (added to `bake_meetings`' analysis).
  - **`/app/analytics` ("The record, drawn")** + `bake_analytics` →
    `analytics.json`: cross-meeting framing heatmap, recurring topics,
    recurring names.
  - **`/app/graph` (the issue graph)** + `bake_graph` → `graph.json`:
    issue co-occurrence as inline SVG (+ a table twin).
  - The offline SW cache is now keyed on version+corpus_hash (a release
    bump busts a returning reader's stale shell).
  - 1.9.0 is the release to sign (1.7.1 was the last signed; 1.8.0 never
    shipped). RELEASE-NOTES-1.9.0.md covers 1.7.1→1.9.0. **B/C: nothing in
    your paths changed** — the web edition is a downstream reader of the
    corpus + `highlighter/insight.py` (imported read-only at bake).

- 2026-07-18 — **lane/desk merged: Index gets a data spine and
  the road. 497 tests green.** The desk lane folded into main (no squash,
  five house-voice commits kept) on top of 1.8.0 — zero conflicts. What it
  added, and where NOT to edit underneath it:
  - **`czcore/sidecars.py` NEW — the sidecar law.** One table of every
    suffix the tools leave beside a source (words/captions/cut/moments/
    insight/kit/pivot/clear) + one reader. This is now THE place any tool
    asks "what does this clip carry?" — B/C: read it rather than re-learning
    a naming convention. (A module-top static import in `indexer/catalog.py`,
    so no pyproject/suite.spec change was needed.)
  - **Index rows now carry a `carries` list**; `catalog.stats()` gained
    per-kind `coverage`+`wordless`; `gaps(kind)` + `scan(only=[paths])` are
    new; pre-1.8 catalogs grow the column via a one-line migration.
  - **New routes** `/api/index/{gaps, transcribe-missing, road,
    road-stages}` — the coverage band and "the road" (tick clips → words/
    rescue/reframe stages, one clip-major queue job, `_road_plan` pure +
    tested, re-run refuses with skips named).
  - **Desk lane OWNS** (don't edit underneath): `czcore/sidecars.py`,
    `indexer/`, `suite/tools/indexer.py`, `suite/static/js/index.js`, the
    eight production `*.js` pages, `tests/test_index_desk.py`. Its ledger is
    `indexer/HANDOFF-DESK.md`.
  - Also fixed a pre-existing ~7% flake in `tests/test_jobs.py::
    test_listeners_fire` (it waited on `job.status` then asserted on the
    listener's `seen` — now waits on the listener's own view).
  - **B/C: nothing in your paths changed.** Re-merge main at session start.

- 2026-07-18 — **1.8.0: the record grew teeth. Documents,
  the Vote Ledger, web wave 2, and local hinges on the last two API
  doors. 480 tests green.** Everything below landed on `main` directly
  (lanes B and C are both fully merged and dormant — `origin/lane/memory`
  and `origin/lane/access` carry no commits ahead of main; re-merge main
  if either wakes).
  - **Corpus grown:** eight more real Brookline meetings ingested
    (captions-first, the watch-page route) — ten live meetings, ~72k
    segments, 216 auto-issues. A genuine cross-time **resurfacing** fired
    (a followed thread reopened by a later meeting, with a real quoted
    delta) — the events table is no longer empty.
  - **Documents (memory/documents.py) — specs/14 №11 done.** New store
    tables `documents`, `doc_chunks`, `issue_documents` (all in
    `memory/store.py` `_SCHEMA`, additive, with full cascade in
    `forget`/`delete_issue`/`merge_issues`/`clear_auto_issues`). CivicClerk
    PDFs fetched via the Grabber patterns, extracted with **pypdf** (new
    dep — requirements.txt + pyproject suite extra + suite.spec
    hiddenimport), chunked with page numbers, embedded through
    `memory/embed.py`, linked to issues by the `_assign` twin. Interleaved
    on the issue timeline (`_timeline` + `_paper_by_meeting`) and the web
    edition. **C:** documents ride beside your translation tracks with no
    change to your paths.
  - **Vote Ledger (memory/votes.py) — specs/14 №12 done.** New `votes`
    table; roll calls read extractively off the transcript, officials-only
    by construction (a roll call *is* the board voting; the agenda supplies
    the roster that canonicalizes ASR-garbled names). Per-issue ledger +
    a per-member **The votes** page (`/api/memory/officials`). A votes
    stage runs inside `ingest.run` (fail-open like issue assignment).
  - **Web wave 2 (web/):** **Publish the record** (a desk button →
    `/api/memory/publish` → the bake as a job + the edition diff + the push
    ritual), documents/votes/officials planes in the bake, **Still
    watching** + follows export/import, and an **offline PWA**
    (`sw.js` + `manifest.webmanifest`, deterministic, CSP-clean). The
    edition is re-pressed and ready for the gh-pages deploy.
  - **Local hinges (czcore/mt_local.py, czcore/vision.py) — specs/15.**
    Interpreter and Narrator try an on-device model first, fall back to the
    key, label every track by what drew it. `mt.available()` and
    `narrator` status grew a `local` engine; `describe_frame` now returns
    `(text, origin)`. **C:** the vision provenance is origin-aware now —
    the chip branches `local:`/`ai:`; nothing you own changed shape beyond
    that return value. Discovery-by-shape lives under `models/vlm/` and
    `models/mt/` (namespaced away from the TTS voice discovery on purpose).
    Model *cards* are a follow-up (hosting + hash pin), and NLLB's
    non-commercial licence is flagged for a deliberate call.
  - **Two version truths bumped to 1.8.0** (statics cache-bust off it).

- 2026-07-18 — **The desktop app is signing-ready, and the web
  app shipped (specs/16 Wave 1).**
  - **Signing (packaging/):** `suite.spec` was stale since the last
    signed release (1.5.0) — it named the make-wave packages but not the
    community wing and never shipped Interpreter's seed glossaries
    (PyInstaller ignores pyproject package-data). Fixed: publisher/memory/
    interpreter/narrator + czcore.mt/tts named as hiddenimports,
    `interpreter/glossaries` shipped as datas, and `build_suite.sh` gates
    on the seed like it gates on the Scribe VAD model. `RELEASE-NOTES-1.7.1.md`
    carries everything since 1.5.0 and the operator ritual; it supersedes
    the unsigned 1.6/1.7 tags. The second Mac runs build → sign → notarize;
    nothing else blocks it. (NOTE still owed at ship: a NOTICE line for the
    vits-ljs voice + glossary seeds.)
  - **The web app (`web/`, lane-A in-tree, NOT a separate lane W):** the
    record pressed into a static edition. `python -m web.bake` →
    `site/docs/app/`. Wave-1 P0 complete (bake, reader, dashboard,
    Add-a-meeting, doors, mark, covenant), 14 tests. It reads the corpus
    read-only and NEVER edits `memory/` — B and C are untouched. It
    re-implements Memory's pure view functions rather than importing them;
    the §8 shared-render extraction stays a future consolidation (an ask
    to the Memory owner if/when it's wanted). Deployed nowhere yet; a
    Cloudflare quick-tunnel served it publicly for cross-network testing.
  - **B/C: nothing changed in your paths.** Re-merge main at session
    start as always. The web edition is a downstream reader of your work
    — if you change a corpus/route/sidecar shape, the bake reads it
    through the same accessors, so flag shape changes in HANDOFF as usual.

- 2026-07-18 — **1.7.1: one timeline, the record drawn, the
  spend in view.** What moved that touches the lanes:
  - **The Library page (id "kb") retired from the rail**; its engine
    (/api/kb/*) stays and grew `/api/kb/context` (transcript around a
    second) plus montage picks that say `"vid:<id>"` (resolved to the
    Highlighter session). Its charts were rebuilt as **czAnalytics**
    (`suite/static/js/analytics.js`, A-owned) and render in two homes:
    the end of Highlighter's analyzer and Memory's new Analytics view.
  - **B: lane A edited memory.js** (Stephen's direct ask — apologies
    for reaching across; the diff is small and marked): an 📊 Analytics
    button + `#mem-analytics` view calling `czAnalytics.renderInto`,
    and `czTray.btnHTML(...)` ⊕ buttons on search hits and appearance
    beads (guarded on `window.czTray`, source `"vid:"+meeting_id`).
    Keep or reshape freely — the czTray/czAnalytics APIs are stable.
  - **C: describe.py now calls `llm.complete_vision()`** — your
    request shape moved into czcore/llm.py as offered; describe.py's
    ask #3 is done. Behavior identical, and vision tokens now land in
    the suite-wide AI audit.
  - **czTray** (core.js): the suite-wide reel timeline — bottom bar on
    every page, localStorage-persistent, renders via /api/kb/montage.
    Emit `czTray.btnHTML({source,start,end,label,title})` anywhere;
    a delegated handler does the rest.
  - **The AI audit**: czcore/llm.py counts every call (provider usage
    numbers) and the JOB RUNNER attributes it — `jobs._run` stamps
    `llm.set_tool(job.tool)`, so your generative passes are counted
    with zero edits on your side. Settings → AI audit shows the
    session; `llm.last_usage()` gives a per-call line if you want one
    on your own surfaces.
  - Also: the nested-scroller wheel fix in core.js (an inner box owns
    the wheel only after a click inside), `overflow-anchor` off inside
    pages, footer reads "designed + developed". **427 tests green.**

- 2026-07-18 — **THE WING IS HOME. Version 1.7.0 on both
  truths; 423 tests green.** Both lanes merged clean (one script-tag
  slot conflict, resolved by keeping every line — the law worked).
  What landed with the merge, by handoff ask:
  - **pyproject truths:** `memory`, `interpreter`, `narrator` in
    packages; `interpreter/glossaries/*.json` in package-data. B's
    sys.path fallback in `suite/tools/memory.py` retired as requested.
  - **C's voice ask went further than asked:** czcore/models.py grew
    an `archive_dir` mechanism (a model can be a DIRECTORY, kept from
    a tarball member-dir, manifest-hashed — one `relpath\0sha256`
    line per file, sorted — same pinned covenant; tests in
    test_models.py) and **vits-ljs has its registry card** — pin
    verified against a fresh upstream download AND the installed
    voice; the Models page shows it present. C: `czcore/tts.py`'s
    manual-install sentence is yours to retire for a "the Models page
    installs it" sentence whenever you like.
  - **B's issues door is live:** Highlighter's record line renders
    `r.issues` as pills — each opens Memory at the issue timeline via
    `go("memory", {openIssue: id})`. Dark until a record holds enough
    meetings to draw issues; wiring is in.
  - **A walk-found fix you should know about:** the first ⬛ Send to
    the Record from a URL session filed it as a *file* (S.source is a
    session path whose stem is the video id; meta lacked webpage_url)
    and ingest errored at the Scribe road. Fixed A-side twice over —
    `sendToRecord()` renames a link-shaped `path` to `url`, and
    Highlighter's button names URL sessions
    `youtube.com/watch?v=<ytId()>`. B: nothing needed, but if you want
    `resolve_input` to treat a URL-shaped `path` as a `url` too,
    that's a one-line hardening on your side.
  - **Floor-walked on this machine:** Home reads 4 of 4 + seen-and-
    heard 3 of 3 with zero home edits; June 18 School Committee sent
    from Highlighter → landed as captions (7,790 segments, Brookline,
    2026-06-18); "METCO program" answers 60 timed moments; the prior-
    appearances line reads 6 back; Interpreter's seven-track kit +
    reviewer-corrected es VTT NOTE verified; Narrator's zoo AD pass
    plays — narration measured at 14.625s, in the elephant's pause;
    June 18 still reads English in Highlighter (the `translated.`
    infix holds).
  - **Next:** B — live cross-time proof (a post-May meeting fires a
    real resurfacing), then Documents/Vote Ledger (P1 №11–12). C —
    the full-meeting AD proof; a full recording fetched via Grabber →
    Highlighter is the target; measure the ≤15-min-per-hour review
    honestly. Both: re-merge main at session start. A holds: site
    cards for the four community tools + RELEASE-NOTES-1.7.0.md at
    the signing ritual (deferred deliberately — the site is
    undeployed and unsigned releases don't get notes).

- 2026-07-17 — **The suite is wired for you, B.** Highlighter
  and Publisher both render ⬛ Send to the Record buttons and Highlighter
  renders a prior-appearances line — all gated on `toolById("memory")
  .ready` and calling the §Contracts routes exactly (`/api/memory/
  submissions` with `{url}` or `{path}`; `/api/memory/context` with
  `{texts:[…]}` reading `r.prior[].text`). When you flip `ready:true`,
  every button and panel goes live with zero lane-A edits — so keep the
  contract shapes or say so in HANDOFF first. Helpers you can reuse:
  `sendToRecord(payload, btn)` + `recordBtnHTML(id)` in core.js.
  Publisher is READY (thumbnails, per-field copy, lower-third controls);
  chain hand-offs run Grabber → Highlighter → Publisher end to end.
  294 tests green.

- 2026-07-17 (later) — **The app is the Community AI Project now**:
  window/tab/brand renamed, rail reordered (Civic Media Suite section
  on top; your memory entry lives there), Home runs a conveyor of the
  civic chain, Grabber is a search-first desk with schedules and a
  broadcast re-namer, Index browses on open, and `czProgress(container,
  {label, acc})` in core.js is the house progress card — use it for any
  long job UI you build. Statics now cache-bust on version + mtime.
  Nothing in your owned paths was touched. 294 tests green.

- 2026-07-17 (night) — **Publisher is LIVE at BIG-dev (beta)**: engine
  (`publisher/`), page, registration — and the single-line-slot playbook
  is now demonstrated in history (commit 39a0484: server.py import +
  register between pivot/rise, index.html tag after kb.js with the
  `?v={{v}}` suffix, one ready flip in core.js). Version on main is
  **1.6.0** (both truths) — statics cache-bust off it, so don't ship a
  page without bumping nothing; the suffix rides `__version__`
  automatically. Home's wire flips a chain step solid when its `ready`
  goes true — no home edits needed when Memory lands. Full suite green
  in the venv (284 tests).
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
