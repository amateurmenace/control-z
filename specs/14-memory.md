# Community Memory
### A civic memory engine for The Community AI Project

**Status:** Draft spec, v0.1 · **Stage:** BETA at launch · **Owner:** Stephen Walter (Weird Machine / BIG) · **Family:** The Community AI Project · **Related:** Community Highlighter (sibling), Community AI in a Box (distribution), Driftwood (beta instrumentation)

> **Highlighter is a microscope. Memory is a telescope.** Highlighter lets you examine one meeting in depth; Memory lets you track an issue across dozens of meetings, multiple public bodies, and years of civic time.

**On the name.** "Community Memory" continues the Captioner/Highlighter naming family — and it's also a resurrection. Community Memory (Berkeley, 1973) was the first public computerized bulletin board: a teletype in a record store, built on the premise that ordinary people should have access to shared computing. This project is that premise, fifty years later, pointed at civic life. If a different name wins later, working alternates: *The Long View*, *Hindsight*, *Perennial*. The rest of this spec says Memory.

---

## 1. Problem Statement

Civic issues unfold over years, but civic attention is meeting-shaped. A rezoning, a school consolidation, or an MBTA Communities compliance fight will surface across a dozen meetings of three different bodies over 30 months — and no resident, reporter, or even board member can reconstruct that arc without heroic effort. The record exists (Massachusetts Open Meeting Law makes these recordings public), but it is scattered, unsearchable across time, and effectively amnesiac. The cost is real: institutional memory lives in the heads of a few long-tenured insiders, newcomers can't catch up, and accountability for what was said two years ago is nearly impossible.

Highlighter solved this for a *single* meeting. Nothing in the suite — or, frankly, anywhere in community media — solves it for *time*.

## 2. Goals

1. **Build the corpus.** A processed, diarized, issue-indexed archive of public meetings for Brookline and Boston: ≥300 meetings / ≥600 hours within 6 months of pipeline completion, with new meetings ingested within 72 hours of publication.
2. **Make time legible.** A resident can go from "what's the story with the Harvard St. rezoning?" to a sourced, watchable timeline in under 2 minutes.
3. **Make issues followable.** Users can follow an issue ("a thread") and get notified when it resurfaces — target ≥40% of registered beta users following at least one thread.
4. **Feed the microscope.** Highlighter can query Memory in real time: every meeting analyzed in Highlighter gets prior-appearance context from the corpus via API.
5. **Generate demand for expansion.** ≥10 qualified "bring Memory to my town" requests in the first 90 days of public beta — the demand funnel for Community AI in a Box.

## 3. Non-Goals

- **Not an official record.** Memory supplements, never replaces, official minutes. Every page says so. (Rationale: legal clarity, trust, and it keeps clerks as allies rather than threatened parties.)
- **No AI stance scores for individuals.** Memory will show a person's own words over time (clips, in context); it will not compute "Councilor X is 73% anti-housing." (Rationale: the human-centric value on the project's front page; accuracy is unprovable; the harm mode is obvious.)
- **Not a public comment platform.** Participation tooling (agenda digests, comment coaching) is a separate future app; Memory links out, it doesn't host debate.
- **No towns without a stable video source in v1.** If meetings aren't recorded and published somewhere ingestible, Memory can't help yet. The request form captures these towns for advocacy, not onboarding.
- **No live processing in v1.** Memory is a post-meeting system; live context is delivered *through Highlighter* via the API, not by Memory ingesting live streams itself.

## 4. Users & User Stories

