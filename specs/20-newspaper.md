# 20 — The newspaper: the record gets its own face

**Status:** Draft v1.0 · **Stage:** adopted as the next build's contract ·
**Owner:** Stephen Walter (Weird Machine) · **Related:**
`.claude/rules/branding.md` and `brand/` (the brand law and its vendored
assets), specs/16 (the reader — restyled here, and partly superseded on this
domain), specs/17 §8 (scope), specs/19 (R1 closed 2026-07-19; this is the
"beautiful" and "user friendly" columns coming due), `record/OPERATING.md` §5
(how a change reaches the domain)

> publicrecord.studio is live and wearing someone else's clothes. The edition
> it serves was designed when the reader was the *suite's* public face at
> control-z.org/app — the desk's cream paper and oxblood accents, a sidebar of
> thirteen locked tool doors with the record squeezed between them, and door
> pages whose demo images do not even resolve from the cloud press. The brand
> architecture has since been settled and it is unambiguous: **civicmedia is
> the press; publicrecord is the newspaper.** A resident opening the town's
> record should get a paper — white page, ink text, one deep-green accent,
> headlines that behave like headlines — not a tour of the print shop. This
> spec is that paper, and the feature debt that travels with it: every desk
> surface whose *reading and composing* half can live in a browser, lives here.

---

## 1. Problem statement

Three problems, visible on one screenshot.

**It wears the desk's clothes.** The edition's CSS is the suite's tokens
(cream page, oxblood `--memory`, amber measurement) concatenated with web
rules — right when the reader was the suite's tour, wrong now that the record
has its own domain and its own brand. Branding law: publicrecord is the
*quietest* property — neutrals + deep green, zero fuchsia, ever — and the test
is *"would a skeptical 70-year-old town-meeting regular trust this?"* The
answer to cream-and-oxblood is: it reads as somebody's app. A paper reads as a
paper.

**It leads with the press, not the paper.** The sidebar gives thirteen desk
tools equal billing with the record's own surfaces. On civicmedia.studio that
rail *is* the product; on publicrecord.studio it is somebody else's masthead
on the front page. And the door pages reference demo slides
(`site/content/assets/slide-*.jpg`) that the record's container never carried
— `record/Dockerfile` copies `web/` but not `site/` — so every door on the
live domain shows a broken image. The structural fix and the brand fix are the
same fix: the doors compress to one quiet page, and the slides stop being
referenced on this domain at all.

**The work surfaces are missing.** The desk's Highlighter reads a meeting,
scores the moments with reasons, and cuts a reel. All of that *reading and
composing* is browser-shaped — the analyzer's output already ships in the
edition (`analysis_json`: framing, questions, tension moments) — yet the web
shows a locked door where the moments should be. Same story, smaller, for
Publisher's kits and Interpreter's language menu. The only step that honestly
needs the desk is rendering media. Everything up to that line belongs here.

## 2. Goals

1. **The record looks like the record.** publicrecord's own tokens, drawn from
   `brand/`, on every page — white/offwhite, ink, deep green, mono headlines,
   Inter body, weight doing the hierarchy work. No cream, no oxblood, no
   fuchsia, no purple, anywhere on this product.
2. **A front page worth the name.** A lead story with a real thumbnail, briefs,
   standing stories, a numbers box, an updates column — the day's record laid
   out like a paper, not a dashboard of cards.
3. **The work surfaces arrive.** Moments on every meeting page; a reel
   composer that does everything but render; the doors compressed to one
   honest page about the press. For every desk tool: its *readable output* and
   its *composable intent* live here; only rendering stays at the desk.
4. **Interactivity that earns its keep.** Instant search, hover peeks,
   transcript minimap, keyboard paths, cross-filtering — all progressive
   enhancement over pages that read completely with JS off.
5. **Every promise kept.** Every existing `/app/*` URL still answers. The
   edition stays complete with the API dark. The bake stays byte-idempotent.
   Readers stay uncounted.

## 3. Non-goals

- No accounts, no server-side reader state — the reel composer's state lives
  in the URL and localStorage, nowhere else.
- No video hosting, no rendering in the cloud. "Render this reel" is a
  hand-off to the desk, stated plainly.
- No dark mode this wave (the player's media surface stays dark as always;
  the page itself is a light paper — revisit after the paper exists).
- Not a rebrand of the desk suite. `suite/` keeps its tokens; what changes is
  that the *edition* stops borrowing them.

## 4. The design language — ink on white

The tokens come from `brand/` (vendored from the branding law; copy values
verbatim, never invent). The ones this product uses:

