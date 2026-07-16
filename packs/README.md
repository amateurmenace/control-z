# The Fusion template pack

Five paste-ready Fusion setups that consume a **Depth** matte, for the free
edition of DaVinci Resolve. 3 KB — it's five text files.

`control-z-fusion-templates.zip` →

| template | what it does |
|---|---|
| `fog.setting` | depth-shaped atmosphere — the far end of the shot mists first |
| `rack-focus.setting` | depth-keyed variable blur with an animatable focal plane |
| `depth-grade.setting` | splits depth into near / mid / far stencils to grade through |
| `parallax.setting` | 2.5D displaced push-in for lockoffs and stills |
| `haze-light.setting` | depth-weighted glow — the honest "relight-ish" |

## Use

1. Make a depth matte for your clip: `depth-cli run scene.mov` (or drop the clip
   on Depth in the Suite app). You get a 10-bit gray matte clip beside it.
2. Open a `.setting` in any text editor, select all, copy.
3. In Resolve's **Fusion** page, click on empty node-graph space and paste.
4. Wire it up as the sticky note in each template says — your image into one
   input, the depth matte into the other.

Or install them into Fusion's own templates directory with
`depth-cli templates -o ~/Documents/control-z-templates`.

## Honest notes

- These are **Fusion tool setups**, not magic: they're built from stock nodes
  (Bitmap, Background, VariBlur, Displace, SoftGlow, Merge) that exist in the
  free edition. Nothing here needs Studio.
- They're a starting point, not a look. Every value is meant to be moved.
- **Not yet paste-tested inside Resolve** — they're generated and structurally
  validated (balanced braces, expected tools, correct input wiring) by the test
  suite, but a human hasn't pasted all five into a live Fusion comp yet. If one
  misbehaves, that's a bug worth filing.

MIT.
