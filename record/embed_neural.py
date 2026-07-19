"""Meaning, bought by the batch — the neural half, and why it is optional.

`memory/embed.py` ends with a promise: it calls itself a seam, and says that
when a real model earns its keep, "swap the body here and every caller inherits
it". This is that swap, made in the one place it can be afforded — a server
with a bill attached — and made *beside* the lexical vector rather than instead
of it.

That word beside is the whole design. The desk's 256-dimension hashed vector
downloads nothing, needs no key, and runs on old hardware; it is the covenant
made literal, and it stays the default and the fallback everywhere. What Gemini
buys is the one thing hashing structurally cannot do: two passages about the
same subject in entirely different words. So publicrecord keeps both columns,
search blends both and tells the reader which found what, and an edition is
pressed from neither — `emb_neural` is the single column the record can lose
without losing anything it promised anyone.

Which is why nothing in this file raises. A key that was never set, a key that
was revoked, a 503 at two in the morning, a package that is not installed:
every one of them returns None for that text and a number in the report, and
the record goes on searching lexically. The failure mode of a paid dependency
inside a civic archive has to be "less", never "down".

Two details are load-bearing and quiet enough to get wrong:

**The vectors arrive un-normalised.** `gemini-embedding-001` is trained
Matryoshka-style and 768 dimensions is a truncated prefix of its 3072; below
full width the API does not re-normalise what it hands back. `memory.embed
.cosine()` is a bare dot product, `policy.VECTOR_FLOOR` and every threshold in
the issue engine are calibrated against unit vectors, and pgvector's cosine
operator would keep working while every number above it drifted. So the L2
division happens here, on the way in, exactly once — and never on the way out,
where some later caller would forget it and nothing would complain.

**A dead vector is NULL, not zeros.** The same rule the lexical column obeys,
for the same reason: cosine distance against a zero vector is undefined, and
one NaN poisons an HNSW ordering silently, with no error anywhere.

The batch cap and the retry ladder are the cost tradeoff, stated plainly: a
hundred texts per call and three backed-off retries make a 300-meeting backfill
minutes and pennies instead of hours, and turn a transient outage into a pause
rather than a hole in the corpus. Every call that succeeds writes a row to
`spend` — the ledger is the covenant's arithmetic, and a number nobody can see
is a number nobody controls.

    python -m record.embed_neural --backfill [--town X] [--limit N]
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from typing import List, Optional, Sequence

from memory import embed

from .settings import NEURAL_DIM, NEURAL_MODEL, settings

# The SDK is not a suite dependency and is not installed at the desk; the
# Studio's own container is the only place it is expected. Guarded, so that
# importing this module — which `record.store` does on every neural search —
# can never be the thing that takes the service down.
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # the common case everywhere but the server
    genai = None       # type: ignore
    genai_types = None  # type: ignore

# A hundred is the batch the pricing and the latency both like; the API accepts
# a list of strings and returns one embedding per string, in order, and that
# ordering is the only thing tying a vector back to its segment — so a reply
# whose length disagrees with the request is treated as a failure below rather
# than zipped hopefully against the wrong rows.
BATCH_MAX = 100

# 2,048 input tokens is the model's ceiling. A civic segment is about forty-five
# words and nowhere near it; a document chunk can be. Clipping rather than
# refusing is the right trade — a vector for the first several pages of a
# planning memo is worth more to a searcher than a NULL — and it is worth
# knowing that is what happened, hence the comment rather than silence.
MAX_CHARS = 7500

# Asymmetric on purpose. The model is trained so that a RETRIEVAL_QUERY vector
# lands near the RETRIEVAL_DOCUMENT vectors that answer it; embedding both
# sides with the same task type, or mixing in SEMANTIC_SIMILARITY, still
# produces plausible numbers and quietly retrieves worse.
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

# Three sleeps, four attempts, then give up and say so. Long enough to ride out
# a rate limit or a restart, short enough that a nightly job does not sit on a
# dead endpoint until morning.
_BACKOFF = (1.0, 4.0, 10.0)

# Codes that will fail identically on the next attempt: a bad key, a forbidden
# project, a malformed request. Retrying these buys nothing but latency.
_PERMANENT = {400, 401, 403, 404, 413}

_CLIENT = None
_LEDGER_WARNED = False

# One vector per input text, position for position, None where there is none.
_Vecs = List[Optional[List[float]]]


# -- availability ----------------------------------------------------------

def available() -> bool:
    """Whether the neural half can actually run: a key configured *and* the
    SDK importable. Both halves matter — a key with no package and a package
    with no key fail at different depths and would otherwise be discovered by
    a traceback in the middle of a backfill."""
    return genai is not None and bool(settings.gemini_key)


def status() -> dict:
    """What to show a health endpoint or the steward console. `reason` is
    empty when the capability is present and a sentence when it is not,
    because "false" alone sends someone reading logs."""
    if genai is None:
        reason = "the google-genai package is not installed"
    elif not settings.gemini_key:
        reason = "RECORD_GEMINI_KEY is not set"
    else:
        reason = ""
    return {"model": NEURAL_MODEL, "dim": NEURAL_DIM,
            "available": not reason, "reason": reason}


def _client():
    """One client for the process. Built on first use rather than at import so
    that a module-level import never touches the network or the environment."""
    global _CLIENT
    if _CLIENT is None and available():
        _CLIENT = genai.Client(api_key=settings.gemini_key)
    return _CLIENT


# -- the vectors themselves ------------------------------------------------

def _unit(values) -> Optional[List[float]]:
    """L2-normalise, or refuse. The refusals are the point: a vector of the
    wrong width means the model or the dimension pin moved underneath a corpus
    that cannot tell (there is no dimension tag on a stored vector), and a
    zero or non-finite norm means there is no direction to store."""
    try:
        vals = [float(x) for x in (values or [])]
    except (TypeError, ValueError):
        return None
    if len(vals) != NEURAL_DIM:
        return None
    norm = math.sqrt(sum(v * v for v in vals))
    if not norm or not math.isfinite(norm):
        return None
    return [v / norm for v in vals]


def _clip(text) -> str:
    return str(text or "")[:MAX_CHARS]


def _permanent(exc) -> bool:
    """The SDK raises APIError with a `.code`; anything else is read
    defensively, because guessing wrong here only costs three extra retries
    while assuming the attribute exists would cost an AttributeError inside
    the error path."""
    return getattr(exc, "code", None) in _PERMANENT


def _reason(exc) -> str:
    code = getattr(exc, "code", None)
    return f"{exc.__class__.__name__} {code}" if code else exc.__class__.__name__


def _call(texts: Sequence[str], task: str) -> _Vecs:
    """One request. Raises on anything at all — the retry ladder above is the
    only place failure is interpreted."""
    cfg = genai_types.EmbedContentConfig(
        output_dimensionality=NEURAL_DIM, task_type=task)
    resp = _client().models.embed_content(
        model=NEURAL_MODEL, contents=list(texts), config=cfg)
    vecs = [_unit(getattr(e, "values", None))
            for e in (getattr(resp, "embeddings", None) or [])]
    if len(vecs) != len(texts):
        raise RuntimeError(
            f"{NEURAL_MODEL} returned {len(vecs)} vectors for {len(texts)} "
            f"texts; position is the only link back to a segment, so this "
            f"batch is discarded rather than mis-assigned")
    return vecs


def _attempt(texts: Sequence[str], task: str) -> Optional[_Vecs]:
    """The ladder. Returns the vectors, or None when the call could not be
    made at all — the caller distinguishes "no vector for this text" from "no
    answer for any of them", because only the second is worth stopping for."""
    for i in range(len(_BACKOFF) + 1):
        try:
            return _call(texts, task)
        except Exception as e:               # deliberately everything
            if _permanent(e) or i == len(_BACKOFF):
                print(f"  embed failed ({_reason(e)}) for {len(texts)} text(s)")
                return None
            time.sleep(_BACKOFF[i])
    return None


