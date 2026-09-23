# Session prompt — publicrecord.studio: finish the vision

The vision, in one line: **a public record any town can own — it reads with
the servers gone, it grows nightly from the towns' own channels, anyone can
cut and edit what matters into reels and papers, and every place AI touches
it is named and checkable.** The reading half shipped (specs/17→20). The
studio shipped whole (specs/21). What remains is three arcs: **finish the
making half (specs/22), make the record GROW again and scale it, and keep
the openness honest.** This prompt is the orientation; the specs it names
are the sources of truth.

## Where the world is (verified 2026-09-23)

- LIVE at **v2.1.10** (image r32, SW `cz-record-2.1.10-66c05a9544c70585`),
  API healthy (rev 00022-cl6), neural up, store serving
  (`aab17fcb26e41b50` etc.). 903 tests at HEAD. All of specs/17–21 shipped.
- **The corpus is FROZEN at 2026-06-18** — 12 meetings, 2 towns, 63.9 h; no
  new meeting in three months despite the nightly schedulers. `described: 0,
  languages: 0`. This is the loudest gap in the vision.
- **HEAD = `6abb278`** (specs/22 settled). The working tree holds a
  **~531-line UNCOMMITTED partial of specs/22 P0** (app.js +328, css +60,
  tests +185: `toggleCut`/`wireSegTicks`/`wireBeadTicks`/`searchTick`,
  `parseSegTimes`/`segBounds`/`stepEdge` segment-snapped trim,
  `writeTray`/`trayAct`, `TestCuttingRoom` ×5). Provenance unknown session;
  no review arc; not committed. **Inspect it first — adopt what survives
  reading, rewrite what doesn't, never commit it blind.**
- **The record's public home now exists:**
  `github.com/amateurmenace/publicrecord-studio` (created 2026-09-23,
  extracted from control-z@6abb278 — the Dockerfile's exact closure, 536
  tests green standalone). control-z on GitHub is 46 commits stale by
  design; the covenant/constitution still point `SOURCE_REPO` at it.
- Test Postgres (localhost:55433) is DOWN — start it before the suite
  (`docker start` the record-test container, or see OPERATING §8).

## Resolved — build to these, do not re-litigate

