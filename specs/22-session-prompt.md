# Session prompt — specs/22 the cutting room: build P0

publicrecord.studio — **specs/21 is DONE** (all four phases live; edition
**v2.1.10**, image `record/api:r32`, corpus `66c05a9544c70585`, SW
`cz-record-2.1.10-66c05a9544c70585`, API rev 00022-cl6, Pages 5d9f6d4).
**specs/22-cutting-room.md is v0.2 SETTLED** — Stephen answered all five
§6 questions 2026-07-22, every proposal taken. Build P0, one phase, one
deploy (**v2.1.11 / r33**).

## The settlements (build to these — do not re-open)

1. **Preview = new-tab deep links in P0**; the scoped panel stage is its
   own later phase (P2) behind a written one-engine design. Do NOT touch
   the /app/r player-singleton in P0.
2. **ONE working tray** + file-into-paper (P1); no reel library.
3. **Make-this-yours (P1): append or replace, offered explicitly**;
   replace confirms.
4. **P0 ships all three cutting surfaces at once**: transcript rows +
   search hits + issue beads.
5. **Sub-segment trims are OUT, confirmed.** Segment-snapped is the
   design, stated in §5.6.

## P0 scope (spec §5.1, §5.2, §5.6, §7)

- **Ticks everywhere timed units show**: every transcript `.seg` row on a
  meeting page (clip = the segment's own bounds `[start, next-start)`,
  kind `segment`, quote the row's words); every search hit on `/app/s`
  (kind `hit`; end bound from the §5.6 fetch, default start+12 until it
  arrives); every issue bead (kind `bead`, same end-bound path). Ticks are
  script-added at hydration (JS-off pages stay clean), pressed markup
  untouched. Clip identity stays `(pid, kind, t)`; the link grammar never
  carried kind and does not change — NO codec change in P0.
- **The panel becomes the real tray on every page**: the studio panel's
  reel block grows the clip list with per-clip reorder / trim / remove +
  a ▶ preview deep link (new tab) — the meeting-page tray's controls,
  page-agnostic. The meeting-page tray remains; both paint the same
  `cz-reel` key and reconcile via the existing storage-event plumbing.
  Tray ops must not depend on CREEL (meeting-page state) — extract them
  to work on the stored clips directly.
- **Cross-page trim honesty (§5.6)**: fetch the clip's meeting
  `/app/m/<pid>/transcript.txt` (already pressed), parse `[H:MM:SS]`
  starts, cache per pid; trim snaps to those bounds anywhere. Where the
  fetch fails: the ±2 s nudge stays and the tray SAYS so. No new plane,
  no press change.
- Panel styles stay studio-scoped (`cz-` namespace under html.cz-m-studio;
  grep before minting — `rt-` is the meeting tray's, `pb-` papers',
  `pf-` featured cards').

## The laws (verify, don't trust)

decodeReel's law (encoders too; cut() at every free-text cap — a clip
QUOTE is display meta, never travels in links); the b= encode laws; node
twins for anything lifted; the API-door guard (`js.count("/api/")===3` —
transcript.txt is a BASE-relative fetch, not a door); full suite green
before deploy (903 at v2.1.10); the 5-lens adversarial review + focused
fix re-review (caught real regressions FOUR phases running); **PLAY a
reel with newly-cut clips against a REAL tape on live — mind the slate**
(real content sits past the dead-air open); SW-STALENESS law (the deploy
bumps to 2.1.11; unregister between local presses); commit in the house
voice ending `Co-Authored-By: Claude <noreply@anthropic.com>`. Do not
push control-z to origin (~47 commits local by design); the Pages repo IS
pushed.

## Read first

`specs/22-cutting-room.md` (v0.2, the settled spec) · memory:
`specs21-web-studio` (the P3 traps: aria migrations move their CSS
selector; bare var(--focus-ring); painted truth over storage),
`publicrecord-verify-harness` (pane is localhost-ONLY; headless for live;
SW unregister between presses; renderer-blank + headless-narrow traps;
the slate) · key code: `web/static/app.js` — the composer section
(CREEL/wireTicks/buildTray/clipAct/trimTo, line ~1262+), the studio panel
(refreshReelSummary ~line 320), the seg rows (`#transcript .seg`,
data-t); `web/emit.py` page_meeting (transcript markup), page_search,
page_issue (the timeline beads).

## Establish state

- `curl -s https://publicrecord.studio/app/manifest.json` → 2.1.10.
- `nc -z localhost 55433` then the suite → 903 green.
- The deploy loop is OPERATING §5 (gunzip step not optional; never rebake
  the public edition on this Mac); pre-authorized for P0 — the settlement
  is on the record in spec §6.

## After P0

CHANGELOG · spec status (P0 shipped) · PARALLEL state of main · memory ·
then P1 (make-this-yours + file-into-paper — settled, spec §5.4/§5.5) and
P2 (the preview stage, design-first) as their own phases.

## Still Stephen's — do not do unprompted

Push control-z to origin. Any new free text into the store. Any studio
hue on a rendered paper. The $100 GCP budget. The classification residual
tail. Sub-segment trims (settled OUT). The /app/r singleton (P2 designs
it first, on paper).
