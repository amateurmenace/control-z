# Lane C handoff — Interpreter + Narrator

Kept current at every push, four sections, per PARALLEL.md.

## Landed

**Community Narrator, wave 2 — the VOD AD pipeline, end to end.**

- **Engines.** `narrator/gaps.py`: speech intervals merged across
  breaths, bracket-only markers ([Music], (applause)) counted as air —
  they are exactly where narration lives; gaps padded 0.25s each edge,
  2.6-words/sec fit budgets; the graphics wedge found by stillness
  (shots ≥12s with near-zero internal motion = slides). `plan_cues`
  marries gaps and graphics; wall-to-wall programs (specs/15's own edge
  case) fall back to shot-anchored transcript-only cues — never a dead
  end, never a mix that talks over the meeting. `narrator/describe.py`:
  vision on the guarded key (config read from czcore.llm, never edited
  — both providers take base64 JPEG), DCMP enforced in the prompt AND
  checked in a pure lint (camera-talk / interprets / past-tense /
  over-budget). `czcore/tts.py` (lane C's second czcore addition, per
  the law): sherpa-onnx VITS voices discovered by shape under the
  shared models dir; honest install sentence until the store carries a
  TTS entry. `narrator/mix.py`: the ducked mix as one tested
  filtergraph — narration keys a sidechain compressor; three outputs
  in one ffmpeg pass through czcore.ffrun.
- **Page + routes** (`suite/tools/narrator.py`, `static/js/narrator.js`):
  three moves on one queue — ① map (shots + pauses + wedge), ② draft
  (per-cue vision, czProgress, drafts survive cancel), ③ render (TTS
  per accepted cue, cached by text hash → ducked mix). The review
  timeline is the product: graphics ride the top lane, pauses the
  bottom; every cue is a card with its budget, lint chips, accept /
  edit / regenerate; "Accept all clean" takes lint-free drafts only —
  flagged ones wait for human eyes. "Write transcript" lands the
  descriptions VTT with no voice at all (the extended-mode contract).
  Outputs: mixed program (.mp4, video stream untouched), mixed audio
  (.m4a), narration track (.wav, program-length), descriptions VTT
  with provenance in the file. Nothing unaccepted ever reaches a track.
- **Proven on real footage** (the 19s zoo clip — the only local video
  with a transcript this side of a full-meeting fetch): the transcript's
  own "(baaaaaaaaaaahhh!!)" elephant trumpet counted as air and made a
  real 2.0s gap; gpt-4o-mini drafted "Two elephants behind a barrier."
  (5 words, budget 5, lint-clean); accepted via accept-all-clean;
  vits-ljs spoke it; the mix landed all three outputs — measured: the
  narration wav is digital silence (−91 dB) until 14.5s and carries the
  line exactly in the cue window; the .mp4 muxes h264 untouched + AAC
  mix. Slots wired (server.py modelstore↔ofx, tag after interpreter.js,
  narrator ready flip) — the "seen and heard" wire reads 3 of 3.
- **Tests: 25** narrator tests (gap math incl. bracket-air and the
  wall-to-wall fallback, budgets, stillness, plan, lint, VTT gate, mix
  graph, voice discovery) — suite total 353, green in the lane venv.

**Community Interpreter, wave 1 — end to end** (previous push). Any
meeting Highlighter has read becomes timed caption tracks in the seven
panel languages (Español, Simple English, 中文, Português, Kreyòl,
Tiếng Việt, Русский).

**Community Interpreter, wave 1 — end to end.** Any meeting Highlighter
has read becomes timed caption tracks in the seven panel languages
(Español, Simple English, 中文, Português, Kreyòl, Tiếng Việt, Русский).

