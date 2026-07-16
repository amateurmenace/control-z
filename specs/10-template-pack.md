# The control-z template pack — ten Fusion setups

**Goal:** a pack of ten paste-ready Fusion `.setting` files that turn the suite's
*outputs* into finished work, in the **free** edition of DaVinci Resolve. Five
already exist (Depth); five are new and cover the other tools. All ten must be
**paste-tested in a live Fusion comp** before they ship — that is the whole point
of this task.

## Read this first: the pack is currently unverified

`depth/templates/*.setting` were **hand-authored, never pasted into Resolve.**
The test suite only checks that braces balance and expected tool names appear —
it cannot tell whether Fusion accepts the file, whether an input name is real, or
whether the wiring produces an image. The site already says so
(`packs/README.md`: "Not yet paste-tested inside Resolve").

So the first job is not writing new templates. It is **finding out whether the
existing five work at all**, because everything new inherits their idioms. Expect
to fix things: `Bitmap`'s channel enum, whether `EffectMask` accepts a `Mask`
output, `VariBlur`'s `Blur` input name, and `Displace`'s parameter set are all
educated guesses.

Stephen has Resolve. Use it. A template that pastes cleanly and does nothing is
worse than no template, because it costs a user their trust and twenty minutes.

## The ten

Each is one `.setting`, self-contained, with a **sticky Note** naming exactly what
to wire where. Every tool used must exist in the free edition (no ResolveFX
Studio, no DCTL, no Neural Engine). Prefix node names `CZ*` so they're obvious in
a user's comp.

### The five that exist (verify, then fix)

| file | does | consumes |
|---|---|---|
| `fog.setting` | depth-shaped atmosphere; far end mists first | Depth matte |
| `rack-focus.setting` | depth-keyed variable blur, animatable focal plane | Depth matte |
| `depth-grade.setting` | near/mid/far stencils to grade through | Depth matte |
| `parallax.setting` | 2.5D displaced push-in for lockoffs and stills | Depth matte |
| `haze-light.setting` | depth-weighted glow — the honest "relight-ish" | Depth matte |

### The five to build

Chosen because each one takes a thing the suite already *emits* and makes it
useful. Stencil emits mattes and nobody ships the hard part — using them.

1. **`veil-blur.setting` — privacy blur through a Stencil matte.** ★ build first.
   Blur (and optionally mosaic) *only* inside a tracked matte, with a
   grow/feather on the matte so edges don't leak. This is the single most
   valuable template in the pack: it's the journalist use case, it's the
   groundwork for Veil on the roadmap, and doing it by hand today is miserable.
   Wire: image → `CZVeilBlur.Input`; Stencil matte → `CZVeilMask.Image`.
   Include a **mosaic variant** in the same file, bypassed by default.
   Honest note in the sticky: *this blurs where the matte says; check every
   frame before you publish — Stencil's confidence strip tells you where to look.*

2. **`cutout.setting` — composite on a Stencil alpha.** Bring in Stencil's
   ProRes 4444 (RGB+alpha) over a new background (another MediaIn or a
   `Background` color). Includes a `MatteControl` so the alpha can be tuned
   rather than trusted.

3. **`matte-tune.setting` — grow / shrink / feather / despeckle any matte, and
   *look* at it.** Works on Stencil, Depth, or Hush's clean-confidence matte.
   Two viewer-able outputs: the tuned matte alone, and the matte over the image
   as a tint. This is the QC bench the other templates assume you have.

4. **`confidence-grain.setting` — grain where Hush actually cleaned.** Hush ≥3.7
   can export its clean-confidence matte into the output **alpha**. This adds
   `FastNoise` grain merged over the image, masked by that alpha, so grain lands
   where the denoiser averaged deepest and backs off where real noise survived.
   It is the free-Fusion echo of what Speak's grain does natively — worth
   shipping precisely because it proves the handoff is real, and because not
   everyone will install Speak. Sticky note must point at Speak as the better
   path (it works in density, not on the output).

5. **`social-vertical.setting` — 9:16 with a blurred backdrop.** The most-shipped
   social format: scale + blur the frame as a backdrop, sit the real image on
   top, at a 1080×1920 canvas. Pairs with Pivot for the crop, but must also work
   standalone. Sticky note should say to set the comp/timeline to 1080×1920.

## Constraints

- **Free edition only.** Stock Fusion tools: `Blur`, `VariBlur`, `Bitmap`,
  `MatteControl`, `ErodeDilate`, `FastNoise`, `Background`, `Merge`, `Transform`,
  `Crop`, `Displace`, `SoftGlow`, `Pixelize`, `ColorCorrector`, `Note`. If a
  template needs a Studio ResolveFX, it doesn't ship.
- **Every value is a starting point.** Defaults should look sane on ordinary
  footage and be obviously adjustable.
- **The sticky note is the manual.** One `Note` per file, top-left, naming each
  wire in plain language. Users will not read a README that lives elsewhere.
- **Nothing auto-gains.** A subtle effect must look subtle (the covenant).

## Definition of done

1. Every one of the ten **pastes into a live Fusion comp in free Resolve without
   error** and produces the effect on real footage. Screenshot each.
2. `depth-cli templates` (and any new `--pack` surface) writes all ten.
3. The zip in `packs/` is regenerated and `packs/README.md` lists all ten —
   with the "not paste-tested" caveat **removed only for the ones actually
   tested**, and kept honestly for any that aren't.
4. Tests extended: structural checks per template (balanced braces, expected
   tools, a `Note` present, no Studio-only tool ids in any file).
5. `CHANGELOG.md` entry; site card copy updated (`site/templates/home.html`,
   "The template pack" card currently says five).

## Test protocol (the part that matters)

For each template, in free Resolve:
1. Open a clip on the Edit page → right-click → **Open in Fusion** (or the
   Fusion page).
2. Open the `.setting` in a text editor, select all, copy.
3. Click empty node-graph space, paste. **Record whether it errors.**
4. Wire per the sticky note; feed a real matte from
   `depth-cli run` / `stencil-cli run` on the Pexels clips in `Test Footage`.
5. View the result. Does it do the thing? Screenshot.
6. Fix, re-export, repeat.

Log the outcome per template — including any that had to be redesigned — so the
CHANGELOG can be specific instead of "improved templates".
