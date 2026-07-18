# The Community AI Project — Program Spec
### The suite as one system: sequencing, shared infrastructure, and the decisions that span all of it

**Status:** Draft spec, v0.1 · **Owner:** Stephen Walter (Weird Machine / BIG) · **Scope:** the whole portfolio — Captioner and Highlighter (shipped), Memory, Interpreter + Narrator, Publisher, and In-a-Box (specced) · **Reads with:** the five app specs in this folder; this document sits above them.

> The individual specs answer *what each app is*. This one answers *what the project is* — the dependency graph beneath the apps, the order to build them in, the infrastructure built once and reused everywhere, and the licensing / governance / sustainability decisions that can't live inside any single app.

**Thesis, in one line:** corporate AI extracts toolmaking; the Community AI Project proves communities can own it. The apps are the proof. **In-a-Box is the distribution** — the mechanism that turns a portfolio into infrastructure other communities run themselves. Every decision below serves that arc.

---

## 1. The Portfolio, at a glance

| App | What it is | Status | Serves |
|---|---|---|---|
| **Captioner** | Encoder-agnostic live captioning | **Production** (6+ mo on air) | viewers, stations |
| **Highlighter** | Diarized, searchable single-meeting video + clipping | **Production** | watchers, journalists, producers |
| **Memory** | Cross-meeting civic corpus — the telescope to Highlighter's microscope | Specced · beta | watchers, journalists, officials, stewards |
| **Interpreter** | Live translation into the seven panel languages + Simple English | Specced · beta | non-English residents |
| **Narrator** | Audio description for community TV (novel to public access) | Specced · beta | blind / low-vision residents |
| **Publisher** | Program in → clips, copy, social, newsletter out | Specced · beta | producers, station staff |
| **In-a-Box** | The suite packaged for any station to run | Specced · pilot | other PEG stations, the movement |

Two are shipped and mature. That fact is load-bearing for the sequencing: it means the distribution layer can start with real cargo, not vaporware.

## 2. The Dependency Graph (why order isn't arbitrary)

```
  Captioner (ASR + timing)  ──────────────┬──────────────┬────────────────┐
       │                                  │              │                │
       ▼                                  ▼              ▼                ▼
  Highlighter                        Interpreter     Narrator        Publisher
  (moment detection,                 (ASR→MT)        (gaps from      (needs detection
   diarization, clipping)                             Captioner       -as-a-service)
       │                                               timings)            │
       │  ── extract: DETECTION-AS-A-SERVICE ──────────────────────────────┤
       │                                                                   │
       ▼                                                                   │
    Memory  ◄── reuses detection service, builds the shared MEDIA PIPELINE │
       │        (ffmpeg→ASR→diarize→embed→analyze) that others borrow from │
       │                                                                   │
       │  owns the CORPUS + SUBMISSIONS API ◄── Highlighter & Publisher    │
       │        both call "Send to the Record"  ───────────────────────────┘
       ▼
   In-a-Box  ◄── packages everything; starts with {Captioner, Highlighter, Publisher},
                 absorbs each app as it hardens; config-driven multi-tenancy is its spine
```

**Three shared unlocks fall out of this graph — build them once:**

1. **Detection-as-a-service.** Highlighter's moment detection, extracted from its UI into a callable service. *Publisher needs it for clip candidates; Memory reuses it.* This is the single most leveraged piece of engineering in the whole program — build it while building Publisher, and Memory inherits it for free. (Flagged as the one real eng task in the Publisher spec; it's actually a program-level asset.)
2. **The media pipeline.** ffmpeg → ASR → diarization → embeddings → analysis. Memory builds the most elaborate version (cross-meeting speaker resolution, issue clustering). Publisher and the accessibility apps need lighter slices of the same spine. Build Memory's, expose the stages, let the others call them.
3. **The corpus + submissions API.** Memory owns it. Highlighter's and Publisher's "Send to the Record" buttons both call it. It's the hub that makes the suite feel like one system instead of five tabs.

Everything else that recurs — config-driven multi-tenancy (the Driftwood/Lookout pattern), local-first compute on the Neighborhood AI cluster, Driftwood-as-beta-instrumentation, cloud portability — is a *pattern* you already own, applied repeatedly. In-a-Box formalizes the multi-tenancy pattern into a product.

## 3. Sequencing — the recommended order

The organizing principle: **for a solo maintainer, burnout is the existential risk** (named in the In-a-Box spec). So sequence to de-risk the biggest assumptions cheaply *before* the biggest build — prove you can ship, prove someone adopts, then swing big at the marquee.

### Recommended: the de-risking spine

**Move 1 — Publisher (~5–6 wks to usable).** The cheap foundation, not the boring one. It forces the detection-service extraction Memory will reuse, serves BIG's own producers (instant low-stakes feedback, and the station visibly makes more), and proves solo-shipping capacity. Lowest risk goes first. *Assumption de-risked: "I can ship a new app solo, and it builds shared rail."*

