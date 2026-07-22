# Session prompt — finish specs/21 (P3), then specs/22: the cutting room

publicrecord.studio — two jobs, in order: **(1)** close out specs/21 with P3
(v2.1.10/r32) and mark the spec done; **(2)** draft and build **specs/22 —
the cutting room**: the full online reel-making toolset, within and across
meetings (Stephen's direction, 2026-07-22: "the full ability to create
highlight reels within and cross meetings"). `specs/21-web-studio.md` v0.4
and this file are the orientation; the new spec is yours to write first.

## Where the world is

LIVE at edition **v2.1.9** (image `record/api:r31`, corpus `66c05a9544c70585`).
Shipped through 2026-07-22, all live and verified:

- **P0** (v2.1.6/r28): the three-mode footprint — preview pill / studio
  sidebar / paper; the §6.1 palette amendment (studio hues under
  `html.cz-m-studio` ONLY, zero fuchsia anywhere, no studio hue on any
  rendered paper, ever).
- **P1** (v2.1.7/r29): **your paper** (`publicrecord.paper/1` — story blocks
  by pid/slug + reel blocks + title), edited in the studio panel, rendered
  at `/app/p`, traveling as `cz-paper` draft / whole-paper link /
  `paper.json` — plus the **share store** (POST/GET `/api/papers`,
  content-addressed sha256[:16], private bucket `publicrecord-papers`, no
  list, no delete API — takedown per OPERATING §6).
- **P2** (v2.1.9/r31, 2026-07-22 — live-verified: prod store round-trip
  paper `88ba5977746282f1`, the P1 paper `aab17fcb26e41b50` unregressed,
  SW cache `cz-record-2.1.9-66c05a9544c70585`): **charts + notes.** Four chart kinds —
  `votes` (the new **votes.json** plane: the meeting pages' own roll calls
  restated date-ordered, one fetch at any corpus size; filled dot passes,
  hollow fails, half-tone square any OTHER outcome the record wrote —
  never binarize; every dot a receipt, exposed to AT via role="group" +
  per-mark aria-labels), `reach` (an issue's timeline), `framing` (one
  meeting or the whole record), `topics` — all computed CLIENT-side from
  pressed planes, paper palette only, each with a table twin in its own
  scroll wrap. **Notes**: the editor's own words, labeled "the editor's
  note" out loud; plain text ≤2,000 UTF-16 units, `\n` only, client cleans
  / store refuses (the P2 checkpoint, settled 2026-07-22). The panel grew
  ＋ a note and ＋ a chart; `paperHasLive()` is the ONE truth the share row
  and both typing handlers read (a gate whose truth changes under a
  keystroke repaints on exactly that boundary — the fix re-review's catch).
  **Papers carrying P2 kinds travel as v=2** (whole links AND minted short
  links; PAPER_VS is ["1","2"]) so the shipped v1 reader shows its honest
  newer-version message; stories+reels papers stay byte-identical v=1.
  `cut()` keeps every cap surrogate-safe (encodeURIComponent throws on a
  stranded half — a latent P1 crash, fixed at all four sites; lone
  surrogates dropped anywhere they hide).
- **Our AI Constitution** (`/app/ai` canonical, publicrecord.studio/constitution
  shareable) + the footer recredit. **Keep the ledger TRUE**: when our use
  of AI changes, `/app/ai` changes in the same commit.

Tests: run the suite and trust it, not this line (898 green at the P2
deploy). Commits on control-z main are **NOT pushed to origin, by
design — do not push origin.** The Pages repo (`amateurmenace/publicrecord`)
is the deploy artifact and IS pushed.

## Resolved — build to these, do not re-litigate

1. §6.1 palette: studio hues studio-scoped only; ZERO fuchsia; a rendered/
   shared/baked paper carries NO studio hue, ever.
2. §6.2 store: additive, never load-bearing. Free text stored = title +
   notes ONLY (the settled posture). **Any new free-text field needs its own
   Stephen checkpoint BEFORE the store accepts it.**
3. The P2 chart cut: votes · reach · framing · topics. Participation joins
   only when a diarized meeting exists (today: zero speaker data corpus-wide).
4. P3 featured papers: `/app/p` empty state + ONE quiet front-page line
   (Stephen, 2026-07-22). Naming: your paper / the editor / edit; the
   pressed record is "the edition." Dark mode for the reader: DECLINED.

## Job 1 — specs/21 P3 (v2.1.10/r32), then mark the spec done

- **Templates**: pre-shaped papers the editor starts from, client-side only
  (they just write the draft) — e.g. "the roll calls, watched" (votes +
  framing + a note prompt), "an issue, watched" (issue story + reach + note,
  offered from an issue page). Offered in the panel's empty state; never
  overwrite a non-empty draft without a confirm.
- **Featured papers as a front door**: 2–3 example papers built AT PRESS
  TIME from the record's own top issues/votes (deterministic — byte-
  idempotent presses must hold), as plain `/app/p?v=…` links (**v=2 the
  moment a featured paper carries a chart or note; v=1 only for
  stories+reels — match `paperV()` exactly**): in the
  `/app/p` stub's empty state (server-rendered, OUTSIDE `#paperbody` — the
  renderer owns that node's innerHTML; hide them via JS when a real paper
  renders) + one quiet line on the front page. A Python link-builder must
  match the JS codec byte-for-byte — add a node twin parity test (build in
  Python, decode in node), and mind the encode laws below.
