# The Web App
### The Community AI Project, in any browser

**Status:** v1.0 — **Wave 1 shipped** (2026-07-18) · **Stage:** built, pressed from the real Brookline corpus into `site/docs/app/`, awaiting the site's deploy ritual · **Owner:** Stephen Walter (Weird Machine / BIG) · **Family:** The Community AI Project · **Related:** Community Memory (specs/14 — the content), Publisher (specs/13), the site (specs/07), the program (specs/12), PARALLEL.md (lane law)

> **Wave 1 is built (lane A, in-tree — not a separate lane W).** `web/` holds
> `bake.py` (the press), `emit.py` (the HTML stubs), `tools.py` (the web
> registry), `canon.py` (the URL twin), and `static/{app.js,app.web.css}` (the
> reader). `python -m web.bake` presses an edition; `tests/test_web_bake.py`
> pins it (canon golden table run in node against the real reader, idempotence,
> budgets, structure — 14 tests). Everything in §6 P0 is done: the bake, the
> reader, Home's dashboard, Add-a-meeting, the doors, the mark + panel, the
> covenant page. Deferred to Wave 2/3 as specced: the desk "Publish the record"
> button, follows-survive export/import, the offline PWA, kit pages, the Library
> band, multi-town, the desk beacon. The shared-render extraction (§8) was NOT
> done — the reader re-implements Memory's pure view functions rather than
> importing them; drift is guarded by the accent/canon tests, and the extraction
> stays a future consolidation. Design note: fonts fall back to system (as the
> desk does) rather than self-hosting woff2, keeping the CSP 'self' clean with
> zero external assets — self-hosting the display faces is a Wave-2 polish.

> **The desk makes; the web serves.** Every tool in the suite produces artifacts that are already web-native — transcripts, timelines, subtitle tracks, kits, embeds. The web app doesn't port the workshop; it opens the workshop's front room to everyone with a browser, and it is honest — beautifully, usefully honest — about which work still needs the desk.

**On the name.** It has none. It is the same product wearing its public face: the brand block reads `community ai project` exactly as the desk app does, with one mono chip beside it — **`WEB`** — and, beside the chip, the door back: **Get the desktop app**. No "lite," no "viewer," no second brand to explain. The rest of this spec says *the web app*; the pressed corpus it serves is **an edition**.

---

## 1. Problem Statement

The suite's covenant — local, honest, quiet — is its integrity and its ceiling. Everything Memory knows about a town lives in one SQLite file on one Mac in one station. A resident on a phone, a journalist on deadline, a screen-reader user, a neighbor who speaks Portuguese: none of them can touch the record without first owning a Mac and downloading a DMG. Meanwhile the record itself is made of portable parts — captions-first transcripts, YouTube video IDs, issue timelines, VTT tracks — that a static web page could serve perfectly, with **no backend, no accounts, and no telemetry**. The access gap isn't technical. It's that nobody has pressed an edition.

The suite server must never cross this gap itself: it binds 127.0.0.1 by design and by audit (~40 routes accept client filesystem paths — fine at the desk, file-disclosure anywhere else). The web app is a separate, purpose-built, static thing — the path specs/13 §P2 and specs/14 §9 already drew.

## 2. Goals

1. **Open the record.** Anyone with the URL can search the corpus, read any meeting, walk any issue timeline, and land in the tape at the cited second — on a phone, in under 60 seconds from first visit, with no install and no account.
2. **Show the whole suite.** Every tool is present on the web rail. What works, works fully; what needs the desk is **locked like a door, not hidden like a shame** — its page teaches what it does, shows it doing it, and offers the DMG. The web app doubles as the product's living tour.
3. **A front door that measures itself.** Home is a dashboard: the corpus counted (meetings, hours, issues, languages, described programs), coverage drawn over time, the newest tape and the loudest threads surfaced, and a working **Add a meeting** flow.
4. **Grow the desk.** The web app is the top of the funnel: locked doors, the `WEB` chip's neighbor button, and every "finish this at the desk" hand-off point to the download. Target: it becomes the #1 referrer to the DMG (GitHub release stats — the only counter the covenant allows us).
5. **Keep the covenant in public.** Static files only. No accounts, no cookies, no analytics, no video rehosting. Follows live in localStorage; notifications are RSS; the player is an embed facade. The covenant page says all of this in one screen.

