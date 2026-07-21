# Session prompt — specs/21: finish the spec (P2 → P3)

publicrecord.studio — specs/21 "be the editor of your own paper": finish the
spec (P2 data viz + analyses, P3 deepen). This prompt is the orientation;
`specs/21-web-studio.md` v0.3 is the source of truth.

## Where the world is

LIVE at edition **v2.1.8** (image `record/api:r30`, corpus `66c05a9544c70585`).
Shipped 2026-07-20/21, all live and verified:

- **P0** (v2.1.6/r28): the three-mode footprint — preview PILL / studio
  sidebar / paper — all in `web/static/app.js` + `app.web.css`; the §6.1
  palette amendment (two purples under `html.cz-m-studio` ONLY, zero fuchsia);
  the pressed paper byte-clean (guard test).
- **P1** (v2.1.7/r29): **your paper** — the curated document
  (`publicrecord.paper/1`: story blocks by pid/slug + reel blocks + title),
  edited in the studio panel (context adds, ↑↓✕, title field, share row),
  rendered at the `/app/p` stub, traveling as localStorage draft (`cz-paper`)
  / whole-paper link (`?v=1&t=…&b=m.<pid>,i.<slug>,r.<pid>:<s>-<e>~…`) /
  `paper.json` — **plus the share store, LIVE**: `POST/GET /api/papers` on
  record-api, strict validation (the title is the ONLY free text; refs
  fullmatch `[\w-]{1,128}`), server-side canonical bytes → sha256[:16] = the
  address, private bucket `publicrecord-papers` (created, IAM'd,
  `RECORD_PAPERS_BUCKET` set), no list, no delete API (takedown = steward,
  OPERATING §5/§6). Store checkpoint with Stephen: ANSWERED 2026-07-21 —
  API + private bucket, stories+reels+title cut, `/app/p` + sidebar shape.
- **Our AI Constitution** (`/app/ai`, canonical) + shareable
  **publicrecord.studio/constitution** (root hand-file in the Pages repo +
  pressed `/app/constitution` twin — OPERATING §5 "Hand-files" lists them);
  the sitewide footer recredit (weird machine + brookline interactive group +
  the constitution link); buttons on the covenant page + the town-scope block.
  Its ledger states models precisely — keep it TRUE: **when our use of AI
  changes, /app/ai changes in the same commit** (the page promises this).
- Two adversarial workflow passes folded 23 + 13 confirmed findings; the
  re-review repaired a pre-P1 live SW bug (bare-stub precache cached
  redirected responses — the shell now precaches slash-canonical forms,
  navigations slash-normalize, `!res.redirected` guards the cache).

885 tests. **~35 commits on control-z main NOT pushed to origin — by design;
do not push origin.** Pages repo (`amateurmenace/publicrecord`) is the deploy
artifact and IS pushed.

## Resolved — build to these, do not re-litigate

1. §6.1 palette: studio-scoped only (`#a855f7` surfaces / `#7c3aed` text-AA /
   `#22c55e` non-text under `html.cz-m-studio`); ZERO fuchsia anywhere; a
   rendered/shared/baked paper carries NO studio hue, ever.
2. §6.2 store: shipped as approved. Additive, never load-bearing.
3. Naming: **your paper / the editor / edit** ("edition" = the pressed
   record); the constitution is **Our AI Constitution**.
4. Dark mode for the reader: DECLINED (specs/20 Q3 — "ink on white").

## Settle with Stephen early (AskUserQuestion, before building the surface)

1. **P2 note/analysis blocks × the store**: a note block adds free text
   beyond titles to the stored form — extend `record/papers.py` deliberately
   (proposed: note blocks = plain text, length-capped ~2,000 chars,
   control-chars stripped, esc()'d at render like titles; same strict
   refusal; no markdown/html). Get sign-off on the cap + posture BEFORE the
   store accepts note blocks. (Client-side notes in links/paper.json can ship
   regardless — the store is the gated half.)
2. **P2 chart-block cut**: which charts a paper can carry (proposed: votes
   over time / an issue's reach across meetings / participation-speaking
   share / the framing lenses — all computable from the pressed planes).
3. Optional P3 taste call: featured/example papers as a front-page door.

## Build — one deploy per phase

- **P2 — data viz + analyses (v2.1.9 / r31).** Chart blocks computed
  CLIENT-side over the pressed planes (`analytics.json`, `graph.json`,
  votes/framing inside `meetings/*.json`) — **inline SVG only** (CSP is
  `script-src 'self'`, no libraries), **every chart with a table twin** (the
  rule the baked charts keep), charts wear the PAPER palette (deep-green
  measurement scale; no studio hue on any rendered paper). Note blocks per
  the checkpoint. Extend: normalizeBlock/portablePaper/encodePaperQS/
  decodePaper (+ node twins in `tests/test_web_bake.py::TestPaper`),
  `record/papers.py` `_block` (+ `tests/test_paper_store.py`), the panel
  (add-chart/add-note UI), the `/app/p` renderer. **Load the `dataviz` skill
  BEFORE writing any chart code.**