# -- the ledger ------------------------------------------------------------

# What an embedding costs, pinned the way czcore/models.py pins hashes.
#
# $0.15 per 1M input tokens for gemini-embedding-001, paid tier, verified
# against ai.google.dev/gemini-api/docs/pricing on 2026-07-19. A price is not a
# constant of nature: when this drifts, the ledger drifts silently with it,
# because `spend.units` records what was actually bought and this only converts.
# The console shows both, so a divergence between the estimate and the invoice
# is visible rather than inferred.
USD_PER_MILLION_TOKENS = 0.15

# A civic segment averages about forty-five words; tokens run a little above
# words. Deliberately generous — an estimate that undercounts is a cap that
# does not hold.
TOKENS_PER_SEGMENT = 60


def estimate_usd(units: int) -> float:
    """Dollars for a number of embedded segments. Rounded up in spirit: this
    is what a cap is measured against, so it should never flatter itself."""
    return (units * TOKENS_PER_SEGMENT / 1_000_000.0) * USD_PER_MILLION_TOKENS


def spent_usd(corpus) -> float:
    """What this record has spent on embeddings so far, from the ledger rather
    than from a counter this process happens to hold — so a cap survives a
    restart, a second job, and a job someone ran last week."""
    if corpus is None:
        return 0.0
    try:
        with corpus._con() as con:
            row = con.execute(
                "SELECT COALESCE(SUM(units),0) AS n FROM spend "
                "WHERE model=%s", (NEURAL_MODEL,)).fetchone()
        return estimate_usd(int(row["n"] or 0))
    except Exception:
        # A cap that cannot read the ledger must not silently become no cap.
        raise