- **The a11y nit**: the mode control → `role=radiogroup` + `role=radio` +
  `aria-checked` + roving tabindex + arrow keys (today: group + aria-pressed).
- **Polish** + any LOW findings deferred from the P2 review fold.
- **Inline reel stages on /app/p: only with care or not at all** — the
  /app/r player is a page-singleton (armed gate, settling, global onYT).
  P1/P2 play via /app/r links, which works. If the cutting room (job 2)
  builds a proper preview stage, prefer inheriting THAT there over a
  one-off here.
- Then: spec status → done, CHANGELOG, PARALLEL "state of main", memory.

## Job 2 — specs/22: the cutting room (draft the spec, settle, build)

The reel composer exists and is live (specs/20 P1/P2-B): tick moments on a
meeting page → ONE global tray (`cz-reel`, cross-meeting), trim IN/OUT to
transcript-segment bounds, reorder, share `/app/r` v1/v2 links, cite sheet,
`reel.json`, kits hand off to it, papers snapshot it. What "full ability"
still wants — the gaps, from the code:

1. **Cut from anywhere, not only moment cards.** The transcript itself
   (every segment row gets a quiet add-to-reel affordance), search results
   (a hit → a clip), issue beads (a bead → a clip). Clip identity stays
   (kind, time); entry points multiply.
2. **The studio panel becomes a real tray everywhere.** Today the full
   tray (reorder/trim/remove per clip) lives on meeting pages; the sidebar
   shows only a count + play/share/clear. Per-clip control should ride the
   panel on ANY page, so cutting continues from search, issues, /app/r.
3. **Preview while cutting** — hear the clip before keeping it. THE ONE
   DANGEROUS ITEM: the /app/r seek engine is a page-singleton. Either a
   carefully-scoped preview stage (its own armed gate + settle window,
   never two players fighting one onYT), or deliberate "preview opens
   /app/r in a new tab" — decide with Stephen, don't drift into it.
4. **"Make this yours" on /app/r** — open a shared reel into your tray
   (append or replace — ask), so reels are remixable, not just playable.
5. **Named reels?** Today: one global tray; papers hold snapshots. Multiple
   named reels = real UX weight (which tray do meeting-page ticks feed?).
   A Stephen question — propose keeping ONE working tray + "file this reel
   into your paper / save as…" rather than a reel library, but ask.