- **Engine: `czcore/mt.py`** (lane C's one czcore addition, per the law).
  Rolling caption/ASR fragments coalesce into sentence-shaped cues
  (translating half-sentences is how names get mangled — and it cuts
  spend ~40%); cues translate in 40-line numbered chunks over the
  guarded key (Highlighter's N| protocol, generalized); per-town
  glossary constraints ride every pass; a dropped line falls back to
  English and is marked, never silent. Simple English is the same
  pipeline with a plain-language instruction — first-class, as specced.
  `mt.available()` reports the engine honestly; no key → a sentence,
  not a pretend. A local MT runtime has a slot here the day one fits
  the dep set (NLLB-class wants sentencepiece, which we don't ship —
  see Asks).
- **Glossaries: `interpreter/glossary.py` + `glossaries/brookline.json`.**
  Versioned per town; seed ships with 26 do-not-translate Brookline
  names and 10 civic terms rendered in all seven languages — every one
  marked `suggested`, because nobody has vetted them yet; only a human
  flips `vetted` in the UI. Working copies live in app support and win
  over the seed; saves bump the version.
- **Tracks land beside the meeting** (`meeting.translated.<code>.srt/
  .vtt/.json` + `*.interpreter.json` kit sidecar) — the `translated.`
  infix keeps `en` winning Highlighter's first-caption-file-sorted
  fallback; that invariant is pinned in a test.
- **Page** (`suite/tools/interpreter.py` + `static/js/interpreter.js`):
  library shelf of read meetings, language chips with per-track state,
  one queue job across selected languages (czProgress, cooperative
  cancel, per-language caching), provenance banner on every track
  ("AI translation — beta · model · glossary town vN · review status ·
  n lines kept English"), the VTT carries the same note IN the file,
  cue rail with source-English under every line, one-tap ⚑ flag per
  line feeding the review queue, corrections apply back and rewrite
  the track in place, per-language SRT/VTT export links + Reveal,
  native `<track>` elements on a `<video>` player when the full
  recording is local (my own `/api/interpreter/media` + `/track`
  routes serve them).
- **Review queue:** `review-queue.json` in app support, one open item
  per (meeting, language, line), read across meetings in the inspector;
  resolve with a correction patches the cue JSON and rewrites both
  track files with the provenance note updated to say
  "n reviewer-corrected lines".
- **Proven on the June 18 School Committee session** (7,790 caption
  segments → 4,814 cues, 5h04m): the full seven-language kit written
  through the page and the queue on the configured key (gpt-4o-mini).
  Per-language honesty, straight from the kit sidecar: es 62 lines
  kept English / 31 glossary misses (1 reviewer-corrected, through the
  queue UI), pt 75/63, ru 82/186, ht 108/66, vi 165/84, zh 609/168,
  simple 714/118. Glossary renders verified landing in es
  ("Comité Escolar (School Committee)") and zh (学校委员会（School
  Committee）). The flag→queue→correct loop was exercised end to end:
  the corrected line rewrote the .srt and .vtt and the VTT NOTE now
  reads "1 reviewer-corrected lines". In-player tracks verified on a
  clip with a local recording (native caption menu, es showing).
- **Tests:** 34 in `tests/test_interpreter_mt.py` +
  `tests/test_interpreter_tracks.py` — coalesce/chunk math, N| parse +
  fallback honesty, glossary prompt/check/save semantics, srt/vtt
  golden output, sidecar shapes, the en-sort invariant, queue
  flag/resolve. Full suite green in the lane venv.
- Single-line slots wired per the law: server.py import/register
  (indexer↔kb slot), index.html tag after publisher.js with `?v={{v}}`,
  core.js `interpreter` ready flip only. Home's "seen and heard" wire
  shows 2 of 3 live with no home edits — it worked exactly as A said.

## Next (after A merges)

- **A full-meeting AD proof.** The pipeline is proven on the zoo clip;
  the library holds no full meeting video yet. First fetched full
  recording (Grabber → Highlighter "Download full video") becomes the
  real target: openings, votes and slide stretches are where the gap
  map and the graphics wedge earn their keep. The ≤15-min-per-hour
  review target gets measured there, honestly.
- Interpreter follow-ons, small: corrections flowing into glossary
  suggestions; per-body language defaults; VOD re-pass button copy.
- Narrator P1s when the wave comes: extended-mode web playback (pause
  video during long descriptions), backfill nominations, per-station
  voice choice.
- **Known beta wart, named on purpose:** the N| protocol occasionally
  drifts one line inside a chunk (a cue carries its neighbor's
  translation) — visible mostly in zh and Simple English, whose higher
  kept-English counts (609/714 of 4,814) come from the model merging
  short lines. The per-line fallback marking + review queue is the
  beta answer; a wave-2+ candidate is a cheap alignment-check pass or
  smaller chunks for those two targets.

## Asks (A-owned files; exact and minimal)

1. **pyproject.toml** — add `"interpreter"` AND `"narrator"` to
   `[tool.setuptools] packages`, plus
   `interpreter = ["glossaries/*.json"]` under
   `[tool.setuptools.package-data]`. Dev checkouts run fine without it
   (`python -m suite` puts the repo root on sys.path), but an installed
   or frozen suite won't import either package until this lands —
   please pair it with the merge that takes server.py's imports.
   (CLI entries can wait; neither tool ships one yet.)
2. **czcore/models.py — a TTS voice entry, when you're ready.** The
   store's REGISTRY is a closed dict, so Narrator ships the honest
   manual sentence: download `vits-ljs` (public-domain LJSpeech corpus)
   from k2-fsa/sherpa-onnx releases, tag `tts-models`, untar into the
   models folder — czcore/tts.py finds any VITS voice by shape. A
   registry entry would make it one click; note the archive is a
   tarball (the `archive_member` mechanism fits) and note for the
   license card: piper-family voices that need `espeak-ng-data` pull in
   GPL-licensed data files — `vits-ljs` was chosen partly because its
   lexicon needs none. Your call on which voice earns the card.
3. **czcore/llm.py — vision, someday.** Narrator builds its own
   image-bearing request from `llm.get_config()` (read-only) because
   `complete()` is text-only. If A ever wants one door for multimodal,
   narrator/describe.py's request shape is ready to move in; until
   then it stays lane-C-local and guarded the same way.

## Changelog fragments (house voice, for A to fold)

- **Community Narrator ships (beta) — the picture, spoken.** Audio
  description for community TV, a thing public access has essentially
  never had: open a read meeting with its recording and the pass runs
  in three moves — the pauses and the slides mapped (a [Music] or an
  applause marker counts as air, because it is; a shot that holds
  still is a slide, and slides read aloud are the point), each moment
  drafted by vision on your own key in DCMP style with a lint that
  names camera-talk, interpretation and past tense instead of trusting
  the prompt, and every draft waiting on a human accept — nothing
  unaccepted reaches a track. The render speaks each approved line in
  a local voice (sherpa-onnx; the page names the exact voice to
  download and finds it by itself), ducks the program under the
  narration with a sidechain compressor, and lands four outputs:
  the mixed program, the mixed audio, a program-length narration
  track, and a descriptions transcript that always carries every
  approved description — wall-to-wall programs get the transcript and
  the extended mode instead of a mix that talks over the meeting,
  never a silent failure. Provenance rides the page and the files
  alike: vision model, voice, review status.
- **The wing speaks with one engine each.** `czcore/tts.py` joins
  `czcore/mt.py` in the middle of the table — translation and speech
  for whatever the wing carries across next.

- **Community Interpreter ships (beta) — the meeting, carried across.**
  Open anything Highlighter has read and pick from the seven panel
  languages — Español, Simple English (plain language, first-class),
  中文, Português, Kreyòl, Tiếng Việt, Русский. One queue job coalesces
  the rolling captions into sentence-shaped cues, translates them
  chunked on your own key with the town's glossary riding every pass
  (do-not-translate names, vetted civic terms — the Brookline seed
  ships honestly marked *suggested*), and lands timed .srt + .vtt
  beside the meeting. Provenance is UI: every track says its model,
  glossary version and review status on the page and inside the .vtt
  itself; lines the model dropped stay English and say so. Every line
  takes one tap to flag into the review queue; a reviewer's correction
  rewrites the track in place. With the full recording local, tracks
  ride the player's own caption menu. No key? The page says so in a
  sentence and still reads existing tracks.
- **The translation engine moved to the middle of the table.**
  `czcore/mt.py` — cue coalescing, chunked N|-protocol translation,
  glossary constraints — is czcore's now, grown from Highlighter's
  translate feature, for everything the wing will carry across next.
