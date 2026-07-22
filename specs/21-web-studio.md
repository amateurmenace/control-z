# 21 — Be the editor of your own paper: the web studio

**Status:** v0.4 · **Stage:** **P2 SHIPPED + LIVE (edition v2.1.9, image r31,
2026-07-22) — charts + notes: four chart kinds (votes over time on the new
votes.json plane · an issue's reach · the framing lenses · recurring topics),
computed client-side from the pressed planes in the paper palette with table
twins and receipts; notes as the editor's own words (strict store posture
checkpointed 2026-07-22 — plain text, 2,000 UTF-16 units, newlines only, the
second and last free text the store holds), labeled "the editor's note" at
render; P2 papers travel as v=2 so the shipped v1 reader degrades honestly.
Two adversarial passes folded (16 + 1 confirmed). P1 shipped v2.1.7/r29
2026-07-21 (your paper + the share store); P0 v2.1.6/r28 2026-07-20.
**P3 (templates, featured papers, the a11y nit) remains — then the spec is
done.** The next direction after P3 is specs/22, the cutting room
(`specs/22-session-prompt.md`).** · **Owner:** Stephen Walter (Weird Machine) ·
**Related:** specs/20 (the newspaper — the reader this builds on and keeps as a
*mode*), `.claude/rules/branding.md` (the brand law + the audience split; the
studio-mode palette is now a *ratified* amendment, §6.1), specs/17 §6.2 (the
covenant: if the servers vanish, the record still reads *and composes*), the
P1/P2 make-loop already shipped (reel composer, cross-meeting reels, the kit
plane).

> The newspaper (specs/20) gives you the record's front page. **This gives you
> yours.** The record is raw material; the reader becomes the editor — curating a
> paper of what matters to them (stories, highlight reels, data viz, analyses),
> arranging it, and sharing it as their own edition. The paper aesthetic stays;
> the studio *interactivity* becomes the point. One footprint control decides how
> much studio you see — preview, studio, or just the paper — and the covenant is
> unchanged.

---

## 1. Problem statement

publicrecord shipped as a reader — quiet, ink on white, the record's own front
page. P1/P2 quietly moved the *making* half into the browser (reels, cross-meeting
reels, kits), but it's buried inside the reading, and the paper you see is the
*record's*, not *yours*. The interactivity — cut a reel, chart a trend, curate a
front page — is the key feature, and it's hidden.

## 2. The vision — the editor of your own paper

Let a user become the editor. The record's planes are raw material; a user
curates their **own** front page: pick the stories, cut highlight reels, add data
visualizations and analyses, arrange it, and share it via a unique link as their
edition. Everyone gets the record; each editor makes it *theirs*.

## 3. The shape — three modes + the sidebar (resolved with Stephen)

The studio lives **on publicrecord**, and the user controls how much of it they
see. One footprint control, three states:

- **Preview (default).** The studio is visually *present* in a compact preview —
  you can see that you can edit, with an inviting **"Enter the studio"** button.
  Not the full cockpit, but not hidden either.
- **Studio (enter).** The full editor — louder, more colorful, more controls and
  interface. Where you curate: build reels, add data viz, write analyses, arrange
  your paper. This is the one place publicrecord's volume goes *up* (§6).
