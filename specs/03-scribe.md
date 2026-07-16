# Scribe — transcription, captions, text-based cutting

**"Scribe writes it all down."** Local Whisper-class transcription with speakers, a real
transcript editor, caption export — and the paper-edit superpower: select text, get a
cut timeline back into free Resolve. Replaces Studio Speech-to-Text and the Descript/
Rev/Simon Says subscriptions. Accent: ink `#52678C`.

**Users:** everyone — the suite's widest tool. Stations captioning for access
requirements; journalists pulling quotes from pressers; documentary paper edits.
(community-captioner remains the *live* sibling; Scribe is post. Shared brand, shared
future models.)

## Covenant hooks

- **Shows its work:** word-level confidence shading in the editor (low-confidence words
  are visibly tinted — you proof *those*, not everything); diarization uncertainty marked
  at speaker turns; the export dialog states exactly what timecode math it wrote.
- **Honest limitations:** accuracy on crosstalk/accented speech below human captioners;
  diarization confuses similar voices in rooms with bleed; no live captioning (that's
  community-captioner); translation is Babel's job later, not hidden in here half-done.

## Stack (all local, all permissive — see 00 policy table)

- ASR: **faster-whisper** (CTranslate2, int8 default) — `large-v3-turbo` default, model
  picker down to `base` for old machines. Word timestamps on.
- VAD: Silero — segments long files, kills hallucinated silence text.
- Diarization: sherpa-onnx pipeline (pyannote segmentation-3.0 MIT weights self-mirrored
  + 3D-Speaker embeddings) → clustering; names editable ("Speaker 2" → "Chair Vitolo"),
  persisted per project and reusable across episodes of the same show (embedding match —
  small, honest: "suggested: Chair Vitolo (87%)").
- Timecode: honor embedded source TC (probe via czcore.media); all exports in source TC.

## The editor (this tool is 70% UI — budget accordingly)

- Transcript as the primary surface: click a word → playhead jumps; play → karaoke
  highlight. Edit text inline (fixes propagate to captions); merge/split segments; speaker
  relabel by drag or keystroke. Search with hit-list scrubbing.
- **Selects workflow:** highlight text spans → they stack in a *pull list* (reorderable,
  each with source TC in/out, padded handles setting). This is the paper edit.
- Multi-file project bin (an interview series is one project; search spans all files).

## Exports (czcore.exports — the roundtrip is the product)

| Export | Format | Free-Resolve path |
|---|---|---|
| Captions | SRT / VTT (line-length + CPS presets: broadcast 32×2, social) | Timeline → Import Subtitle |
| Transcript | TXT / DOCX-friendly MD / JSON (words+speakers+conf) | — |
| **Selects reel** | CMX3600 EDL + FCPXML 1.10 (cut list from pull list, handles included) | Timeline import → conform from media pool |
| Speaker/segment markers | **marker EDL** (Resolve's Timeline → Import → Timeline Markers From EDL — works in free) | markers land on the timeline, colored per speaker |
| Burn-in | rendered open-caption pass (ffmpeg subtitles filter) | for socials/YouTube-ready |

## CLI

```
scribe-cli transcribe *.mov --model large-v3-turbo --diarize -o project.scribe/
scribe-cli export project.scribe --srt --markers --selects selects.json --edl -o exports/
```

## Milestones

- **v0.1 (CLI):** transcribe queue + diarize + SRT/VTT/JSON/TXT + marker EDL. Immediately
  useful to stations before any UI exists.
- **v0.2:** editor UI (single file): word-click nav, inline edit, speaker rename, caption
  presets, confidence shading.
- **v0.3:** projects/multi-file, pull list + EDL/FCPXML selects export, search everywhere.
- **v1.0:** speaker suggestion across episodes, polish, builds, site page, release.
  (Minutes later builds on Scribe's project format — keep the JSON schema versioned.)

## Risks

Diarization stack is the flakiest piece — isolate behind `scribe.diarize()` so the
implementation can swap without touching the editor; ship v0.1 even if diarization lags
a release. FCPXML conform quirks across Resolve versions → EDL is the tested-first path
(dumb and bulletproof), FCPXML the convenience path.
