# Lane C handoff — Interpreter (+ Narrator next)

Kept current at every push, four sections, per PARALLEL.md.

## Landed

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

- **Narrator wave 2**: shots (czcore/shots.py) + dialogue-gap map from
  Scribe word timings → gap-fitted DCMP-style descriptions through the
  guarded key (vision) → `czcore/tts.py` on sherpa-onnx → ducked mix →
  review timeline. Meeting-graphics wedge is P0 of the wave.
- Interpreter follow-ons, small: corrections flowing into glossary
  suggestions; per-body language defaults; VOD re-pass button copy.
- **Known beta wart, named on purpose:** the N| protocol occasionally
  drifts one line inside a chunk (a cue carries its neighbor's
  translation) — visible mostly in zh and Simple English, whose higher
  kept-English counts (609/714 of 4,814) come from the model merging
  short lines. The per-line fallback marking + review queue is the
  beta answer; a wave-2+ candidate is a cheap alignment-check pass or
  smaller chunks for those two targets.

## Asks (A-owned files; exact and minimal)

1. **pyproject.toml** — add `"interpreter"` to `[tool.setuptools]
   packages` and `interpreter = ["glossaries/*.json"]` under
   `[tool.setuptools.package-data]`. Dev checkouts run fine without it
   (`python -m suite` puts the repo root on sys.path), but an installed
   or frozen suite won't import the package until this lands — please
   pair it with the merge that takes server.py's import.
   (`narrator` + `interpreter-cli`/`narrator-cli` scripts can wait for
   wave 2; I'll ask again with the files in hand.)
2. **Nothing else.** czcore/models.py wasn't needed this wave (no model
   downloads — the engine is the guarded key). If wave 2's TTS voice
   wants a store entry, that ask comes with wave 2.

## Changelog fragments (house voice, for A to fold)

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