## 3. Non-Goals

- **Not a hosted suite.** No compute, no uploads, no jobs. The Bureau (a self-hosted station service for ASR/renders) is a separate future product per specs/13 §P2 — this spec never grows into it.
- **Never a proxy to the desk.** The web app speaks only to its own origin and YouTube's embed/thumbnail hosts. It must never be pointed at a suite server on a routable address, and nothing in it may encourage that.
- **No accounts, no telemetry, ever** — restating specs/00 because the web is where the temptation lives. We will not know our reader count, and we ship anyway.
- **No video hosting.** Embeds and transcripts. A meeting whose tape exists only as a local file ships transcript-first with an honest note — not an upload pipeline.
- **No person pages.** The bake is the enforcement point: officials-only aggregation (specs/14 §8) is applied at press time; nothing person-aggregated about private citizens is ever emitted into an edition.

## 4. Users & Stories

The resident-watcher, the civic journalist, the non-English resident, the blind or low-vision resident, the official — specs/14 §4's cast, now without Macs — plus two new faces: the **station director** evaluating the suite (the tour funnel), and the **steward** pressing editions.

- As a resident on a phone, I open a link from the neighborhood group chat and land at the exact moment of the vote, with the transcript scrolled to the words.
- As a journalist, I select a sentence in a transcript and press **Cite** — quote, speaker, body, date, and a deep link land on my clipboard, receipts included.
- As a Portuguese-speaking resident, I flip the transcript to Português and the caption strip under the player follows it.
- As a screen-reader user, I read the meeting as a document — the transcript is the page, not a widget — and the Narrator description track is available as text.
- As a resident, I paste a YouTube link into **Add a meeting**; the web app tells me instantly it's already on the record and walks me there — or composes a submission for the steward.
- As a station director, I click Stencil on the rail, watch it cut a matte in the demo loop, understand in one screen why that lives at the desk, and download the DMG.
- As the steward, I press **Publish the record** at the desk and the site's edition is current.

## 5. The Shape

One page, one rail, one grammar — the suite's, responsive. Four kinds of surface:

**The mark.** Brand block as at the desk, plus the `WEB` chip (mono, 9px, letterspaced, `--line` border) and the **Get the desktop app** button beside it — quiet, always visible, never modal. It opens a compact panel, not a takeover: three lines on what the desk adds (*work on your own footage; render, transcribe, and cut with local AI; nothing ever uploads*), the macOS requirement line, the DMG link, and the release version. The same panel is the target of every locked door's CTA — one panel, one story, told once.

**The record, live.** Memory's surfaces — search, meeting pages, the long view — rendered from the edition instead of the API (§8: one renderer, two data planes). Plus the player (§7) carrying Interpreter and Narrator tracks. This is most of the product and it is fully alive.

**The doors, locked.** Every desk tool keeps its rail seat, full accent, real glyph. §6.P0.5 specs the pattern.

**Home, the dashboard.** §6.P0.3 — the count, the coverage, the new, the loud, and the way in.

## 6. Requirements

### P0 — press the first edition (cannot ship without)

