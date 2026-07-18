# Community Publisher
### The publish kit: any program in → clips, descriptions, newsletter blurb, social cuts out

**Status:** Draft spec, v0.1 · **Stage:** BETA at launch · **Owner:** Stephen Walter (Weird Machine / BIG) · **Family:** The Community AI Project · **Related:** Community Captioner (ASR + caption burn-in), Community Highlighter (moment detection + clipping), Community Memory (programs can be sent to the record), Community AI in a Box (multi-tenant future)

**What this is, honestly:** a workflow product, not a research product. Publisher is ~80% orchestration of components the suite already has — Captioner's transcripts, Highlighter's moment detection and clipping — plus a copywriting layer and a review queue. That's the point: it ships fast, and it serves the people the station actually exists for.

---

## 1. Problem Statement

Community media producers make the program and then face a second, unpaid job: cutting clips, writing descriptions, resizing for three aspect ratios, drafting the newsletter blurb, and posting everywhere. Most don't — so programs air once, land in a VOD graveyard, and the station's reach stays a fraction of its output. The gap between "we made it" and "anyone saw it" is pure tedious admin, which the project's own mission statement identifies as exactly the thing to automate so volunteers can focus on action.

## 2. Goals

1. **Kit latency:** a complete publish kit ready ≤30 minutes after a program ends (or upload completes).
2. **Producer effort:** ≤10 minutes of human time from kit-ready to published (review, tweak, export).
3. **Adoption:** ≥60% of BIG's active producers use Publisher for at least one program within 90 days.
4. **Reach:** measurable lift in clips published per program week-over-week (baseline ≈ near zero; target ≥3 clips/program).
5. Quietly turn the station into a neighborhood wire service: program-derived content flowing to newsletter and social on a weekly rhythm.

## 3. Non-Goals

- **Not an editor.** Trims and reorders happen in the review queue; real editing stays in Resolve/Highlighter. (Scope discipline; the suite already has editing surfaces.)
- **No auto-posting in v1.** Nothing publishes without a human clicking approve; v1 exports bundles rather than holding platform credentials. (Trust, safety, and one less OAuth surface to maintain solo.)
- **No engagement-bait optimization.** Titles and clips optimize for accuracy and accessibility, not outrage. House style is a config, not a growth hack.
- **Not a scheduler/CMS.** Integrations hand off to existing tools (YouTube, newsletter platform); Publisher doesn't become the station's system of record.

## 4. Users & User Stories

- As a **volunteer producer**, I want clips, titles, and descriptions drafted for me the moment my program ends so that publishing takes minutes, not an evening I don't have.
- As **station staff**, I want a weekly newsletter section assembled from everything published this week so that the newsletter writes its first draft itself.
- As a **producer**, I want vertical cuts with burned-in captions so that my program's best moment works on phones without sound.
- As **station staff**, I want a brand kit (logo, colors, lower-thirds, voice presets) applied to every export so that everything leaving the building looks like us.
- As a **producer with a series**, I want Publisher to remember my show's tone and format so that episode 12's kit sounds like episodes 1–11.
- *Edge cases:* programs with music/performance (rights-sensitive — flag, don't clip, surface a warning); very short programs (skip clip candidates below a threshold, still generate copy); poor audio (low ASR confidence flags the kit as "review carefully"); a producer rejects all clip candidates (manual in/out picker as fallback).

## 5. Requirements

### P0 — the kit

1. **Inputs:** file upload, Highlighter link, or a "program ended" webhook from the live workflow. Anything Captioner has already transcribed skips ASR.
2. **Moment detection → 3–5 clip candidates** (reusing Highlighter's detection: topic shifts, applause/reaction, quotable density), each rendered in 9:16, 1:1, and 16:9 with burned captions (Captioner data) and brand-kit lower-thirds.
3. **Copy generation:** title options + platform-appropriate descriptions (including accessible alt text), chapter markers, a newsletter blurb in the station's template, and 2–3 social post drafts per platform voice. Voice presets: station-formal, casual, series-specific (learned from prior approved kits).
4. **Thumbnail candidates:** frame extraction + title overlay in brand style.
5. **Review queue UI:** kit as a single screen — pick clips (with light trim), edit any copy inline, regenerate any element with an instruction ("shorter, funnier"), approve.
6. **Export bundle:** ZIP (videos, thumbnails, copy as .txt/.md, transcript page) + per-field copy buttons. *Acceptance:* Given an approved kit, When the producer exports, Then every asset is correctly named, branded, and platform-sized with no manual file wrangling.
7. **Brand kit config, per station:** logo, palette, fonts, lower-third templates, voice presets — config-driven in the Driftwood/Lookout pattern, which is what makes multi-tenancy later a config problem instead of a rewrite.
8. **Beta badge + Driftwood feedback board.**

### P1 — the handoffs

9. **Direct integrations, still human-triggered:** publish to YouTube (API) with chapters and captions attached; push blurb to the newsletter platform; copy-to-clipboard deep links for social. One-click, post-approval.
10. **Weekly digest assembly:** everything approved this week → a drafted newsletter section and a "this week at the station" social thread.
11. **Send to the Record:** one-click submission of the full program to Community Memory (its submissions API), closing the loop between publishing and the corpus.
12. **Audiogram export** (waveform + captions) for radio/podcast-adjacent producers.

### P2 — the network

13. Multi-tenant operation under In-a-Box (per-station brand kits, isolated queues).
14. Series intelligence: per-show style memory, recurring segment detection.
15. Scheduling handoff (Buffer-class integration) if stations ask; not before.

## 6. Architecture Notes

Thin by design: FastAPI orchestrator on Cloud Run; render jobs (ffmpeg) as Cloud Run Jobs; Claude for copy and clip-candidate ranking; reuse Captioner's ASR store and Highlighter's detection service rather than duplicating either (if Highlighter's detection isn't yet a callable service, extracting it is the one real engineering task in here — budget for it). Postgres-or-Firestore follows whatever Memory decides; Publisher's data model is simple enough not to care. Containerized and config-driven for the box.

## 7. Success Metrics

**Leading:** kit-ready latency ≤30 min (p90); producer time-to-publish ≤10 min (measured in-app); % of kit elements accepted without edit (copy quality proxy); weekly active producers.
**Lagging:** clips published per program; newsletter assembly time (staff-reported, before/after); VOD → social referral traffic; producer retention (do they come back for episode 2); station adoption via In-a-Box.

## 8. Phasing

- **Phase 1 (~4–5 wks):** inputs, clip candidates + renders, copy generation, review queue, export bundle, brand kit config. *The kit exists.*
- **Phase 2 (~3 wks):** YouTube + newsletter handoffs, weekly digest, Send to the Record.
- **Phase 3:** audiograms, series memory, multi-tenant under the box.

## 9. Open Questions

- **(Eng, blocking Phase 1 estimate):** is Highlighter's moment detection extractable as a service today, or is it entangled with its UI? Answer determines whether Phase 1 is 4 weeks or 6.
- **(Staff/policy, non-blocking):** music-rights handling for performance programs — flag-only, or a hard no-clip rule? Station policy call.
- **(Design, non-blocking):** how much series voice-learning is real vs. a preset picker in v1? Ship the picker; instrument demand.
- **(Product, non-blocking):** newsletter platform at BIG (Mailchimp? Buttondown?) — pick the first integration from what's actually in use.
