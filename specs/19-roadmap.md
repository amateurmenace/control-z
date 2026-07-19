# 19 — What next: finish, then grow

**Status:** Draft v0.1 · **Stage:** adopted as the working roadmap ·
**Owner:** Stephen Walter (Weird Machine) · **Related:** specs/14 (the engine's
unshipped studio phase), specs/16 (the reader), specs/17 (the hosted record),
specs/18 (the split), `record/OPERATING.md` (the live system), PARALLEL.md

> Two products, one honest sentence each. **publicrecord.studio is live and
> serving nothing** — Cloud Run answers, the database is migrated and seeded,
> and the corpus is in flight from the desk; no key, no console auth, no
> scheduler, no domain. **civicmedia.studio is built and unreleased** — 2.0.0
> is tagged, signed, and notarized, and the DMG on disk predates its own tag
> by three commits. The roadmap's first job is not features. It is to make
> both sentences false.

---

## 1. The rule this roadmap runs on

**Finish before feature.** Every phase below ends with something a resident or
an operator can touch, and no phase opens until the one before it closed. The
repository's history already proves the cost of the alternative: the covenant
page claimed AGPL for a month while the repo was MIT, and the reader promised
"vector search stays at the desk" while a server was being built to disprove
it. Claims run ahead of the work when the work is not sequenced.

The six words this roadmap was asked for, translated into things that can be
checked:

| Word | Meaning here | Proof |
|---|---|---|
| **powerful** | search that understands; a record that feeds itself; history past RSS's 15-item window | a meeting posted Monday night is searchable by meaning Tuesday morning, no Mac involved |
| **user friendly** | the steward never edits JSON; the reader never learns our architecture | every intake decision is a preview with a cost number; every degradation is a sentence |
| **beautiful** | one brand source; the record reads like a paper, not an app | `emit.py` draws from `brand/`, not by hand; Control-Z gets its keycap; the long view survives a phone |
| **efficient** | the index scales past the static envelope; the bill stays legible; nothing presses twice | `segs.json` stays under its 2 MB warn line at 10× the corpus; the spend ledger matches the invoice |
| **complete** | `OPERATING.md` §8 reaches zero; the split finishes; 2.0.0 is on the releases page | the lists themselves |
| **new** | specs/14's studio phase and specs/17's waves 2–3, in that order | reels, infographics, context API, Boston depth, crosstown |

---

## 2. R1 — The record breathes (publicrecord, days)

The wave-1 backend exists and is proven; R1 is the eight switches between
"deployed" and "alive." In order, because each gates the next:

1. **The corpus lands.** In flight from the desk through the Cloud SQL proxy.
   Gate: the import ends *"the record arrived whole"* and `/api/health`
   reports 10 meetings, 72,816 segments.
2. **The neural half turns on.** `RECORD_GEMINI_KEY` into Secret Manager, the
   embed backfill as a Cloud Run job with a hard spend cap, every batch in the
   `spend` ledger. *Acceptance:* `/api/search?space=neural` returns `meaning`
   chips, and `/api/steward/spend` shows what it cost to the dollar.
3. **The console turns on.** OAuth web client id + `RECORD_STEWARD_ALLOWLIST`.
   *Acceptance — chosen deliberately:* the steward's first audited act is
   renaming `City Realy` to `City Realty`, the caption garble the import
   carried on purpose because fixing it was a steward's job, not an importer's.
4. **Ingest runs where the record lives.** `record-pipeline` job: approved
   submission → captions-first ingest → embed → issue-assign. No Scribe in the
   container; a no-caption meeting parks in `asr_tasks` for the drain, and the
   console says so. **One meeting is walked end to end and read by a human
   before any backlog runs** — the connector has polled and classified against
   three real channels, but hosted ingest has carried zero meetings.
5. **The scheduler.** Nightly per town, 03:00 America/New_York. The intake
   caps (`max_per_poll`, `since`) are what make this safe to leave alone.
6. **The reader goes live-first, static-always.** The deferred `app.js`
   decision, now decided: when the edition knows a Studio exists and
   `/api/freshness` answers, the search field calls `/api/search` (meaning
   chips and all); when it doesn't, the static index answers and the page says
   *"meaning-search needs the Studio; words still work."* The edition remains
   complete without the API — that covenant is load-bearing and tested.
7. **The domain.** Complete specs/18's site move: tools site to the tools
   repo with its own Pages + `control-z.org`; swap the monorepo's Pages
   domain to `publicrecord.studio`; press from the cloud to GCS behind it.
   control-z.org never goes dark; every `/app/*` citation survives.