All of specs/20+21's laws (palette bounds, zero fuchsia, paper-mode quiet,
store strictness — free text = title + notes ONLY, covenant client-only
compose), and specs/22's five settled answers (Stephen 2026-07-22): new-tab
preview NOW / scoped stage LATER as its own phase; ONE tray +
file-into-paper (no reel library); append-or-replace EXPLICIT on open;
all three cutting surfaces in P0 (transcript rows, search hits, issue
beads); sub-segment trims OUT (segment-snapped, cross-page bounds from the
clip's meeting `transcript.txt`).

## Settle with Stephen early (AskUserQuestion, per arc)

1. **Arc B scope**: which towns/bodies next, and how far back to backfill?
   (Boston has ONE meeting; "years of meetings" is the promise. Budget
   stays $100/mo unless he raises it — ASR hours are the constraint; the
   drain, not a bill.)
2. **Why the corpus froze**: after diagnosis, the fix may need his call
   (dead channel rules in `record/sources.py` vs. a stalled scheduler vs.
   summer recess — do not silently re-point sources).
3. **Arc C source-of-truth**: monorepo stays the dev home with
   export-on-release to `publicrecord-studio` (a `make release` that
   re-runs the extraction + tags it per edition), or the new repo becomes
   the dev home. Recommend export-on-release now, migration later.
4. Described video + translations (the empty planes): in scope this arc or
   parked? (Captioner/Translator exist as tools; wiring them into the
   press is real work.)

## Build

**Arc A — the cutting room (specs/22, v2.1.11/r33 …).** Read
`specs/22-cutting-room.md` v0.2 + `specs/22-session-prompt.md` (commit
6abb278) — P0 was cleared to build. Triage the uncommitted partial against
the spec, finish P0 (three cutting surfaces + the panel as the one tray +
transcript.txt trim bounds + new-tab preview + append-or-replace on
`/app/r` make-this-yours), node twins for every codec change, then the
review arc, then deploy. Later phases per the spec (the scoped preview
stage).

**Arc B — the record grows (operational + scale).** Diagnose the freeze:
scheduler run history (`gcloud run jobs executions list`), poll previews
(a poll that files zero and reports zero unmatched = the feed returned
nothing — check channel ids), the steward queue, then fix and PROVE a new
meeting lands end-to-end (ingest → press → live). Then scale: new
bodies/channels via `record/sources.py` rules + steward preview, backfill
in budget-sized batches (captions-first; ASR only where transcripts are
missing), watch `record/OPERATING.md` §7 money. Success = the edition_date
moves weekly without anyone touching it.

**Arc C — the openness stays honest.** Repoint `SOURCE_REPO` in
`web/emit.py` to `github.com/amateurmenace/publicrecord-studio` (covenant +
constitution pages; the constitution's "same commit" law now has a public
repo to be true against). Add the release step to OPERATING §5: every
deploy re-exports the closure to the public repo and tags it `vX.Y.Z`
(the repo README already documents the extraction; automate it —
`git archive` of the Dockerfile's COPY set + the record tests + specs).
Add minimal CI to the public repo (the 536-test suite, no PG required).
Then the parked residue as time allows: the classification tail
(model/budget — Stephen's call), the brand open questions (his taste).

## Read first, then verify live before acting

`specs/22-cutting-room.md` + `specs/22-session-prompt.md`;
`record/OPERATING.md` (§4 adding meetings, §5 deploy + hand-files, §6
broken, §7 money); memory: `specs21-web-studio` (ALL the P3 traps —
aria-attribute CSS pairing, bare `var(--focus-ring)`, painted-truth
controls, `n_of()`, the minted namespaces `pf-`/`cz-tpl*`/`pb-`/`rt-`),
`specs20-newspaper-shipped` (SW-STALENESS LAW: every deploy bumps
`--version`), `publicrecord-verify-harness` (pane is localhost-only;
unregister the SW between local presses; HEADLESS-390 screenshots lie —
trust pane JS geometry; pane hidden ⇒ focus() no-ops; renderer-blank;
the slate). Old codec traps: `b=` free text TWICE-encoded; `cut()` at
every cap; grep the sheet before minting CSS names.

## Establish state

`curl -s https://publicrecord.studio/app/manifest.json` (version, and
WATCH `edition_date` — Arc B's metric) · start the test PG, then
`RECORD_TEST_PG_DSN=postgresql://record:record@localhost:55433/record_test
.venv/bin/python -m unittest discover -s tests -q` → 903 at HEAD ·
`git status` (the uncommitted partial) · `git log --oneline
origin/main..main | wc -l` → ~46, unpushed BY DESIGN (the public repo is
the release surface now — control-z origin stays Stephen's call).

## Deploy (proven 10×; pre-authorized per phase once its checkpoint is settled)

Suite green → docker build/push `record/api:rNN` → verify in-container →
`gcloud run jobs update record-press --args="^|^-m|record.press|--version|2.1.N"`
→ `gcloud run deploy record-api` → execute the press → clone
`amateurmenace/publicrecord`, rsync from `gs://publicrecord-edition/app`,
gunzip gzip-magic in place, KEEP the root hand-files (CNAME, index.html,
constitution/ — OPERATING §5 lists them) → push → verify live (curls +
headless desktop + pane geometry at 375/390) → **Arc C release step: export
+ tag `publicrecord-studio`**. Never rebake the public edition on this Mac.

## House rules

Per phase: adversarial review workflow (this sentence authorizes
workflows) — covenant, brand+a11y (AA numeric), backcompat (reader AND
studio AND store AND the wild links v1/v2), JS-off/mobile, logic edges —
fold every confirmed finding, then a focused re-review of the fixes (the
law has paid four consecutive times). PLAY reel-shaped things against a
real video (mind the slate). Tests for every codec/plane/store change.
Commits in the house voice, `Co-Authored-By: Claude
<noreply@anthropic.com>`. After each phase: CHANGELOG, spec status,
PARALLEL, memory.

## Still Stephen's — do not do unprompted

Push control-z to origin. New store fields or any free text beyond
title+notes. Re-point ingest sources or spend beyond the $100 budget.
Studio hue on a rendered paper; paper mode louder. The classification
tail's model spend. Deleting or migrating the monorepo. The brand
open questions (Command-Z, Translator prefix, Neighborhood AI URL,
Control-Z's mark).
