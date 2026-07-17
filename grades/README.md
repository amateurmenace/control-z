# The control-z node tree

A **blank grading scaffold** for DaVinci Resolve — the structure of a working
grade with none of the grade in it. Nine stages at the top level, wired and
empty; two of them (`Noise Reduction` and `Look`) are **compound nodes** that
open into a Studio-or-free choice — use a Studio feature if you have it, or
combine free effects to match it.

`control-z-node-tree.zip` → `control-z-node-tree.drx` + `control-z-node-tree.dpx`

## Install

1. Unzip. **Keep both files in the same folder** — Resolve reads the grade from
   the `.drx` and the thumbnail from the `.dpx`, and the import fails without
   the pair.
2. In Resolve, open the **Color** page → **Gallery** → open the album list on
   the left → right-click a **PowerGrade** album → **Import**.
3. Pick the `.drx`. The still lands in the album; drag it onto a clip (or
   right-click → *Apply Grade*) to get the node tree.

Imports and applies in the **free** edition — every node is empty of
corrections and the Studio slots are off, so nothing errors on a tool you can't
run.

## The nodes

Signal order, left to right:

`Noise Reduction`* → `Exposure` → `Contrast` → `Balance` → `Sat` →
( `FG` ∥ `BG` → `Parallel Mixer` ) → `Look`*

The seven single nodes are empty. The two starred stages are **compound nodes**
— double-click to step inside:

- **`Noise Reduction`** opens into `Studio NR` → `Free NR` → `Sat v Lum Curves`.
  Have Studio? Enable Studio NR (Resolve's spatial/temporal NR — off by default
  so the grade opens clean without it). Don't? Drop
  [Hush](https://control-z.org) on **`Free NR`** and let the Sat-vs-Lum curve
  take the last of the chroma noise — both free-edition tools, same result.
- **`Look`** opens into three nodes for the film look. Studio's one-node answer
  is **Film Look Creator**; the free answer is to build it from stock effects —
  or drop [Speak](https://github.com/amateurmenace/Speak) in for film tone,
  subtractive color, halation and grain.

The compound nodes are the whole project in miniature: a slot for the Studio
feature if you own it, and the free combination that matches it if you don't.

## Notes

- Exported from a 4K timeline, so the `.dpx` thumbnail is 33 MB (DPX is
  uncompressed; it barely zips). Exporting from an HD timeline would produce
  a ~8 MB thumbnail if a smaller download ever matters.
- The thumbnail is Hush's own synthetic validation test card — no third-party
  footage is embedded in either file.
- Grades are timeline-color-space dependent. This one carries no corrections,
  so there's nothing to mistranslate — but the look you build on it will be.

MIT, like everything else here.
