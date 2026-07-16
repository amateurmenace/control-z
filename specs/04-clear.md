# Clear — dialogue rescue

**"Clear rescues the voice."** Voice isolation, de-hum, de-click, de-ess, and room-tone
matching — the RX-shaped hole in every community edit, and Studio's Voice Isolation,
local and free. Accent: teal `#4A8C7E`.

**Users:** every interview recorded in a real room. Stations (HVAC, mic hum, gym
reverb), journalists (street noise), filmmakers (location dialogue).

## Covenant hooks

- **Shows its work — "Listen to what was removed."** One button monitors the *residual*
  (input minus output), Hush's "Noise Removed" view translated to audio. If you hear
  words in the residual, you're over-processing — the tool teaches gain-staging honesty.
  Plus before/after spectrograms and a null-test readout (RMS of residual by band).
- **Honest limitations:** heavy isolation adds artifacts on music-under-voice (that's
  Split's separation job later); no real-time Fairlight insert until the VST3 lands
  (v1.x); RX's manual spectral repair (paint out a cough) is out of scope v1.

## Processing modules (chainable, each bypassable, order fixed)

1. **De-hum** — mains hum auto-detect (50/60 Hz + harmonics via Goertzel sweep), adaptive
   notch bank with harmonic tracking. Pure DSP, no model.
2. **De-click/crackle** — transient detect + AR-model interpolation (scipy). Pure DSP.
3. **Voice isolation** — DeepFilterNet 3 (48 kHz, real-time-class) with a *mix-back*
   slider (100% isolated → tasteful 60-70% default; full-wet is rarely right and the UI
   says so). **Deep mode:** Demucs htdemucs vocal/other separation for wrecked clips
   (slow, offline — labeled as such).
4. **De-ess** — split-band compressor keyed 5–9 kHz. Pure DSP.
5. **Room tone** — capture a noise/ambience profile from a marked region (or auto-find
   quietest 2 s), then **generate arbitrary lengths** of matching tone (shaped-noise
   resynthesis from Welch PSD with randomized phase, crossfade-looped). Fills cut-out
   gaps; exports a 30 s `roomtone.wav` for the editor's bin. Nobody gives this away.
6. **Loudness** — output normalize to target (−24 LKFS broadcast / −16 podcast / −14
   streaming presets) with true-peak ceiling; measurement readout doubles as a tiny
   preview of Level.

## App shape

- **v1: standalone batch + preview.** Drop WAV/AIFF or video files (audio extracted,
  processed, and remuxed back against the untouched video stream, or exported as WAV
  stems for Fairlight). A/B loop player with module toggles + residual monitor.
  Presets: Interview Room / Field / Podium PA / Archive Tape.
- **v1.x: VST3 “Clear Live”** — DeepFilterNet3 + de-hum in a Rust `nih-plug` VST3
  (MIT-compatible; JUCE rejected for GPL/commercial licensing), so Fairlight gets a
  real-time insert in free Resolve. The offline app stays the flagship (deep mode,
  room tone, batch).

## CLI

```
clear-cli process in.wav --preset interview --isolate 0.65 --dehum auto --loudness -24 -o out.wav
clear-cli roomtone in.wav --from 00:12.5 --len 30 -o tone.wav
clear-cli batch folder/ --preset field --remux -o cleaned/
```

## Milestones

- **v0.1 (CLI):** de-hum + de-click + DF3 isolation + loudness, WAV in/out, residual
  export (`--residual`), golden DSP tests (synthetic hum/clicks with known parameters
  must null to spec).
- **v0.2:** room tone module, video remux path, presets, deep mode (Demucs).
- **v0.3:** UI (A/B player, spectrograms, residual monitor, batch queue).
- **v1.0:** builds/signing, site page, release. **v1.x:** nih-plug VST3.

## Risks

DF3 artifacts on non-speech (define the tool as *dialogue* rescue, mix-back default);
sample-rate plumbing (process at 48 kHz, resample in/out, test with 44.1/96); remux A/V
sync (test with drop-frame and odd container offsets — golden ffprobe assertions).
