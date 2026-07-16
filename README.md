# Weird Machine · Resolve tools

**Free, open finishing tools for DaVinci Resolve — that work in the *free* version.**
Two plugins, one clean-to-filmic pipeline, built from original signal processing
and color science, and given away.

🌐 **[control-z.org](https://control-z.org)** — the site, the live demos, and the design study.

This repository is the **shared downloads hub** for both tools. Grab installers from
the [**Releases**](https://github.com/amateurmenace/control-z/releases) page.

---

## 🔇 Hush — noise reduction, first

Temporal + spatial + self-tuning noise reduction that shows its work. Auto Setup
measures your clip and dials in every slider; then, new in v3.6, it rebuilds the
**optical character** the denoise removed — lens-like acutance and film-matched
grain — and exports a clean-confidence matte for the grade downstream.

- Works in free & Studio Resolve · Color, Edit and Fusion pages
- macOS (universal), Windows (x64, OpenCL), Linux from source · MIT
- **Source & issues:** [amateurmenace/Hush-OpenNR](https://github.com/amateurmenace/Hush-OpenNR)
- Releases here are tagged **`hush-vX.Y.Z`**

## 🎞️ Speak — the film look, last

Hush's companion for the *end* of the node tree: film-stock density, subtractive
color, halation, bloom and grain — built from original color science, working in
DaVinci Wide Gamut. It reads Hush's confidence matte downstream to lay grain
exactly where the image was cleaned most.

- Releases here are tagged **`speak-vX.Y.Z`**
- _(Source repo & first release coming soon.)_

---

## Install (macOS)

1. Download the `.pkg` from [Releases](https://github.com/amateurmenace/control-z/releases) and double-click.
2. Restart DaVinci Resolve.
3. Find the plugin under **Effects → OpenFX → Filters** and drag it onto a node.

## Install (Windows)

1. Download the `-Windows.zip`, unzip, and run the included installer `.bat`
   (or copy the `.ofx.bundle` into `C:\Program Files\Common Files\OFX\Plugins`).
2. Restart DaVinci Resolve.

---

*A [Weird Machine](https://weirdmachine.org) project, in partnership with
[Brookline Interactive Group](https://brooklineinteractive.org) and the
[Community AI Project](https://communityai.studio). MIT licensed — free forever.*
