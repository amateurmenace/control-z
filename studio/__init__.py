"""Community AI Studio — the record, hosted (specs/17).

The desk presses editions; the Studio keeps the record. Meetings arrive nightly
from the towns' own channels, the corpus lives in Postgres with pgvector,
search understands meaning as well as words, and a steward tends it from a
browser. No Mac in the loop — and the reader still never logs in.

What this package is *not* is a second engine. `memory/` is the civic-record
engine and stays that way: the issue clustering, the dedupe tiers, the vote
reader, the analysis passes are imported here, not reimplemented, so the
hand-audited logic produces the same record on both stores. What `studio/` adds
is the half a desk never needed — a Postgres store behind the same seam, an
HTTP surface, connectors that poll, steward auth, and a press job.

Layout:
  settings.py     — configuration from the environment only. No ~/Movies, no
                    support_dir, nothing that assumes a home directory.
  store.py        — PgCorpus: memory.seam.CorpusStore over Postgres + pgvector.
  migrate.py      — numbered plain-SQL migrations, applied once, recorded.
  embed_neural.py — the neural half of search (Gemini, server-side, batched).
  import_desk.py  — corpus.db → the Studio, transliterated, never re-derived.
  app.py          — the FastAPI service: search, submissions, freshness.
  auth.py         — Google Sign-In, allowlist, stewards only.
  steward.py      — the eight curation verbs, behind auth, with an audit log.
  press.py        — presses the specs/16 edition on corpus change.
  connectors/     — the towns' own channels, polled politely.

The covenant, translated up (specs/17 §9): readers get no accounts, no
tracking, no analytics, no fingerprinting. Accounts exist for stewards only.
The edition remains downloadable whole. The server spends the project's money,
never the reader's identity.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"
