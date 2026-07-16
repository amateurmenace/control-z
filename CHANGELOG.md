# control-z apps — changelog

## unreleased

### suite 0.4.0.dev0 — suite services — 2026-07-16
- **Install OpenFX page** (specs/08 §5): detects Resolve and
  /Library/OFX/Plugins, reads installed Hush/Speak versions from their
  Info.plists, and checks the latest GitHub release on click — one GET to
  the public API, nothing phones home on its own; prerelease-only repos
  (Speak beta) resolve via the release list and wear a beta badge. Install
  downloads the release .pkg to ~/Downloads and opens the system installer
  (which owns the privileges — the plugins dir is root-owned and the page
  says so instead of pretending). One-click OFXPluginCacheV2.xml clear for
  the rescan gotcha; uninstall removes the bundle when the dir is writable
  and otherwise prints the exact sudo command. Verified against this
  machine's real state: Resolve found, Hush 3.3.0 → v3.7.0 update offered,
  Speak not-installed → v0.2.0 beta offered.
- **Models page**: the czcore registry with license + sha-256-pinned badges
  and true on-disk sizes, download (through the queue, hash-verified) and
  remove per model; whisper cache and diarization pair listed and
  removable; Stencil runtime status. Verified: yunet removed and
  re-downloaded with its hash checked.
- **Settings page**: every cache with its real size and a clear button
  (all regenerable — the page says nothing here can lose work), job-history
  clear (active jobs never touched — unit-tested), model store and app-data
  paths, about block.
- Queue page grew a "clear finished" button; czcore JobManager grew
  clear_finished().
- The rail has no coming-soon states left: v0.4 closes the milestone list
  short of v1.0 (packaging, signing, notarization, DMG).
- **v0.2, sound + words.** **Clear**: audio workspace (waveform + amber-on-ink
  spectrogram with before/after A/B), rescue chain from the CLI's own calls
  (de-hum auto-detect, de-click, DF3 isolation when the binary exists — honest
  hint when not, de-ess, loudness presets), video remux against the untouched
  stream, room-tone generator, and the covenant surfaces: a "what was removed"
  monitor chip playing the residual, loudness I/peak meters, and a residual
  by-band null test ("presence band loud = you're eating words"). Verified on
  synthesized degraded dialogue: found the injected 60 Hz hum + harmonics,
  repaired the clicks, presence band read −16.5 dB (quiet).
  **Scribe**: the transcript-first editor — word-click seeks, karaoke follows
  the audio clock with the caption overlaid on video (current word amber),
  low-confidence words tinted (proof those), inline segment edits saved to the
  sidecar, speaker rename everywhere, caption presets, SRT/VTT/TXT/marker-EDL
  exports, and the pull list → CMX3600 selects EDL in source TC. Diarization
  models fetched into the shared store; verified: two TTS voices separated
  perfectly, 23 s transcribed in 16 s (base), selects EDL honors embedded TC.
- **v0.3, the GPU pair.** **Depth**: false-color scrub (source/blend/depth),
  click-to-probe crosshair reading the local map, histogram with draggable
  in/out handles, stability meter, matte render (10-bit gray ProRes,
  edge-guided, temporal EMA with cut resets) through the queue, Fusion
  template pack writer. Honest note in the UI: scrub previews are per-frame;
  the render smooths. MiDaS-small fetched hash-verified on first use.
  **Stencil**: click-to-prompt (⌥-click excludes), SAM 2.1 propagation through
  the queue, matte tint + onion skin overlays, the confidence-strip QC loop
  (0.85 threshold line, low frames named), coverage %, post chain
  (grow/feather/despeckle/temporal majority) and luma / ProRes-4444-alpha
  exports. Runtime (torch + sam2) stays an honest optional — the page says
  exactly what to install when it's missing.
- New engine deps into the venv story: faster-whisper, sherpa-onnx, soundfile,
  scipy, pyloudnorm (+ torch/sam2 as Stencil's optional heavies).
- Suite rail: no coming-soon states left among the tools — Install OpenFX,
  Models, Settings remain v0.4.

### czcore.denoise — the Hush core, ported — 2026-07-16
- **Pivot and Rise now carry Hush's denoising**, because both make noise
  worse (punch-ins scale it up; SR models synthesize texture from it).
  `czcore/denoise.py` is a faithful vectorized port of Hush-OpenNR's
  `nr_core.h` reference: the noise estimator (fine + coarse |Laplacian| and
  |temporal diff| medians with Hush's calibration constants, 16-bin
  brightness gain curve), the hard-knee gated 3-frame temporal merge with
  Ghost Guard and per-neighbour exposure offsets, the two-scale residual
  re-measure, and the fine NLM band (bias-corrected, edge-aware Preserve
  Detail). Hush defaults throughout. Honestly NOT ported (still plugin-only):
  shift-search motion tracking, firefly zapper, Render Boost, Deep Clean,
  medium/coarse EQ bands, the refine texture stack — reports say
  "hush-core", never plain "Hush".
- Wiring: Rise cleans BEFORE scaling (suite checkbox default on; CLI
  `--denoise`; preview cleans the patch so the A/B compares scalers on what
  the render will feed them). Pivot cleans the crop before any scaling with
  the temporal neighbours cropped at the CURRENT frame's rect — the stack
  stays registered while the camera path moves (suite checkbox, default
  off). Both paths use a 1-frame lookahead and put the measured σ in the
  report.
- Verified: 9 golden tests (estimator accuracy, +12 dB static-trio PSNR,
  motion no-ghosting, edge survival, near-identity on clean, determinism);
  on the real SD test clip the cleaned ×2 output measures ~45% less luma
  noise (0.39% → 0.22%) and ~54% less chroma than the plain ×2. Cost:
  ~160 ms/frame SD, ~1.6 s/frame 1080p — roughly halves Rise throughput,
  named in the UI.
- Brand line updated everywhere: control-z is "free cleaning, prepping, and
  finishing tools for DaVinci Resolve" (app rails, tool docstrings, README,
  pyproject, site templates + rebake).

