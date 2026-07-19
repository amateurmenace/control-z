"""The corpus in Postgres — the same record, the same answers, other dialect.

This is `memory.seam.CorpusStore` a second time. It is deliberately structured
like `memory/store.py` method for method, so the two can be read side by side
and a divergence is visible rather than buried; and every judgement call it
makes comes from `memory/policy.py`, so the two cannot drift on *what* the
record means even when they differ on how to ask for it.

The four places the dialect genuinely bites, and what is done about each:

**`end` is a reserved word.** Not merely awkward — `s.end` is a syntax error in
Postgres, because the token after a dot must be a ColId. The column is `end_s`
and every read aliases it back to `"end"`, so callers, tests and the reader see
identical dict keys on both stores.

**bm25 is negative, ts_rank_cd is positive.** SQLite orders keyword hits
ascending by a negative score; Postgres orders descending by a positive one.
Porting the ORDER BY across would return the *worst* matches first and, because
the score is rank-derived, corrupt every number in the result with no error
anywhere. `policy.rank_scores` takes an ordering and makes the numbers, so each
store owes only a correct sort.

**A connection is no longer free.** The desk opens one per operation — a search
costs it something like 121 of them, which is microseconds against a local file
and a catastrophe across a network. So: a pool, and the meeting JOIN folded
into the search queries rather than resolved per hit.

**Vectors are typed.** `emb` is a `vector(256)` rather than a blob of float32,
and a zero-norm vector is stored as NULL rather than as zeros — cosine distance
against a zero vector is undefined, and one NaN poisons an HNSW ordering
silently. `memory.embed.as_vec` reads either shape, which is why the engine
above the seam never learns which store it is talking to.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import List, Optional

from memory import embed, policy

# One open transaction per task, when a caller has asked for one via unit().
# A ContextVar rather than an attribute because the service is concurrent and
# two requests curating at once must not share a transaction.
_UNIT: ContextVar = ContextVar("record_unit", default=None)

# The hit envelope, identical on both stores. Selected once here rather than
# assembled per row, because this JOIN is what replaces the desk's N+1.
# How far the HNSW walk reaches, relative to what the caller asked for. Pinned
# here rather than left at Postgres's default of 40, because the default is
# below the reader's own page size and an index that stops being used is not an
# error anybody sees — it is the same answer, slower, until somebody times it.
# The factor buys recall under a town or body filter, where candidates are
# discarded after the index has already chosen them.
HNSW_EF_MIN = 64
HNSW_EF_FACTOR = 4
# pgvector rejects an ef_search above 1000 rather than clamping it, so the
# search must clamp first — a raised limit must never become a 500.
HNSW_EF_MAX = 1000
# How much wider the vector subquery pulls when a meetings-side filter (town or
# body) will thin its results after the index has chosen. A recall/latency
# trade: the index cost is dominated by ef_search, not the LIMIT, so
# over-fetching a few multiples is cheap and keeps a scoped search from coming
# back thin.
HNSW_SCOPE_OVERFETCH = 4

_HIT_COLS = """
    s.meeting_id, s.id AS seg_id, s.start AS t, s.end_s AS "end", s.text,
    NULLIF(s.speaker, '') AS speaker,
    m.title, m.date, m.body, m.town, m.url, m.source_kind, m.video_id,
    m.media_path, m.duration