1. **The bake.** `python -m web.bake --corpus <corpus.db> --out site/docs/app` presses an edition: `manifest.json` (schema version, generated-at, corpus hash, counts), `stats.json`, `meetings/{id}.json` (meta + segments + moments), `issues/{id}.json` (timeline nodes, beads, milestones, resurfacing deltas), `search/` (prebuilt lexical index, prefix-sharded, gz), `urls.json` (canonical-URL → meeting-id map for client-side dedupe), `feeds/` (RSS per issue + one firehose), `tracks/{meeting}/{lang}.vtt` and `ad/{meeting}.vtt` when Interpreter/Narrator sidecars exist, and per-page HTML stubs (below). Pure stdlib, no build chain — the site's discipline. Embedding BLOBs never ship; vector search stays at the desk and the search page says so in one honest line. *Acceptance:* baking the two real Brookline meetings yields a browsable edition ≤ 3 MB gz; baking is idempotent (same corpus → byte-identical edition, manifest hash proves it).
2. **The reader.** The web app itself: no-build vanilla JS on the suite's tokens (§9), path-routed (`/app/m/{id}`, `/app/i/{id}`, `/app/s?q=`) via baked HTML stubs that carry real `<title>`/OG tags — links must unfurl in a group chat with the meeting's name, date, and thumbnail. Search hits are time-coded and keyboard-walkable; meeting pages are transcript-first documents; the long view draws the issue rail and bead timelines exactly as the desk does. Every bead, hit, and timestamp is a copyable permalink. **Cite** on any transcript selection copies quote + speaker + body + date + deep link. Transcript (.txt/.vtt) and timeline (.json/.csv) downloads on every page — anti-lock-in is a page element, not a policy footnote. *Acceptance:* cold load on a mid-tier phone (Fast-3G throttle) paints the dashboard < 2 s; first-visit search → seeked playback < 60 s; every acceptance click-path passes with JS disabled down to a readable transcript (stubs carry the text).
3. **Home is a dashboard.** Top: the search field ("ask the record") and **Add a meeting**. Then the stat band — meetings, hours, bodies, issues, segments, languages, described programs — Space Grotesk numerals with amber tick-marks (amber is measurement, and these are measurements; every number is a link into its shelf). Then the **coverage strip**: meetings-per-month bars, stacked per body, hand-drawn SVG, hover/tap names the month's meetings. Then two rails: **New on the record** (latest meetings — thumbnail facade, body chip, date, minutes) and **The long view** (top issues by reach, follow ☆, last-resurfaced line). Then the resurfacing feed: latest "what changed since last time" deltas, each quoting its bead. Then the access meters: % captioned, % translated (per language), % described — the mission, measured, on the front page. *Acceptance:* every figure on Home traces to `stats.json` traces to a corpus query named in `web/bake.py`; nothing is hand-typed.
4. **Add a meeting.** Paste a URL → canonicalize client-side (the same canon as `memory/ingest.py`, twice-written, one golden test table keeps the twins honest) → if it's in `urls.json`: "already on the record — since May 12" and a walk-in link. Otherwise a submission composer: town, body, date, note — the exact shape of the desk's stable `POST /api/memory/submissions` contract — delivered, on a static site, as a prefilled GitHub issue against the corpus inbox repo, with copy-JSON and mailto fallbacks beside it. One honest sentence sets expectations: *a steward reviews; the record updates on the next pressing.* When a Bureau exists, the same JSON POSTs live; the contract never changes. *Acceptance:* pasting a `youtu.be` short link of an ingested `watch?v=` meeting resolves as already-on-the-record.
5. **The doors.** One template, per-tool content, driven by TOOLS gaining `surface: "desk" | "web"` — the coming.js mechanism, grown up. A locked page is: the tool's glyph, accent, verb, and one-liner at full dignity; a real demo (the site's slide assets and loops — real footage, per specs/07's discipline, never mock UI); a three-beat "what it does" strip; one plain sentence on *why it's a desk tool* (your files, your GPU, your Resolve — the true reason, stated in the failures-are-sentences voice); the Download CTA into the mark's panel; and a **"but its work lives here"** cross-link where true (Scribe → every transcript you're reading; Interpreter → the language menu; Publisher → kits; Grabber → how tape gets here). Rail shows a small `desk` tag in the `soon` slot's position. Nothing grays out; nothing dead-ends; every lock is a door. *Acceptance:* no locked page contains a control that pretends to work; every one links a real demo asset and the panel.
6. **The covenant page.** One screen at `/app/covenant`: static files only, no accounts, no cookies, no analytics, follows live in your browser, notifications are RSS, embeds are click-to-load (youtube-nocookie), corrections annotate rather than rewrite, takedown path to the steward, AGPL-3.0 / CC BY-SA 4.0. Footer of every page links it in six words: *no accounts · no tracking · yours*.

