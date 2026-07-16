# control-z apps — program overview

Six tools greenlit, built in this order: **Pivot → Stencil → Scribe → Clear → Rise → Depth.**
Companion doc: `07-site-redesign.md` (the control-z.org rebrand, buildable in parallel).
Brand/strategy context: `~/Hush/control-z-suite-spec.md`.

## The one dependency wrinkle (decided up front)

Pivot punches into footage; a 9:16 crop from HD source is ~608×1080 — below delivery res.
So **Rise is built engine-first**: a tiny library (`rise_engine`) with a stable API lives in the
monorepo from day one. Pivot v0.2 ships "Enhance punch-ins" by calling it (single-image
Real-ESRGAN, tiled). Rise-the-app (tool #5) later wraps the *matured* engine (temporal
consistency, face restore, batch UI). Nothing is built twice; Pivot never blocks on Rise.

```
rise_engine.upscale(frames: Iterable[ndarray], scale: 2|4, model="realesrgan-x4",
                    device="auto", tile=512, on_progress=cb) -> Iterable[ndarray]
```

## Shared architecture (every standalone tool)

One **app pattern**, learned from community-captioner and kept for the whole suite:

- **Python 3.11+ backend** (FastAPI + websocket job events) serving a **local web UI** at
  `127.0.0.1:<port>`, opened in a `pywebview` window (double-click app) or any browser
  (`--serve` for lab/headless station use). No cloud, no accounts, no telemetry — covenant.
- **UI:** hand-written HTML/CSS/JS using the control-z design tokens (cream paper, green,
  per-tool accent — see 07). No JS framework, no build chain. Canvas overlays for preview.
- **Preview:** server decodes (PyAV), serves JPEG frames on demand + a scrub strip; overlays
  (crop paths, mattes, confidence) drawn client-side from JSON. No in-browser codec fights.
- **ML runtime:** ONNX Runtime by default (CoreML EP on macOS, DirectML/CUDA on Windows,
  CPU fallback). PyTorch allowed only where ONNX is impractical (Stencil's SAM2 v0.1) and
  noted as a size cost. Whisper via faster-whisper (CTranslate2).
- **Media IO:** bundled **LGPL ffmpeg** build; H.264/HEVC via hardware encoders
  (VideoToolbox / MF / NVENC — avoids GPL x264), ProRes via `prores_ks`, mattes as
  ProRes 4444 / 16-bit formats. PyAV for frame-accurate decode loops.
- **Models:** shared store at `~/Library/Application Support/control-z/models`
  (`%APPDATA%\control-z\models` on Windows). First-run downloader with pinned SHA-256,
  resumable, and a **model card shown before download** (license, source, purpose) —
  that's the covenant's transparency applied to weights.
- **Packaging:** PyInstaller onedir per app; macOS signed (Developer ID 6M536MV7GT) and
  notarized (fix the notarization debt before Pivot 1.0 — trust is the brand). Windows zip
  + installer bat, Hush-style. CLI entry point per tool (`pivot-cli`, …) — stations script things.

## Repo layout (monorepo: `/Users/stephen/control-z`)

```
control-z/
  specs/            00–07 (this folder)
  core/             czcore — shared package (app shell, media, shots, exports, model store)
  pivot/ stencil/ scribe/ clear/ rise/ depth/    one package per tool
  site/             control-z.org (see 07) — may graduate to its own repo at launch
```

One repo, one venv, one CI, individual releases (`pivot-v0.1.0` tags). OFX tools (Hush,
Speak) stay in their own repos — different toolchain. If the GitHub org lands later, this
repo transfers cleanly (transfers redirect; renames don't — learned on Hush-OpenNR).

### czcore contents (build only what Pivot needs, grow per tool)

- `media.py` — probe (streams/fps/duration via ffprobe JSON), FrameSource (PyAV decode,
  seek, downsampled analysis stream), writers (encode presets).
- `shots.py` — shot boundary detection (luma/edge-delta detector, PySceneDetect-compatible
  thresholds); every temporal tool respects cut boundaries.
- `models.py` — model registry/downloader/hasher + license cards.
- `exports/` — srt.py, edl.py (CMX3600 + marker EDL), fcpxml.py, fusion_setting.py
  (keyframed node generator), json sidecars. Shared because Scribe/Pivot/Stencil all
  hand things back to free Resolve through files.
- `appshell/` — FastAPI factory, job queue with progress events, pywebview launcher,
  settings, ui/ static tokens.

## Model & license policy (enforced, per tool)

Permissive weights only (MIT/Apache/BSD). **No CC-BY-NC checkpoints, no gated downloads.**
The chosen stack, verified at spec time — re-verify at build time:

| Model | Used by | License |
|---|---|---|
| YuNet face det (OpenCV Zoo) | Pivot | MIT |
| YOLOX-s person det | Pivot v0.2 | Apache-2.0 |
| U²-Net-p saliency | Pivot v0.2 (fallback) | Apache-2.0 |
| SAM 2.1 (hiera-S / B+) | Stencil | Apache-2.0 |
| faster-whisper / Whisper large-v3-turbo | Scribe | MIT |
| Silero VAD | Scribe, Clear | MIT |
| Diarization: sherpa-onnx pipeline (pyannote seg-3.0 MIT weights, self-mirrored + 3D-Speaker embeddings Apache) | Scribe | MIT/Apache |
| DeepFilterNet 3 | Clear | MIT/Apache dual |
| Demucs (htdemucs) | Clear (heavy separation mode) | MIT |
| Real-ESRGAN x2/x4 | rise_engine | BSD-3 |
| GFPGAN 1.4 (optional face restore) | Rise | Apache-2.0 |
| Video Depth Anything **Small** | Depth | Apache-2.0 (larger DA2 checkpoints are CC-BY-NC — **do not ship**) |

Explicitly rejected: Ultralytics YOLOv8 (AGPL), CodeFormer (NC), RVM (GPL), larger
Depth-Anything checkpoints (NC), anything requiring a HuggingFace login at runtime.

## Testing culture (ported from Hush — non-negotiable)

- Algorithms validated **outside the app**: synthetic scenes with known ground truth,
  golden numbers pinned in tests, re-pins require a CHANGELOG entry.
- A `<tool>_cli` real-clip harness per tool (like `hush_cli`) so changes are scored on
  reference footage before release. Reference clips stay out of the repo.
- Every tool ships its "shows its work" surface, and its README keeps an
  **Honest limitations** section naming what Studio/the paid tool still does better.

## Definition of done, per tool

Spec'd → core algorithm + tests green → CLI works on real footage → UI → mac build signed
→ Windows build → tool page on control-z.org with before/after + model card + limitations
→ release tag + announcement. A tool is "shipped" on the site only past that whole gate.
