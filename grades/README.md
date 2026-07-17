# The control-z node tree

A **blank grading scaffold** for DaVinci Resolve — the structure of a working
grade with none of the grade in it. Nine nodes (eight labeled, plus a Parallel
Mixer), wired and empty.

`control-z-node-tree.zip` → `control-z-node-tree.drx` + `control-z-node-tree.dpx`

## Install

1. Unzip. **Keep both files in the same folder** — Resolve reads the grade from
   the `.drx` and the thumbnail from the `.dpx`, and the import fails without
   the pair.
2. In Resolve, open the **Color** page → **Gallery** → open the album list on
   the left → right-click a **PowerGrade** album → **Import**.
3. Pick the `.drx`. The still lands in the album; drag it onto a clip (or
   right-click → *Apply Grade*) to get the node tree.

Works in the **free** edition — there are no Studio-only effects in it, by
design (verified: zero OFX/ResolveFX references in the grade data).

## The nodes

Signal order, left to right:

`Noise Reduction` → `Exposure` → `Contrast` → `Balance` → `Sat` →
( `FG` ∥ `BG` → `Parallel Mixer` ) → `Look`

Eight labeled nodes plus the Parallel Mixer that recombines the FG/BG split.
Every node is empty — the scaffold, not a look. Two of them are where the suite
plugs in:

- **`Free NR`** → drop [Hush](https://control-z.org) on it. That's the node
  Resolve's own noise reduction would occupy — except its NR is Studio-only,
  which is the entire reason Hush exists.
- **`Look`** → drop [Speak](https://github.com/amateurmenace/Speak) on it.
  Film tone, subtractive color, halation and grain, at the end of the tree.

## Notes

- Exported from a 4K timeline, so the `.dpx` thumbnail is 33 MB (DPX is
  uncompressed; it barely zips). Exporting from an HD timeline would produce
  a ~8 MB thumbnail if a smaller download ever matters.
- The thumbnail is Hush's own synthetic validation test card — no third-party
  footage is embedded in either file.
- Grades are timeline-color-space dependent. This one carries no corrections,
  so there's nothing to mistranslate — but the look you build on it will be.

MIT, like everything else here.
