# 21 — The Web Studio: make things from the record, in the browser

**Status:** v0.1 · **Stage:** **brief — not started** · **Owner:** Stephen Walter
(Weird Machine) · **Related:** specs/20 (the newspaper — the reader this builds
on and partly re-opens), specs/16 (the web companion), `.claude/rules/branding.md`
(the brand law + the audience split this decision touches), specs/17 §6.2 (the
covenant: if the servers vanish, the record still reads), the P1/P2 make-loop
already shipped (reel composer, cross-meeting reels, the kit plane).

> publicrecord shipped as a newspaper — quiet, ink on white, a reader for
> residents (specs/20 P0 stripped the desk's sidebar of thirteen tool-doors on
> purpose). Along the way P1/P2 moved the *making* half of the suite into the
> browser: the reel composer, cross-meeting reels, the kit plane. But that make
> loop is buried inside the reading — you stumble onto it on a meeting page.
> The record's biggest latent value — that everything needed to cut a highlight
> reel from a civic meeting is *already here* — is hidden behind the paper.
> **This spec brings the studio back: a place, on the web, to make.**

---

## 1. Problem statement

A resident opening publicrecord gets a paper, which is right. But a journalist,
an organizer, a PEG producer — anyone who wants to *make* something from the
record — gets the same quiet reader, with the making tools scattered and
unannounced. There is no workspace, no sidebar, no "your reels," no invitation
to compose. The desk app has a studio feel people miss; the web has the record's
content and (already) the make loop, but wears none of the studio's clothes.

## 2. The vision — split the difference

Keep the paper for **reading**; add a **studio** for **making**.

A studio shell — a persistent, collapsible **sidebar** — that foregrounds the
make loop and keeps your work at hand:

- **Side reels.** Your reels — in-progress and saved — always visible in the
  rail, not only while composing on a meeting page. Open one, keep building,
  share it, start another.
- **The make loop, first-class.** Search / browse the record → tick moments →
  compose (cross-meeting reels already work) → share, cite, export. The studio
  is where you come to do this, not something you trip over.
- **A moment library + the tools.** The record's moments as raw material; the
  kit workspace (Publisher's reading half); a clear map of what you can make.
- **The desk boundary, made inviting.** The covenant's one hard line —
  **rendering the finished video, and the finishing tools (Hush, Speak, Pivot,
  Stencil, Rise, Depth, …), need the desktop** — stops being fine print and
  becomes a first-class moment: *"Your reel is cut. Render it to video in the
  Studio →"* with a prominent, honest desktop download. Desktop-only features
  are shown, labeled, and one click from getting them — never hidden, never
  faked in the browser.

The result: a resident still gets a newspaper; a maker gets a studio; and the
line between "what the browser can do" and "what the desk does" is the clearest,
most inviting thing on the page rather than a disclaimer.

## 3. The decision this spec must make first (Stephen's call)

This shifts publicrecord **louder** and toward the **maker**, partly reversing
P0's strip-the-sidebar decision, and it brushes the brand's audience split
(resident-reader ≠ media-maker). Resolve it deliberately, don't drift into it:

1. **Where does the studio live?** (a) A **studio mode on publicrecord** — an
   opt-in louder shell layered over the same record, while the reading pages stay
   a paper; or (b) **civicmedia.studio's web face** — a distinct studio property
   that reads the record. This is Control-Z's dual-nature pattern (lives inside
   the suite *and* stands alone) applied to the whole make loop.
2. **How loud, and for whom?** Is the sidebar **always on** (every visitor sees a
   studio) or **opt-in** (you enter the studio; residents keep the paper)? The
   safe reading of "split the difference": making is a *place you go*, not a
   cockpit imposed on every reader.
3. **Naming + volume** per the brand law: what carries the studio's identity, and
   how far up the volume dial it goes without making the reader's paper louder.

Write the answers into this spec (§2 → a real §5 "shape") before building.

## 4. The covenant holds — load-bearing, unchanged

The studio is a *front end on the same client-only record*, not a new backend:

- **No accounts, no tracking, no server on the make path.** Reading and composing
  run in the browser. Reels/kits live in `localStorage` + the share link + an
  exportable file — never a user row on a server.
- **specs/17 §6.2 still true:** if Cloud Run and Postgres vanish, the record still
  reads *and composes*. The server is for meaning-search and freshness only.
- **The desk keeps what touches media + local compute.** Rendering video, the
  finishing tools — desk work, gated honestly, download offered.

If a studio feature can't be built inside this covenant, it doesn't belong on the
web; it belongs at the desk (with a download).

## 5. Phased sketch (to be firmed up after §3)

- **P0 — the shell.** A studio layout (collapsible sidebar); a studio home /
  workspace that foregrounds making; the reel tray promoted to a persistent
  **side-reels** panel (saved + in-progress, client-side); the desk boundary as
  first-class UI (a real "render needs the Studio → download" surface). The
  reading pages keep their paper.
- **P1 — the make loop, first-class.** Search/browse → tick → compose → share /
  cite / export, all from the studio; the moment library; saved-reel management
  without accounts (localStorage + export/import a "reel file" + share links).
- **P2 — deepen.** A studio face for kits; example / featured reels as a front
  door; the finishing-tool showcase with clear desk hand-offs; polish.

## 6. Non-goals

Accounts or server-side user state (covenant). Server-side video rendering (stays
the desk). Abandoning the quiet paper for residents — the newspaper survives; the
studio is added beside it, not on top of it.

## 7. Open questions

The brand decision (§3, first). Always-on sidebar vs opt-in studio mode. How
"saved reels" persist and travel without accounts (localStorage + export +
share-link; a portable `reel.json` / `kit.json` the desk also opens). Whether the
studio is a new route (`/app/studio`) or a reframe of `/app`. How the sidebar
degrades on mobile and with JavaScript off. How much of the desk's tool catalog
the studio *presents* (as download-gated) vs. omits.