### suite 0.1.0.dev0 — 2026-07-16
- **The Suite desktop app lands** (specs/08): one FastAPI + WebSocket server
  over the existing engines, single-page UI (hand-written HTML/CSS/JS, no
  framework) in a pywebview window — `python -m suite`, `--serve` for a
  browser. Grade-room design per spec §6: ink/forest surfaces, cream text,
  amber for measurements only, per-tool accents, node-wire rail indicator.
- Shell: rail with honest coming-in-v0.x pages for the four tools not yet
  moved in, Home with Prep/Finish doors + recents, shared viewer (zoom/pan,
  A/B wipe, canvas overlays, JKL + arrows; nb_frames metadata treated as an
  estimate and clamped to the decodable truth), filmstrip, Easy/Studio
  inspector density remembered per tool, scope rack (histogram + waveform
  on every image tool).
- Jobs: czcore.appshell grew a persistent SQLite queue — FIFO worker,
  cooperative cancel, history survives restarts, jobs killed by a quit are
  recorded as interrupted. WebSocket events + poll fallback; cross-tool
  Queue page. The legacy immediate mode is unchanged (pivot micro-UI still
  green).
- Frame service: PyAV decode → cached JPEGs at viewer height with prefetch
  around the playhead; frame indices derived from pts (frame-accurate on
  CFR, golden-tested against a painted synthetic clip); past-EOF is a 404,
  never an aliased frame.
- Export presets in czcore.media: ProRes 422/HQ (hardware
  `prores_videotoolbox` when present, `prores_ks` fallback), ProRes 4444
  (+alpha), DNxHR HQX, H.264/HEVC (VideoToolbox, libx264/5 fallback) —
  every render reports the encoder that actually ran and passes color tags
  through untouched (and says so). Validated by real encodes.
- **Pivot moved in fully** (old page prints a retirement note, still works):
  analyze warms the scrub cache during its own decode pass, path-trace +
  punch-in scopes, per-shot overrides re-solve in place, render through the
  export panel, Fusion .setting export. Verified end-to-end on the 4K
  reference clip: 659/659 frames of ProRes 4444 (ffprobe-counted), bt709
  tags carried, override → punch verified, 1318-key .setting written.
- **Rise moved in**: probe + interlace guard (combed sources refused with a
  sentence; Studio-only bypass), A/B wipe against honest bicubic, detail
  heatmap = |model − bicubic| with an added-energy readout, model picker
  showing true on-disk availability, batch → queue. Verified: 96/96-frame
  batch through hardware ProRes; a 4K job cancelled mid-run removed its
  partial file. `rise.video.upscale_video` extracted from the CLI (CLI
  behavior unchanged); `resolve_model("auto")` now falls back to lanczos
  when the ONNX isn't converted instead of crashing.
- Tests: 119 green (26 new — job store persistence/cancel/interrupt, frame
  cache accuracy/EOF/mtime-keying, export preset mapping/alpha honesty).
- Honest limitations: previews are proxy JPEGs (native-pixel loupe planned),
  one job runs at a time, jobs are threads not worker processes (isolation
  arrives before Stencil's propagation), no drag-drop into the webview,
  headings fall back to system fonts (Space Grotesk/DM Sans not bundled),
  Windows untested.
- Trap for the file: FastAPI + `from __future__ import annotations` +
  a function-local `WebSocket` import makes every /ws connect 403 silently
  (string annotations resolve against module globals) — keep FastAPI names
  imported at module level.

### site (single-page rebuild) — 2026-07-16
- One-page architecture: tool pages retired; each tool is a homepage section
  (`#t-<id>`) with its live simulation, feature list, brief how-to, and a
  `<details>` technical expander (architecture, model card, honest limitations,
  replaces). Node tree + chips now anchor-jump. Stale pages cleaned at bake.
- Epic dark hero (white-paper band promoted): philosophy/why + four value
  cards over live grain; CTA row (suite download, tools, design study).
- New sections: Downloads (Suite app card, Hush/Speak OpenFX, white paper —
  carried into the bake from Hush-OpenNR/docs), DaVinci + Premiere guide
  cards, "Who is this for?" (stations section retired into it), free-toolbox
  grid on the homepage (9 tools with blurbs/links).
- Topline: "A Weird Machine project in collaboration with Brookline
  Interactive Group" (linked). Footer: designed/developed credit (Stephen
  Walter × Claude Code · 2026), Weird Machine logo, Community AI Project
  (communityai.studio) + BIG partnership line, MIT license link.
- specs/08-suite-app.md: the control-z Suite desktop app scoped (architecture,
  IA, per-tool workspaces, export contract incl. ProRes 4444+alpha, OpenFX
  installer page, design language, milestones, risks, build-session prompt).

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
