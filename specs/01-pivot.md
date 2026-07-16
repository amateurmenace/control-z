# Pivot — smart reframe

**"Pivot follows the subject."** Auto-reframes 16:9 masters to 9:16 / 1:1 / 4:5 (any aspect)
with subject tracking and editor-grade camera motion — the Studio Smart Reframe / Opus-style
SaaS feature, local and free. Accent: slate `#5B7A9E`.

**Users:** stations posting shows to Shorts/Reels/TikTok; journalists filing vertical cuts;
filmmakers delivering socials without re-editing.

## Covenant hooks

- **Shows its work:** the *path trace* view — detection boxes, chosen subject, deadzone,
  and the solved camera path drawn on the preview; plus a per-shot report ("shot 4: two
  faces, followed the speaking-sized one, 3 camera moves"). Export burns optional debug
  overlay for QC.
- **Honest limitations (v0.1):** no saliency model yet (faces/persons only — sports and
  wildlife will miss); no in-shot zoom changes; Studio's Smart Reframe is one click inside
  the timeline while Pivot is a roundtrip.

## Pipeline

```
probe → shot detect (czcore.shots) → per shot:
  sample frames (analysis stream ~360p, every 2nd frame)
  → detect: YuNet faces (v0.1) + YOLOX-s persons (v0.2) + motion-saliency fallback
  → track: IoU/position association (faces), pick subject (policy below, or user pin)
  → target series: (cx, cy, size, conf) per sampled frame → interpolate to full rate
→ solve camera path (per shot, independent — never smooth across a cut)
→ render: PyAV decode → crop → scale (Lanczos) [→ rise_engine if punch-in > 1.0 and enabled]
        → encode (hw H.264/HEVC or ProRes) + pass-through audio
→ exports: video(s) per aspect · path JSON sidecar · Fusion .setting (v0.2) · QC report
```

**Subject policy (v0.1):** largest persistent face track weighted by center bias and
temporal stability; ties broken by size × duration. User overrides per shot: click-to-pin
a track (UI) / `--pin shot4:track2` (CLI). No subject found → shot falls back to
center-weighted motion saliency (frame-difference centroid), else static center crop.

**Vertical framing:** eyeline at 38% from top by default (headroom slider), face fully in
frame with margin; group shots frame the track cluster's weighted centroid.

## The path solver (Pivot's soul — build + test first)

Per shot, given target centers `t[n]` (normalized 0..1 along the crop axis) and crop
half-width `hw` (from aspect math):

- **Mode `punch` (default when shot < 2.0 s, or target motion range < deadzone):**
  static crop at the robust median of `t` (trim 10% outliers). Editors punch, they don't
  drift — most shots should resolve to `punch`.
- **Mode `follow`:** offline controller with human-operator feel:
  - **Deadzone ±d** (default 0.06): subject drifts inside it, camera holds still (hard zero
    velocity, with hysteresis h=0.015 so it doesn't chatter at the boundary).
  - **Anticipation:** offline lookahead L=12 frames — the reference the controller chases is
    the median of `t[n..n+L]`, so moves start slightly early, like an operator.
  - **Motion profile:** braking-parabola velocity setpoint with hard caps `v_max`
    (default 0.010/frame) and `a_max` (0.0012/frame²) → S-curve moves; overshoot bounded
    to ~4·a_max (~0.5% of frame width — an imperceptible ease, pinned by golden tests).
  - **Edge behavior:** path clamped to [hw, 1-hw]; subject beyond reach → pin to edge.
- Output: `path[n]` full-rate crop centers (x always; y solved too when source is being
  cropped vertically, e.g. 16:9→1:1 from 9:16 source).

**Solver tests (golden, stdlib-only):** static target → exactly static path; step target →
settles within tolerance, zero overshoot, respects v/a caps; sinusoid → bounded lag, no
oscillation growth; jitter within deadzone → identity; cut boundary → no cross-shot bleed;
punch/follow auto-classification cases.

## Rise hook (the reason Rise is engine-first — see 00)

Punch-in factor = target_out_width / crop_src_width. When > 1.0:
- v0.1: Lanczos + mild adaptive sharpen, and the QC report *labels the softness honestly*.
- v0.2+: "Enhance punch-ins (Rise)" toggle → crops route through `rise_engine.upscale`
  (x2/x4, tiled). UI shows estimated added render time before committing. Per-shot
  override (enhance only the punched shots — it's per-shot math anyway).

## Outputs

- Rendered file per selected aspect: `name.pivot-9x16.mov|mp4` (H.264/HEVC hw, ProRes422/4444 option), audio copied.
- `name.pivot.json` — shots, tracks, chosen subjects, solved paths, settings (re-render
  deterministic from sidecar; also Stencil/Scribe-style interchange for the curious).
- **Fusion `.setting` export (v0.2):** keyframed Transform (Center/Size splines) per shot —
  paste onto the clip in free Resolve's Fusion page to keep the reframe *live* in the NLE
  instead of baking. (Free Resolve imports no keyframed FCPXML transforms reliably; the
  external scripting API is Studio-only; `.setting` paste is the clean free-tier path.)
- QC report (`.html`): per-shot decisions, punch-in factors, low-confidence shots flagged.

## UI (v0.2; CLI ships first)

Three panes, one screen: **queue** (drop files, aspect checkboxes, presets) · **preview**
(player, crop rectangle + path trace overlay, track chips with click-to-pin, per-shot
punch/follow/static override) · **shot strip** (thumbnails at cut boundaries, badges:
mode, subject, punch-in warning). Render queue with per-aspect progress. Nothing blocks
on the UI: every control mirrors a CLI flag.

## CLI (v0.1 acceptance surface)

```
pivot-cli analyze in.mov --aspect 9:16 [--pin shotN:trackM] [--report out.html] -o in.pivot.json
pivot-cli render  in.mov --path in.pivot.json --aspect 9:16 --codec h264|hevc|prores [--enhance] -o out.mov
pivot-cli auto    in.mov --aspect 9:16 1:1   # analyze+render, defaults
```

## Milestones

- **v0.1 (CLI):** shots, YuNet faces, tracker, solver (tested), render, JSON sidecar,
  report. Works on BIG test footage end-to-end.
- **v0.2:** web UI, pin/override, Fusion .setting export, YOLOX persons, rise_engine seed
  ("Enhance punch-ins"), batch queue.
- **v0.3:** saliency fallback model (U²-Net-p), multi-subject group framing, y-axis solve,
  marker import (reframe only marked ranges).
- **v1.0:** signed/notarized builds, docs page, before/after demos from BIG footage,
  honest-limitations section, release.

## Risks

Face detector misses (small faces in wide meeting shots) → analysis stream at higher res
when detections are sparse; persons model in v0.2 covers podium shots. Path feel is
subjective → the solver params are exposed as three human presets (Calm / Standard /
Attentive) and the golden tests pin the *math*, not the taste.
