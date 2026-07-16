# control-z apps — changelog

## unreleased

### site (interactive redesign) — 2026-07-16
- Rebuilt on the Hush site's actual component vocabulary (studied
  `Hush-OpenNR/site/index.template.html`): Space Grotesk/DM Sans, mono topline,
  amber-period hero, `.pcard` pair cards, `.feat` chips, dark `.ntree` with
  animated wire dots + click/keyboard node selection, `.wipe` before/after
  slider, grain-canvas `.study` bands, auto-cycle-until-click tabs, scroll-
  animated chart bars, numbered install steps, tipcards. Assets baked base64.
- Homepage: live Hush wipe in the hero (real footage); the suite as a clickable
  Resolve-style node tree in true pipeline order (restore→edit→sound→color→
  deliver, Speak last in color); audience tabs auto-cycle and relight the tree;
  Hush×Speak pair cards; grain-band covenant; "money undone" animated chart.
- Per-tool interactive demos, all real data or real math: Hush + Rise wipe
  sliders (actual outputs), Pivot solver playground (the shipping controller
  ported to JS — drag the subject), Scribe paper-edit (its own diarized
  transcript; clicks emit a real CMX3600 EDL), Clear WebAudio room (synthesized
  hum/room/voice with de-hum, isolate mix-back, and "listen to what's removed"),
  Depth probe + depth-shaped fog (real engine data), Stencil confidence-strip
  QC loop, Speak mini node-tree. All verified in-browser.

### site — 2026-07-16
- control-z.org rebuilt as the suite site per specs/07: Jinja2 bake to
  `site/docs/`, data-driven from `content/tools.yaml`. Homepage pipeline map
  (lit/breathing nodes, audience filter chips), tool-page template (verbline,
  replaces strip, quick start, model card, honest limitations), roadmap
  (proposed tools live ONLY there), mission/stations/toolbox pages.
  Not yet deployed: CNAME move + Hush-OpenNR/docs redirects happen at launch.

### stencil 0.1.0.dev0 — 2026-07-16
- SAM 2.1 video propagation (torch/MPS), prompt-file CLI, matte post chain
  (temporal majority, grow/feather/despeckle — golden-tested), luma +
  ProRes 4444 alpha exports, per-frame confidence with low-confidence frame
  report (the covenant surface). Verified on 4K footage (~2 fps propagation
  on M1 Max at 720p analysis). Deferred: click UI (v0.2), ONNX diet (v0.3).

### scribe 0.1.0.dev0 — 2026-07-16
- faster-whisper transcription (word timestamps, VAD), sherpa-onnx
  diarization (verified: 2-voice test separated perfectly), SRT/VTT with
  broadcast/social caption presets, TXT, marker EDL (speaker-colored,
  free-Resolve importable), CMX3600 selects EDL from pull lists. NDF
  timecode math golden-tested (23.976 drift documented). Deferred: editor
  UI (the v0.2 centerpiece), FCPXML.

### clear 0.1.0.dev0 — 2026-07-16
- De-hum (auto 50/60 Hz detect + harmonic notches, >20 dB kill golden-tested),
  de-click (second-difference detector — IIR ringing bug found and fixed;
  rarity guard so speech never counts as clicks), DF3 voice isolation via the
  official deep-filter binary (PyPI package is unmaintained — learned the hard
  way), room tone (random-phase PSD resynthesis, loop-safe), loudness
  normalize (BS.1770, refuses to hide peak conflicts), residual export
  ("listen to what was removed"). Deferred: UI, video remux, Demucs deep
  mode, nih-plug VST3.

### rise 0.1.0.dev0 — 2026-07-16
- Real-ESRGAN x4 converted from official BSD-3 weights to our pinned ONNX
  (rise.convert), tiled inference with seam-free overlap blending
  (golden-tested vs whole-frame), beats-bicubic golden test, honest lanczos
  fallback, CLI with interlace guard (refuses combed sources) and flow-gated
  temporal stabilization. Engine live inside Pivot's --enhance.

### depth 0.1.0.dev0 — 2026-07-16
- MiDaS-small ONNX backend (MIT) behind a model-agnostic engine (VDA-Small
  planned), temporal EMA with shot-boundary resets, per-shot robust
  normalization, He-et-al guided-filter edge-aware upsampling, 10-bit gray
  ProRes matte export, false-color previews, five-template Fusion pack
  (fog / rack focus / depth grade / parallax / haze light — NEEDS paste-test
  in Resolve before release). Verified on 4K footage.

### pivot 0.2.0.dev0 — 2026-07-16
- Web UI (czcore.appshell: FastAPI + local page): open clip, analyze with
  progress, scrub preview with crop overlay + subject dot, path-trace sparkline
  (targets vs solved path), per-shot mode overrides (re-solve in place),
  render + Fusion export from the page. Verified end-to-end in a browser.
- Fusion `.setting` export: animated Crop with one keyframe per frame
  (czcore.exports.fusion_setting) — the free-Resolve keyframe roundtrip.
  NEEDS a paste-test in Resolve before release.
- YOLOX-s person detection (Apache-2.0, hash-pinned), lazy "auto" mode: runs
  only on frames with no face; per-shot subject falls back face → person.
- rise.engine seed: frozen upscale API, tiled ONNX runner ready, honest
  `lanczos` fallback backend (labeled, never claims synthesis). `--enhance`
  wired into render + UI.
- Sidecar v1 now stores raw targets per aspect (enables instant re-solve).

### pivot 0.1.0.dev0 — 2026-07-16
- Path solver (punch/follow, deadzone+hysteresis, lookahead anticipation,
  jerk-limited motion; overshoot pinned at ≤4·a_max by golden tests) + presets
  (calm/standard/attentive).
- Shot detection (adaptive luma-diff, czcore.shots), greedy face tracker
  (YuNet, MIT, hash-pinned auto-download), per-shot subject selection.
- Renderer: frame-accurate (EOF flush handled), native-res crops (no silent
  upscale), audio stream-copy or honest skip, h264/hevc/prores.
- CLI: analyze / render / auto with per-shot QC report; sidecar JSON v1.
- Verified end-to-end on 4K ProRes footage (659/659 frames). Known v0.1 limits:
  faces-only detection (subjects lost when the face is undetectable — persons
  model lands in v0.2), no y-axis eyeline offset yet, no Fusion export yet.

### czcore 0.1.0.dev0 — 2026-07-16
- shots (pure cut detector + PyAV diffs), media probe parser, model store with
  sha256 pinning + license cards. 51 tests green (stdlib-only run).
