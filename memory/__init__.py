"""Community Memory — the record across meetings and years.

Highlighter is a microscope; Memory is a telescope. Where Highlighter reads
one meeting in depth, Memory keeps the whole civic record: many meetings, many
public bodies, years of time — searchable, watchable, with receipts.

The covenant holds here as everywhere in the suite: free forever, local only,
no accounts, no telemetry. Memory *supplements the official record, never
replaces it* — every AI surface says so, shows its work, and names its limits.

Layout (this package is lane B's, owned end to end):
  store.py    — the corpus: one SQLite file under media_dir("memory"), FTS5
                for words, local vectors beside it for related language.
  seam.py     — what the engine may assume of a store, so the desk's SQLite and
                the Studio's Postgres (specs/17) can both answer to it.
  policy.py   — the record's judgement calls, held apart from the SQL that
                stores them: merging, blending, the vector floor, dedupe.
  embed.py    — a small, offline, no-download text embedding (lexical). The one
                seam to swap when a neural model earns its place.
  detect.py   — moment detection, borrowed from Highlighter behind our own door
                until czcore/moments.py lands (PARALLEL detection seam).
  analyze.py  — the reading: extractive by default (stands alone, no key), a
                generative summary only when the user brings a key — labeled.
  ingest.py   — the pipeline: captions-first (like Highlighter), Scribe ASR
                only for video without a published transcript.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"
