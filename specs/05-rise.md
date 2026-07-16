# Rise — super-resolution

**"Rise restores the detail."** SD→HD/4K upscaling for archives and punch-in rescue —
Studio Super Scale / Topaz territory, local and free. Accent: gold `#C99A3A`.

**Two lives, by design (see 00):** `rise_engine` (library) ships early inside Pivot v0.2
for punch-in enhancement; **Rise the app** (this spec) graduates that engine for archives
and batch work. The engine API is frozen from day one so Pivot never breaks.

**Users:** stations upscaling tape-era masters for modern delivery; filmmakers rescuing
old projects; Pivot users punching in past native res.

## Covenant hooks

- **Shows its work — the detail heatmap.** A view showing *where* the model added energy
  (|out − bicubic(in)| heat overlay) plus an A/B wipe against honest bicubic — so you see
  what's reconstruction vs. what was already there. Invented detail is labeled as such:
  the report says "synthesized texture," not "recovered."
- **Honest limitations:** per-frame model + stabilization ≠ Topaz's temporal models on
  fast motion; faces can go uncanny (face restore is opt-in, previewed, defaulted off for
  journalism — an *ethics note in the UI*: synthesized faces are not evidence).

## Engine (`rise_engine`)

- Models: Real-ESRGAN x2/x4 (BSD-3) general + `-anime` variant, ONNX Runtime
  (CoreML/DirectML/CUDA EPs), tiled with overlap-blend (default 512 px tiles + 16 px
  feather) → bounded VRAM at any input size.
- **Temporal stabilization (app v0.2):** per-frame SR then flow-guided blend of the
  previous *output* toward the current (gated by warp error — Hush's render-boost idea,
  inverted for SR); kills the shimmer that makes per-frame SR unusable on video.
- Optional **GFPGAN 1.4** face restore pass (Apache), strength slider, off by default.
- API: see 00. Deterministic given (model, tile, seed-free); golden PSNR/SSIM tests on
  synthetic down-up pairs pin the engine per release.

## App

- Batch queue: drop files → per-file scale/model/codec → estimates (time, size, punch-in
  math for "I need 4K from this 1080 master").
- Preview: A/B wipe (source-bicubic vs Rise), detail heatmap toggle, 100%/200% loupe.
- Interlaced-source guard: detect telecine/interlacing (ffprobe + comb detection) and
  route through QTGMC-style deinterlace first or warn — SD archives are the whole user
  base, and feeding combed fields to SR is the #1 way to get garbage. (Full restoration
  chains stay Rewind's future job; Rise just refuses to make things worse silently.)
- Output: ProRes 422/4444, DNxHR, or hw H.264/HEVC; color/range metadata passed through
  untouched (601→709 tagging preserved and *reported*, never silently converted).

## CLI

```
rise-cli up in.mov --scale 2 --model realesrgan-x2 --stabilize --codec prores -o out.mov
rise-cli probe in.mov            # interlace/telecine + punch-in report
```

## Milestones

- **v0.1 (engine, ships inside Pivot v0.2):** ONNX Real-ESRGAN tiled stills path + golden
  tests. No app.
- **v0.2 (app CLI):** video loop + temporal stabilization + interlace guard + reports.
- **v0.3:** UI (queue, A/B wipe, heatmap), GFPGAN opt-in, presets (Tape→HD, HD→UHD,
  Punch-in rescue).
- **v1.0:** builds, site page with archive before/afters (BIG vault demo), release.

## Risks

Model provenance/quality drift across community ONNX exports → convert and pin our own
exports with hashes; shimmer on detailed motion (stabilization gate tuning — golden clips
in the real-clip harness); scope creep toward Rewind (deinterlace guard only, say no to
dropout repair here).