8. **The split closes.** Strip the ten tool directories, apply AGPL-3.0 (the
   holder question is settled: Stephen Walter, Weird Machine, partners
   credited), rename both repos, re-point both Macs, split the eight
   both-sided test files.

*R1 done means:* the opening sentence about publicrecord is false, and
`OPERATING.md` §8 is empty.

## 3. R2 — The desk ships and lends itself (civicmedia, days)

1. **2.0.0 ships.** Rebuild the DMG **from the `v2.0.0` tag** (the notarized
   artifact predates it), re-notarize, and hold for the one gate that cannot
   run on a dev machine: `spctl` on a Mac that has never seen the certificate.
   This release needs that gate more than any before it — the bundle identity
   is new. Then the GitHub release, `RELEASE-NOTES-2.0.0.md` as the body.
2. **The drain closes its loop** (specs/17 §6.4; `czcore/drain.py` is built
   and gated). A desk volunteers with the service token, claims an
   `asr_tasks` row, transcribes on its own hardware, posts the transcript
   back. *Acceptance:* a no-caption meeting becomes searchable without a
   GPU ever being billed.
3. **"Send to the Record" points at the Studio** (specs/17 §11.5, deferred
   from wave 1). Highlighter and Publisher gain the third target with the
   steward key; the desk stops being the only door.
4. **Brand debt, paid.** Control-Z's keycap mark (the one TODO the brand
   system shipped with); `web/emit.py` reads `brand/` instead of inlining the
   publicrecord mark by hand — the divergence risk specs/18 flagged.

## 4. R3 — The record becomes media (specs/14's studio phase, weeks)

The features that were always the point, now that the plumbing can carry them:

1. **The context API** (specs/14 §P1.10). Highlighter asks the record for
   prior appearances mid-analysis; every meeting arrives with its history.
   The seam is ready — `search`/`semantic` are town-scoped and the engine is
   identical on both stores.
2. **Backfill, past the 15-item window.** Per-body YouTube playlists first
   (low volume, high signal, zero new dependencies — `channel_feed_url`
   already accepts them); the YouTube Data API only if playlists don't
   exist for a body. Boston City Council's human captions make it the best
   first backfill target.
3. **The index past the envelope.** At 10 meetings, `search/segs.json` is
   1.1 MB gz; the warn line is 2 MB; the specs/14 target of 300 meetings
   implies ~33 MB — infeasible statically. The answer is already implied by
   R1.6: **live-first search makes the static index a fallback**, so it can
   cap itself to the most recent N meetings with an honest line, while the
   API searches everything. Measure before choosing N; the bake already
   prints the number that decides.
4. **Cross-meeting reels** (specs/14 §P1.13) — desk-rendered against the
   hosted corpus, clips across meetings with automatic attribution.
5. **The infographic maker** (specs/14 §7) — two templates first (Issue
   Timeline, Vote Record), receipts on every figure, print-ready. This is
   the "leave it at the library" artifact and the misinformation guardrail
   in one object.
6. **Boston depth.** CivicClerk documents for Boston bodies, rosters and
   glossaries per town — the officials-only enforcement needs the roster.

## 5. R4 — Many towns, one instrument (specs/17 wave 3, months)

Town onboarding as configuration (the request funnel from specs/14 §P0.9
feeding it); crosstown views the day two corpora mature; per-town digests and
RSS; In-a-Box v2 documented as the compose file it already is; IAP if
stewards multiply; the muni-IT procurement note specs/12 §9 still owes.

## 6. Non-goals, still

No video hosting. No reader accounts, ever — the reader's only state is
localStorage. No stance inference about any person. No cloud GPU ASR as a
default — the drain exists so the hard case costs a station's own watts, not
a bill. No Firebase. And no new feature while its phase's finishing list is
open; that is the whole point of this spec.

## 7. Open questions

- **(Stephen)** The Gemini key's monthly ceiling before R1.2 flips it on.
  The backfill estimate is low single dollars for 73k short segments; the
  cap in the job should be set anyway, and the ledger proves the estimate.
- **(Stephen)** OAuth consent screen + web client id — console work, a
  human's ten minutes; gcloud cannot do the consent screen.
- **(Stephen, R3)** Do Brookline/Boston maintain per-body playlists? If BIG
  controls its own channel, creating them is the cheapest backfill there is.
- **(Eng, R3)** The static index cap N — measure the gz curve on the real
  corpus before choosing; the reader's offline promise sets the floor.
- **(Design, R3)** Infographic template pair for v1 — Issue Timeline + Vote
  Record recommended; the long view and the ledger are the two surfaces
  residents already cite.