### P1 — the loop (fast follows)

7. **Publish from the desk.** A "Publish the record" action on the desk's Memory page: runs the bake as a JobManager job into `site/docs/app`, shows the edition diff (meetings added, issues moved), and hands the human the push ritual. The web app footer shows the edition date from `manifest.json` — a stale edition should embarrass its steward gently.
8. **Follows that survive.** ☆ writes localStorage; the still-watching panel renders followed issues' resurfacings from the edition and offers each issue's RSS. Export/import follows as a small JSON (anti-lock-in even for preferences).
9. **The caption strip, translated.** Under the player, a synced caption line fed by the edition's VTT cues, following embed time via the iframe API's time messages; the language menu (seven + Simple English, when Interpreter tracks exist) drives both strip and transcript. AD text renders as an inline described-transcript view. *Acceptance:* strip drift ≤ 0.5 s across a 2-minute continuous play on the reference meeting.
10. **Offline, quietly.** PWA manifest + service worker: shell precached, last-read meetings kept, an unassuming "read offline" affordance — the library-kiosk and thin-broadband case. Update banner in the house voice: *the record refreshed — reload for the new pressing.*
11. **Kits go public.** Publisher bundles gain a `--web` face in the bake: `/app/k/{slug}` renders `kit.json` — clips (embedded or downloadable), copy with provenance lines, alt text visible as text — the review room's public reading copy.

### P2 — the wide door (architectural insurance)

12. **Library analytics band** on Home (framing, names, topics across meetings) baked from the Library's cross-meeting queries — live band, desk drill-down.
13. **The desk beacon.** If a suite is serving on this same machine's loopback, offer "open at the desk" hand-offs (a probe against `127.0.0.1:8300/api/app`). Ships only if browser private-network rules allow it cleanly; otherwise the hand-off stays a downloaded sidecar the desk tools already speak.
14. **Multi-town editions.** The bake takes N corpora; Home grows a town switch; issue IDs stay town-scoped but comparable (specs/14 §P2.15 alignment).

## 7. The Player

The desk's playback law, kept in public: **embed, don't host.** A meeting page's player is a **facade** — the `i.ytimg.com` still, the duration, one play affordance; the `youtube-nocookie.com` iframe loads on tap (consent and performance in one move). Seeks ride the existing postMessage pattern; the transcript auto-follows; the caption strip (§P1.9) rides below. Local-file meetings render the transcript as the primary artifact with the honest line *the tape lives at the station* — and the station's contact from the edition's town config. Provenance chips on every AI-touched surface, and the standing disclosure: *AI-generated — verify against the official record.*

## 8. Architecture