**Personas:** the *resident-watcher* (cares about one or two issues), the *civic journalist* (local reporter, newsletter writer, or community media producer), the *official/staffer* (board member, town staff who need the record), the *corpus steward* (local partner — ideally a PEG station — who tends a town's corpus), and *Highlighter itself* (a first-party API client).

Priority-ordered:

- As a **resident-watcher**, I want to follow "the thread" on an issue I care about so that I'm notified when it resurfaces on any body's agenda or in any meeting.
- As a **resident-watcher**, I want to see an issue's full timeline — every meeting segment, vote, and document — so that I can catch up on two years of history in one sitting.
- As a **civic journalist**, I want to search across all meetings for a phrase or topic and jump to the exact video moments, so that sourcing a story takes minutes instead of days.
- As a **civic journalist**, I want to build a highlight reel from clips *across different meetings* so that I can publish "the 3-minute history of the ADU debate" with automatic attribution.
- As a **resident-watcher**, I want to turn an issue timeline into a shareable infographic so that I can explain the situation to my neighbors without writing an essay.
- As **Highlighter**, I want to submit a meeting to the corpus and query prior appearances of the current meeting's topics, so that every Highlighter analysis arrives with historical context.
- As an **official/staffer**, I want the roll-call history on an issue so that I can see exactly what was moved, seconded, and decided, and when.
- As a **corpus steward**, I want a curation queue (merge/split issues, fix speaker labels, correct transcripts) so that the corpus stays trustworthy as it grows.
- As a **resident of a town Memory doesn't cover**, I want to request my town and see where it sits in the queue, so that expansion is transparent.
- *Edge cases:* a submitted video that's already in the corpus (dedupe → link to existing); a meeting with no usable audio (fail gracefully, flag for steward); an issue the clusterer wrongly merges (steward split tool); a follower whose thread goes quiet for a year (periodic "still watching" digest instead of silence).

## 5. System Model (core objects)

| Object | What it is | Key fields |
|---|---|---|
| **Town** | Tenant boundary (Brookline, Boston at launch) | name, bodies[], sources[], steward org, governance config |
| **Body** | A public body (Select Board, School Committee, ZBA, City Council…) | name, member roster (seeded, versioned over time) |
| **Meeting** | One recorded session | source URL/upload, date, body, agenda, media refs, status: `queued → transcribing → diarizing → analyzing → live` |
| **Segment** | Diarized transcript span — the atomic unit | speaker ref, timestamps, text, embedding, issue links |
| **Speaker** | A resolved identity across meetings | voice embedding cluster, display name, role, `is_official` flag |
| **Document** | Non-video corpus material | type (warrant, plan, budget, filing), PDF, chunks, embeddings, issue links |
| **Issue** | The telescope's object — a topic tracked over time | canonical name, aliases, embedding centroid, timeline of appearances, status arc, follower count |
| **Thread** | A user's subscription to an issue | user, issue, notification prefs |
| **Reel** | Cross-meeting highlight compilation | clip list (meeting+in/out), order, render status, permalink |
| **Infographic** | Data-grounded shareable artifact | template, bound data queries, overrides, permalink, print/PDF asset |

**Working vocabulary** (in the Lookout tradition): the corpus is **the record**; a followed issue is **a thread**; a new appearance is **a resurfacing**; the timeline page is **the long view**.

## 6. Requirements

### P0 — the corpus and the telescope (cannot ship beta without)

1. **Ingestion connectors.** (a) BIG's first-party Brookline archive (this is the unfair advantage — BIG *produces* these meetings); (b) Boston public bodies via their published video channels (connector pattern: per-source adapter that yields video + date + body + agenda link). *Acceptance:* a new Brookline or Boston council meeting appears in Memory, fully processed, within 72h of publication with zero manual steps.
2. **Processing pipeline.** ffmpeg audio extraction → ASR (Whisper large-v3, run **locally** on the Neighborhood AI Mac Studio cluster per the climate-justice value; cloud batch as fallback) → diarization (pyannote) → cross-meeting speaker resolution (voice-embedding clustering seeded by body rosters + transcript-context name extraction, e.g. "the Chair recognizes Councilor ___") → segment embeddings → Claude analysis passes (summary, agenda-item segmentation, motions/votes extraction, issue candidates). *Acceptance:* ≥95% of ingested meetings reach `live` without manual intervention; officials on seeded rosters are correctly labeled in ≥90% of their segments.
3. **Backfill.** 12 months × ~2 bodies per town to start (~150–300 meetings, illustrative). Claude Batch API for cost.
4. **Issue engine.** Clustering over segments per town → LLM-labeled canonical Issues with alias sets; incremental assignment for new meetings (nearest-issue above threshold, else "candidate issue" queue); steward tools to merge/split/rename. Users can also mint a thread from any search result. *Acceptance:* given a known multi-meeting issue (e.g., an MBTA Communities zoning article), the issue page surfaces ≥80% of its true appearances in the backfilled window (hand-audited sample).
5. **Search + the long view.** Cross-corpus semantic + keyword search with jump-to-timestamp playback; the Issue Timeline page: horizontal time axis, meetings as nodes, segments as beads, documents interleaved, votes as milestones.
6. **Threads + resurfacings.** Follow an issue; email notification on new appearance, with the clip and one-paragraph delta summary ("what changed since last time").
7. **Submissions API + dedupe.** `POST /v1/submissions` (URL or upload) → three-tier dedupe (canonicalized source URL → media hash → transcript-shingle similarity >0.9) → `{meeting_id, status: exists|queued}`. This powers Highlighter's **"Send to the Record"** button and public submissions alike. *Acceptance:* resubmitting an existing meeting by a different URL of the same video links rather than duplicates.
8. **Beta posture.** Persistent BETA badge in the header; "AI-generated — verify against the official record" disclosure on all analysis surfaces; feedback affordance on every page — **run the beta program on a Driftwood instance** (the tools instrument each other).
9. **Bring Memory home.** Public request form: town/state, where meetings live (links), requester role, optional local partner org. Triage on video-source feasibility; public waitlist page showing requested towns and status.

### P1 — the connective tissue and the studio (fast follows)

10. **Context API for Highlighter.** `POST /v1/context/query` accepts agenda items or transcript segments, returns related issues, prior segments with timestamps, related documents, and stats ("this topic: 14 prior appearances across 2 bodies since 2024"). Highlighter renders a **"Prior appearances"** panel during analysis. Webhooks: `meeting.processed`, `issue.resurfaced`.
11. **Documents in the record.** ✅ **SHIPPED 1.8.0.** PDF ingestion (warrants, comprehensive plans, budgets, filings): chunk, embed, link to issues, interleave on timelines with page-level citations. *Built:* `memory/documents.py` fetches a meeting's agendas/minutes/packets from the town's CivicClerk portal (anonymous), extracts + chunks with pypdf (page-numbered), embeds each chunk through `memory/embed.py`, and links to issues by the keyword-then-cosine `_assign` twin; `documents`/`doc_chunks`/`issue_documents` tables in `memory/store.py`; interleaved on the issue timeline (desk `_timeline`, web `bake.py`/`emit.py`) with "p. N" citations; JS-off readable in the edition.
12. **Vote Ledger.** ✅ **SHIPPED 1.8.0.** Structured motions/votes extraction → per-issue and per-member roll-call grids, every cell linking to the video moment. *Built:* `memory/votes.py` reads roll calls extractively off the transcript (verbatim + timestamped, never inferred), officials-only *by construction* — the roster from the town's own agenda canonicalizes ASR-garbled names; `votes` table in `memory/store.py`; per-issue ledger on the issue page + a per-member **The votes** page (`/api/memory/officials`, `web/emit.py` `page_officials`); a votes stage runs inside `ingest.run`. Filtering (by body/member/outcome) is the remaining polish.
13. **Cross-meeting reels.** Search/timeline results → clip basket → reel editor (reorder, trim, auto lower-thirds: "Brookline Select Board · Mar 12, 2025", chapter markers per source meeting) → server-side MP4 render (Cloud Run job, ffmpeg) + shareable web player. **Auto-draft:** "make me a 3-minute history of {issue}" selects representative clips across the arc; the human edits. This deliberately imports Highlighter's editing DNA and points it across time.
14. **Infographic maker.** See §7 — it's substantial enough to spec separately.

### P2 — the wide telescope (architectural insurance)

15. **Crosstown view.** Same-issue comparison across towns ("how Brookline vs. Boston handled ADUs") — becomes meaningful once ≥2 towns have mature corpora; design issue IDs and embeddings to be town-scoped but comparable now.
16. **Docket pre-alerts.** Agenda pre-scanning: "your thread is on Thursday's agenda" — the bridge to the future participation app; requires agenda connectors, so build agenda parsing into connectors now even though alerts ship later.
17. **Attention analytics.** Stacked "attention stream" (topic share per body per quarter), term tracker (n-gram trends over years), longitudinal speaking-time analytics.
18. **Steward program.** Formal roles, curation queue SLAs, per-town governance config (see §8) — co-designed with Neighborhood AI.

## 7. The Infographic Maker

The innovation is **infographics with receipts**: every figure, quote, and timeline entry is bound to corpus data and carries a source chip that deep-links to the timestamped clip or document page. Shareable civic media that can be *checked* — which is simultaneously the feature and the misinformation guardrail.

- **Templates:** Issue Timeline card · Vote Record card · By the Numbers · Quote card (video still + attribution) · Attention chart · Then/Now clip pair.
- **AI create/edit:** chat-driven ("timeline of the ADU debate 2023–2026, emphasize the final vote") generating from live corpus queries; a parameter panel (date range, included data points, palette within the design system) for direct tweaking; every edit re-validates data bindings.
- **Free text is fenced.** User-written captions are visually distinct from sourced data; sourced elements cannot be hand-edited into saying something else — you can remove a data point, not rewrite it.
- **Sharing:** permalink at `/i/{slug}` with OG image for social unfurls; embeddable iframe; **print-friendly**: dedicated print stylesheet + one-click PDF export (flyer-ready — this is the "leave it at the library" format, and it matters in community media land).
- **Ownership & remix:** creator can edit; anyone can **fork** ("remix this infographic") into their own copy with lineage noted — the community-owned ethos applied to civic media artifacts.
- *Acceptance:* Given a published infographic, When a viewer taps any statistic, Then they land on the exact corpus source within one click; Given a print export, Then it renders legibly in black-and-white on US Letter.

## 8. Values, Privacy & Governance Decisions (explicit, not vibes)

- **Public record, careful defaults.** Everything ingested is already public under the Open Meeting Law. But *aggregation changes exposure*: person-level pages and cross-meeting search default to **officials only**. Private citizens speaking at public comment remain findable within a meeting (as today, via Highlighter) but are not auto-aggregated into identity pages. Per-town governance config can adjust this — a Neighborhood AI co-design item.
- **Takedown & correction path.** Public policy page; stewards process requests; corrections annotate rather than silently rewrite (the record remembers its own edits).
- **No stance inference** (restating the non-goal because it will come up in every demo Q&A).
- **Local-first compute** for ASR/diarization/embeddings on the cluster; frontier API (Claude) for analysis passes — documented honestly on the Values page rather than hand-waved.

## 9. Architecture & Stack

- **Services:** FastAPI on Cloud Run (API + web), Cloud Run Jobs for pipeline stages, Cloud Tasks for orchestration, GCS for media, **Cloud SQL Postgres** for the relational core (issues ↔ segments ↔ meetings ↔ votes ↔ threads are join-heavy; Firestore fights you here — recommendation over the house default, flagged in Open Questions), Qdrant for vectors. React front end.
- **Portability constraint:** containerized, storage-abstracted (GCS/S3-agnostic) — if the AWS Imagine Grant (Community Cloud Compute) lands, Memory's heavy lifting should be able to move without rework. Design for either; deploy on GCP now.
- **API auth:** per-app keys; Highlighter is a first-party client; public read endpoints rate-limited.
- **Cost posture (rough, honest):** local ASR ≈ marginal-zero on owned hardware; Claude analysis on the order of low single-digit dollars per meeting-hour with batching; render jobs are pennies. Backfill is the main spend — batch it.

## 10. Success Metrics

**Leading (first 60 days of beta):** corpus size & freshness (≥300 meetings, ≤72h latency); ≥40% of registered users create a thread; resurfacing-email CTR ≥25%; search → playback within one session ≥60%; ≥1 Highlighter-submitted meeting per week via the API.
**Lagging (2 quarters):** ≥10 qualified town requests; ≥3 published journalist uses (cited in a local outlet/newsletter); reels + infographics shared ≥100 times combined; steward corrections trending down per meeting (quality proxy); at least one town onboarded via the request funnel → In-a-Box.

## 11. Phasing (solo-dev honest)

- **Phase 0 — Foundation (~6–8 wks):** connectors (BIG archive + Boston), pipeline, backfill, meeting pages + search, beta badge, request form. *The record exists.*
- **Phase 1 — The Telescope (~6 wks):** issue engine, threads + resurfacings, the long view, submissions API + Highlighter "Send to the Record." *Time becomes legible.*
- **Phase 2 — Connective Tissue (~4–6 wks):** context API + Highlighter prior-appearances panel, documents, Vote Ledger. *Microscope and telescope converge.*
- **Phase 3 — The Studio (~6 wks):** cross-meeting reels, infographic maker. *The record becomes media.*
- **Phase 4 — The Wide View:** crosstown, docket pre-alerts, attention analytics, steward program, town #3.

## 12. Open Questions

- **(Policy — Neighborhood AI, blocking for launch copy):** exact defaults and per-town config for private-citizen aggregation; takedown policy text.
- **(Eng — non-blocking):** Postgres recommendation vs. Firestore house pattern — confirm before Phase 0 schema work.
- **(Eng — non-blocking):** dedupe threshold tuning; what counts as "same meeting" when a body posts both a full feed and a trimmed cut.
- **(Design — non-blocking):** issue ontology curation load — how much steward time does a healthy town corpus actually need per month? Instrument from day one.
- **(Product — non-blocking):** does Memory eventually absorb Highlighter's archive browsing, or do they stay two doors into one corpus? Decide after Phase 2 usage data.
- **(Infra — non-blocking):** GCP-now/AWS-later boundary if CCC funds — which stages migrate first (ASR? renders?).
