# Stencil — AI roto mattes

**"Stencil traces the subject."** Click an object in one frame; get a clean matte for the
whole shot — Studio's Magic Mask / Mocha-class roto, local and free, delivered as matte
clips any page of free Resolve can use. Accent: plum `#8E6A9E`.

**Users:** colorists isolating faces/skies/garments; journalists prepping blur mattes
(future Veil shares this core); filmmakers comping without Studio.

## Covenant hooks

- **Shows its work — the confidence timeline.** SAM2's per-frame mask IoU predictions are
  drawn as a strip under the player; frames below threshold glow amber ("check these").
  Nobody's roto tool tells you where it's unsure; Stencil's whole QC loop is built on it.
- **Honest limitations:** hair/motion-blur edges are soft-matte quality, not keyer quality;
  v0.1 has no brush refinement (re-prompting on a bad frame usually beats brushes anyway);
  heavyweight install (PyTorch runtime) until the ONNX port lands.

## Core: SAM 2.1 video propagation (Apache-2.0)

- v0.1 runs **PyTorch** SAM2.1-hiera-small (default) / base+ (quality) on MPS/CUDA/CPU —
  reliable reference first; ONNX/CoreML export is a v0.3 optimization, not a blocker.
- Interaction model (native SAM2): positive/negative point clicks + optional box, on any
  frame; propagation runs bidirectionally from prompted frames; add corrective clicks on
  bad frames and re-propagate (memory bank keeps earlier prompts).
- Multiple objects per shot (each its own masklet → its own matte track).
- Shot-bounded: czcore.shots segments first; propagation never crosses cuts.

## Matte post-processing (per object, keyframable globals)

Grow/shrink (signed px) → feather (gaussian, px) → temporal smooth (3-frame morphological
majority — kills single-frame flicker without lag) → optional despeckle (drop components
< area). All previewable; all recorded in the sidecar JSON.

## Exports (the whole product is "mattes free Resolve actually uses")

- **Luma matte MOV** (ProRes 422, black/white) — universal: Media Pool → right-click grade
  node → *Add Matte* (Color page external matte, works in free) or Fusion loader.
- **ProRes 4444 alpha** (RGB fill + alpha) for edit-page overlay / Fusion merge.
- PNG sequence option; EXR later if demand appears.
- Sidecar `name.stencil.json` (prompts, model, post settings — reopenable session).
- A **recipes doc page** ships with the tool: three copy-paste workflows (grade-through-
  matte, background replace, tracked blur) with screenshots — adoption lives or dies here.

## UI

Player + click prompting (pos/neg), object chips with colors, onion-skin matte overlay
(50% tint), confidence timeline strip, per-object post controls, shot list, export queue.
Scrub-while-propagating (progressive results stream in as frames complete).

## CLI

```
stencil-cli run in.mov --prompts prompts.json --object 1 --out-mode luma -o in_matte.mov
stencil-cli resume in.stencil.json --export prores4444
```

## Milestones

- **v0.1:** single clip, multi-object prompts, propagation, confidence strip, post chain,
  luma + 4444 exports, session sidecar, recipes doc. (UI from day one — Stencil is
  unusable headless-first, unlike Pivot.)
- **v0.2:** re-prompt loop polish, batch shots, GPU memory tiling for UHD, PNG/EXR.
- **v0.3:** ONNX/CoreML runtime (shrink install), low-VRAM mode, Veil groundwork
  (track-class presets: face/plate).

## Risks

VRAM at UHD (propagate at 1080 analysis res, upscale masks with guided filter — standard
practice, ship it that way and say so); torch bundle size (label the download honestly:
~2 GB with models; ONNX port is the diet plan); temporal edge chatter (the post chain +
confidence strip make it visible and fixable rather than pretending it can't happen).