**Move 2 — In-a-Box Wave 1, overlapping Move 1's tail (~4 wks packaging + ongoing).** Package the three things that now exist — Captioner, Highlighter, Publisher — stand up a minimal Mission Control, get **one** external station live. Test the entire movement thesis for the price of packaging, *before* five months on Memory. *Assumption de-risked: "Another station will actually adopt this" — the most valuable thing to learn early, and the cheapest.*

**Move 3 — Memory (~4–5 mo).** The marquee telescope; the high-value bet. Reuses the detection service, builds the shared pipeline, and — critically — generates the town-request demand that becomes In-a-Box's cohort pipeline. This is where the project gets its civic splash and its most fundable artifact. *Assumption de-risked: "Civic memory across time is buildable and wanted."*

**Move 4 — Interpreter + Narrator (~4 mo; Interpreter's first phase is fast).** The accessibility pillar on the Captioner spine. Interpreter's live-caption phase ships language access quickly and opens language-access + disability funders; Narrator is the genuinely novel capstone (AD in public access essentially doesn't exist). *Assumption de-risked: "The suite leads on accessibility, not just retrofits it."*

**Move 5 — In-a-Box, full (capstone + continuous).** The cohort program scales, each app enters the box as it matures, the sustainability model goes live. This isn't a final phase so much as the track Move 2 started, now carrying the full suite. *Assumption de-risked: "This is a movement, not a portfolio."*

### The honest alternative: Memory-first

Follow the energy, lead with the marquee. Legitimate — Memory is the most fundable piece and the one you're actually fired up about, and founder energy is real fuel for a solo dev. **The cost:** you front-load your single longest, riskiest build, and nothing else ships for ~6 months. **If you take it,** lock these down *before* Phase 0 so the risk is bounded: the Neighborhood AI policy calls (officials-only aggregation defaults, takedown text), the Postgres-over-Firestore decision, and the detection-service extraction (do it first even without Publisher, since Memory wants it too). I lead with Publisher only because proving the loop cheaply protects against the burnout failure mode; if your funders or your energy point at Memory, take Memory and bound it.

### What NOT to do
- **Don't build all four in parallel.** One builder, four tracks, guaranteed thrash. In-a-Box packaging is the *only* thing that parallelizes cleanly (it's ops, not app-building).
- **Don't put In-a-Box strictly last.** Its Wave 1 validates the whole thesis with tools that already exist; waiting until the end means learning "will anyone adopt this?" after you've spent a year building for adopters who may not exist.
- **Don't split Interpreter and Narrator far apart.** They share an ingest spine; keep them adjacent.

## 4. Program Timeline (solo-dev honest)

Quarters, not dates. **Heavy caveat:** these assume close-to-dedicated time. In reality this competes with Hope Group client work, BIG operations, teaching, and Lookout — so treat the calendar as *sequence and relative effort*, and read the wall-clock as **12–18 months**, not the ~11 the raw sum implies.

| Quarter | Primary build | Parallel track | Milestone |
|---|---|---|---|
| **Q1** | Publisher (Ph1–2) + detection-service extraction | — | Publisher live at BIG; detection is now a service |
| **Q2** | In-a-Box Wave 1 packaging + Memory Ph0 (pipeline, backfill, connectors) | first external pilot station on {Captioner, Highlighter, Publisher} | **The record exists**; movement thesis tested with one real adopter |
| **Q3** | Memory Ph1–2 (telescope, threads, context API, votes, docs) | Highlighter ↔ Memory API live | **Time is legible**; microscope and telescope converge; town-requests start arriving |
| **Q4** | Memory Ph3 (reels, infographics) → Interpreter Ph1 (live captions, 7 languages) | In-a-Box cohort #1 recruiting from town-requests | Memory studio ships; language access live; cohort forming |
| **Q5** | Narrator (VOD pipeline, review UI, meeting-graphics wedge) + Interpreter Ph2–3 (TTS, reviewers) | governance kit + license ratified; Publisher enters the box | Accessibility pillar complete; box carries 3+ apps |
| **Q6+** | Hardening, backfill, town #3 | sustainability model live; open-enrollment decision (data-gated) | **Portfolio is infrastructure** |

## 5. Shared Infrastructure (build once, reuse everywhere)

- **Detection service** — §2. Extract during Publisher; Memory inherits.
- **Media pipeline** — §2. Memory owns the full version; expose stages for lighter callers.
- **Corpus + submissions API** — §2. The hub. Memory owns; everything sends to it.
- **Config-driven multi-tenancy** — the Driftwood/Lookout pattern as law across every app: station identity, sources, features are config, never code forks. This is what makes In-a-Box a config problem instead of five rewrites.
- **Local-first compute** — ASR, diarization, embeddings, MT, TTS, and vision-where-viable run on the Neighborhood AI Mac Studio cluster (the climate-justice value, made literal); Claude for analysis / generation / Simple English. Documented honestly per app, not hand-waved.
- **Cloud portability** — containerized, storage-abstracted (GCS/S3-agnostic). Deploy on **GCP now**; if the **AWS Imagine Grant (CCC)** lands, the heavy stages migrate without rewrite. In-a-Box ships Terraform for *both* clouds — AWS is a first-class citizen because CCC made it one, not an afterthought port.
- **Driftwood as beta instrumentation** — every app's beta program runs on a Driftwood board; every In-a-Box station gets its own board wired to your triage. The tools instrument each other; this is the recursive proof of the toolmaking thesis.

## 6. Cross-Cutting Decisions (can't live in one app)

### Licensing
- **Code: AGPL-3.0.** Network-copyleft closes the SaaS loophole — a vendor can't fork the commons into a black box and rent it back. Values-coherent ("no black boxes") with teeth, and structurally protective against the exact extractive pattern In-a-Box is written against. **Flagged as a decision, not a default:** AGPL sits on some corporate/muni-IT banned lists; ship a plain-language "what this means for your station" note (self-hosting unmodified owes nothing extra) to defuse the procurement reflex. *Decision needed before In-a-Box Phase 1.*
- **Content: CC BY-SA 4.0.** Already the site's license; keep it.
- **Name policy:** anyone may run the code; "Community AI Project" branding requires staying within the values charter. Lightweight trademark-style guard against values-drift in forks.

### Values as engineering constraints (not posters)
- **No AI stance inference on individuals** — hard non-goal across the suite. Show people their own words in context; never compute "Councilor X is 73% anti-housing."
- **Officials-only aggregation by default** — private citizens findable within a meeting, not auto-aggregated into identity pages; per-town governance config can adjust. *Neighborhood AI co-design; blocking for Memory launch copy.*
- **Anti-lock-in** — data export + offboarding path from day one in every hosted context. It's what makes "community owned" true rather than decorative.
- **Provenance as UI** — every AI surface (translation, description, analysis) carries model + review status. "Trust is earned through transparency," made literal.

### Sustainability
- **Grants bootstrap** (AWS Imagine precedent; accessibility, language-access, disability-equity, and press-infrastructure funders each have a door into different apps — this suite is unusually fundable across categories).
- **Sliding-scale fees sustain** — hosted-tier hosting+support sized to cover marginal cost and, past N stations, a support contractor. Published transparently.
- **Paid onboarding** (white-glove setup) as the third leg.
- **Explicit non-model: no data monetization, ever.** Load-bearing for every claim the project makes.

### Governance
- Governance **templates**, not authority — data-governance, AI-disclosure, takedown/correction, model-provenance, co-designed with Neighborhood AI and shipped in the box for each community to adapt and own.

## 7. Program-Level Success Metrics

Not per-app (those live in each spec) — the whole:
- **Suite depth at BIG:** all four new apps in production; Captioner/Highlighter/Publisher/Memory in weekly use.
- **Distribution:** 3–5 pilot stations live; ≥1 external code contribution merged (the movement signal).
- **Corpus growth through the network:** ≥2 towns beyond Brookline/Boston stewarded by pilot stations in year one.
- **Fundability realized:** grant capture across ≥2 distinct funder categories (accessibility, civic/press infra).
- **Sustainability:** sliding-scale revenue covering marginal infra by ~month 12.
- **The recursive proof:** Driftwood instrumenting the betas, the box shipping Driftwood, stations feeding Memory — the toolmaking thesis demonstrated, not asserted.

## 8. Program-Level Risks

- **Solo-maintainer burnout — the existential one.** Mitigations: the de-risking sequence (ship small, prove adoption, *then* the big build); docs-as-product as the scaling mechanism; cohort-gating on In-a-Box; a paid tier explicitly funding a contractor at scale. **Kill/pause criterion:** if any single build blows past 1.5× its phase estimate, stop and cut scope to the P0 spine rather than pushing the date.
- **Scope creep across a seven-app surface** — mitigated by the maturity gate (nothing enters the box that BIG isn't running in production) and ruthless P0 discipline in each spec.
- **Funding discontinuity** — mitigated by cross-category fundability and the sliding-scale model reducing grant dependence over time.
- **Values drift in forks** — mitigated by AGPL + name policy + values charter.
- **The distribution layer outpacing the apps** — mitigated by the maturity gate; In-a-Box never ships ahead of production reality.

## 9. Open Questions (program-level)

- **(Strategy, blocking Move 1):** Publisher-first vs. Memory-first — the §3 call. Decide based on funding timeline and honest energy assessment. Everything downstream sequences from this.
- **(Legal, blocking In-a-Box Phase 1):** AGPL ratification + the muni-IT note.
- **(Eng, blocking Publisher estimate):** is Highlighter's detection extractable as a clean service, or entangled with its UI? Determines whether the shared unlock is a week or a month.
- **(Policy, blocking Memory copy):** Neighborhood AI privacy defaults + takedown text.
- **(Eng, blocking Memory Phase 0):** Postgres-over-Firestore confirmation for the join-heavy corpus.
- **(Partners, blocking cohort recruitment):** MassAccess vs. ACM national as first distribution channel.
- **(Program, non-blocking):** does Memory eventually absorb Highlighter's archive browsing, or do they stay two doors into one corpus? Decide after Memory Phase 2 usage data.