```css
/* surfaces + text (publicrecord takes the quiet set) */
--surface-page:#f8fafc; --surface-card:#ffffff;
--text-primary:#0f172a; --text-secondary:#475569; --text-muted:#94a3b8;
--border-hairline:#e2e8f0; --border-strong:#94a3b8;
/* the accent — and the whole accent */
--accent:#052e16;                 /* green-deep: marks, links, active states */
--state:#059669;                  /* green-emerald: focus ring, live dot ONLY */
/* measurement tints (backgrounds in graphics only, never chrome) */
--tint-1:#f0fdf4; --tint-2:#dcfce7; --tint-3:#4ade80; --tint-4:#22c55e;
/* type */
--font-mono:'JetBrains Mono',ui-monospace,monospace;  /* masthead, headlines,
                                    kickers, numerals, chips, timestamps */
--font-sans:'Inter',system-ui,sans-serif;             /* body prose only */
```

**The law, restated for this surface.** Zero fuchsia and zero purple, ever —
that is branding's hardest rule for publicrecord. Deep green is *the* accent;
emerald appears only as a state light (focus, the live dot); the brighter
greens exist only as tints inside measurement graphics (coverage strip,
score bars, heatmap cells). Flat vector: no drop shadows, no gradients, radius
0–4px. If a surface needs texture, the dot-grid is the only one allowed.

**Type does the hierarchy.** JetBrains Mono carries the masthead, every
headline, every kicker, every number, every chip — the IDE-meets-civic voice,
now doing a newspaper's job. Inter carries running prose at 16px/1.55. The
weight range is the design: 400 body, 500 names and links, 700 headlines and
section rules, 800 the lead story and the stat numerals. Kickers (the mono
overline labels — `THE LONG VIEW`, `NEW ON THE RECORD`, `BY THE NUMBERS`) are
11px, uppercase, +0.06em tracking, `--text-secondary`.

**Newspaper idioms, used honestly:**
- **Masthead**: the publicrecord keycap mark (from `brand/logos/`, never
  redrawn) + `publicrecord.studio` lowercase mono lockup, over a double
  hairline rule — the classic masthead rule pair.
- **Folio line** under it: the towns · *"pressed from the record of
  {edition_date}"* · the covenant's six words. The edition date finally reads
  as what it is — a dateline.
