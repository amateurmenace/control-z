# Depth — depth mattes + the depth toolkit

**"Depth measures the scene."** Monocular depth for every clip — exported as mattes free
Resolve can grade, fog, and rack-focus through, with a ready-made Fusion template pack.
Replaces Studio's Depth Map + a slice of Relight. Accent: indigo `#5E5A8C`.

**Users:** colorists (depth-graded atmosphere, sky/subject separation without roto);
filmmakers (fake rack focus, 2.5D parallax on stills/lockoffs); artists (fog, relight-ish
gradients, projection looks).

## Covenant hooks

- **Shows its work:** depth histogram + false-color view with a draggable probe (click
  a pixel, read its relative depth); temporal-stability meter per shot (flicker risk
  flagged before you export, not after you grade).
- **Honest limitations:** *relative* depth, not metric — great for mattes/atmosphere,
  not measurement; struggles on mirrors/glass/scale tricks; Studio's Relight does true
  normals+lighting — our relight recipes are gradient approximations until an OFX lands.

## Stack

- **Video Depth Anything — Small** (Apache-2.0; larger checkpoints are CC-BY-NC and are
  rejected per 00 policy) via ONNX Runtime; temporally consistent by design (its whole
  point) + light EMA smoothing per pixel as belt-and-suspenders.
- Shot-bounded (czcore.shots); per-shot depth range normalization with a global option
  (consistent scale across a scene when clips match).
- Upscale of depth to source res with edge-guided filter (joint bilateral against RGB) —
  crisp depth edges that track image edges.

## Exports

- **Depth matte clip:** 16-bit gray ProRes 4444 (default) or EXR/TIFF sequence; near/far
  mapping controls (invert, gamma, in/out points on the histogram) baked or raw.
- **The template pack (the adoption trick — ships *with* v0.1):** five Fusion `.setting`
  files that consume the matte on free Resolve's Fusion page, one paste each:
  1. **Fog** — depth-shaped atmosphere with color + falloff controls
  2. **Rack Focus** — depth-keyed variable blur with animatable focal plane
  3. **Depth Grade** — matte → three luma bands for near/mid/far grading stencils
  4. **Parallax 2.5D** — displaced push-in for lockoffs/stills
  5. **Haze Light** — depth-weighted glow/relight gradient (the honest "relight-ish")
  Each template's tool page shows the paste-and-go recipe. Color-page users get the
  external-matte recipe (Add Matte → key through depth bands).
- Sidecar JSON (settings, model, ranges) for deterministic re-export.

## App

Small by suite standards: drop clips → per-shot preview (false color / probe / histogram
with in/out handles) → export queue. CLI mirrors everything:

```
depth-cli run in.mov --range shot --map gamma=1.2,invert -o in_depth.mov
depth-cli templates install   # drops the .setting pack into Fusion's templates dir
```

## Milestones

- **v0.1:** VDA-Small ONNX pipeline, per-shot normalize, ProRes4444 export, false-color
  preview + probe, **template pack**, CLI.
- **v0.2:** UI polish (histogram in/out, global scene normalize), EXR/TIFF, stability meter.
- **v0.3:** OFX applier exploration — a small "Depth Toolkit" OpenFX (fog/blur in-node,
  reading the sidecar matte) if template-pack friction proves it's needed; shares Hush's
  OFX scaffolding.
- **v1.0:** builds, site page, release.

## Risks

Temporal flicker on hard cases (the stability meter + EMA are the mitigations; be honest
on the tool page); model updates changing depth scales between versions (pin model hash
per project sidecar); template-pack breakage across Resolve versions (CI checklist:
paste-test the pack on current free Resolve each release).
