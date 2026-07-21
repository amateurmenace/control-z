# 21 — Be the editor of your own paper: the web studio

**Status:** v0.2 · **Stage:** **spec — key decisions resolved with Stephen; ready
to firm §7 and build P0** · **Owner:** Stephen Walter (Weird Machine) ·
**Related:** specs/20 (the newspaper — the reader this builds on and keeps as a
*mode*), `.claude/rules/branding.md` (the brand law + the audience split; the
studio-mode palette is a live amendment, §6), specs/17 §6.2 (the covenant: if the
servers vanish, the record still reads *and composes*), the P1/P2 make-loop
already shipped (reel composer, cross-meeting reels, the kit plane).

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

## 6. Decisions still open — settle with Stephen before building the surface

1. **The studio-mode palette (a branding amendment).** "More colorful" studio
   mode wants energy beyond the record's neutrals + deep green. Does it borrow
   civicmedia/Control-Z's pop (purple / bright green)? publicrecord's law is
   **zero fuchsia** — loosening it, even only in studio mode, is a real amendment.
   Recommended framing: **paper mode stays strictly quiet (untouched); the studio
   mode earns a bounded, deliberate palette lift** — but how far, and which
   accents, is Stephen's sign-off.
2. **How a shared curated paper travels without accounts.** Options: URL-encode a
   compact edition (covenant-pure, size-limited); an exportable **paper file**
   (like `reel.json`, the desk could open it); or a content-addressed, read-only
   shared-paper store (like the edition bucket — no accounts, no tracking, but a
   server holds user content — a covenant nuance). Likely a mix; decide the
   default.
3. **Naming.** "your edition," "your paper," the verb for curating — brand's call.

## 7. Phased sketch (firm this up first)

- **P0 — the footprint shell.** Preview / studio / paper modes + the sidebar
  (default-on, hide/expand). Surface the existing make loop (reels) inside the
  studio. **Paper mode = the specs/20 reader, untouched.** JS-off + mobile degrade
  honestly (paper mode is the fallback).
- **P1 — the curated paper (document model).** Assemble a page from the blocks
  that already exist (stories + reels); arrange, title, share via link + export.
  "Edit your own front page."
- **P2 — data viz + analyses.** Chart blocks over the record's planes; note/analysis
  blocks; a curated paper carries charts + text, not just stories + reels.
- **P3 — deepen.** Templates, more block types, example / featured editions as a
  front door, polish.

## 8. Non-goals

Accounts / server-side user identity. Server-side video rendering (the desk). And
— the line that protects the resident — **paper mode never gets louder**: the
quiet reading experience is preserved untouched; all the volume lives in the
studio the editor chooses to open.