- **Decks**: a one-line standfirst under every headline (the meeting summary,
  the issue's last-resurfaced line) in Inter 400 `--text-secondary`.
- **Column rules**: 1px hairlines between columns; a 2px ink rule opens each
  section; the lead story earns a 3px deep-green top rule.
- **Pull-moments**: a moment quoted big — mono timestamp, 2px green left
  rule, Inter 500 — the paper's pull-quote, except every one is a deep link.
- **The scope banner** shrinks from a boxed interruption to one folio-adjacent
  line with the town pills inline. It informs; it does not interrupt.

**Images arrive.** The CSP has allowed `i.ytimg.com` since wave 1 and the
edition never used it outside the player. Now: the lead story carries a large
16:9 still, briefs and meeting rails carry small ones, issue timelines may
carry the still of the meeting a bead cites. Hairline border, no shadow,
`loading=lazy` everywhere but the lead, alt text always. Thumbnails add zero
bytes to the edition.

**Fonts are self-hosted.** Real Inter (400/500/700) and JetBrains Mono
(400/700/800), subset latin woff2, vendored into `web/static/fonts/` with
their OFL texts, `font-display: swap`, preload only the two critical faces.
CSP stays `font-src 'self'`. The bake's budget report grows a fonts line;
first paint ≤ 150 KB gz *excluding* swapped fonts, and the system stack is
the visible fallback, not a blank.

**Accessibility is a gate, not a hope.** WCAG 2.1 AA: `--text-muted` is for
decoration and large labels only, never body text (it fails contrast);
yes/no/abstain never differ by color alone (filled/outline/letter); every
interactive state has a visible focus ring (`--state`); everything respects
`prefers-reduced-motion`; the transcript stays a real document; 375px wide
gets the same paper in one column, tap targets ≥ 44px.

## 5. The shape — page by page

- **`/app` — the front page.** Masthead + folio. Then, in a newspaper grid:
  the **lead story** (latest meeting: big still, mono headline, deck, body
  chip, duration, its top two moments as pull-links); a **briefs column**
  (recent meetings, small stills, one-line decks); **standing stories** (the
  long view — top issues, follow ☆, last-resurfaced line); **by the numbers**
  (the stat band in mono 800 tabular numerals, every figure a link); the
  **updates column** (resurfacing deltas, each quoting its bead); the **access
  ledger** (captioned/translated/described — honest zeros with the drain
  note); a **votes teaser** (latest roll calls → `/app/votes`).
- **`/app/s` — search.** The field leads; town/body pills under it; instant
  results (debounced ≥300ms, ≥3 chars) riding the exact live-first/static
  logic R1.6 shipped — provenance chips restyled to the new palette (meaning:
  deep-green border; word: slate; both: deep-green filled; related: dashed).
  Hover a hit → a **peek** (±1 segment of context from the segs plane).
  `j`/`k`/`Enter` walk hits; `/` focuses search from any page.
- **`/app/m/<pid>` — the meeting.** Transcript-first as ever, restyled: sticky
  mini-header (title · now-playing time · Cite) once the masthead scrolls
  away; a right-margin **minimap** (segment density with moment marks,
  clickable); speaker names at 500; the playing segment follows the tape. And
  the page grows its second column: **Moments** (§6).
- **`/app/i/<slug>` — the issue.** The long view restyled: beads on a spine,
  hover quotes, keyboard walkable. Plus **tombstones**: an issue a steward
  `forget`-ed emits a page that says *"removed from the record by a steward on
  {date}"* — sourced from the audit ledger at press time — so a citation to a
  curated-away issue resolves to an explanation, never a bare 404. (This is
  the debt R1.7 named: control-z.org/app still carries a page publicrecord
  correctly dropped.)
- **`/app/votes`, `/app/officials`, `/app/analytics`, `/app/graph`,
  `/app/watching`, `/app/add`, `/app/covenant`** — restyled to the paper, same
  contracts. The votes ledger: YES deep-green filled, NO ink outline,
  ABSTAIN/ABSENT slate, letters always. Analytics heatmaps move to the green
  tint scale.
- **`/app/press` — NEW, and the doors go quiet.** One page about the press
  that makes the paper: the civicmedia story in three sentences, the tool
  list as one-line entries (name, verb, *why it needs the desk*), the DMG
  link, the credit line to communityai.studio — branding's cross-link done
  once, done right. The thirteen `/app/t/<tool>/` URLs **survive as slim
  redirect stubs** into `/app/press#<tool>` (citations never die), and the
  broken slide images leave this domain structurally — nothing on
  publicrecord.studio references `site/content/assets` anymore. "Get the
  desktop app" lives here and in the footer, demoted from the masthead.

## 6. The work surfaces — the desk's reading half moves in

The rule that decides every row: **if it reads or composes, it lives here; if
it renders media or touches local files, it stays at the desk and the page
says so in one sentence.**

| Desk tool | What already ships in the edition | Its web face (this spec) |
|---|---|---|
| Memory | everything | the record itself (done since wave 1) |
| **Highlighter** | `analysis_json` — framing, questions, tension moments | **Moments panel + reel composer** (below) |
| Publisher | nothing yet (`kit.json` unpressed) | `/app/k/<slug>` pages the moment kits exist (P2; the door line stays honest until then) |
| Interpreter | track slots (0 languages in the cloud corpus today) | the language menu, honest about the drain filling it (R2) |
| Narrator | AD track slots (same) | described-transcript view when tracks exist |
| Scribe / Grabber / Index / Clear / Rise / Depth / Slate / Stencil / Pivot | — | one-line entries on `/app/press`: your files, your GPU, your Resolve |

**Moments (Highlighter's reading half).** Each meeting page gains a Moments
panel: the analyzer's scored moments as cards — mono timestamp, kind kicker
(`VOTE`, `TENSION`, `QUESTION`, `DECISION`), the quote, the reason line, a
score bar in the tint scale. Click seeks the tape. If the current
`analysis_json` shape is too thin for this, the bake presses a `moments`
array per meeting (t, end, kind, score, reason, quote) — press what the
analyzer already knows; never re-analyze at read time.

**The reel composer (Highlighter's composing half, P1).** On any meeting:
tick moments into a reel tray; reorder; trim to segment bounds; live total
runtime. Output, in order of covenant-cleanliness: a **share link** (state
URL-encoded, versioned, no server); a **cite sheet** (quote + speaker + body
+ date + deep link per clip, one copy button); a **`reel.json`** download the
desk Highlighter opens to render — the one desk-bound step, stated:
*"rendering the video needs the desk."* A shared link opens `/app/r` — a
viewer that plays the sequence through the existing embed facade, seeking
clip to clip. Cross-meeting reels stay R3; the composer is built so a second
meeting's moments slot in without a redesign.

## 7. Requirements

### P0 — the paper (cannot call it publicrecord without)

1. **The coat.** publicrecord tokens from `brand/` replace the desk
   concatenation in `emit_assets`; masthead + folio + footer on every page;
   chips, buttons, banners, ledgers restyled; fonts vendored. *Acceptance:*
   no cream/oxblood/amber/fuchsia hex anywhere in the pressed edition's CSS;
   the mark is byte-equal to `brand/logos/`; AA contrast passes.
2. **The front page** per §5. *Acceptance:* lead + briefs + standing stories +
   numbers + updates all render from edition planes (nothing hand-typed);
   thumbnails lazy-load; JS-off shows the same content linearly.
3. **The meeting page** — restyle + Moments panel + minimap + sticky header.
   *Acceptance:* moments seek the tape; the minimap's marks match the moments
   plane; JS-off still reads the whole transcript with moments inline.
4. **Search** — instant + peeks + chips restyled, live-first logic untouched.
   *Acceptance:* the R1.6 degradation tests still pass unmodified in
   substance; keyboard path works; no query fires under 3 chars.
5. **The press page + door redirects.** *Acceptance:* all 13 `/app/t/*` URLs
   200 (as redirect stubs); zero references to `site/content/assets` in the
   pressed edition; no broken image anywhere on the domain.
6. **Tombstones.** *Acceptance:* a `forget`-ed issue's URL renders the
   explanation page with the audit date; pressed idempotently (audit rows are
   stored state, not wall clock).

### P1 — the composer

7. The reel tray, share links, cite sheet, `reel.json`, and the `/app/r`
   viewer. *Acceptance:* a reel of 3 clips from one meeting plays through the
   facade, survives a fresh browser via its URL alone, and the JSON opens at
   the desk.
8. Transcript follow-along + peeks polish; `/` global search focus.

### P2 — the wide paper

9. Kits pages when kit.json presses; cross-meeting reel groundwork; dark
   mode decision; per-issue RSS surfacing in the paper's chrome.

## 8. Architecture notes

- **`brand/` is the single source** for the record's face — tokens and marks.
  This supersedes specs/16 §9's "app.css tokens are the single source" *for
  this product*: the desk keeps its tokens; the edition takes the brand's.
  The drift-guard tests that pinned desk-token inheritance repoint at
  `brand/` (the guard survives; its target corrects). This also pays specs/19
  R2.4's debt where `emit.py` inlines the mark by hand.
- **The container is the press.** `record/Dockerfile` copies `web/` — so
  every asset the edition needs must live under `web/static/` (fonts, any
  local imagery), and **any `web/` or `brand/` change requires an image
  rebuild + job update before `record-press` can emit it.** `brand/` joins
  the Dockerfile COPY list. Nothing on this domain may reference `site/`.
- **Idempotence holds.** No wall clock anywhere new — tombstone dates come
  from audit rows; reel state lives client-side; thumbnails are URLs derived
  from `video_id`. Same corpus + same audit → byte-identical edition.
- **Budgets.** Edition ≤ 3 MB gz unchanged (fonts ~200 KB are the only new
  bytes; thumbnails are remote). First paint ≤ 150 KB gz + swapped fonts.
  The bake fails loudly on busts, as ever.
- **Every `/app/*` URL keeps answering.** Doors become stubs, never 404s.
  Feeds, JSON planes, transcripts: untouched paths.

## 9. Verification

Browser-first: every wave ends with the pressed edition deployed to
publicrecord.studio and walked in a real browser — screenshots taken,
critiqued, iterated; then 375px and reduced-motion passes. The suite's gates
stay: idempotence, the covenant set (no server on the reading path, no
cookies, CORS discipline), the R1.6 degradation proofs. New tests pin: the
palette ban (no desk/pop hex in pressed CSS), tombstone emission, the moments
plane, door-stub survival, and the fonts budget line.

## 10. Open questions

1. **(Stephen)** Mono headlines are the branding law and they will look like
   a civic terminal's front page — distinctive, honest, ours. If you want a
   serif display face instead (a more classical paper), that is a branding
   amendment first, not a CSS choice here. Default: mono.
2. **(Stephen)** Do the `/app/t/*` stubs eventually drop entirely once
   civicmedia.studio hosts the tool pages, or live forever? (Default: live
   forever; stubs are cheap and citations are sacred.)
3. **(Stephen)** Dark mode: after the paper ships, or never for the reader?
4. **(Eng)** Whether `analysis_json` as pressed carries enough for Moments
   or the bake grows the `moments` plane — measure on the real corpus first.