6. **Trim bounds**: clips snap to transcript segments — that is honesty
   (the record's own units), keep it; sub-segment trims only if Stephen
   asks. State it in the spec as a decision, not an accident.

Settle 3–5 of those with Stephen (AskUserQuestion) BEFORE building each
surface, then phase it (one deploy per phase, P0 smallest-honest-slice
first). Write `specs/22-cutting-room.md` in the house voice with the
covenant section explicit: composing stays client-only (localStorage +
links + files); no accounts; the desk keeps rendering.

## The laws that bind every phase (carried forward — verify, don't trust)

- decodeReel's law: every decoder AND encoder total — malformed → fewer
  blocks/clips, never a throw. `cut()` for every cap on free text.
- The b= encode laws: URLSearchParams decodes the WHOLE value once BEFORE
  the "," split — free text rides twice-encoded; refs are [\w-] and ride
  once-encoded (decoded twice, harmlessly). "+" decodes as space; "~" is
  the clip separator; "." splits kind once.
- Node twins for every codec change (`TestPaper.helpers()` lift list — new
  consts/functions used by lifted code must join it). Store tests for every
  `record/papers.py` `_block` change. The API-door guard counts `/api/`
  occurrences (3) — a new outbound path is added there DELIBERATELY or CI
  fails.
- CSS class names: check for collisions before minting (`.lensbar` was
  already the meeting page's 9px pill and silently squashed P2's chart rows
  — later same-specificity rules win; the paper-block namespace is `pb-`).
- Full suite green before every deploy; per phase an adversarial review
  workflow (5 lenses: covenant, brand+a11y AA-numeric, backcompat
  reader+studio+store, JS-off/mobile, logic edges) → fold EVERY confirmed
  finding → focused re-review of the fixes (both P1 passes and the P2 pass
  caught fix-regressions or live bugs).
- PLAY anything reel-shaped against a REAL video — mind the SLATE (real
  moments sit past the dead-air open; a synthetic seed with early
  timestamps plays dead air and reads as broken).
- SW-STALENESS LAW: a code-only change needs a `--version` bump or
  returning readers keep stale JS — and the LOCAL preview loop needs the SW
  unregistered between same-version presses.
- Commit in coherent pieces in the house voice, ending
  `Co-Authored-By: Claude <noreply@anthropic.com>`. After each phase:
  CHANGELOG, spec status, PARALLEL "state of main", memory.

## Read first, then verify live

`specs/21-web-studio.md` (v0.4, P0–P2 shipped) · `specs/20-newspaper.md`
(the reel composer + /app/r it builds on) · `record/OPERATING.md` (§5
deploy + hand-files + store, §6 takedown) · `.claude/rules/branding.md`.
Memory: `specs21-web-studio`, `specs20-newspaper-shipped`,
`publicrecord-verify-harness` (ALL the traps: pane is localhost-ONLY;
unregister the SW between local presses; HEADLESS-390 fake clipping —
trust pane JS geometry; the pane's renderer blanks after scroll and its
document can be 0×0/hidden — screenshot to force composition, re-navigate
to recover; the slate). Key code: `web/static/app.js` — the reel section
(REEL_KEY/CREEL/buildTray/reelSeek/the /app/r engine), the "YOUR PAPER"
section (PART 1 is server-free and a test scans it), the chart builders;
`web/emit.py` `page_reel`/`page_paper`/`emit_stubs`/the SW block;
`record/papers.py`; `tests/test_web_bake.py` (TestReel + TestPaper twins).

## Establish state

- `curl -s https://publicrecord.studio/app/manifest.json` → version 2.1.9.
- `nc -z localhost 55433` then
  `RECORD_TEST_PG_DSN=postgresql://record:record@localhost:55433/record_test .venv/bin/python -m unittest discover -s tests -q` → green.
- `git -C ~/control-z log --oneline origin/main..main | wc -l` → unpushed
  by design; do not push origin.

## Deploy (proven; pre-authorized per phase once its checkpoint is settled)

Suite green → `docker build --platform linux/amd64 -f record/Dockerfile -t
us-east1-docker.pkg.dev/publicrecord-studio/record/api:rNN .` → push →
verify in-container → `gcloud run jobs update record-press --region=us-east1
--image=…:rNN --args="^|^-m|record.press|--version|2.1.N"` → `gcloud run
deploy record-api --image=…:rNN --region=us-east1` → `gcloud run jobs
execute record-press --region=us-east1 --wait` → clone
`amateurmenace/publicrecord` → `gcloud storage rsync -r
--delete-unmatched-destination-objects gs://publicrecord-edition/app app` →
**gunzip gzip-magic files in place** (OPERATING §5) → commit + push →
verify live (curls + headless desktop; narrow via pane geometry). Never
rebake the public edition on this Mac.

## Still Stephen's — do not do unprompted

Push the control-z monorepo to origin. Any NEW free text into the store
without his posture sign-off. Any studio hue on a rendered paper. The $100
GCP budget. The classification residual tail. Sub-segment trim bounds. The
/app/r player singleton beyond what a settled preview design needs.
