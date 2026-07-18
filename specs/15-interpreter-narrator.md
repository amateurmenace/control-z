# Community Interpreter & Community Narrator
### Captioner's siblings: live translation and audio description for community TV

**Status:** Draft spec, v0.1 · **Stage:** BETA at launch · **Owner:** Stephen Walter (Weird Machine / BIG) · **Family:** The Community AI Project · **Related:** Community Captioner (upstream parent — both siblings consume its feed and timing data), Community AI in a Box (both ship in the box), Driftwood (beta feedback)

Two products, one spec, because they share an ingest spine: both sit downstream of Community Captioner's encoder-agnostic feed and its timestamped ASR output. **Interpreter** turns one broadcast into many languages. **Narrator** makes the visual layer of community TV audible — a thing that essentially does not exist anywhere in public access, which makes it the suite's genuinely novel claim.

---

## 1. Problem Statement

Boston-area civic life happens in at least seven languages, but community broadcasts happen in one. Residents who speak Spanish, Haitian Creole, Chinese, Portuguese, Vietnamese, or Russian can watch their government meet but not understand it — a language-access gap that municipal mandates increasingly recognize and that human interpretation can't scale to cover every meeting of every body. Separately, blind and low-vision residents get a soundtrack with holes in it: every slide, chart, site plan, and lower-third shown at a meeting is information they simply don't receive. Commercial TV was dragged into audio description by FCC mandate; PEG access was never required to follow, so it never did.

## 2. Goals

1. **Interpreter:** every Captioner-covered live broadcast available with captions in the seven languages already promised by the project site's accessibility panel (Español, Simple English, 中文, Português, Kreyòl, Tiếng Việt, Русский), at ≤2s added latency over English captions.
2. **Interpreter:** translated *audio* (TTS) available for VOD in ≥4 languages, and as a delayed live web stream where feasible.
3. **Narrator:** ≥50% of new BIG VOD programming carries an audio-described track within 6 months of launch, at ≤15 minutes of human review time per program hour.
4. **Narrator (civic wedge):** every described meeting includes descriptions of on-screen graphics/slides — the highest-value, most tractable AD target in government video.
5. Establish the "public access leads where commercial TV was dragged" narrative: 2 external stations piloting via In-a-Box within a year.

## 3. Non-Goals

- **Not replacing human interpreters** for legally mandated live interpretation contexts; Interpreter extends coverage to the long tail no budget reaches, and every output is labeled AI-generated.
- **No live AD for unstructured programming in v1** (drama, sports, verité). Live AD without known dialogue gaps is an unsolved problem; we scope live to template-driven structured formats (meetings) as an experiment, not a promise.
- **No new ingest path.** If Captioner can't see the program, the siblings don't process it. (Keeps the encoder-agnostic problem solved exactly once.)
- **No per-language human review requirement before publishing** — that would cap coverage at human capacity, which is the problem we're solving. Review is post-hoc and community-powered instead.

## 4. Users & User Stories

- As a **Kreyòl-speaking resident**, I want live captions of the School Committee meeting in my language so that I can follow decisions about my kid's school as they happen.
- As a **blind resident**, I want the charts and slides shown at a budget hearing described in the audio so that I receive the same information as sighted attendees.
- As a **station operator**, I want translated caption tracks and an AD track attached to VOD automatically so that accessibility doesn't depend on my staffing.
- As a **community reviewer**, I want to flag and correct a bad translation in my language so that the glossary improves and my community stops seeing that mistake.
- As a **broadcast engineer**, I want to choose which secondary audio service airs per program (translation vs. description) so that I can work within the channel constraints of my headend.
- As a **low-vision web viewer**, I want an "extended description" playback mode that pauses the video during long descriptions so that nothing is truncated to fit a gap.
- *Edge cases:* proper nouns mangled in translation (glossary/do-not-translate lists); crosstalk segments (mark low-confidence, translate conservatively); programs with wall-to-wall dialogue (Narrator produces a descriptions transcript + extended-mode only); Kreyòl TTS unavailability (captions-first for ht, documented).

## 5. Community Interpreter — Requirements

**Pipeline:** Captioner ASR (English, timestamped) → segment-aware MT → per-language outputs. Whisper translates *into* English only, so the architecture is fixed: ASR(en) → MT(target). Local-first MT (NLLB-200 / MADLAD-class models on the Neighborhood AI cluster) with API fallback per language where local quality is insufficient — the honest per-language quality table is a launch artifact, not a footnote.

**P0**
1. **Live translated captions** in all seven panel languages, delivered as additional WebVTT tracks in the web player with a language selector. Added latency ≤2s over English captions.
2. **Simple English as a first-class language.** Live intralingual plain-language captioning (shorter sentences, common words, jargon expanded) — cognitive accessibility, and quietly one of the most novel features in the suite. Same pipeline, different target.
3. **Civic glossary system, per town:** do-not-translate lists (place names: "Coolidge Corner"; proper nouns), civic term dictionary ("warrant article," "override," "home rule petition") with vetted translations per language. Glossaries are versioned and editable by reviewers.
4. **Broadcast delivery where the plant supports it:** English on CC1; Spanish on CC3 (the long-standing 608 convention) / additional 708 services for others as headend capability allows. Per-program config, engineer-facing.
5. **Beta labeling + feedback:** "AI translation — beta" watermark on translated tracks; one-tap "flag this line" feeding a per-language review queue (a Driftwood board per language is the cheap v1).
6. **VOD re-pass:** after broadcast, re-translate with full-context segmentation for higher quality; VOD tracks supersede live tracks.