- **Paper (hide all).** The studio recedes entirely; just the resulting **paper**
  — quiet, ink on white, the reading experience specs/20 shipped. A user's curated
  paper (or the record's default) reads clean and shareable.

**The sidebar:** default **on**; the user can **hide** it or **expand** it.

The three modes are the brand resolution: the resident's quiet reading is
preserved *as paper mode*; the studio's energy lives *in studio mode*; the volume
is the editor's choice, not a fixed property of the property.

## 4. The curated paper — what you edit and share

The unit of creation is a **curated paper**: a page a user assembles from blocks —

- **Stories** — meetings and issues from the record (the front page's cards).
- **Highlight reels** — the reel composer (cross-meeting, already built), embedded
  and playable.
- **Data viz** — charts computed client-side over the record's planes: votes over
  time, an issue's reach, participation, budget, the framing lenses. *(New.)*
- **Analyses / notes** — the curator's own framing text, and the record's own
  analyses surfaced.

Arranged, titled, and **shared via a unique link** as the editor's own edition —
each is their own version, which they can keep editing. Client-side throughout
(localStorage + the link + an exportable file); no accounts.

## 5. The covenant holds — load-bearing, unchanged

Client-only reading + composing + **curating**; **no accounts, no tracking, no
server on the make path**. A curated paper lives in the link + localStorage + an
exportable file. Data viz is computed in the browser over the pressed planes
(`analytics.json`, `graph.json`, votes, framing) — no new backend. The desk keeps
what touches media/local compute (rendering video, the finishing tools), gated
honestly with a real download. specs/17 §6.2 still holds: if the servers vanish,
the record still reads *and composes*.

## 6. Decisions — resolved with Stephen (2026-07-20)

1. **The studio-mode palette — RATIFIED amendment.** Studio mode borrows
   civicmedia/Control-Z's pop: **purple `#a855f7` (`--pop-purple`) + bright green
   `#22c55e` (`--green-bright`)** as bounded accents on the *studio chrome only*
   (the studio frame, its controls, active/live states). Deep green stays the
   primary. The bounds are load-bearing and testable:
   - **No fuchsia** ever — the `#d946ef` line holds; the amendment adds two hues,
     not a repeal.
   - **Paper mode is untouched** — the studio accents never appear in paper mode,
     nor in the masthead/folio/section-nav that every mode shares.
   - **A shared/baked paper carries none of it** — a curated paper renders in the
     quiet paper palette wherever it is read, so the volume is the *editor's*
     choice in *their* studio, never imposed on a reader.
   This is the brand resolution the audience split predicts: in studio mode
   publicrecord becomes a *tool* (the making half), and the tool-brand's accents
   are the honest face for it. `.claude/rules/branding.md` §"Volume rules" is
   amended accordingly; the amendment is scoped to studio mode by construction.
2. **How a shared curated paper travels — a content-addressed store, with the
   link + file as the covenant substrate.** The default share is a
   **content-addressed, read-only shared-paper store**: a paper is PUT by the
   hash of its own bytes, so the URL *is* the content address — idempotent (same
   paper → same URL), no accounts, no reader identity, no tracking, size-capped,
   read-only on GET, hosted like the edition bucket (same project, same bill).
   Stephen accepted the covenant nuance (a server now holds user-authored
   content) knowingly. **The covenant is kept whole by construction:** the store
   is *additive*, never load-bearing. Every paper also lives in `localStorage`,
   in a URL-encoded compact form (for papers small enough), and in an exportable
   **`paper.json`** file (which the desk can open, like `reel.json`). So
   specs/17 §6.2 still holds exactly: if the servers vanish, the record still
   reads *and composes* — only the short-URL convenience is lost, and the file +
   link keep every paper alive and shareable. The write path is a genuine
   infra + `$100`-budget change; it lands in **P1** behind a checkpoint with
   Stephen, and P0 never touches it.
3. **Naming — "your paper" / "the editor" / "edit."** The artifact a user makes
   is **your paper**; the user is **the editor**; the verb is **edit**. This
   pairs with paper-mode and the spec's own title, and it deliberately avoids
   "edition," which already means the pressed record (`edition_date`, "edition
   v2.1.5") and would collide. The studio is the *room*; the paper is the *thing*
   made in it.

## 7. Phasing — firm (2026-07-20)

One deploy per phase; the covenant (§5) and the bounds of §6 hold on every one.

- **P0 — the footprint shell. ✓ SHIPPED + LIVE (v2.1.6, 2026-07-20).** The
  **preview / studio / paper** modes + the **sidebar** (default-on, hide/expand),
  as pure client state on top of the existing paper. Preview is a compact,
  non-blocking pill (not a card — it never covers the reading); the studio wears
  the ratified AA-safe lift; the make-loop is surfaced from the `cz-reel` tray.
  All in `web/static/app.js` + `app.web.css`; the pressed paper is byte-clean. The mode is a class on the shell and a `localStorage`
  preference; **paper mode is the specs/20 reader byte-for-byte untouched**
  (the `main.paper` markup does not move, and no studio hue reaches it). Studio
  mode wears the ratified accents (§6.1). The one make-loop that exists — the
  reel composer and the `/app/r` viewer — is *surfaced* inside the studio, not
  rebuilt. **JS-off and narrow mobile degrade to paper** (the shell renders as
  today; the studio chrome is script-built and reduced-motion-aware). No new
  plane, no new page, no server touched.
- **P1 — your paper (the document model) + the share store. ✓ SHIPPED + LIVE
  (v2.1.7 / r29, 2026-07-21).** The **curated paper** as a client-side document
  (schema `publicrecord.paper/1`): story blocks (meetings, issues) + reel
  blocks + a title; the studio panel is the editor (context adds, ↑ ↓ ✕
  arrange, a title field, the share row); `/app/p` is the one static stub every
  paper renders at (the `/app/r` pattern), enriching from the record's own
  planes in the paper palette. Share travels the three covenant ways —
  `cz-paper` draft, the URL-encoded whole-paper link, `paper.json` — plus the
  **store** (checkpointed with Stephen 2026-07-21 before the write path
  existed): `POST /api/papers` validates strictly (the title is the only free
  text), canonicalizes server-side, writes once to the private
  `publicrecord-papers` bucket at the SHA-256 of the paper's own bytes;
  read-only GET, immutable, no identity, no list, no delete API (takedown =
  a steward's hand, OPERATING §6). Node twins pin the codec; two adversarial
  workflow passes (23 + 13 confirmed findings) folded before deploy — the
  re-review also repaired a pre-P1 SW bug (bare-stub precache cached
  redirected responses; offline stub navigation was broken on live).
- **P2 — data viz + analyses. ✓ SHIPPED + LIVE (v2.1.9 / r31, 2026-07-22).**
  Chart blocks computed **client-side over the planes**, each with a table
  twin and a receipt under every mark, in the paper palette (deep green is
  measurement). The cut, settled with Stephen 2026-07-22: **votes over
  time** (a new pressed plane, `votes.json` — the meeting pages' own roll
  calls restated date-ordered, one fetch at any corpus size; filled dot
  passes, hollow fails, half-tone square any other outcome the record
  wrote), **an issue's reach**, **the framing lenses** (one meeting or the
  whole record), **recurring topics**; participation deferred until a
  diarized meeting exists. **Note blocks** — the editor's own words, labeled
  out loud at render; plain text, 2,000 UTF-16 units, newlines only; the
  client cleans (total), the store refuses (strict) — the second and last
  free text a stored paper may carry (the checkpoint). Papers carrying P2
  kinds travel as **v=2** (links and minted short links), so the shipped v1
  reader shows its honest newer-version message rather than a silently
  thinner paper; stories+reels papers stay byte-identical v=1. Positional
  charts are natural-size SVG in a scrolling wrap; magnitude bars are HTML
  rows (the heatmap's precedent — real, wrappable, AA text at every width).
  Two adversarial workflow passes folded 16 + 1 confirmed findings before
  deploy (outcome binarization, AT-invisible receipts, the v=2 gate, the
  store's own error sentences surfaced, the dead caret-capture, surrogate-
  safe caps, the share row's boundary repaint).
- **P3 — deepen.** Templates, more block types, example / featured papers as a
  front door, polish.

## 8. Non-goals

Accounts / server-side user identity. Server-side video rendering (the desk). And
— the line that protects the resident — **paper mode never gets louder**: the
quiet reading experience is preserved untouched; all the volume lives in the
studio the editor chooses to open.
