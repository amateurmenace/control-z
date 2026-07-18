"""The record's rules, held apart from the SQL that stores them.

Everything here was inside `store.py` when there was one store. A second store
is arriving (specs/17: the desk keeps SQLite, the Studio gets Postgres), and
the day two stores exist, every rule left inside one of them is a fork waiting
to happen — the merge-never-shrink policy was already written out three times
in one file, and a Postgres port would have made it four.

So the split is: **a store owns dialect, this module owns judgement.** How a
row merges, how a search blends, where the vector floor sits, what counts as
the same meeting, which columns are too heavy to list — those are answers about
the record, and they must be the same answer at a desk in Brookline and on a
server the town never sees. The SQL that carries them out is allowed to differ;
the answers are not.

Nothing here touches a database, so all of it is testable without one, and both
stores import it rather than re-deciding.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, List, Optional, Sequence, Tuple

# -- the meeting's shape ---------------------------------------------------

# The hand-maintained mirror of the meetings table. It lived in store.py as
# _MEETING_COLS; both stores' projections now read it here so a column added to
# one store and not the other is a test failure rather than a slow drift.
MEETING_COLS: List[str] = [
    "id", "town", "body", "title", "date", "url", "url_canon", "source_kind",
    "video_id", "media_path", "duration", "uploader", "origin", "n_segments",
    "n_speakers", "status", "error", "source_hash", "shingles", "info_json",
    "analysis_json", "summary", "summary_origin", "added_at", "updated_at",
]

# columns that are big or JSON — kept out of the light list view
HEAVY = {"info_json", "analysis_json", "shingles", "summary"}

LIST_COLS: List[str] = [c for c in MEETING_COLS if c not in HEAVY]

# -- search constants ------------------------------------------------------

# A vector hit below this is noise, not language. Calibrated against unit
# vectors from memory.embed; it is a cosine, so it travels between stores
# unchanged even when one uses a numpy matrix and the other an HNSW index.
VECTOR_FLOOR = 0.05

# Keyword hits score 1.0 down to ~0.5 by rank, so an exact word always outranks
# a merely-related one on a tie. The band is the contract; how each store ranks
# within it (FTS5 bm25 ascending, Postgres ts_rank_cd descending) is not.
KEYWORD_TOP = 1.0
KEYWORD_SPREAD = 0.5

_WORD_RE = re.compile(r"\w+")


def query_tokens(q: str) -> List[str]:
    """The words a search query actually searches for — the shared tokenizer
    behind FTS5's `"tok"*` and Postgres's `tok:*`."""
    return [t for t in _WORD_RE.findall(q or "") if t]


def rank_scores(rows: Sequence) -> List[Tuple[object, float]]:
    """Turn a store's *ordering* into scores. Deliberately rank-derived and not
    relevance-derived: SQLite's bm25() is negative and sorted ascending while
    Postgres's ts_rank_cd() is positive and sorted descending, so the two
    engines cannot hand back comparable numbers — but they can agree on which
    hit is best. Each store owes a correct order; the numbers are made here."""
    n = len(rows) or 1
    return [(r, round(KEYWORD_TOP - KEYWORD_SPREAD * i / n, 4))
            for i, r in enumerate(rows)]


def blend(keyword_hits: Iterable[dict], vector_hits: Iterable[Tuple[dict, float]],
          limit: int) -> List[dict]:
    """Fold word hits and meaning hits into one ranked list, keeping the
    provenance the reader is shown: a hit found both ways says so.

    `keyword_hits` are already-scored hit dicts carrying `seg_id`; `vector_hits`
    are (hit dict, similarity) pairs. Ordering ties break toward the keyword
    band by construction, because its scores start at 1.0."""
    by_id: dict = {}
    for hit in keyword_hits:
        by_id[hit["seg_id"]] = {**hit, "why": "word"}
    for hit, sim in vector_hits:
        sid = hit["seg_id"]
        if sid in by_id:
            by_id[sid]["score"] = max(by_id[sid]["score"], sim)
            by_id[sid]["why"] = "both"
        else:
            by_id[sid] = {**hit, "score": round(sim, 4), "why": "related"}
    hits = sorted(by_id.values(), key=lambda h: h["score"], reverse=True)
    return hits[:limit]


# -- dedupe ----------------------------------------------------------------

def jaccard(want: set, have: set) -> float:
    union = len(want | have)
    return (len(want & have) / union) if union else 0.0


def jaccard_hit(want: set, have: set, threshold: float = 0.9) -> bool:
    """Tier three of the dedupe contract: is this the same meeting posted at a
    second URL? Set math over transcript shingles, identical on both stores —
    Postgres may prefilter candidates with a GIN index, but the decision is
    made here so the boundary behaves the same everywhere."""
    return bool(have) and jaccard(want, have) >= threshold


# -- rows ------------------------------------------------------------------

def merge_plan(row: dict, now: float) -> Tuple[dict, List[str]]:
    """Merge, never shrink — the rule behind upsert_meeting, upsert_issue and
    upsert_document, which each wrote it out longhand.

    Returns `(insert_row, update_cols)`: what to write if the row is new (the
    caller's keys plus both timestamps), and which columns to set if it already
    exists (the caller's keys minus the primary key; `updated_at` is stamped by
    the store). Keys the caller omitted are never mentioned in either, which is
    the whole point — an omitted column keeps its value."""
    insert_row = {"added_at": now, "updated_at": now, **row}
    update_cols = [k for k in row if k != "id"]
    return insert_row, update_cols


def loads(s):
    """JSON or nothing. The record stores lists as json.dumps text on both
    stores (not JSONB) so a round-trip is byte-identical between them."""
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def dedupe_keep_order(items) -> list:
    seen, out = set(), []
    for x in items:
        k = str(x).strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def keyword_set(name: str, aliases) -> list:
    """The lowercased phrases a segment must contain to belong to an issue —
    the canonical name plus its aliases, deduped. This is what assignment
    matches on, so it is deliberately the visible, auditable surface."""
    return dedupe_keep_order(
        [str(name).lower()] + [str(a).lower() for a in (aliases or [])])


def centroid_of(vecs, np) -> Optional[object]:
    """The mean of an issue's member vectors, L2-normalised. Unit length is
    load-bearing: cosine() is a bare dot product and the assignment thresholds
    are calibrated against unit vectors."""
    vecs = [v for v in vecs if v is not None]
    if not vecs or np is None:
        return None
    c = np.mean(np.vstack(vecs), axis=0)
    n = float(np.linalg.norm(c))
    return (c / n) if n else c