**P1**
7. **Translated audio (TTS):** Piper-class local voices for es/pt/zh/vi/ru; delayed live web audio stream (~8–15s behind program) with clear "delayed translation" labeling; SAP delivery for broadcast on a per-program basis (see the one-SAP-channel constraint in §7). Kreyòl TTS is thin across the industry — captions-first for ht until a credible voice exists, stated plainly.
8. **Community reviewer program:** named reviewers per language; corrections flow into glossaries; reviewer credits on the program page (recognition is the compensation model until there's budget for stipends — flag for grants).

**P2**
9. Additional languages by demand signal from the request form; per-body language priorities (e.g., always-on Spanish for School Committee).

*Acceptance samples:* Given a live meeting with Captioner running, When a viewer selects Español, Then translated captions appear within 2s of the English captions with glossary terms rendered per the vetted dictionary. Given a flagged line, When a reviewer corrects it, Then the correction applies to VOD and the glossary within 24h.

## 6. Community Narrator — Requirements

**Pipeline (VOD-first):** shot/scene detection → dialogue-gap map derived from Captioner's word timings → vision-model description generation, *length-constrained to fit each gap* → TTS (distinct, consistent synthetic voice) → auto-ducked mix → human review pass → outputs.

**P0**
1. **VOD audio description** for new programming: mixed AD track produced automatically, published after review.
2. **Review timeline UI** — the product's real heart: gaps and draft descriptions on a timeline; accept / edit / regenerate per cue; target ≤15 min human time per program hour. Descriptions follow DCMP/ACB style conventions (present tense, concise, describe don't interpret) enforced in the generation prompt and linted in the UI.
3. **Meeting-graphics description (the wedge):** slides, charts, site plans, and lower-thirds detected and described — in-gap where possible, and always captured in the descriptions transcript. This is the difference between "AD as compliance" and "AD as civic equity."
4. **Outputs:** mixed secondary audio track (broadcast-ready), standalone AD audio file, descriptions-as-WebVTT (text track for braille-display users and search), and a **WCAG-style extended-description web mode** that pauses video for descriptions too long for their gap.
5. **Beta labeling** and per-program feedback (Driftwood again).

**P1**
6. **Backfill mode** for high-value library titles (stewards nominate).
7. **Experimental live AD for structured formats:** template-driven descriptions for meetings only ("Slide shown: FY27 budget, table of department totals"), explicitly labeled experimental.

**P2**
8. Voice options; per-station voice identity; description density preference (minimal/standard/rich).

*Acceptance samples:* Given a meeting VOD where a budget slide is on screen for 40s under discussion, When Narrator processes it, Then the slide's content is described in the AD track and appears in the descriptions transcript. Given a program with insufficient gaps, Then the extended web mode carries full descriptions and the broadcast track carries the fitted subset — never silent failure.

## 7. Shared Constraints & Architecture

- **The one-SAP-channel problem:** most broadcast plants offer a single secondary audio service. Translation audio and AD therefore compete *on air*; the web player is where all tracks coexist. Per-program engineer choice in config; document the tradeoff rather than pretending it away.
- **Stack:** same spine as the rest of the suite — FastAPI services on Cloud Run, jobs for renders/mixes, local models on the cluster (MT, TTS, vision where viable), Claude for description generation and Simple English, GCS media, config-driven per-station settings (the Driftwood/Lookout pattern), portable containers (CCC-ready).
- **Quality honesty as UI:** every language and every AD track carries provenance (model, review status). Trust is earned through transparency — it's on the values page; make it literal.

## 8. Success Metrics

**Leading:** % of live broadcasts with translated captions (target: 100% of Captioner-covered programs at launch); translated-track selection rate by language; flags per 1,000 lines trending down; AD review time per program hour ≤15 min; % of new VOD described ≥50% by month 6.
**Lagging:** feedback panel of blind/low-vision and non-English-speaking residents reporting parity of information access (qualitative, run twice a year); 2 external stations piloting; language-access citations in town/city accessibility reporting; grant capture referencing the program (this suite is unusually fundable — accessibility, language access, and disability-equity funders all have a door in).

## 9. Phasing

- **Phase 1 (~4–6 wks):** Interpreter live captions (all seven languages) + glossaries + VOD re-pass + beta labeling.
- **Phase 2 (~6 wks):** Narrator VOD pipeline + review UI + meeting-graphics wedge + all four output formats.
- **Phase 3 (~4 wks):** TTS translated audio (VOD + delayed live web), reviewer program, broadcast CC3/SAP delivery per plant capability.
- **Phase 4:** live experimental AD for meetings, backfill mode, additional languages by demand.

## 10. Open Questions

- **(Eng, blocking for Phase 3):** exact headend capabilities at BIG for CC3/708 services and SAP insertion — audit the plant before promising broadcast delivery specifics.
- **(Community, non-blocking):** reviewer recruitment per language — which community orgs partner for Kreyòl, Vietnamese, Russian? (Neighborhood AI + BIG networks.)
- **(Eng, non-blocking):** local MT quality thresholds per language — publish the eval table; decide API fallback per language from data, not vibes.
- **(Design, non-blocking):** AD voice selection — one project-wide voice for brand coherence vs. per-station identity.
- **(Legal-ish, non-blocking):** none required — PEG AD is voluntary — but draft the "leading voluntarily" framing carefully so it invites peers rather than shaming them.