- **P3 — deepen (v2.1.10 or v2.2.0 / r32).** Templates, featured/example
  papers as a front door, polish; the deferred a11y nit (the mode control →
  radiogroup + roving tabindex); consider inline reel stages on `/app/p`
  (deferred from P1 — the `/app/r` player is a page-singleton: armed gate,
  settling, global onYT; P1 plays via `/app/r` links. Touch it carefully or
  not at all). Then mark the spec done (status + PARALLEL + memory).

## Read first, then verify live before acting

- `specs/21-web-studio.md` v0.3 (P0+P1 marked shipped) ·
  `record/OPERATING.md` (§5 deploy + hand-files + store provisioning; §6
  takedown) · `.claude/rules/branding.md` (the law + the 2026-07-21 footer
  amendment; gitignored).
- Memory — trust but verify: `specs21-web-studio` (the shipped shape, the
  traps), `specs20-newspaper-shipped` (the record arc + SW-STALENESS LAW),
  `publicrecord-verify-harness` (ALL the traps: in-app browser is
  localhost-ONLY; unregister the SW between local presses — same-version
  re-presses collide in the SW cache; HEADLESS-390 screenshots show FAKE
  clipping — trust pane JS geometry; the pane's document can be
  visibility:hidden — element.focus() silently no-ops; RENDERER-BLANK after
  scroll — prefer geometry checks; the SLATE — synthetic seed timestamps
  against real videos play dead air).
- The code you extend: `web/static/app.js` — "YOUR PAPER" section (PART 1
  model/codec is server-free and a test scans it: NO fetch/api text before
  the "PART 2: SHARING" marker; `normalizeBlock` is total, decodeReel's law:
  malformed → fewer blocks, never a throw), `refreshPaperSummary` (focus
  restoration: NEVER let a fallback land on ✕), `paper()` (gen guard, pooled
  `fetchPlanes` with tried-vs-gone honesty). `web/emit.py` `page_ai` (the
  ledger to keep true), `page_paper`, `emit_stubs` (shared by bake+press —
  parity free), the SW block (slash-canonical SHELL). `record/papers.py`
  (strict; canonical bytes server-side ONLY — the client never hashes).
  `tests/test_web_bake.py` (node twins; the pressed-CSS palette guard; the
  byte-clean guard; the API-door guard counts `/api/` occurrences — a new
  outbound path must be added there DELIBERATELY or it fails).

## Establish state

- `curl -s https://publicrecord.studio/app/manifest.json` → version 2.1.8.
- `nc -z localhost 55433` then
  `RECORD_TEST_PG_DSN=postgresql://record:record@localhost:55433/record_test .venv/bin/python -m unittest discover -s tests -q`
  → 885 green.
- `git -C ~/control-z log --oneline origin/main..main | wc -l` → ~35
  (unpushed by design).

## Deploy (proven 8×; pre-authorized per phase once its checkpoint is settled)

Suite green → `docker build --platform linux/amd64 -f record/Dockerfile -t
us-east1-docker.pkg.dev/publicrecord-studio/record/api:rNN .` → push → verify
the new code in-container → `gcloud run jobs update record-press
--region=us-east1 --image=…:rNN --args="^|^-m|record.press|--version|2.1.N"`
→ `gcloud run deploy record-api --image=…:rNN --region=us-east1` → `gcloud
run jobs execute record-press --region=us-east1 --wait` → clone
`amateurmenace/publicrecord` → `gcloud storage rsync -r
--delete-unmatched-destination-objects gs://publicrecord-edition/app app` →
gunzip gzip-magic files in place (OPERATING §5) → commit + push → verify live
(curls + headless Chrome DESKTOP; narrow via pane geometry). Never rebake the
public edition on this Mac. A code-only change still needs the version bump
or the SW serves stale JS.

## House rules

Full suite green before every deploy; tests for any plane/stage/JS change
(node twins for every codec change; store tests for every `_block` change).
Per phase: an adversarial review workflow (this sentence authorizes
workflows) — lenses: covenant, brand+a11y (AA verified numerically from
computed styles), backcompat vs the shipped reader AND studio AND store,
JS-off/mobile degrade, logic edges — fold every confirmed finding, then a
focused re-review of your own fixes (both P1 passes caught regressions the
fixes introduced; the re-review found a live bug older than the branch).
Verify in the pane (375/390 geometry) + headless desktop; PLAY anything
reel/paper-shaped against a real video (mind the slate — real moments sit
past it). Commit in coherent pieces in the house voice, ending
`Co-Authored-By: Claude <noreply@anthropic.com>`. After each phase:
CHANGELOG, spec status, PARALLEL "state of main", memory.

## Still Stephen's — do not do unprompted

Push the control-z monorepo to origin. Accept note-block free text into the
store before his posture sign-off. Make paper mode louder, or let any studio
hue reach a rendered paper. Raise the $100 GCP budget. The classification
residual tail. Touching the /app/r player singleton beyond what P3 needs.
