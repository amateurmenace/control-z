# 22 — The cutting room: reels, cut from anywhere

**Status:** v0.2 · **Stage:** **SETTLED (Stephen, 2026-07-22 — all five §6
questions answered, every proposal taken) — P0 is buildable.** · **Owner:**
Stephen Walter (Weird Machine) · **Direction:** Stephen, 2026-07-22 — *"the
full ability to create highlight reels within and cross meetings."* ·
**Related:** specs/20 (the newspaper; §6/§7 built the reel composer and
`/app/r` this room is furnished from), specs/21 (the studio, your paper —
shipped P0–P3; the panel this room moves into),
`.claude/rules/branding.md` (§6.1 palette bounds), `record/OPERATING.md`
(nothing here touches the server at all).

> The reel composer shipped as a corner of the meeting page: tick the
> moments the record scored, and a tray gathers them. But an editor's eye
> doesn't stop at the record's own highlights — the line that matters is in
> the transcript, the search results, the issue's history. **The cutting
> room makes the whole record cuttable.** Any segment, any hit, any bead
> becomes a clip; the tray rides the studio panel onto every page; a shared
> reel opens back up into yours. Composing stays where it has always been —
> in this browser, in the link, in a file — and the desk keeps the render.

---

## 1. Problem statement

specs/20 built a real composer and a real viewer, and specs/21 surfaced them
in the studio — but the cutting itself still starts in exactly one place:
the moment cards of a meeting page. The transcript row that actually
matters, the search hit that found the needle, the issue bead that shows the
pattern — none of them can become a clip without scrubbing a meeting page
for the nearest moment card. The tray's real controls (reorder, trim,
remove) exist only on meeting pages; everywhere else the panel shows a count
and three buttons. Preview means navigating away mid-cut. And a shared reel
is a finished thing — playable, citable, but not openable; a reader who
receives one cannot take it up and cut further. The record is readable
everywhere; it is cuttable almost nowhere.

## 2. What stands (built, live, kept)

The inventory this room is furnished from — none of it is rebuilt:

- **The tray** — ONE global reel (`cz-reel`), spanning meetings; clip
  identity `(pid, kind, t)`; ticks on moment cards toggle membership.
