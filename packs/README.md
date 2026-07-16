# The Fusion template pack

Ten paste-ready Fusion setups for the **free** edition of DaVinci Resolve. Five
consume a **Depth** matte, four consume a **Stencil** matte, one reads Hush's
clean-confidence alpha. ~23 KB — it's ten text files.

`control-z-fusion-templates.zip` →

### Depth matte

| template | what it does |
|---|---|
| `fog.setting` | depth-shaped atmosphere — the far end of the shot mists first |
| `rack-focus.setting` | depth-keyed variable blur with an animatable focal plane |
| `depth-grade.setting` | near / mid / far bands, each with its own grade node |
| `parallax.setting` | 2.5D displaced push-in for lockoffs and stills |
| `haze-light.setting` | depth-weighted glow — the honest "relight-ish" |

### Stencil matte

| template | what it does |
|---|---|
| `veil-blur.setting` | privacy blur (or mosaic) *inside* a tracked matte — the journalist tool |
| `cutout.setting` | composite a Stencil alpha over a new background, alpha tunable |
| `matte-tune.setting` | grow / shrink / feather / despeckle any matte, and *look* at it |
| `social-vertical.setting` | 9:16 with a blurred backdrop, on a 1080×1920 canvas |

### Hush clean-confidence alpha

| template | what it does |
|---|---|
| `confidence-grain.setting` | grain only where Hush actually cleaned (reads the output alpha) |

## Use

1. Make a matte for your clip — `depth-cli run scene.mov` for a depth matte, or
   `stencil-cli run scene.mov --prompts pts.json` for a subject matte (or drop
   the clip on Depth / Stencil in the Suite app).
2. Open a `.setting` in any text editor, select all, copy.
3. In Resolve's **Fusion** page, click on empty node-graph space and paste.
4. Wire it up as the sticky note in each template says — the note names every
   input by node.

Or install the whole pack into a folder with
`depth-cli templates -o ~/Documents/control-z-templates` (add `--pack depth` or
`--pack stencil` for just one set).

## Honest notes

- These are **Fusion tool setups**, not magic: they're built from stock nodes
  (`BitmapMask`, `Background`, `VariBlur`, `Blur`, `Scale`, `Displace`,
  `SoftGlow`, `FastNoise`, `MatteControl`, `ErodeDilate`, `ColorCorrector`,
  `Custom`, `Merge`, `Transform`) that all exist in the free edition. Nothing
  here needs Studio.
- They're a starting point, not a look. Every value is meant to be moved.
- **Paste-tested in a live Fusion comp** on free-edition tools in DaVinci
  Resolve (build 21): every one pastes without error, wires as its note says,
  and produces the effect on real footage. The five Depth templates were
  rebuilt in the process — an earlier hand-authored pass used a `Bitmap` node
  that Fusion silently drops on paste; the correct node is `BitmapMask`.
- `veil-blur` blurs (or mosaics) *where the matte says* — check every frame
  before you publish. Stencil's confidence strip tells you where to look.

MIT.