"""


class PgCorpus:
    """Publicrecord's store. Implements `memory.seam.CorpusStore`."""

    def __init__(self, dsn: str = "", pool_min: int = 1, pool_max: int = 8,
                 check_dims: bool = True):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        from pgvector.psycopg import register_vector

        from .settings import settings

        self.dsn = dsn or settings.dsn
        self.db_path = Settings_redacted(self.dsn)   # the seam's name for "which store"
        self.fts = True          # a GENERATED tsvector column: always present
        self._psycopg = psycopg

        def _configure(con):
            con.row_factory = dict_row
            register_vector(con)

        self.pool = ConnectionPool(self.dsn, min_size=pool_min, max_size=pool_max,
                                   configure=_configure, open=True)
        self.pool.wait(timeout=15)
        if check_dims:
            self._assert_dims()

    # -- lifecycle ---------------------------------------------------------

    def _assert_dims(self) -> None:
        """The lexical space is pinned in four places (embed.DIM, the column,
        the CHECK, and meta) and there is no dimension tag on a stored vector.
        A mismatch does not degrade — it raises a shape error deep inside the
        issue engine — so it is caught here, at connect time, with a sentence."""
        with self._con() as con:
            row = con.execute(
                "SELECT value FROM meta WHERE key='embed_lex_dim'").fetchone()
        if not row:
            return                       # a fresh database, not yet migrated
        stored = int(row["value"])
        if stored != embed.DIM:
            raise RuntimeError(
                f"this corpus was written with {stored}-dimension lexical "
                f"vectors and memory.embed now makes {embed.DIM}. Re-embed the "
                f"corpus or pin embed.DIM back; the vectors carry no dimension "
                f"tag, so nothing downstream would catch this but a crash.")

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def unit(self):
        """One transaction across several calls.

        The curation verbs are sequences — merge is `merge_issues`, then
        `reassign_issue`, then `get_issue` — and every call here commits on its
        own. One writer on one file makes that invisible at the desk; several
        workers against one Postgres make it a half-done merge. Inside this
        block every `_con()` reuses the same open transaction, and an exception
        rolls the whole verb back."""
        if _UNIT.get() is not None:
            yield self                       # already in one; don't nest
            return
        with self.pool.connection() as con:
            con.autocommit = False
            token = _UNIT.set(con)
            try:
                with con.transaction():
                    yield self
            finally:
                _UNIT.reset(token)

    @contextmanager
    def _con(self):
        """A pooled connection — or the open unit-of-work if one is running."""
        held = _UNIT.get()
        if held is not None:
            yield held
            return
        with self.pool.connection() as con:
            yield con

    # -- meetings ----------------------------------------------------------

    def upsert_meeting(self, m: dict) -> None:
        self._merge_row("meetings", m)

    def _merge_row(self, table: str, row: dict) -> None:
        """Merge, never shrink — `policy.merge_plan` decides what that means and
        this spells it in Postgres. Only the keys present are written; omitted
        columns keep their value."""
        now = time.time()
        fresh, cols = policy.merge_plan(row, now)
        # One statement, not SELECT-then-branch. The desk can check and then act
        # because it has one writer; here a nightly job and a steward approval
        # land on the same id and the loser raised UniqueViolation instead of
        # merging. ON CONFLICT does the whole thing atomically, and the DO
        # UPDATE list is still only the caller's keys — merge, never shrink.
        names = list(fresh)
        sets = ", ".join(f"{c}=excluded.{c}" for c in cols) if cols else ""
        sets = (sets + ", " if sets else "") + "updated_at=excluded.updated_at"
        with self._con() as con:
            con.execute(
                f"INSERT INTO {table} ({', '.join(names)}) "
                f"VALUES ({', '.join('%s' for _ in names)}) "
                f"ON CONFLICT (id) DO UPDATE SET {sets}",
                [fresh[c] for c in names])

    def set_status(self, meeting_id: str, status: str, error: str = "") -> None:
        with self._con() as con:
            con.execute(
                "UPDATE meetings SET status=%s, error=%s, updated_at=%s WHERE id=%s",
                (status, error, time.time(), meeting_id))

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM meetings WHERE id=%s",
                            (meeting_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["info"] = policy.loads(d.pop("info_json", ""))
        d["analysis"] = policy.loads(d.pop("analysis_json", ""))
        d.pop("shingles", None)
        return d

    def list_meetings(self, limit: int = 500) -> List[dict]:
        cols = ", ".join(policy.LIST_COLS)
        with self._con() as con:
            rows = con.execute(
                f"SELECT {cols} FROM meetings "
                "ORDER BY (date='') ASC, date DESC, added_at DESC LIMIT %s",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def transcript(self, meeting_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                'SELECT idx, start, end_s AS "end", text, speaker FROM segments '
                "WHERE meeting_id=%s ORDER BY idx", (meeting_id,)).fetchall()
        return [{"start": r["start"], "end": r["end"], "text": r["text"],
                 "speaker": r["speaker"] or None} for r in rows]

    def forget(self, meeting_id: str) -> bool:
        """Real foreign keys do here what the desk does by hand — segments,
        issue links, paper and roll calls all cascade. Events are deliberately
        not foreign keys and outlive their meeting, on both stores."""
        with self._con() as con:
            hit = con.execute("SELECT id FROM meetings WHERE id=%s",
                              (meeting_id,)).fetchone()
            if not hit:
                return False
            con.execute(
                "DELETE FROM issue_documents WHERE doc_id IN "
                "(SELECT id FROM documents WHERE meeting_id=%s)", (meeting_id,))
            con.execute("DELETE FROM documents WHERE meeting_id=%s", (meeting_id,))
            con.execute("DELETE FROM meetings WHERE id=%s", (meeting_id,))
        return True

    # -- segments ----------------------------------------------------------

    @staticmethod
    def _vec(text: str):
        """The lexical vector for a piece of text, or None when it has no
        direction at all. A segment that is pure filler ("I think so, you
        know.") embeds to zeros; the desk stores those zeros and skips them on
        read, and here they must be NULL, because cosine distance against a
        zero vector is undefined and one NaN silently poisons an HNSW sort."""
        v = embed.embed(text)
        if v is None:
            return None
        return v if float(v @ v) > 0 else None

    def replace_segments(self, meeting_id: str, segments: List[dict]) -> int:
        with self._con() as con:
            town = (con.execute("SELECT town FROM meetings WHERE id=%s",
                                (meeting_id,)).fetchone() or {}).get("town", "")
            con.execute("DELETE FROM segments WHERE meeting_id=%s", (meeting_id,))
            for i, s in enumerate(segments):
                text = str(s.get("text", ""))
                con.execute(
                    "INSERT INTO segments (meeting_id, town, idx, start, end_s, "
                    "text, speaker, emb) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (meeting_id, town, i, float(s.get("start", 0.0)),
                     float(s.get("end", 0.0)), text, s.get("speaker") or "",
                     self._vec(text)))
        return len(segments)

    _SEG_COLS = ('s.id, s.meeting_id, s.idx, s.start, s.end_s AS "end", s.text, '
                 's.speaker, s.emb, m.date, m.town')

    def live_segments(self, town: str = "") -> List[dict]:
        sql = (f"SELECT {self._SEG_COLS} FROM segments s "
               "JOIN meetings m ON m.id=s.meeting_id WHERE m.status='live'")
        args: list = []
        if town:
            sql += " AND m.town=%s"
            args.append(town)
        sql += " ORDER BY s.meeting_id, s.idx"
        with self._con() as con:
            rows = con.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def segments_of(self, meeting_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                f"SELECT {self._SEG_COLS} FROM segments s "
                "JOIN meetings m ON m.id=s.meeting_id WHERE s.meeting_id=%s "
                "ORDER BY s.idx", (meeting_id,)).fetchall()
        return [dict(r) for r in rows]

    def live_towns(self) -> List[str]:
        with self._con() as con:
            rows = con.execute(
                "SELECT DISTINCT town FROM meetings WHERE status='live' "
                "AND town<>'' ORDER BY town").fetchall()
        return [r["town"] for r in rows]

    # -- dedupe ------------------------------------------------------------

    def find_by_url_canon(self, url_canon: str) -> Optional[dict]:
        if not url_canon:
            return None
        with self._con() as con:
            r = con.execute("SELECT id FROM meetings WHERE url_canon=%s",
                            (url_canon,)).fetchone()
        return self.get_meeting(r["id"]) if r else None

    def find_by_hash(self, source_hash: str) -> Optional[dict]:
        if not source_hash:
            return None
        with self._con() as con:
            r = con.execute("SELECT id FROM meetings WHERE source_hash=%s",
                            (source_hash,)).fetchone()
        return self.get_meeting(r["id"]) if r else None

    def find_by_shingles(self, shingles: str,
                         threshold: float = 0.9) -> Optional[dict]:
        """Tier three: the same meeting posted at a second URL. The candidate
        scan is the store's business; the boundary is `policy.jaccard_hit`, so
        0.90476 means the same thing on both stores."""
        want = set(shingles.split())
        if not want:
            return None
        with self._con() as con:
            rows = con.execute(
                "SELECT id, shingles FROM meetings "
                "WHERE shingles<>'' AND status='live'").fetchall()
        for r in rows:
            if policy.jaccard_hit(want, set((r["shingles"] or "").split()),
                                  threshold):
                return self.get_meeting(r["id"])
        return None

    # -- search ------------------------------------------------------------

    def search(self, q: str, limit: int = 60, town: str = "",
               space: str = "lexical", body: str = "") -> List[dict]:
        """Words and meaning, blended, with the provenance the reader is shown.

        `town` is not optional in practice: the API layer always passes it, and
        a hosted record that forgets to is a cross-tenant leak. It defaults to
        empty only so the signature matches the desk's.

        `body` scopes to one public body, and it belongs down here rather than
        in the reader for the same reason the static index scopes before its
        own cut: filtering a finished result set means the limit was spent on
        rows the reader had already said they did not want, so a scoped search
        silently returns fewer hits than it found. The reader's two filters and
        this signature now agree."""
        q = (q or "").strip()
        if not q:
            return []
        keyword_hits = [{**dict(r), "score": score}
                        for r, score in policy.rank_scores(
                            self._keyword_rows(q, limit, town, body))]
        by_kw = {h["seg_id"] for h in keyword_hits}
        vector_hits = []
        qvec = self._query_vec(q, space)
        if qvec is not None:
            for row, sim in self._vector_rows(qvec, limit, town, space,
                                              body):
                if sim <= policy.VECTOR_FLOOR:
                    continue
                hit = dict(row)
                if hit["seg_id"] in by_kw:
                    hit = next(h for h in keyword_hits
                               if h["seg_id"] == hit["seg_id"])
                vector_hits.append((hit, sim))
        hits = policy.blend(keyword_hits, vector_hits, limit)
        if space == "neural":
            # The neural half found what the lexical vector could not; the
            # reader is told which, rather than being handed one merged number.
            for h in hits:
                if h["why"] == "related":
                    h["why"] = "meaning"
        return hits

    def semantic(self, qvec, limit: int = 40, town: str = "",
                 space: str = "lexical") -> List[dict]:
        if qvec is None:
            return []
        out = []
        for row, sim in self._vector_rows(qvec, limit, town, space):
            if sim > policy.VECTOR_FLOOR:
                out.append({**dict(row), "score": round(sim, 4)})
        return out

    def _query_vec(self, q: str, space: str):
        if space == "neural":
            from . import embed_neural
            return embed_neural.embed_query(q)
        return self._vec(q)

    def _keyword_rows(self, q: str, limit: int, town: str = "",
                      body: str = "") -> List[dict]:
        """One query, hit envelope and all. `to_tsquery` with `:*` prefixes is
        the same shape as FTS5's `"tok"*`, built from the same tokenizer; the
        ORDER BY is DESC because ts_rank_cd is positive where bm25 is negative,
        and getting that backwards would silently return the worst matches."""
        toks = policy.query_tokens(q)
        if not toks:
            return []
        tsq = " & ".join(f"{t}:*" for t in toks)
        sql = (f"SELECT {_HIT_COLS} FROM segments s "
               "JOIN meetings m ON m.id=s.meeting_id "
               "WHERE s.fts @@ to_tsquery('english', %s) "
               "AND m.status='live'")
        args: list = [tsq]
        if town:
            sql += " AND m.town=%s"
            args.append(town)
        if body:
            sql += " AND m.body=%s"
            args.append(body)
        sql += (" ORDER BY ts_rank_cd(s.fts, to_tsquery('english', %s)) DESC, "
                "s.id LIMIT %s")
        args += [tsq, limit]
        with self._con() as con:
            try:
                return [dict(r) for r in con.execute(sql, args).fetchall()]
            except self._psycopg.errors.SyntaxError:
                # A query whose tokens tsquery will not parse; fall back to the
                # scan rather than 500. ILIKE, not LIKE: SQLite's LIKE is
                # case-insensitive and Postgres's is not, and a silently
                # case-sensitive fallback is a search that quietly finds less.
                con.rollback()
                return self._like_rows(q, limit, town, body)

    def _like_rows(self, q: str, limit: int, town: str = "",
                   body: str = "") -> List[dict]:
        sql = (f"SELECT {_HIT_COLS} FROM segments s "
               "JOIN meetings m ON m.id=s.meeting_id "
               "WHERE s.text ILIKE %s AND m.status='live'")
        args: list = [f"%{q}%"]
        if town:
            sql += " AND m.town=%s"
            args.append(town)
        if body:
            sql += " AND m.body=%s"
            args.append(body)
        sql += " ORDER BY s.meeting_id, s.id LIMIT %s"
        args.append(limit)
        with self._con() as con:
            return [dict(r) for r in con.execute(sql, args).fetchall()]

    def _vector_rows(self, qvec, limit: int, town: str = "",
                     space: str = "lexical", body: str = ""):
        """Nearest neighbours by cosine, through the HNSW index — and it takes
        a subquery to keep the index in play.

        The obvious query is one SELECT: join segments to meetings, filter,
        `ORDER BY emb_neural <=> q LIMIT k`. It is also a trap. The planner
        cannot push an ordered index scan through the join, so it computes the
        distance for **every** embedded segment and top-N sorts the lot.
        Measured on the live record: 2s became 45s the moment the LIMIT crossed
        the index's reach, on the same query, with nothing else running — a
        cliff, which is what made it read as contention until the numbers were
        taken twice.

        So the vector ordering runs in a subquery over `segments` alone, where
        the HNSW index is the only sensible plan and returns `k` candidates
        instead of scanning eighty thousand. Every filter — `status`, `town`,
        `body` — lives on `meetings` and applies *outside* the subquery, after
        the index has chosen, so the subquery over-fetches to cover what the
        outer filter drops. This is the standard approximate-NN-with-post-filter
        shape: under a tight scope it may return fewer than `k`, which is honest
        — the index looked at a bounded neighbourhood and that is what was in it.

        The filter must be `m.town`, never the `town` denormalised onto
        segments. That column lags a steward's town correction — two parity
        tests exist because it does — and the lexical path already scopes on
        `m.town`, so the two halves of one search have to agree on which town a
        meeting is in.

        `SET LOCAL` scopes `ef_search` to the transaction, so a pooled
        connection never carries one search's tuning into the next; it is capped
        at the parameter's own ceiling, above which Postgres refuses the value
        rather than clamping it."""
        col = "emb_neural" if space == "neural" else "emb"

        # Over-fetch whenever a filter can thin the candidates after the index
        # has chosen them. status='live' matches nearly everything; town and
        # body can each be selective, so their presence earns the wider pull.
        overfetch = HNSW_SCOPE_OVERFETCH if (town or body) else 1
        inner_limit = int(limit) * overfetch
        ef = min(HNSW_EF_MAX, max(HNSW_EF_MIN, inner_limit * HNSW_EF_FACTOR))

        outer_where = "m.status='live'"
        outer_args: list = []
        if town:
            outer_where += " AND m.town=%s"
            outer_args.append(town)
        if body:
            outer_where += " AND m.body=%s"
            outer_args.append(body)

        sql = (
            f"SELECT {_HIT_COLS}, 1 - (s.{col} <=> %s) AS sim FROM ("
            f"  SELECT * FROM segments s WHERE s.{col} IS NOT NULL "
            f"  ORDER BY s.{col} <=> %s LIMIT %s"
            f") s JOIN meetings m ON m.id=s.meeting_id "
            f"WHERE {outer_where} "
            f"ORDER BY s.{col} <=> %s LIMIT %s")
        # %s order, left to right: the sim vector in SELECT; the inner block's
        # order-by vector and limit; the outer block's filters (town?, body?),
        # order-by vector, and limit. Assembled in exactly that order.
        args = [qvec, qvec, inner_limit] + outer_args + [qvec, limit]
        with self._con() as con:
            con.execute(f"SET LOCAL hnsw.ef_search = {ef}")
            rows = con.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            sim = float(d.pop("sim"))
            out.append((d, sim))
        return out

    # -- stats -------------------------------------------------------------

    def stats(self) -> dict:
        with self._con() as con:
            m = con.execute(
                "SELECT COUNT(*) AS meetings, "
                "COALESCE(SUM(duration),0) AS seconds, "
                "COALESCE(SUM(CASE WHEN status='live' THEN 1 ELSE 0 END),0) AS live, "
                "COUNT(DISTINCT NULLIF(town,'')) AS towns, "
                "COUNT(DISTINCT NULLIF(body,'')) AS bodies "
                "FROM meetings").fetchone()
            segs = con.execute("SELECT COUNT(*) AS n FROM segments").fetchone()
            iss = con.execute(
                "SELECT COUNT(*) AS n FROM issues WHERE status='active'").fetchone()
            thr = con.execute("SELECT COUNT(*) AS n FROM threads").fetchone()
        d = {k: (int(v) if k != "seconds" else float(v)) for k, v in m.items()}
        d["segments"] = int(segs["n"])
        d["fts"] = self.fts
        d["semantic"] = embed.np is not None
        d["issues"] = int(iss["n"])
        d["threads"] = int(thr["n"])
        return d

    # -- issues ------------------------------------------------------------

    def upsert_issue(self, issue: dict) -> None:
        m = dict(issue)
        for col in ("aliases", "keywords", "related"):
            if isinstance(m.get(col), (list, tuple)):
                m[col] = json.dumps(list(m[col]))
        if "centroid" in m and m["centroid"] is not None:
            m["centroid"] = embed.as_vec(m["centroid"])
        self._merge_row("issues", m)

    def link_segments(self, issue_id: str, links: List[tuple]) -> int:
        with self._con() as con:
            for seg_id, meeting_id, score, why in links:
                con.execute(
                    "INSERT INTO issue_segments (issue_id, seg_id, meeting_id, "
                    "score, why) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (issue_id, seg_id) "
                    "DO UPDATE SET score=excluded.score, why=excluded.why",
                    (issue_id, seg_id, meeting_id, float(score), why))
        return len(links)

    def clear_issue_links(self, issue_id: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM issue_segments WHERE issue_id=%s", (issue_id,))

    def clear_meeting_links(self, meeting_id: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM issue_segments WHERE meeting_id=%s",
                        (meeting_id,))

    def linked_seg_ids(self, meeting_id: str) -> set:
        with self._con() as con:
            rows = con.execute(
                "SELECT seg_id FROM issue_segments WHERE meeting_id=%s",
                (meeting_id,)).fetchall()
        return {r["seg_id"] for r in rows}

    def unlink_meeting(self, issue_id: str, meeting_id: str) -> int:
        with self._con() as con:
            cur = con.execute(
                "DELETE FROM issue_segments WHERE issue_id=%s AND meeting_id=%s",
                (issue_id, meeting_id))
            return cur.rowcount

    def recompute_centroid(self, issue_id: str):
        if embed.np is None:
            return None
        with self._con() as con:
            rows = con.execute(
                "SELECT s.emb FROM issue_segments g JOIN segments s ON s.id=g.seg_id "
                "WHERE g.issue_id=%s AND s.emb IS NOT NULL", (issue_id,)).fetchall()
        cen = policy.centroid_of([embed.as_vec(r["emb"]) for r in rows], embed.np)
        if cen is None:
            return None
        self.upsert_issue({"id": issue_id, "centroid": cen})
        return cen

    def issue_keywords(self, active_only: bool = True) -> List[dict]:
        sql = ("SELECT id, town, name, keywords, aliases, centroid, status, origin "
               "FROM issues")
        if active_only:
            sql += " WHERE status IN ('active','candidate')"
        with self._con() as con:
            rows = con.execute(sql).fetchall()
        return [{"id": r["id"], "town": r["town"], "name": r["name"],
                 "status": r["status"], "origin": r["origin"],
                 "keywords": policy.loads(r["keywords"]) or [],
                 "aliases": policy.loads(r["aliases"]) or [],
                 "centroid": embed.as_vec(r["centroid"])} for r in rows]

    def get_issue(self, issue_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM issues WHERE id=%s",
                            (issue_id,)).fetchone()
        return self._issue_dict(r) if r else None

    def list_issues(self, town: str = "", status: str = "active",
                    limit: int = 300) -> List[dict]:
        """The desk groups by `i.id` alone and selects `t.id IS NOT NULL`
        beside it. Postgres recognises functional dependency on a primary key,
        so `i.*` is fine — but `t.id` comes from a LEFT JOIN and is not, so it
        joins the GROUP BY. Same rows, same order, legal grammar."""
        where = ["i.status=%s"]
        args: list = [status]
        if town:
            where.append("i.town=%s")
            args.append(town)
        with self._con() as con:
            rows = con.execute(
                "SELECT i.id, i.town, i.name, i.name_origin, i.aliases, i.status, "
                "i.origin, i.note, "
                "COUNT(DISTINCT g.meeting_id) AS n_meetings, "
                "COUNT(g.seg_id) AS n_segments, "
                "MIN(NULLIF(m.date,'')) AS first_seen, "
                "MAX(NULLIF(m.date,'')) AS last_seen, "
                "(t.id IS NOT NULL) AS following "
                "FROM issues i "
                "LEFT JOIN issue_segments g ON g.issue_id=i.id "
                "LEFT JOIN meetings m ON m.id=g.meeting_id "
                "LEFT JOIN threads t ON t.issue_id=i.id "
                "WHERE " + " AND ".join(where) +
                " GROUP BY i.id, t.id "
                "ORDER BY n_meetings DESC, n_segments DESC, i.name LIMIT %s",
                args + [limit]).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["aliases"] = policy.loads(d.pop("aliases", "")) or []
            d["following"] = bool(d.get("following"))
            d["n_meetings"] = int(d["n_meetings"])
            d["n_segments"] = int(d["n_segments"])
            out.append(d)
        return out

    def issue_appearances(self, issue_id: str) -> List[dict]:
        """The long view's spine. The desk writes `SELECT DISTINCT … ORDER BY
        (m.date='')`, which Postgres rejects because the sort expression is not
        in the select list — so the flag is selected and dropped, rather than
        the ordering being changed. Bead order is `start`, and load-bearing:
        `issues.delta` slices `beads[:3]` and describes what it finds."""
        with self._con() as con:
            meets = con.execute(
                "SELECT DISTINCT g.meeting_id, m.title, m.date, m.body, m.town, "
                "m.url, m.source_kind, m.video_id, m.media_path, m.duration, "
                "(m.date='') AS _blank, m.added_at AS _added "
                "FROM issue_segments g JOIN meetings m ON m.id=g.meeting_id "
                "WHERE g.issue_id=%s ORDER BY _blank ASC, m.date, _added",
                (issue_id,)).fetchall()
            nodes = []
            for mt in meets:
                beads = con.execute(
                    'SELECT s.id AS seg_id, s.start AS t, s.end_s AS "end", '
                    "s.text, s.speaker, g.score, g.why FROM issue_segments g "
                    "JOIN segments s ON s.id=g.seg_id "
                    "WHERE g.issue_id=%s AND g.meeting_id=%s ORDER BY s.start",
                    (issue_id, mt["meeting_id"])).fetchall()
                node = {k: v for k, v in dict(mt).items()
                        if not k.startswith("_")}
                node["beads"] = [dict(b) for b in beads]
                node["n"] = len(beads)
                nodes.append(node)
        return nodes

    def set_issue_status(self, issue_id: str, status: str) -> None:
        self.upsert_issue({"id": issue_id, "status": status})

    def rename_issue(self, issue_id: str, name: str,
                     aliases: Optional[list] = None) -> Optional[dict]:
        patch = {"id": issue_id, "name": name, "name_origin": "steward",
                 "origin": "steward"}
        if aliases is not None:
            patch["aliases"] = aliases
            patch["keywords"] = policy.keyword_set(name, aliases)
        self.upsert_issue(patch)
        return self.get_issue(issue_id)

    def merge_issues(self, src_ids: List[str], dst_id: str) -> Optional[dict]:
        """Fold sources into a destination. The desk uses `UPDATE OR IGNORE`
        followed by a DELETE, which has no Postgres equivalent — the rewrite is
        "move the links that would not collide, then drop the rest", which is
        exactly what OR IGNORE meant. Getting this wrong loses or duplicates a
        steward's most consequential verb, so it is spelled out."""
        dst = self.get_issue(dst_id)
        if not dst:
            return None
        aliases = list(dst.get("aliases") or [])
        with self._con() as con:
            for sid in src_ids:
                if sid == dst_id:
                    continue
                s = con.execute("SELECT aliases FROM issues WHERE id=%s",
                                (sid,)).fetchone()
                if s:
                    aliases += policy.loads(s["aliases"]) or []
                con.execute(
                    "UPDATE issue_segments g SET issue_id=%s WHERE issue_id=%s "
                    "AND NOT EXISTS (SELECT 1 FROM issue_segments d "
                    "WHERE d.issue_id=%s AND d.seg_id=g.seg_id)",
                    (dst_id, sid, dst_id))
                con.execute("DELETE FROM issue_segments WHERE issue_id=%s", (sid,))
                con.execute(
                    "UPDATE issue_documents g SET issue_id=%s WHERE issue_id=%s "
                    "AND NOT EXISTS (SELECT 1 FROM issue_documents d "
                    "WHERE d.issue_id=%s AND d.chunk_id=g.chunk_id)",
                    (dst_id, sid, dst_id))
                con.execute("DELETE FROM issue_documents WHERE issue_id=%s", (sid,))
                con.execute(
                    "UPDATE threads t SET issue_id=%s WHERE issue_id=%s "
                    "AND NOT EXISTS (SELECT 1 FROM threads d WHERE d.issue_id=%s)",
                    (dst_id, sid, dst_id))
                con.execute("DELETE FROM threads WHERE issue_id=%s", (sid,))
                con.execute(
                    "UPDATE issues SET status='merged', merged_into=%s, "
                    "updated_at=%s WHERE id=%s", (dst_id, time.time(), sid))
        aliases = policy.dedupe_keep_order(aliases)
        self.upsert_issue({"id": dst_id, "aliases": aliases,
                           "keywords": policy.keyword_set(dst["name"], aliases),
                           "origin": "steward"})
        self.recompute_centroid(dst_id)
        return self.get_issue(dst_id)

    def delete_issue(self, issue_id: str) -> bool:
        with self._con() as con:
            hit = con.execute("SELECT id FROM issues WHERE id=%s",
                              (issue_id,)).fetchone()
            if not hit:
                return False
            con.execute("DELETE FROM events WHERE issue_id=%s", (issue_id,))
            con.execute("DELETE FROM issues WHERE id=%s", (issue_id,))
        return True

    def clear_auto_issues(self, town: str = "") -> int:
        sql = ("SELECT id FROM issues WHERE origin='auto' AND status<>'merged' "
               + ("AND town=%s " if town else "") +
               "AND id NOT IN (SELECT issue_id FROM threads)")
        with self._con() as con:
            rows = con.execute(sql, (town,) if town else ()).fetchall()
            ids = [r["id"] for r in rows]
            for iid in ids:
                con.execute("DELETE FROM events WHERE issue_id=%s", (iid,))
                con.execute("DELETE FROM issues WHERE id=%s", (iid,))
        return len(ids)

    # -- threads + events --------------------------------------------------

    def follow(self, issue_id: str) -> Optional[dict]:
        iss = self.get_issue(issue_id)
        if not iss:
            return None
        now = time.time()
        with self._con() as con:
            con.execute(
                "INSERT INTO threads (id, issue_id, last_seen_date, added_at, "
                "updated_at) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (issue_id) DO NOTHING",
                ("thread:" + issue_id, issue_id, iss.get("last_seen") or "",
                 now, now))
        return self.get_thread(issue_id)

    def unfollow(self, issue_id: str) -> bool:
        with self._con() as con:
            cur = con.execute("DELETE FROM threads WHERE issue_id=%s", (issue_id,))
            return cur.rowcount > 0

    def get_thread(self, issue_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM threads WHERE issue_id=%s",
                            (issue_id,)).fetchone()
        return dict(r) if r else None

    def list_threads(self) -> List[dict]:
        """`threads.issue_id` is UNIQUE but not the primary key, and Postgres
        infers functional dependency only from a primary key — so the group is
        by `t.id` (which is the key) plus the issue columns it selects."""
        with self._con() as con:
            rows = con.execute(
                "SELECT t.id AS thread_id, t.issue_id, t.last_seen_date, "
                "i.name, i.town, i.status, "
                "COUNT(DISTINCT g.meeting_id) AS n_meetings, "
                "COUNT(g.seg_id) AS n_segments, "
                "MIN(NULLIF(m.date,'')) AS first_seen, "
                "MAX(NULLIF(m.date,'')) AS last_seen, "
                "(SELECT COUNT(*) FROM events e WHERE e.issue_id=t.issue_id "
                " AND e.seen=0) AS unseen "
                "FROM threads t JOIN issues i ON i.id=t.issue_id "
                "LEFT JOIN issue_segments g ON g.issue_id=t.issue_id "
                "LEFT JOIN meetings m ON m.id=g.meeting_id "
                "GROUP BY t.id, t.issue_id, t.last_seen_date, i.name, i.town, "
                "i.status ORDER BY unseen DESC, last_seen DESC NULLS LAST").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("n_meetings", "n_segments", "unseen"):
                d[k] = int(d[k])
            out.append(d)
        return out

    def add_event(self, kind: str, issue_id: str = "", meeting_id: str = "",
                  thread_id: str = "", payload: Optional[dict] = None) -> int:
        """`cur.lastrowid` does not exist in psycopg; RETURNING does."""
        with self._con() as con:
            r = con.execute(
                "INSERT INTO events (kind, issue_id, meeting_id, thread_id, "
                "payload, added_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (kind, issue_id, meeting_id, thread_id,
                 json.dumps(payload or {}), time.time())).fetchone()
            return int(r["id"])

    def list_events(self, unseen_only: bool = False, limit: int = 100) -> List[dict]:
        sql = ("SELECT e.*, i.name AS issue_name FROM events e "
               "LEFT JOIN issues i ON i.id=e.issue_id")
        if unseen_only:
            sql += " WHERE e.seen=0"
        sql += " ORDER BY e.added_at DESC LIMIT %s"
        with self._con() as con:
            rows = con.execute(sql, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = policy.loads(d.get("payload", "")) or {}
            out.append(d)
        return out

    def unseen_count(self) -> int:
        with self._con() as con:
            r = con.execute("SELECT COUNT(*) AS n FROM events WHERE seen=0").fetchone()
        return int(r["n"])

    def mark_seen(self, issue_id: str = "") -> int:
        with self._con() as con:
            if issue_id:
                cur = con.execute(
                    "UPDATE events SET seen=1 WHERE issue_id=%s AND seen=0",
                    (issue_id,))
            else:
                cur = con.execute("UPDATE events SET seen=1 WHERE seen=0")
            return cur.rowcount

    def advance_thread(self, issue_id: str, last_seen_date: str) -> None:
        with self._con() as con:
            con.execute(
                "UPDATE threads SET last_seen_date=%s, updated_at=%s "
                "WHERE issue_id=%s", (last_seen_date, time.time(), issue_id))

    # -- documents ---------------------------------------------------------

    def upsert_document(self, d: dict) -> None:
        self._merge_row("documents", d)

    def replace_doc_chunks(self, doc_id: str, chunks: List[dict]) -> int:
        with self._con() as con:
            row = con.execute(
                "SELECT meeting_id, town FROM documents WHERE id=%s",
                (doc_id,)).fetchone()
            mid = row["meeting_id"] if row else ""
            town = row["town"] if row else ""
            con.execute("DELETE FROM doc_chunks WHERE doc_id=%s", (doc_id,))
            for i, c in enumerate(chunks):
                text = str(c.get("text", ""))
                con.execute(
                    "INSERT INTO doc_chunks (doc_id, meeting_id, town, idx, "
                    "page, text, emb) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (doc_id, mid, town, i, int(c.get("page", 0)), text,
                     self._vec(text)))
            con.execute("UPDATE documents SET n_chunks=%s, updated_at=%s "
                        "WHERE id=%s", (len(chunks), time.time(), doc_id))
        return len(chunks)

    def get_document(self, doc_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM documents WHERE id=%s",
                            (doc_id,)).fetchone()
        return dict(r) if r else None

    def list_documents(self, town: str = "", meeting_id: str = "",
                       limit: int = 300) -> List[dict]:
        sql, args = "SELECT * FROM documents", []
        conds = []
        if town:
            conds.append("town=%s")
            args.append(town)
        if meeting_id:
            conds.append("meeting_id=%s")
            args.append(meeting_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY (date='') ASC, date DESC, added_at DESC LIMIT %s"
        args.append(limit)
        with self._con() as con:
            rows = con.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def doc_chunks_of(self, doc_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT id, doc_id, meeting_id, idx, page, text, emb "
                "FROM doc_chunks WHERE doc_id=%s ORDER BY idx",
                (doc_id,)).fetchall()
        return [dict(r) for r in rows]

    def forget_document(self, doc_id: str) -> bool:
        with self._con() as con:
            hit = con.execute("SELECT id FROM documents WHERE id=%s",
                              (doc_id,)).fetchone()
            if not hit:
                return False
            con.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        return True

    def link_doc_chunks(self, issue_id: str, links: List[tuple]) -> int:
        with self._con() as con:
            for chunk_id, doc_id, score, why in links:
                con.execute(
                    "INSERT INTO issue_documents (issue_id, chunk_id, doc_id, "
                    "score, why) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (issue_id, chunk_id) "
                    "DO UPDATE SET score=excluded.score, why=excluded.why",
                    (issue_id, chunk_id, doc_id, float(score), why))
        return len(links)

    def clear_doc_links(self, doc_id: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM issue_documents WHERE doc_id=%s", (doc_id,))

    def issue_paper(self, issue_id: str) -> List[dict]:
        with self._con() as con:
            docs = con.execute(
                "SELECT DISTINCT g.doc_id, d.meeting_id, d.town, d.kind, "
                "d.title, d.date, d.url, d.source, d.pages, "
                "(d.date='') AS _blank, d.added_at AS _added "
                "FROM issue_documents g JOIN documents d ON d.id=g.doc_id "
                "WHERE g.issue_id=%s AND d.status='live' "
                "ORDER BY _blank ASC, d.date, _added", (issue_id,)).fetchall()
            nodes = []
            for dr in docs:
                cites = con.execute(
                    "SELECT c.id AS chunk_id, c.page, c.text, g.score, g.why "
                    "FROM issue_documents g JOIN doc_chunks c ON c.id=g.chunk_id "
                    "WHERE g.issue_id=%s AND g.doc_id=%s ORDER BY c.idx",
                    (issue_id, dr["doc_id"])).fetchall()
                node = {k: v for k, v in dict(dr).items() if not k.startswith("_")}
                node["cites"] = [dict(c) for c in cites]
                node["n"] = len(cites)
                nodes.append(node)
        return nodes

    # -- votes -------------------------------------------------------------

    def replace_votes(self, meeting_id: str, votes: List[dict]) -> int:
        now = time.time()
        with self._con() as con:
            con.execute("DELETE FROM votes WHERE meeting_id=%s", (meeting_id,))
            for v in votes:
                roll = v.get("roll") or []
                if not isinstance(roll, str):
                    roll = json.dumps(roll)
                con.execute(
                    "INSERT INTO votes (meeting_id, t, motion, outcome, tally, "
                    "roll, origin, added_at, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (meeting_id, float(v.get("t", 0)),
                     str(v.get("motion", ""))[:400], str(v.get("outcome", "")),
                     str(v.get("tally", "")), roll,
                     str(v.get("origin", "extractive")), now, now))
        return len(votes)

    def votes_of(self, meeting_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM votes WHERE meeting_id=%s ORDER BY t",
                (meeting_id,)).fetchall()
        return [self._vote_dict(r) for r in rows]

    def all_votes(self, town: str = "") -> List[dict]:
        sql = ("SELECT v.*, m.title, m.date, m.body, m.town, m.video_id, "
               "m.source_kind, (m.date='') AS _blank "
               "FROM votes v JOIN meetings m ON m.id=v.meeting_id "
               "WHERE m.status='live'")
        args: list = []
        if town:
            sql += " AND m.town=%s"
            args.append(town)
        sql += " ORDER BY _blank ASC, m.date, v.t"
        with self._con() as con:
            rows = con.execute(sql, args).fetchall()
        return [self._vote_dict(r) for r in rows]

    def _vote_dict(self, r) -> dict:
        d = {k: v for k, v in dict(r).items() if not k.startswith("_")}
        d["roll"] = policy.loads(d.get("roll", "")) or []
        return d

    # -- helpers -----------------------------------------------------------

    def _issue_dict(self, r) -> dict:
        d = dict(r)
        d["aliases"] = policy.loads(d.pop("aliases", "")) or []
        d["keywords"] = policy.loads(d.pop("keywords", "")) or []
        d["related"] = policy.loads(d.pop("related", "")) or []
        d.pop("centroid", None)
        with self._con() as con:
            roll = con.execute(
                "SELECT COUNT(DISTINCT g.meeting_id) AS n_meetings, "
                "COUNT(g.seg_id) AS n_segments, MIN(NULLIF(m.date,'')) AS first_seen, "
                "MAX(NULLIF(m.date,'')) AS last_seen FROM issue_segments g "
                "JOIN meetings m ON m.id=g.meeting_id WHERE g.issue_id=%s",
                (r["id"],)).fetchone()
        d.update({k: (roll[k] if roll else None) for k in
                  ("n_meetings", "n_segments", "first_seen", "last_seen")})
        d["n_meetings"] = int(d["n_meetings"] or 0)
        d["n_segments"] = int(d["n_segments"] or 0)
        d["following"] = self.get_thread(r["id"]) is not None
        return d


def Settings_redacted(dsn: str) -> str:
    from .settings import Settings
    return Settings(dsn=dsn).redacted()


def submission_id(key: str) -> str:
    """A short, opaque, path-safe id for a submission.

    The obvious id is the canonical URL, and it works right up until the URL is
    one `web.canon` could not reduce — canon falls back to `url:<the whole
    thing>`, slashes and query string included, and an id like that cannot
    survive being a path segment: `/api/steward/submissions/<id>/approve`
    silently 404s, so a steward's approve button stops working for exactly the
    submissions that were unusual enough to need review.

    So the id is a digest and the URL lives in its own column, where the unique
    index does the deduping. Stable across processes (blake2b, not Python's
    salted hash), because it is written down."""
    import hashlib
    digest = hashlib.blake2b((key or "").encode("utf-8"), digest_size=8).hexdigest()
    return f"sub:{digest}"