- **One renderer, two data planes.** The pure view functions of Memory's page (hit lists, transcript blocks, timeline geometry, bead/milestone drawing) extract into shared render modules consumed by both the desk page and the web app; data access goes through one adapter (`CZData`) with an `api` backend (desk, loopback) and an `edition` backend (web, static fetch). Drift between desk and web becomes a code-review smell, not a fate. (The extraction is an ask to the Memory owner per the handoff ritual — the web lane never edits `memory/` or `suite/static/js/memory.js` directly.)
- **The package.** New top-level `web/`: `bake.py`, `canon.js`-twin generation, `static/` (the reader), `tests/test_web_bake*.py`. Proposed as **lane W** under PARALLEL's law: owns `web/` and `specs/16` fragments via handoff; its only suite-side wants (TOOLS `surface` field, the shared render extraction, the desk publish button) travel as asks. Output lands in `site/docs/app/` and deploys with the site's existing ritual — gh-pages, `control-z.org/app`, CNAME untouched.
- **Search without a backend.** Bake-time inverted index over segments (the same normalization as the desk's FTS tokenizer), sharded by term prefix to keep any query under ~2 shard fetches; AND + phrase support; results carry meeting/timestamp/speaker. Honest ceiling stated in-page when an edition exceeds the design envelope (≈ 300 meetings / 600 h, specs/14 §2 scale) — at which point the Bureau conversation has earned itself.
- **Budgets, or it isn't power.** First paint ≤ 150 KB gz (shell + css + stats); dashboard interactive < 2 s on Fast 3G; search keystroke → hits < 150 ms warm; any meeting page ≤ 400 KB gz before tape. The bake fails loudly if an edition busts its budgets — performance is an acceptance test, not a hope.
- **Caching, the house law.** HTML stubs `no-cache`; every asset immutable under `?v={manifest-hash}` — the desk's cache-busting rule, translated.
- **CSP, strict.** `default-src 'self'`; frames to `youtube-nocookie.com` only; images `'self'` + `i.ytimg.com`; `connect-src 'self'`. No third-party script, font, or beacon — the covenant, machine-enforced.

## 9. Design Language

Paper light, carried outdoors. The cream page, ink text, per-tool accents, amber strictly for measurement — app.css tokens are the single source; the web app imports them, never forks them. Media surfaces stay dark; footage lives in the dark even on a phone. Space Grotesk numerals own the dashboard (stat band at 44–56 px, tabular figures); DM Sans carries prose; mono carries chips, timestamps, and the `WEB` mark. The wire-and-node motif is the active thread — rail indicator at the desk; on the web it also draws the coverage strip's baseline and the timeline's spine, so the whole product reads as one instrument. Motion is few and settling (the pulse, the strip's draw-in), all behind `prefers-reduced-motion`. Below 720 px the rail becomes a top bar + sheet; the dashboard single-columns in the order count → new → loud; tap targets ≥ 44 px; the transcript is always the widest thing on the page. Meeting pages carry a print stylesheet — timestamped transcript, citation header, black-and-white legible — because "leave it at the library" (specs/14 §7) is also a web feature. WCAG 2.1 AA throughout: the transcript is a real document, the player is operable by keyboard, every chart has a table twin, `lang` attributes ride every translated track.

## 10. Success Metrics

The covenant blinds us on purpose: no analytics means no reader counts, and we ship anyway. What we can count, honestly: DMG downloads (GitHub release stats) and which release followed a web wave; submissions received through the inbox; towns asking "bring this to my town" (specs/14 §2.5's funnel, now with a public front door); editions pressed per month and their staleness; press citations of deep links (found, not tracked). Qualitative gates for wave 1: a resident with only a phone completes search → seeked playback unaided; a screen-reader user reads a full meeting and calls it a document, not an app; a station director finds the download from a locked door in under a minute.

## 11. Phasing

- **Wave 1 — the first pressing.** The bake, the reader (search, meetings, the long view), Home's dashboard, the doors, the mark + panel, the covenant page. Pressed from the real Brookline corpus; deployed at `control-z.org/app`. *The record is public.*
- **Wave 2 — the loop.** Add-a-meeting inbox live; RSS + follows; publish-from-desk; the caption strip; offline. *The record breathes.*
- **Wave 3 — the wide door.** Kit pages, the Library band, multi-town editions, the desk beacon if the platform allows. *The record travels.*

## 12. Open Questions

- **(Product)** `/app` path vs `app.` subdomain — path keeps one CNAME and one Pages deploy (recommended); subdomain needs a second repo. Decide before wave 1 URLs harden.
- **(Product)** The inbox: GitHub issues assume a public corpus repo and a GitHub-comfortable steward — is mailto the primary for wave 1 instead? Steward's call.
- **(Eng)** Edition scale: at what corpus size do search shards or `stats.json` need pagination — instrument the bake's budget report from day one.
- **(Eng)** The caption strip's time-message cadence across embed states (ads, chapter seeks) — validate on the reference meeting before promising ≤ 0.5 s in copy.
- **(Design)** Does the desk's Home eventually show the same dashboard band (the desk counting its own record) — one Home grammar for both faces? Decide after wave 1 ships.
- **(Law of lanes)** Lane W as a fourth lane vs folding into lane A after Memory merges — PARALLEL.md amendment either way; the ownership map above is written to survive both answers.