- **The meeting-page tray** — per-clip reorder / remove / **trim snapped to
  transcript segment bounds** (the segment starts are read off the page's
  own transcript; a clip from *another* meeting falls back to ±2 s nudges,
  because its bounds aren't on this page — §5.6 fixes that honestly).
- **`/app/r`** — the viewer: v1 (one meeting) and v2 (cross-meeting) links,
  clip-to-clip playback through one page-singleton seek engine (the armed
  gate + settle window that survives stale time reports), cite list.
- **The outputs** — share link, cite sheet, `reel.json` (single-meeting, the
  desk's Highlighter opens it), the kit plane's handoff, and reel blocks in
  your paper (snapshots, rendered on `/app/p`).
- **The studio panel** (specs/21) — on every page; today its reel block is a
  count + play / share / clear.

## 3. The vision

An editor reads the record anywhere and cuts it there. Reading a
transcript and a sentence lands — one press, it's a clip. A search surfaces
the same promise made in three different years — three presses, a reel.
An issue's beads already tell a story — cut them in order and the story
plays. The tray follows you; the trim respects the record's own units; a
reel someone shares can be taken up and re-cut; and the paper files what
the cutting room produces. No accounts, no uploads, no server: the reel is
the link is the file.

## 4. The covenant — explicit, unchanged, load-bearing

- **Composing is client-only.** The tray is `localStorage`; a reel travels
  as its link and as `reel.json`; a paper snapshots it. No server on the
  make path, no accounts, no tracking — the store (specs/21 §6.2) holds
  papers only, and **nothing in this spec adds a byte to it**.
- **The record stays the record.** Cutting never writes to a plane, never
  re-times a segment, never asserts a quote the record doesn't hold. A clip
  is a reference — `(pid, start, end)` into the record's own tape.
- **The desk keeps rendering.** Playing a reel is the browser's;
  *rendering* one video is the desk's (`reel.json` → Highlighter), gated
  honestly as it is today.
- **Everything degrades out loud.** JS-off keeps the reading whole;
  a dark plane says so; a reel link that lost characters plays fewer clips,
  never throws (decodeReel's law, both directions).

## 5. The six surfaces

### 5.1 Cut from anywhere

Every place the record shows a *timed* unit grows the same quiet
add-to-reel affordance the moment cards have:

- **Transcript segments** (meeting page): each `.seg` row gets a tick on
  hover/focus — the clip is that segment's own bounds `[start, next-start)`,
  kind `"segment"`, quote the segment's text. The row already carries its
  `data-t`; the bounds are already on the page.
- **Search hits** (`/app/s`): a hit knows its meeting and its segment time —
  a tick beside the jump link cuts it without leaving the results. The hit's
  clip needs its segment's end: fetched from the meeting's own
  `transcript.txt` (§5.6) or defaulted to start + 12 s until it arrives.
- **Issue beads** (issue page): a bead is `(pid, t, quote)` — a tick cuts
  it. A bead's end bound rides the same §5.6 path.

Clip identity stays `(pid, kind, t)`; new kinds (`segment`, `hit`, `bead`)
join `moment` without disturbing the codec (kinds are labels, not grammar —
links carry only `pid:start-end` and never did carry kind). The ticks keep
the moment cards' semantics: pressed = in the reel, press again = out.

### 5.2 The panel becomes the tray — everywhere

The studio panel's reel block grows from a count to the real thing: the
clip list with reorder / trim / remove per clip — the meeting-page tray's
controls, in the drawer, on every page. Cutting continues from search
results, issue pages, `/app/r`, even `/app/p`. The meeting-page tray
remains (it is where the transcript is; cutting beside the words is the
point), and the two are the same tray painting the same key — specs/21's
storage-event plumbing already keeps them honest across tabs.

### 5.3 Preview while cutting — the one dangerous item, decided deliberately

Hearing a clip before keeping it is the cutting room's missing sense. It is
also the one place this spec touches machinery with sharp edges: the
`/app/r` seek engine is a **page-singleton** — one global `onYT` ready
hook, one `REELPLAY` state, an armed gate and settle window tuned for
sequential playback. Two players improvising against one another is how a
clip skips or a seek fights a seek. **Options, for §6.1:**

- **(a) Preview opens the record in place** — a clip row's ▶ opens the
  clip's own deep link (`/app/m/<pid>#t<t>`, or `/app/r` for the reel) in a
  **new tab**. Zero new machinery, zero singleton risk, always honest.
  Cost: a context switch per listen.
- **(b) A scoped preview stage in the panel** — one small player in the
  studio drawer, built once, owned by the panel: its own armed gate and
  settle window, a shared `onYT` dispatcher (the ready hook becomes a
  fan-out; each stage registers, none assumes), and a hard rule that
  starting the preview pauses any page player (and vice versa) so exactly
  one engine ever seeks. The real cutting-room feel; a real amount of new
  machinery on the one component that has bitten before.

**Proposal:** ship (a) in P0 — cutting from anywhere must not wait on
player work — and build (b) as its own phase behind a settled design, with
the singleton's laws (armed gate, settling, one-engine rule) written into
the spec before code. If (b) lands, `/app/p`'s reel blocks inherit the same
stage rather than growing a one-off (specs/21 P3 deferred exactly this).

### 5.4 "Make this yours" — on `/app/r`

A shared reel becomes takeable: one button on the viewer offers the reel to
your tray. If the tray is empty, it just arrives. If not, the editor
chooses **append** (after what you have) or **replace** (start from this) —
never silently either. Clips arrive as ordinary clips (same identity, same
trim rules); provenance is the record itself, so nothing needs attributing.
This is the remix loop: cut, share, taken up, cut again.

### 5.5 One tray, or named reels? (the §6.2 question)

Multiple named reels are real UX weight: which reel do meeting-page ticks
feed? What does the pill count? Where does "clear" point? Every answer
adds a selector to every cutting surface. **Proposal: keep ONE working
tray** — the bench you cut on — and let *finished* reels live where
finished things already live: **file this reel into your paper** (a reel
block is a named, ordered, durable snapshot; the paper renders it, its
link replays it, `paper.json` keeps it) and the share link itself (a reel
IS its link — "save as…" is copy). "Make this yours" (§5.4) closes the
loop by reopening any filed or shared reel onto the bench. A reel library
with names, if Stephen wants one, is a later spec — the storage shape
(`cz-reel` stays the bench; named reels would be separate keys) does not
foreclose it.

### 5.6 Trim stays segment-snapped — a decision, not an accident

Trimming steps clip edges along **transcript segment bounds** because the
segments are the record's own units — a trim can widen or narrow a clip
only to things somebody actually said, whole. This spec keeps that and
**states it**: sub-segment trim bounds arrive only if Stephen asks for
them (they trade honesty-of-units for finesse, and the desk already offers
finesse). What P3 *fixes* is the fallback: today a clip trimmed away from
its own meeting page nudges ±2 s because the other meeting's bounds aren't
on the page. The cutting room makes cross-page trimming the common case,
so the tray fetches the clip's meeting `transcript.txt` (already pressed,
one fetch per meeting, parsed `[H:MM:SS]` starts, cached) and snaps
everywhere. No new plane, no press change; where the fetch fails, the ±2 s
nudge remains and the tray says so.

## 6. The settlements — Stephen, 2026-07-22 (all five answered; build to these)

1. **Preview (§5.3): new-tab now, the stage later.** P0 ships preview as
   deep links opening in a new tab — zero player risk, always honest. The
   scoped panel stage is its own later phase (P2) behind a written
   one-engine design, and `/app/p`'s reel blocks inherit it when it lands.
2. **Named reels (§5.5): ONE working tray + file-into-paper.** The tray
   stays the single bench; finished reels live as paper blocks and share
   links; make-this-yours reopens any of them onto the bench. A library
   may come later — the storage shape does not foreclose it.
3. **"Make this yours" (§5.4): append or replace, offered explicitly.**
   Empty tray: the reel just arrives. Otherwise an explicit choice —
   append after what you have, or replace it behind a confirm. Never
   silently either.
4. **Cut-from-anywhere scope (§5.1): all three surfaces in P0.**
   Transcript rows + search hits + issue beads together — one coherent
   "the record is cuttable" moment, one deploy, one review.
5. **Sub-segment trims (§5.6): OUT, confirmed.** Trim stays snapped to
   the record's own units; the desk keeps finesse.

## 7. Phasing — one deploy per phase, each behind its settlement

- **P0 — cut from anywhere + the tray everywhere.** §5.1's ticks on all
  three settled surfaces (transcript rows, search hits, issue beads);
  §5.2's per-clip tray in the panel; §5.6's transcript.txt snapping so
  cross-page trims are honest; preview as new-tab deep links per §6.1.
  Client-only throughout — no emit change beyond tick affordances in the
  stubs' hydration, no plane change, no server change.
- **P1 — the remix loop.** §5.4 make-this-yours on `/app/r`;
  file-this-reel-into-your-paper named in the tray (the block type already
  exists); the cite sheet and `reel.json` offered from the panel tray
  wherever it stands.
- **P2 — the preview stage**, if settled in: the §5.3(b) design, alone in
  its phase, with the one-engine rule and the dispatcher named in the spec
  amendment first. `/app/p` reel blocks inherit it.
- **P3 — deepen.** Whatever the room turns out to want once real cutting
  happens in it (bulk ticks from a search page? a bead-run cut of an
  issue's whole timeline? polish from the review folds).

Every phase: the full suite green, the five-lens adversarial review + the
focused re-review of the fold, **play a real reel against a real tape**
(the slate law), the SW version bump, and the deploy per OPERATING §5.

## 8. Non-goals

Accounts, server-held reels, uploads. Rendering video in the browser (the
desk's, forever). Sub-segment trims (unless §6.5 says otherwise).
A reel library (unless §6.2 says otherwise). Editing the record itself —
the cutting room cuts *references*, and the record never notices.

## 9. The laws (inherited, binding)

decodeReel's law for every encoder and decoder this spec touches; `cut()`
at every free-text cap; the `b=`/`c=` encode laws (free text twice-encoded,
refs once); node twins for any codec change; the API-door guard
(`js.count("/api/") === 3` — the cutting room adds no door); CSS names
grepped before minting (`rt-` is the tray's namespace, `pb-` the paper's,
`pf-` the featured cards'); §6.1 palette bounds (studio hues under
`html.cz-m-studio` only — the tray in the panel wears studio accents, a
rendered paper never does); byte-idempotent presses; JS-off degrades to
the reading, out loud.
