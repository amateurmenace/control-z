"""A small, honest, offline text embedding.

The spec wants "semantic + keyword" search. Keyword is SQLite FTS5 (exact,
fast, in store.py). This file is the *related-language* half: a fixed-width
vector built from hashed word and character n-grams, L2-normalised, so two
segments that talk about the same thing in different words still land near each
other. It downloads nothing, needs no model, and runs on old hardware — the
covenant made literal. It is lexical, not neural, and the UI says so.

`embed()` is the single seam: when a local neural model earns its keep on the
cluster, swap the body here and every caller — store search, the context API —
inherits it with no other change.

Hashing uses blake2b, not Python's salted builtin `hash()`, so a vector
written today matches one computed in a fresh process tomorrow. That stability
is load-bearing: the vectors live in the database.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import List, Optional

try:  # numpy is a suite dependency; degrade to keyword-only if it is ever absent
    import numpy as np
except Exception:  # pragma: no cover - suite always ships numpy
    np = None  # type: ignore

DIM = 256
_WORD = re.compile(r"[a-z0-9']+")

# civic filler that carries no topical signal — kept small on purpose
_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "been", "it", "this", "that", "these", "those",
    "i", "you", "he", "she", "we", "they", "so", "as", "at", "by", "with",
    "from", "up", "out", "if", "then", "than", "there", "here", "just", "have",
    "has", "had", "do", "does", "did", "not", "no", "yes", "okay", "um", "uh",
    "going", "know", "think", "right", "well", "kind", "sort", "like",
}


def _bucket(token: str) -> int:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big") % DIM


def tokens(text: str) -> List[str]:
    """Words (minus filler) plus their character 3-grams — the fuzzy half that
    lets 'rezoning' and 'rezone' share weight."""
    out: List[str] = []
    for w in _WORD.findall((text or "").lower()):
        if w in _STOP or len(w) < 2:
            continue
        out.append(w)
        if len(w) > 4:
            padded = f"^{w}$"
            out.extend(f"#{padded[i:i + 3]}" for i in range(len(padded) - 2))
    return out


def embed(text: str, dim: int = DIM):
    """A unit-length vector for a piece of text. Returns a numpy float32 array
    (or None if numpy is unavailable — callers treat None as 'no semantics')."""
    if np is None:
        return None
    v = np.zeros(dim, dtype=np.float32)
    for tok in tokens(text):
        v[_bucket(tok) if dim == DIM else (_bucket(tok) % dim)] += 1.0
    n = float(np.linalg.norm(v))
    if n > 0:
        v /= n
    return v


def to_bytes(vec) -> bytes:
    if vec is None or np is None:
        return b""
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(blob: Optional[bytes]):
    if not blob or np is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


def cosine(a, b) -> float:
    """Cosine similarity of two already-unit vectors (dot product). Pure-python
    fallback so a caller without numpy still gets a number."""
    if a is None or b is None:
        return 0.0
    if np is not None:
        return float(np.dot(a, b))
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db)
