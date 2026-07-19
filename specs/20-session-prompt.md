# Session prompt — build the newspaper (specs/20)

Paste this as the opening message of a fresh session. It is written to be
handed to someone who did not build R1, and it names its own facts.

---

# The goal

publicrecord.studio is **live** and wearing the desk's clothes. Open it — the
record works (12 meetings, meaning-search, filters, a working console) but it
reads as somebody's app, not a town's paper: cream page, oxblood accents, and a
sidebar of thirteen locked desktop-tool doors given equal billing with the
record's own surfaces, several of them showing a broken demo image. The brand
architecture is settled and unambiguous: **civicmedia is the press;
publicrecord is the newspaper.** This session gives the record its own face and
moves the desk's *reading and composing* surfaces into the browser.

Finish this session with publicrecord.studio redesigned and testable in a real
browser: an ink-on-white newspaper — a real front page, meeting pages that show
their moments, a search that feels instant — that a skeptical 70-year-old
town-meeting regular would trust. That is **specs/20 P0 complete**. The reel
composer is P1; kits and dark mode are P2 — do not start them until P0 closes,
and the roadmap's rule still holds: finish before feature.

# Read first, in this order

  1. specs/20-newspaper.md      — the contract you are building
  2. .claude/rules/branding.md  — the law specs/20 draws from (it is gitignored
                                  but present; publicrecord is the *quietest*
                                  property — neutrals + deep green, zero fuchsia
                                  ever, and the 70-year-old test)
  3. brand/                     — the vendored tokens (`tokens/`) and marks
                                  (`logos/`); copy values byte-for-byte, never
                                  invent a hex or redraw a mark
  4. record/OPERATING.md §5     — how a `web/` change actually reaches the
                                  domain (rebuild image → update jobs → press →
                                  rsync into the Pages repo → push). This is not
                                  optional plumbing; nothing you style is visible
                                  until it runs.
  5. web/emit.py, web/bake.py, web/static/{app.js,app.web.css}  — the reader you
                                  are restyling. Read app.web.css's header: it
                                  currently *inherits* the desk's tokens. specs/20
                                  §8 repoints that at brand/.
  6. git log -30                — the house voice; match it exactly.

Project memory holds the facts that cost real time (see [[r1-record-breathes]]).
Trust it; verify anything about live state before you act on it.

# Establish state before planning anything

    curl -s https://record-api-907309358085.us-east1.run.app/api/health | python3 -m json.tool
    RECORD_TEST_PG_DSN=postgresql://record:record@localhost:55433/record_test \
      .venv/bin/python -m unittest discover -s tests -t .        # was 801 green
    open https://publicrecord.studio                              # see what you are replacing

Then confirm the three facts specs/20 turns on, so your plan targets reality:

  - **The images are already pressed.** `meeting.json` carries `thumb` and a
    full `analysis` block (framing, questions, decisions with outcomes). The
    front page's stills and the Moments panel draw from data that already
    exists — you are rendering it, not generating it. Prove it:
    `curl -s https://publicrecord.studio/app/meetings/VOUCZHfdzWc.json | python3 -m json.tool | head -40`
  - **The broken door images are a different thing** — `emit.py` references
    `site/content/assets/slide-*.jpg`, which the container never copies
    (`record/Dockerfile` COPYs `web/`, not `site/`). specs/20 removes those
    references from this domain entirely; the doors become one `/app/press`
    page. Do not try to ship the slides.
  - **The container is the press.** Every asset the edition needs lives under
    `web/static/` (fonts, any imagery). `brand/` must join the Dockerfile COPY
    list. A `web/` or `brand/` change is invisible until you rebuild the image,
    update the jobs to it, run `record-press`, and rsync GCS → the
    `amateurmenace/publicrecord` repo (§5). Budget for that loop.

# The work, in dependency order

Build P0 in this order; each is a coherent commit and a browser check.

**§20.1 — the coat (do this first; everything else wears it).** publicrecord
tokens from `brand/` replace the desk-token concatenation in
`emit_assets`. Self-host Inter (400/500/700) and JetBrains Mono (400/700/800)
as subset woff2 under `web/static/fonts/` with their OFL texts, `font-display:
swap`, CSP still `font-src 'self'`. Masthead (the publicrecord keycap from
`brand/logos/`, byte-equal — never redrawn — + the lowercase mono lockup over a
double hairline rule), the folio line (towns · the dateline · the covenant's
six words), and the footer, on every page. Restyle the shared chrome: chips,
buttons, the scope banner (shrink it from a boxed interruption to one
folio-adjacent line), the vote ledger, the analytics tints. **The ban is a
test:** no cream/oxblood/amber/fuchsia/purple hex survives in the pressed CSS,
and AA contrast passes (`--text-muted` never carries body text).