def _log_spend(corpus, units: int, purpose: str, town: str = "",
               target: str = "") -> None:
    """Every call the project paid for, written down where a steward can see
    it. A ledger that cannot be written is a loud line and nothing more: the
    embeddings are already bought by the time this runs, and losing them to a
    bookkeeping error would be the worse of the two failures."""
    global _LEDGER_WARNED
    if corpus is None or units <= 0:
        return
    try:
        with corpus._con() as con:
            con.execute(
                "INSERT INTO spend (model, purpose, town, target, units, "
                "added_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (NEURAL_MODEL, purpose, town, target, int(units), time.time()))
    except Exception as e:
        if not _LEDGER_WARNED:
            _LEDGER_WARNED = True
            print(f"  spend ledger unwritable ({e.__class__.__name__}) — the "
                  f"calls are still being made and are no longer being counted")


# -- the public seam -------------------------------------------------------

def embed_batch(texts: List[str], purpose: str = "embed", town: str = "",
                corpus=None, target: str = "") -> _Vecs:
    """Vectors for many texts at once — the ingest path.

    Returns a list the same length as `texts`, position for position, each
    item a unit-length list of `NEURAL_DIM` floats or None. None means only
    what it says: no vector for that text, from a blank string, a refusal, or
    an outage. Nothing here raises, so a caller never has to decide whether a
    half-finished batch is safe to write — the Nones are the answer.

    A plain list rather than an array because the caller writes it through an
    explicit `::vector` cast; the query path below has a different consumer
    and hands back a different shape for a reason given there."""
    out: _Vecs = [None] * len(texts)
    if not texts or not available():
        return out
    # Blank and whitespace-only texts never reach the API: they cost money,
    # they embed to nothing useful, and the segment table has plenty of them.
    live = [(i, _clip(t)) for i, t in enumerate(texts) if str(t or "").strip()]
    for start in range(0, len(live), BATCH_MAX):
        chunk = live[start:start + BATCH_MAX]
        vecs = _attempt([t for _, t in chunk], TASK_DOCUMENT)
        if vecs is None and len(chunk) > 1:
            # One text the API will not accept must not cost the other
            # ninety-nine their vectors, so a dead batch is retried as
            # singletons before it is believed.
            vecs = []
            for _, t in chunk:
                one = _attempt([t], TASK_DOCUMENT)
                vecs.append(one[0] if one else None)
        if vecs is None:
            continue
        got = 0
        for (i, _), v in zip(chunk, vecs):
            out[i] = v
            got += 1 if v is not None else 0
        _log_spend(corpus, got, purpose, town, target)
    return out


def embed_query(q: str, corpus=None, town: str = ""):
    """One query vector, or None when the neural half cannot answer.

    Returned through `memory.embed.as_vec` — a float32 array — rather than as
    a plain list, for two reasons that agree. It is what the lexical half of
    `PgCorpus._query_vec` returns, so the two spaces are the same kind of
    object to the code above them; and pgvector's psycopg dumper is registered
    for arrays and its own Vector only, so a plain list would be adapted as
    `float8[]` and `vector <=> float8[]` is an operator that does not exist.
    Without numpy this is None, which is exactly what the lexical half does in
    the same circumstance."""
    q = (q or "").strip()
    if not q or not available():
        return None
    vecs = _attempt([_clip(q)], TASK_QUERY)
    v = vecs[0] if vecs else None
    if v is None:
        return None
    _log_spend(corpus, 1, "query", town, "search")
    return embed.as_vec(v)


# -- the backfill ----------------------------------------------------------

def backfill(corpus, town: str = "", limit: int = 0,
             verbose: bool = True, cap_usd: float = 0.0) -> dict:
    """Fill `segments.emb_neural` wherever it is NULL, in batches.

    Returns `{"embedded", "skipped", "failed", "available"}`. When the
    capability is absent it returns immediately with `available` false and
    nothing embedded — it does not half-run, and it does not pretend. The
    record searches lexically either way, which is the only reason this is
    allowed to be a no-op instead of an error.

    The cursor walks `id` rather than re-asking for NULLs, because a text the
    API refuses stays NULL and would otherwise be handed back forever. Those
    rows are simply picked up again by the next run, when the refusal may have
    been temporary after all."""
    from .settings import settings
    cap = cap_usd if cap_usd > 0 else settings.spend_cap_usd
    out = {"embedded": 0, "skipped": 0, "failed": 0, "available": available(),
           "cap_usd": cap, "spent_usd": 0.0, "stopped_at_cap": False}
    if not out["available"]:
        if verbose:
            print(f"neural embeddings unavailable: {status()['reason']}")
            print("nothing embedded; the record still searches lexically.")
        return out

    after, remaining = 0, (limit if limit > 0 else -1)
    while True:
        want = BATCH_MAX if remaining < 0 else min(BATCH_MAX, remaining)
        if want <= 0:
            break
        # The cap is checked at the top of the loop — before a row is read, let
        # alone bought — and it is measured against the `spend` ledger rather
        # than a counter this process holds. That is what makes it survive a
        # restart, a second job running beside this one, and a job somebody ran
        # last week. A cap enforced after the purchase is a receipt.
        if cap > 0:
            already = spent_usd(corpus)
            out["spent_usd"] = round(already, 4)
            if already + estimate_usd(want) > cap:
                out["stopped_at_cap"] = True
                if verbose:
                    print(f"  stopping: ${already:.2f} already spent against a "
                          f"${cap:.2f} cap. {out['embedded']:,} embedded this "
                          f"run; the rest stay NULL and search stays lexical "
                          f"for them, which is a degradation and not a loss.")
                break
        sql = ("SELECT id, text FROM segments "
               "WHERE emb_neural IS NULL AND id > %s")
        args: list = [after]
        if town:
            sql += " AND town=%s"
            args.append(town)
        sql += " ORDER BY id LIMIT %s"
        args.append(want)
        with corpus._con() as con:
            rows = [dict(r) for r in con.execute(sql, args).fetchall()]
        if not rows:
            break
        after = max(int(r["id"]) for r in rows)
        if remaining > 0:
            remaining -= len(rows)

        target = f"segments:{rows[0]['id']}-{after}"
        vecs = embed_batch([r["text"] or "" for r in rows], purpose="embed",
                           town=town, corpus=corpus, target=target)

        wrote = 0
        with corpus._con() as con:
            for r, v in zip(rows, vecs):
                if v is None:
                    if (r["text"] or "").strip():
                        out["failed"] += 1
                    else:
                        out["skipped"] += 1
                    continue
                # `::vector` rather than a bare parameter: the value is a
                # plain list of floats, which psycopg would otherwise adapt to
                # float8[], and the cast is a no-op if it is ever anything
                # pgvector already knows how to dump.
                con.execute(
                    "UPDATE segments SET emb_neural = %s::vector WHERE id=%s",
                    (_pg_vector(v), int(r["id"])))
                wrote += 1
        out["embedded"] += wrote
        if verbose:
            print(f"  {wrote:>4} embedded  "
                  f"({out['embedded']:,} done, {out['failed']:,} failed, "
                  f"{out['skipped']:,} blank)")
        if wrote == 0 and any((r["text"] or "").strip() for r in rows):
            # A whole batch of real text came back with nothing, after the
            # ladder and the singleton retries. That is an outage or a revoked
            # key, not a bad segment; grinding through the rest of the corpus
            # would only make the same call ten thousand more times.
            if verbose:
                print("  the API answered nothing for an entire batch — "
                      "stopping here; rerun when it is back.")
            break
    return out


def _pg_vector(vals: Sequence[float]) -> str:
    """pgvector's text input form. Seven significant digits because the column
    is float4 and anything finer is discarded on the way in anyway."""
    return "[" + ",".join("%.7g" % float(v) for v in vals) + "]"


# -- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m record.embed_neural",
        description="The neural half of search: Gemini embeddings, batched, "
                    "stored beside the lexical vector and never instead of it.")
    ap.add_argument("--backfill", action="store_true",
                    help="embed every segment whose emb_neural is NULL")
    ap.add_argument("--town", default="", help="restrict to one town")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N segments (0 = all)")
    ap.add_argument("--dsn", default="", help="override RECORD_DSN")
    args = ap.parse_args(argv)

    st = status()
    print(f"{st['model']} @ {st['dim']}  "
          f"{'available' if st['available'] else 'unavailable: ' + st['reason']}")
    if not args.backfill:
        return 0
    if not st["available"]:
        # An explicit --backfill that cannot run is a failed job, not a quiet
        # success. The scheduler is entitled to hear about it.
        print("--backfill was asked for and cannot run.")
        return 1

    from .store import PgCorpus
    corpus = PgCorpus(args.dsn)
    t0 = time.time()
    try:
        r = backfill(corpus, town=args.town, limit=args.limit)
    finally:
        corpus.close()
    print(f"embedded {r['embedded']:,} segment(s) in {time.time() - t0:.1f}s  "
          f"(failed {r['failed']:,}, blank {r['skipped']:,})")
    return 1 if r["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