**§20.2 — the front page.** The newspaper grid of §5: a lead story (latest
meeting, big `i.ytimg.com` still, mono headline, deck, its top moments as
pull-links), a briefs column, standing stories (the long view), a by-the-numbers
box (mono 800 tabular numerals, every figure a link), the updates column
(resurfacing deltas quoting their beads), the access ledger, a votes teaser.
Everything traces to an edition plane named in the bake; nothing hand-typed;
JS-off shows the same content linearly.

**§20.3 — the meeting page.** Transcript-first as ever, restyled: sticky
mini-header once the masthead scrolls away, a right-margin minimap (segment
density with moment marks), speakers at weight 500, the playing segment
following the tape. Then the **Moments panel** — the analyzer's scored moments
as cards (mono timestamp, kind kicker, quote, reason, a score bar in the green
tint scale), each seeking the tape. Measure `analysis_json` on the real corpus
first: if it is too thin, grow a `moments` plane in the bake — press what the
analyzer already knows, never re-analyze at read time.

**§20.4 — search.** Instant (debounced ≥300ms, ≥3 chars), hover peeks (±1
segment of context), provenance chips restyled to the new palette, `j`/`k`/`/`
keyboard paths. **The live-first/static-always logic R1.6 shipped is
load-bearing and must not regress** — the degradation tests
(`TestReaderDegradesToStatic`, the browser-dark walk) must still pass in
substance. Search is an upgrade on the static floor, never a dependency.

**§20.5 — the press page, and the doors go quiet.** One `/app/press` page: the
civicmedia story in three sentences, the tool list as one-line entries (name,
verb, the true reason each needs the desk), the DMG link, the credit line to
communityai.studio. The thirteen `/app/t/<tool>/` URLs **survive as slim
redirect stubs** into `/app/press#<tool>` — citations never die — and no
edition page references `site/content/assets` anymore.

**§20.6 — tombstones.** A `forget`-ed issue's URL renders *"removed from the
record by a steward on {date}"* from the audit ledger at press time, not a bare
404. This closes the debt R1.7 named: control-z.org/app still serves a page
publicrecord correctly dropped. Idempotent — the date is stored audit state,
never wall-clock.

**Then, only if P0 is genuinely closed,** the reel composer (§20 P1): the
moment tray, share links (state in the URL, no server), the cite sheet, a
`reel.json` the desk renders, and the `/app/r` viewer. Build it so a second
meeting's moments slot in without a redesign, but cross-meeting reels stay R3.

# Pre-authorized this session

Restyling the whole edition · vendoring fonts into `web/static/` · adding
`brand/` to the Dockerfile · rebuilding and pushing the image · updating the
Cloud Run jobs · pressing editions and deploying them to the
`amateurmenace/publicrecord` Pages repo (OPERATING §5) · the `/app/press` page
and the door-stub redirects.

# Still Stephen's — do not do these

Making `control-z-tools` public and the full specs/18 split (R1.8). Anything
that raises the $100 GCP budget. A branding *amendment* — if you think the
paper wants a serif display face instead of mono headlines, that is a change to
the branding law, so propose it and stop; do not just style it (open question
1). Choosing dark mode for the reader (open question 3).

# House rules

Full suite green before every push. Add tests for everything new — the palette
ban, tombstone emission, the moments plane, door-stub survival, the fonts
budget line — and never weaken the R1.6 degradation proofs to make a restyle
pass; a red gate is information, fix the cause. **Verify in a real browser at
publicrecord.studio, not just curl** — take screenshots, critique them against
the branding law, iterate; then a 375px pass and a `prefers-reduced-motion`
pass. Commit in coherent pieces in the house voice, ending
`Co-Authored-By: Claude <noreply@anthropic.com>`. Update CHANGELOG, specs/20
status, OPERATING §5 if the deploy flow changes, and PARALLEL's "state of main".

The covenant is not negotiable and the redesign does not get to bend it:
readers never log in and are never tracked; every page reads completely with
JavaScript off and with the API dark; the bake stays byte-idempotent; the
edition stays under its budgets; everything degrades out loud. Beauty is the
goal, but a beautiful page that needs a server to be read is the wrong page.

# Finish by handing Stephen the paper

Not a summary. Deploy P0 to publicrecord.studio and hand him a numbered list of
what to open and what he should see: the front page with a real lead story and
thumbnails, a meeting whose moments he can click into the tape, an instant
search, the press page where thirteen doors used to shout, and the same record
still reading with the API turned off. Screenshots of the before and the after,
side by side. If any P0 item could not land, say which and why rather than
leaving him to find the gap on the page.
