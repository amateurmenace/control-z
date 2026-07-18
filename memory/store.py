"""The corpus: one SQLite file under media_dir("memory"), the record itself.

Meetings and their diarized segments are the relational core (the spec's
Postgres, translated to SQLite per PARALLEL — issues↔segments↔meetings are
join-heavy and SQLite is honest about that). FTS5 carries keyword search when
the build has it (this one does), LIKE when it doesn't. Segment vectors live in
a blob column beside the text — the spec's Qdrant, translated to "local
embeddings beside the store."

Threading, the indexer's way: the Corpus object holds only a path and a couple
of flags; every operation opens its own short-lived connection. WAL mode lets
the pipeline job write while page requests read. Nothing is shared across
threads but the file.

Dedupe is three-tier, exactly as the submissions contract asks: canonical
source URL, then media hash, then transcript-shingle similarity. The first two
are cheap and run before a job is queued; the third runs once the words exist.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from czcore.paths import media_dir

from . import embed, policy

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    town TEXT DEFAULT '', body TEXT DEFAULT '', title TEXT DEFAULT '',
    date TEXT DEFAULT '',
    url TEXT DEFAULT '', url_canon TEXT DEFAULT '',
    source_kind TEXT DEFAULT '', video_id TEXT DEFAULT '',
    media_path TEXT DEFAULT '', duration REAL DEFAULT 0,
    uploader TEXT DEFAULT '', origin TEXT DEFAULT '',
    n_segments INTEGER DEFAULT 0, n_speakers INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued', error TEXT DEFAULT '',
    source_hash TEXT DEFAULT '', shingles TEXT DEFAULT '',
    info_json TEXT DEFAULT '', analysis_json TEXT DEFAULT '',
    summary TEXT DEFAULT '', summary_origin TEXT DEFAULT '',
    added_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL, idx INTEGER,
    start REAL, end REAL, text TEXT DEFAULT '', speaker TEXT DEFAULT '',
    emb BLOB);
CREATE INDEX IF NOT EXISTS idx_seg_meeting ON segments(meeting_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- the telescope's own objects: issues tracked across meetings, the threads
-- that follow them, and the events (resurfacings) a thread wakes up for.
CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    town TEXT DEFAULT '', name TEXT DEFAULT '',
    name_origin TEXT DEFAULT 'extractive',   -- extractive | ai:<model>
    aliases TEXT DEFAULT '',                  -- JSON list, the names it goes by
    keywords TEXT DEFAULT '',                 -- JSON list, what a segment must say
    related TEXT DEFAULT '',                  -- JSON list, its vocabulary (display)
    centroid BLOB,                            -- mean of member vectors, for ranking
    status TEXT DEFAULT 'active',             -- active | candidate | merged
    origin TEXT DEFAULT 'auto',               -- auto | minted | steward
    merged_into TEXT DEFAULT '', note TEXT DEFAULT '',
    added_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS issue_segments (
    issue_id TEXT NOT NULL, seg_id INTEGER NOT NULL,
    meeting_id TEXT NOT NULL, score REAL DEFAULT 0, why TEXT DEFAULT '',
    PRIMARY KEY (issue_id, seg_id));
CREATE INDEX IF NOT EXISTS idx_isg_issue ON issue_segments(issue_id);
CREATE INDEX IF NOT EXISTS idx_isg_meeting ON issue_segments(meeting_id);
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY, issue_id TEXT NOT NULL UNIQUE,
    last_seen_date TEXT DEFAULT '', added_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
    issue_id TEXT DEFAULT '', meeting_id TEXT DEFAULT '', thread_id TEXT DEFAULT '',
    seen INTEGER DEFAULT 0, payload TEXT DEFAULT '', added_at REAL);
CREATE INDEX IF NOT EXISTS idx_evt_issue ON events(issue_id);

-- the town's own paper: documents fetched from the portal the town publishes
-- on, chunked and linked into the record so what was WRITTEN sits beside what
-- was SAID. The PDF bytes stay on disk beside the corpus; chunks carry page
-- numbers so every citation reads "p. 12", never "somewhere in the packet".
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    meeting_id TEXT DEFAULT '', town TEXT DEFAULT '',
    kind TEXT DEFAULT '',                    -- Agenda | Agenda Packet | Minutes | …
    title TEXT DEFAULT '', date TEXT DEFAULT '',
    url TEXT DEFAULT '',                     -- the portal URL it was fetched from
    source TEXT DEFAULT '',                  -- civicclerk:<tenant> | file
    pages INTEGER DEFAULT 0, n_chunks INTEGER DEFAULT 0,
    sha256 TEXT DEFAULT '',                  -- of the fetched bytes (the receipt)
    status TEXT DEFAULT 'live', error TEXT DEFAULT '',
    added_at REAL, updated_at REAL);
CREATE INDEX IF NOT EXISTS idx_doc_meeting ON documents(meeting_id);
CREATE TABLE IF NOT EXISTS doc_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL, meeting_id TEXT DEFAULT '',
    idx INTEGER DEFAULT 0, page INTEGER DEFAULT 0,
    text TEXT DEFAULT '', emb BLOB);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON doc_chunks(doc_id);
CREATE TABLE IF NOT EXISTS issue_documents (
    issue_id TEXT NOT NULL, chunk_id INTEGER NOT NULL,
    doc_id TEXT NOT NULL, score REAL DEFAULT 0, why TEXT DEFAULT '',
    PRIMARY KEY (issue_id, chunk_id));
CREATE INDEX IF NOT EXISTS idx_idoc_issue ON issue_documents(issue_id);
CREATE INDEX IF NOT EXISTS idx_idoc_doc ON issue_documents(doc_id);

-- the vote ledger: roll calls read straight off the transcript, verbatim and
-- timestamped — a record of what was moved and who said yes, never a guess
-- about what anyone believes. Officials only, by construction: the people in
-- a roll call are the people voting.
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL, t REAL DEFAULT 0,
    motion TEXT DEFAULT '', outcome TEXT DEFAULT '',
    tally TEXT DEFAULT '',                   -- '4–1' when the chair reads it out
    roll TEXT DEFAULT '',                    -- JSON [{name, vote, t, quote}]
    origin TEXT DEFAULT 'extractive',        -- extractive | ai:<model>
    added_at REAL, updated_at REAL);
CREATE INDEX IF NOT EXISTS idx_vote_meeting ON votes(meeting_id);
"""

# The record's rules live in policy.py now, so the Studio's Postgres store
# inherits the same answers instead of re-deciding them. These names stay as
# aliases because this module has always spelled them this way.
_HEAVY = policy.HEAVY
_MEETING_COLS = policy.MEETING_COLS


class Corpus:
    """The desk's store — one SQLite file. Implements `memory.seam.CorpusStore`
    (structurally; the Protocol is not a base class on purpose)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or media_dir("memory") / "corpus.db")
        # one Corpus is shared by every request thread AND the single job
        # worker; the vector cache is one tuple (writes, matrix, ids) so a
        # reader always sees a consistent trio — a single attribute read/write
        # is atomic under the GIL, three separate fields are not.
        self._cache = (-1, None, [])
        with self._con() as con:
            con.executescript(_SCHEMA)
            try:
                con.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5("
                    "meeting_id UNINDEXED, seg_id UNINDEXED, text)")
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False    # search falls back to LIKE, and says so
            con.commit()

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Nothing to release: every operation here opens and closes its own
        connection, and the only shared state is the vector cache. The Studio's
        store returns a pool; the seam asks both the same question."""
        self._cache = (-1, None, [])

    @contextmanager
    def unit(self):
        """A unit of work. SQLite has one writer and WAL already serialises it,
        so this yields immediately and every inner `_con()` behaves exactly as
        it always has — the desk's behavior is untouched by design. It exists
        because the Studio's curation verbs are multi-call sequences that must
        not half-land, and the callers of those sequences live in shared code."""
        yield self

    @contextmanager
    def _con(self):
        """A short-lived connection, committed on clean exit and always closed —
        so a long-running server never accumulates handles."""
        con = sqlite3.connect(self.db_path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # -- meetings ----------------------------------------------------------

    def upsert_meeting(self, m: dict) -> None:
        """Insert or update a meeting row by id. Only the keys present are
        written; omitted columns keep their value (merge, never shrink)."""
        now = time.time()
        with self._con() as con:
            exists = con.execute("SELECT id FROM meetings WHERE id=?",
                                 (m["id"],)).fetchone()
            fresh, cols = policy.merge_plan(m, now)
            if exists:
                if cols:
                    sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=?"
                    con.execute(f"UPDATE meetings SET {sets} WHERE id=?",
                                [m[c] for c in cols] + [now, m["id"]])
            else:
                cols = list(fresh)
                con.execute(
                    f"INSERT INTO meetings ({', '.join(cols)}) "
                    f"VALUES ({', '.join('?' for _ in cols)})",
                    [fresh[c] for c in cols])
            con.commit()

    def set_status(self, meeting_id: str, status: str, error: str = "") -> None:
        with self._con() as con:
            con.execute(
                "UPDATE meetings SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, time.time(), meeting_id))
            con.commit()

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM meetings WHERE id=?",
                            (meeting_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["info"] = _loads(d.pop("info_json", ""))
        d["analysis"] = _loads(d.pop("analysis_json", ""))
        d.pop("shingles", None)
        return d

    def list_meetings(self, limit: int = 500) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT " + ", ".join(
                    c for c in _MEETING_COLS if c not in _HEAVY) +
                " FROM meetings ORDER BY (date='') ASC, date DESC, added_at DESC "
                "LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def transcript(self, meeting_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT idx, start, end, text, speaker FROM segments "
                "WHERE meeting_id=? ORDER BY idx", (meeting_id,)).fetchall()
        return [{"start": r["start"], "end": r["end"], "text": r["text"],
                 "speaker": r["speaker"] or None} for r in rows]

    def forget(self, meeting_id: str) -> bool:
        with self._con() as con:
            hit = con.execute("SELECT id FROM meetings WHERE id=?",
                              (meeting_id,)).fetchone()
            if not hit:
                return False
            if self.fts:
                con.execute("DELETE FROM segments_fts WHERE meeting_id=?",
                            (meeting_id,))
            con.execute("DELETE FROM segments WHERE meeting_id=?", (meeting_id,))
            # nothing cascades — the meeting's paper and its roll calls go too,
            # and so do its issue links. Without this last one the segments go
            # but their issue rows stay, pointing at ids that no longer exist:
            # list_issues LEFT JOINs and counts the ghosts, issue_appearances
            # INNER JOINs and hides them, and the two surfaces disagree about
            # the same issue. An issue's size is what its timeline shows.
            con.execute("DELETE FROM issue_segments WHERE meeting_id=?",
                        (meeting_id,))
            con.execute(
                "DELETE FROM issue_documents WHERE doc_id IN "
                "(SELECT id FROM documents WHERE meeting_id=?)", (meeting_id,))
            con.execute(
                "DELETE FROM doc_chunks WHERE doc_id IN "
                "(SELECT id FROM documents WHERE meeting_id=?)", (meeting_id,))
            con.execute("DELETE FROM documents WHERE meeting_id=?", (meeting_id,))
            con.execute("DELETE FROM votes WHERE meeting_id=?", (meeting_id,))
            con.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
            self._bump(con)
            con.commit()
        return True

    # -- segments ----------------------------------------------------------

    def replace_segments(self, meeting_id: str, segments: List[dict]) -> int:
        """Swap in a meeting's segments (delete-then-insert), building the FTS
        row and the vector for each. Idempotent: re-ingesting overwrites."""
        with self._con() as con:
            if self.fts:
                con.execute("DELETE FROM segments_fts WHERE meeting_id=?",
                            (meeting_id,))
            con.execute("DELETE FROM issue_segments WHERE meeting_id=?",
                        (meeting_id,))
            con.execute("DELETE FROM segments WHERE meeting_id=?", (meeting_id,))
            for i, s in enumerate(segments):
                text = str(s.get("text", ""))
                cur = con.execute(
                    "INSERT INTO segments "
                    "(meeting_id, idx, start, end, text, speaker, emb) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (meeting_id, i, float(s.get("start", 0.0)),
                     float(s.get("end", 0.0)), text, s.get("speaker") or "",
                     embed.to_bytes(embed.embed(text))))
                if self.fts:
                    con.execute("INSERT INTO segments_fts VALUES (?,?,?)",
                                (meeting_id, cur.lastrowid, text))
            self._bump(con)
            con.commit()
        return len(segments)

    # -- dedupe ------------------------------------------------------------

    def find_by_url_canon(self, url_canon: str) -> Optional[dict]:
        if not url_canon:
            return None
        return self._first("SELECT * FROM meetings WHERE url_canon=?",
                           (url_canon,))

    def find_by_hash(self, source_hash: str) -> Optional[dict]:
        if not source_hash:
            return None
        return self._first("SELECT * FROM meetings WHERE source_hash=?",
                           (source_hash,))

    def find_by_shingles(self, shingles: str,
                         threshold: float = 0.9) -> Optional[dict]:
        """Third-tier dedupe: Jaccard over transcript shingle sets. Catches the
        same meeting posted at a second URL (full feed vs trimmed cut)."""
        want = set(shingles.split())
        if not want:
            return None
        with self._con() as con:
            rows = con.execute(
                "SELECT id, shingles FROM meetings "
                "WHERE shingles!='' AND status='live'").fetchall()
        for r in rows:
            if policy.jaccard_hit(want, set((r["shingles"] or "").split()),
                                  threshold):
                return self.get_meeting(r["id"])
        return None

    # -- search ------------------------------------------------------------

    def search(self, q: str, limit: int = 60, town: str = "") -> List[dict]:
        """Cross-corpus search: FTS keyword hits, blended with related-language
        (vector) hits, every hit time-coded to a segment for jump-to-play.

        `town` scopes the whole search to one town. It defaults to empty — the
        behavior this has always had — but a record serving several towns must
        pass it, and the Studio's API layer always does: aggregation across
        towns is a covenant question, not a convenience."""
        q = (q or "").strip()
        if not q:
            return []
        # 1) keyword — exact, ordered by relevance
        keyword_hits = [{**self._hit(seg), "score": score}
                        for seg, score in self._keyword(q, limit, town)]
        by_kw = {h["seg_id"]: h for h in keyword_hits}
        # 2) related language — vector neighbours the words missed. The matrix
        # is corpus-wide, so a town filter is applied once a hit is resolved;
        # over-fetch so scoping cannot quietly shorten the result.
        qvec = embed.embed(q)
        vector_hits = []
        for seg_id, sim in self._semantic(qvec, limit * 5 if town else limit):
            hit = by_kw.get(seg_id)
            if hit is None:
                seg = self._segment(seg_id)
                hit = self._hit(seg) if seg else None
            if hit is None or hit.get("_status") != "live":
                continue
            if town and hit.get("town") != town:
                continue
            vector_hits.append((hit, sim))
        # the fold — and the provenance the reader is shown — is policy, shared
        hits = policy.blend(keyword_hits, vector_hits, limit)
        for h in hits:
            h.pop("_status", None)
        return hits

    def semantic(self, qvec, limit: int = 40, town: str = "") -> List[dict]:
        """Vector-only search — the context API's prior-appearances feed."""
        out = []
        for seg_id, sim in self._semantic(qvec, limit * 5 if town else limit):
            seg = self._segment(seg_id)
            if not seg:
                continue
            hit = self._hit(seg)
            if hit.pop("_status", "") != "live":
                continue
            if town and hit.get("town") != town:
                continue
            out.append({**hit, "score": round(sim, 4)})
            if len(out) >= limit:
                break
        return out

    def _keyword(self, q: str, limit: int, town: str = ""):
        with self._con() as con:
            if self.fts and _fts_query(q):
                sql = ("SELECT s.* FROM segments_fts f JOIN segments s "
                       "ON s.id=f.seg_id JOIN meetings m ON m.id=s.meeting_id "
                       "WHERE segments_fts MATCH ? AND m.status='live'" +
                       (" AND m.town=?" if town else "") +
                       " ORDER BY bm25(segments_fts, 1, 1, 8) LIMIT ?")
                args = [_fts_query(q)] + ([town] if town else []) + [limit]
                rows = con.execute(sql, args).fetchall()
            else:
                sql = ("SELECT s.* FROM segments s "
                       "JOIN meetings m ON m.id=s.meeting_id "
                       "WHERE s.text LIKE ? AND m.status='live'" +
                       (" AND m.town=?" if town else "") +
                       " ORDER BY s.meeting_id LIMIT ?")
                args = [f"%{q}%"] + ([town] if town else []) + [limit]
                rows = con.execute(sql, args).fetchall()
        # bm25 order → a descending 1.0..~0.5 score so keyword beats vector
        # ties. The store owes an ordering; the numbers are policy's, because
        # bm25 is negative and Postgres's ts_rank_cd is positive and the two
        # can never hand back comparable relevance.
        return policy.rank_scores(rows)

    def _semantic(self, qvec, limit: int):
        if qvec is None or embed.np is None:
            return []
        mat, ids = self._matrix()
        if mat is None or not len(ids):
            return []
        sims = mat @ qvec
        k = min(limit, len(ids))
        top = sims.argsort()[::-1][:k]
        return [(ids[i], float(sims[i])) for i in top
                if sims[i] > policy.VECTOR_FLOOR]

    def _matrix(self):
        writes = self._writes()
        cached = self._cache          # one atomic read → a consistent trio
        if cached[0] == writes:
            return cached[1], cached[2]
        if embed.np is None:
            return None, []
        with self._con() as con:
            rows = con.execute(
                "SELECT id, emb FROM segments "
                "WHERE emb IS NOT NULL AND length(emb)>0").fetchall()
        ids, vecs = [], []
        for r in rows:
            v = embed.from_bytes(r["emb"])
            if v is not None:
                ids.append(r["id"])
                vecs.append(v)
        mat = embed.np.vstack(vecs) if vecs else None
        self._cache = (writes, mat, ids)   # one atomic write; readers see old or new, never a mix
        return mat, ids

    def _segment(self, seg_id: int) -> Optional[sqlite3.Row]:
        return self._first_row("SELECT * FROM segments WHERE id=?", (seg_id,))

    def _hit(self, seg) -> dict:
        m = self._first_row(
            "SELECT id, title, date, body, town, url, source_kind, video_id, "
            "media_path, duration, status FROM meetings WHERE id=?",
            (seg["meeting_id"],))
        info = dict(m) if m else {"id": seg["meeting_id"]}
        return {
            "meeting_id": seg["meeting_id"], "seg_id": seg["id"],
            "t": seg["start"], "end": seg["end"],
            "text": seg["text"], "speaker": seg["speaker"] or None,
            "title": info.get("title", ""), "date": info.get("date", ""),
            "body": info.get("body", ""), "town": info.get("town", ""),
            "url": info.get("url", ""), "source_kind": info.get("source_kind", ""),
            "video_id": info.get("video_id", ""),
            "media_path": info.get("media_path", ""),
            "duration": info.get("duration", 0),
            # not part of the envelope — search filters on it and drops it, so
            # both stores hand back the same seventeen keys.
            "_status": info.get("status", ""),
        }

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
        d = dict(m)
        d["segments"] = segs["n"]
        d["fts"] = self.fts
        d["semantic"] = embed.np is not None
        d["issues"] = self._count(
            "SELECT COUNT(*) AS n FROM issues WHERE status='active'")
        d["threads"] = self._count("SELECT COUNT(*) AS n FROM threads")
        return d

    # -- issues: the telescope's tracked topics ---------------------------

    def live_segments(self, town: str = "") -> List[dict]:
        """Every segment of every live meeting, with its vector and its meeting's
        date/town — the raw material the issue engine clusters over."""
        with self._con() as con:
            rows = con.execute(
                "SELECT s.id, s.meeting_id, s.idx, s.start, s.end, s.text, "
                "s.speaker, s.emb, m.date, m.town FROM segments s "
                "JOIN meetings m ON m.id=s.meeting_id "
                "WHERE m.status='live'" + (" AND m.town=?" if town else "") +
                " ORDER BY s.meeting_id, s.idx",
                (town,) if town else ()).fetchall()
        return [dict(r) for r in rows]

    def segments_of(self, meeting_id: str) -> List[dict]:
        """One meeting's segments with vectors and its date/town — what
        incremental issue assignment matches, without scanning the whole corpus."""
        with self._con() as con:
            rows = con.execute(
                "SELECT s.id, s.meeting_id, s.idx, s.start, s.end, s.text, "
                "s.speaker, s.emb, m.date, m.town FROM segments s "
                "JOIN meetings m ON m.id=s.meeting_id WHERE s.meeting_id=? "
                "ORDER BY s.idx", (meeting_id,)).fetchall()
        return [dict(r) for r in rows]

    def live_towns(self) -> List[str]:
        with self._con() as con:
            rows = con.execute(
                "SELECT DISTINCT town FROM meetings WHERE status='live' "
                "AND town!='' ORDER BY town").fetchall()
        return [r["town"] for r in rows]

    def upsert_issue(self, issue: dict) -> None:
        """Insert or merge an issue by id (merge, never shrink — like meetings).
        `aliases`/`keywords` may be passed as lists; they are stored as JSON.
        `centroid` may be a vector; it is stored as bytes."""
        m = dict(issue)
        for col in ("aliases", "keywords", "related"):
            if isinstance(m.get(col), (list, tuple)):
                m[col] = json.dumps(list(m[col]))
        if "centroid" in m and not isinstance(m["centroid"], (bytes, type(None))):
            m["centroid"] = embed.to_bytes(m["centroid"])
        now = time.time()
        with self._con() as con:
            exists = con.execute("SELECT id FROM issues WHERE id=?",
                                 (m["id"],)).fetchone()
            fresh, cols = policy.merge_plan(m, now)
            if exists:
                if cols:
                    sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=?"
                    con.execute(f"UPDATE issues SET {sets} WHERE id=?",
                                [m[c] for c in cols] + [now, m["id"]])
            else:
                cols = list(fresh)
                con.execute(
                    f"INSERT INTO issues ({', '.join(cols)}) "
                    f"VALUES ({', '.join('?' for _ in cols)})",
                    [fresh[c] for c in cols])
            con.commit()

    def link_segments(self, issue_id: str, links: List[tuple]) -> int:
        """Attach segments to an issue: links is [(seg_id, meeting_id, score, why)].
        Idempotent per (issue, segment) — re-assigning overwrites the score."""
        with self._con() as con:
            for seg_id, meeting_id, score, why in links:
                con.execute(
                    "INSERT INTO issue_segments (issue_id, seg_id, meeting_id, "
                    "score, why) VALUES (?,?,?,?,?) ON CONFLICT(issue_id, seg_id) "
                    "DO UPDATE SET score=excluded.score, why=excluded.why",
                    (issue_id, seg_id, meeting_id, float(score), why))
            con.commit()
        return len(links)

    def clear_issue_links(self, issue_id: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM issue_segments WHERE issue_id=?", (issue_id,))
            con.commit()

    def clear_meeting_links(self, meeting_id: str) -> None:
        """Drop one meeting's issue links — the first step of re-assigning it."""
        with self._con() as con:
            con.execute("DELETE FROM issue_segments WHERE meeting_id=?",
                        (meeting_id,))
            con.commit()

    def linked_seg_ids(self, meeting_id: str) -> set:
        """Which of a meeting's segments already belong to some issue. The
        candidate queue asks this to find what is left over; it used to ask by
        opening the store's own connection and running the SELECT itself."""
        with self._con() as con:
            rows = con.execute(
                "SELECT seg_id FROM issue_segments WHERE meeting_id=?",
                (meeting_id,)).fetchall()
        return {r["seg_id"] for r in rows}

    def unlink_meeting(self, issue_id: str, meeting_id: str) -> int:
        """Detach one meeting's segments from one issue — the second half of
        split, once the new issue has taken them."""
        with self._con() as con:
            cur = con.execute(
                "DELETE FROM issue_segments WHERE issue_id=? AND meeting_id=?",
                (issue_id, meeting_id))
            con.commit()
            return cur.rowcount

    def recompute_centroid(self, issue_id: str):
        """Average the linked segments' vectors into the issue's centroid. Runs
        after assignment so ranking (context, mint) tracks membership."""
        if embed.np is None:
            return None
        with self._con() as con:
            rows = con.execute(
                "SELECT s.emb FROM issue_segments g JOIN segments s ON s.id=g.seg_id "
                "WHERE g.issue_id=? AND s.emb IS NOT NULL AND length(s.emb)>0",
                (issue_id,)).fetchall()
        cen = policy.centroid_of([embed.as_vec(r["emb"]) for r in rows],
                                 embed.np)
        if cen is None:
            return None
        self.upsert_issue({"id": issue_id, "centroid": cen})
        return cen

    def issue_keywords(self, active_only: bool = True) -> List[dict]:
        """Every issue's keyword set + centroid — what incremental assignment
        matches a fresh meeting's segments against."""
        sql = ("SELECT id, town, name, keywords, aliases, centroid, status, origin "
               "FROM issues")
        if active_only:
            sql += " WHERE status IN ('active','candidate')"
        with self._con() as con:
            rows = con.execute(sql).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"], "town": r["town"], "name": r["name"],
                "status": r["status"], "origin": r["origin"],
                "keywords": _loads(r["keywords"]) or [],
                "aliases": _loads(r["aliases"]) or [],
                "centroid": embed.from_bytes(r["centroid"])})
        return out

    def get_issue(self, issue_id: str) -> Optional[dict]:
        with self._con() as con:
            r = con.execute("SELECT * FROM issues WHERE id=?",
                            (issue_id,)).fetchone()
        if not r:
            return None
        return self._issue_dict(r)

    def list_issues(self, town: str = "", status: str = "active",
                    limit: int = 300) -> List[dict]:
        """Issues with their rollups (meetings, segments, span) and whether a
        thread follows them — the browse list and the record's issue rail."""
        where = ["i.status=?"]
        args: list = [status]
        if town:
            where.append("i.town=?"); args.append(town)
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
                " GROUP BY i.id "
                "ORDER BY n_meetings DESC, n_segments DESC, i.name LIMIT ?",
                args + [limit]).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["aliases"] = _loads(d.pop("aliases", "")) or []
            d["following"] = bool(d.get("following"))
            out.append(d)
        return out

    def issue_appearances(self, issue_id: str) -> List[dict]:
        """The long view's spine: one node per meeting the issue appears in, each
        with its time-coded beads (segments) so every node deep-links to play."""
        with self._con() as con:
            meets = con.execute(
                "SELECT DISTINCT g.meeting_id, m.title, m.date, m.body, m.town, "
                "m.url, m.source_kind, m.video_id, m.media_path, m.duration "
                "FROM issue_segments g JOIN meetings m ON m.id=g.meeting_id "
                "WHERE g.issue_id=? ORDER BY (m.date='') ASC, m.date, m.added_at",
                (issue_id,)).fetchall()
            nodes = []
            for mt in meets:
                beads = con.execute(
                    "SELECT s.id AS seg_id, s.start AS t, s.end, s.text, s.speaker, "
                    "g.score, g.why FROM issue_segments g "
                    "JOIN segments s ON s.id=g.seg_id "
                    "WHERE g.issue_id=? AND g.meeting_id=? ORDER BY s.start",
                    (issue_id, mt["meeting_id"])).fetchall()
                node = dict(mt)
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
            kw = _keyword_set(name, aliases)
            patch["aliases"] = aliases
            patch["keywords"] = kw
        self.upsert_issue(patch)
        return self.get_issue(issue_id)

    def merge_issues(self, src_ids: List[str], dst_id: str) -> Optional[dict]:
        """Fold source issues into a destination: their segment links move over,
        their aliases join the destination's, the sources become `merged`
        tombstones that point home (the record remembers its own edits)."""
        dst = self.get_issue(dst_id)
        if not dst:
            return None
        aliases = list(dst.get("aliases") or [])
        with self._con() as con:
            for sid in src_ids:
                if sid == dst_id:
                    continue
                s = con.execute("SELECT aliases FROM issues WHERE id=?",
                                (sid,)).fetchone()
                if s:
                    aliases += _loads(s["aliases"]) or []
                con.execute(
                    "UPDATE OR IGNORE issue_segments SET issue_id=? WHERE issue_id=?",
                    (dst_id, sid))
                con.execute("DELETE FROM issue_segments WHERE issue_id=?", (sid,))
                con.execute(
                    "UPDATE OR IGNORE issue_documents SET issue_id=? WHERE issue_id=?",
                    (dst_id, sid))
                con.execute("DELETE FROM issue_documents WHERE issue_id=?", (sid,))
                # a thread on a source follows the survivor
                con.execute(
                    "UPDATE OR IGNORE threads SET issue_id=? WHERE issue_id=?",
                    (dst_id, sid))
                con.execute("DELETE FROM threads WHERE issue_id=?", (sid,))
                con.execute(
                    "UPDATE issues SET status='merged', merged_into=?, updated_at=? "
                    "WHERE id=?", (dst_id, time.time(), sid))
            con.commit()
        aliases = _dedupe_keep_order(aliases)
        self.upsert_issue({"id": dst_id, "aliases": aliases,
                           "keywords": _keyword_set(dst["name"], aliases),
                           "origin": "steward"})
        self.recompute_centroid(dst_id)
        return self.get_issue(dst_id)

    def delete_issue(self, issue_id: str) -> bool:
        with self._con() as con:
            hit = con.execute("SELECT id FROM issues WHERE id=?",
                              (issue_id,)).fetchone()
            if not hit:
                return False
            con.execute("DELETE FROM issue_segments WHERE issue_id=?", (issue_id,))
            con.execute("DELETE FROM issue_documents WHERE issue_id=?", (issue_id,))
            con.execute("DELETE FROM threads WHERE issue_id=?", (issue_id,))
            con.execute("DELETE FROM events WHERE issue_id=?", (issue_id,))
            con.execute("DELETE FROM issues WHERE id=?", (issue_id,))
            con.commit()
        return True

    def clear_auto_issues(self, town: str = "") -> int:
        """Before a rebuild, drop the machine-made issues nobody follows — but
        keep minted, steward-touched, and followed issues (a rebuild refreshes
        their links, it never forgets a human's work)."""
        with self._con() as con:
            rows = con.execute(
                "SELECT id FROM issues WHERE origin='auto' AND status!='merged' "
                + ("AND town=? " if town else "") +
                "AND id NOT IN (SELECT issue_id FROM threads)",
                (town,) if town else ()).fetchall()
            ids = [r["id"] for r in rows]
            for iid in ids:
                con.execute("DELETE FROM issue_segments WHERE issue_id=?", (iid,))
                con.execute("DELETE FROM issue_documents WHERE issue_id=?", (iid,))
                con.execute("DELETE FROM events WHERE issue_id=?", (iid,))
                con.execute("DELETE FROM issues WHERE id=?", (iid,))
            con.commit()
        return len(ids)

    # -- threads + events: follow an issue, wake for a resurfacing ---------

    def follow(self, issue_id: str) -> Optional[dict]:
        iss = self.get_issue(issue_id)
        if not iss:
            return None
        tid = "thread:" + issue_id
        now = time.time()
        with self._con() as con:
            con.execute(
                "INSERT INTO threads (id, issue_id, last_seen_date, added_at, "
                "updated_at) VALUES (?,?,?,?,?) ON CONFLICT(issue_id) DO NOTHING",
                (tid, issue_id, iss.get("last_seen") or "", now, now))
            con.commit()
        return self.get_thread(issue_id)

    def unfollow(self, issue_id: str) -> bool:
        with self._con() as con:
            cur = con.execute("DELETE FROM threads WHERE issue_id=?", (issue_id,))
            con.commit()
            return cur.rowcount > 0

    def get_thread(self, issue_id: str) -> Optional[dict]:
        r = self._first_row("SELECT * FROM threads WHERE issue_id=?", (issue_id,))
        return dict(r) if r else None

    def list_threads(self) -> List[dict]:
        """Followed issues, each with its rollups and how many resurfacings the
        follower hasn't seen yet — the 'still watching' surface."""
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
                "GROUP BY t.issue_id ORDER BY unseen DESC, last_seen DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def add_event(self, kind: str, issue_id: str = "", meeting_id: str = "",
                  thread_id: str = "", payload: Optional[dict] = None) -> int:
        with self._con() as con:
            cur = con.execute(
                "INSERT INTO events (kind, issue_id, meeting_id, thread_id, "
                "payload, added_at) VALUES (?,?,?,?,?,?)",
                (kind, issue_id, meeting_id, thread_id,
                 json.dumps(payload or {}), time.time()))
            con.commit()
            return cur.lastrowid

    def list_events(self, unseen_only: bool = False, limit: int = 100) -> List[dict]:
        sql = ("SELECT e.*, i.name AS issue_name FROM events e "
               "LEFT JOIN issues i ON i.id=e.issue_id")
        if unseen_only:
            sql += " WHERE e.seen=0"
        sql += " ORDER BY e.added_at DESC LIMIT ?"
        with self._con() as con:
            rows = con.execute(sql, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = _loads(d.get("payload", "")) or {}
            out.append(d)
        return out

    def unseen_count(self) -> int:
        return self._count("SELECT COUNT(*) AS n FROM events WHERE seen=0")

    def mark_seen(self, issue_id: str = "") -> int:
        with self._con() as con:
            if issue_id:
                cur = con.execute(
                    "UPDATE events SET seen=1 WHERE issue_id=? AND seen=0",
                    (issue_id,))
            else:
                cur = con.execute("UPDATE events SET seen=1 WHERE seen=0")
            con.commit()
            return cur.rowcount

    def advance_thread(self, issue_id: str, last_seen_date: str) -> None:
        with self._con() as con:
            con.execute(
                "UPDATE threads SET last_seen_date=?, updated_at=? WHERE issue_id=?",
                (last_seen_date, time.time(), issue_id))
            con.commit()

    # -- documents: the town's own paper, beside what was said -------------

    def upsert_document(self, d: dict) -> None:
        """Insert or update a document row by id (merge, never shrink)."""
        now = time.time()
        with self._con() as con:
            exists = con.execute("SELECT id FROM documents WHERE id=?",
                                 (d["id"],)).fetchone()
            fresh, cols = policy.merge_plan(d, now)
            if exists:
                if cols:
                    sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=?"
                    con.execute(f"UPDATE documents SET {sets} WHERE id=?",
                                [d[c] for c in cols] + [now, d["id"]])
            else:
                cols = list(fresh)
                con.execute(
                    f"INSERT INTO documents ({', '.join(cols)}) "
                    f"VALUES ({', '.join('?' for _ in cols)})",
                    [fresh[c] for c in cols])
            con.commit()

    def replace_doc_chunks(self, doc_id: str, chunks: List[dict]) -> int:
        """Swap in a document's chunks (delete-then-insert), embedding each —
        idempotent like replace_segments. Chunks carry the page they start on
        so every citation names its page."""
        with self._con() as con:
            row = con.execute("SELECT meeting_id FROM documents WHERE id=?",
                              (doc_id,)).fetchone()
            mid = row["meeting_id"] if row else ""
            con.execute("DELETE FROM issue_documents WHERE doc_id=?", (doc_id,))
            con.execute("DELETE FROM doc_chunks WHERE doc_id=?", (doc_id,))
            for i, c in enumerate(chunks):
                text = str(c.get("text", ""))
                con.execute(
                    "INSERT INTO doc_chunks (doc_id, meeting_id, idx, page, "
                    "text, emb) VALUES (?,?,?,?,?,?)",
                    (doc_id, mid, i, int(c.get("page", 0)), text,
                     embed.to_bytes(embed.embed(text))))
            con.execute("UPDATE documents SET n_chunks=?, updated_at=? "
                        "WHERE id=?", (len(chunks), time.time(), doc_id))
            con.commit()
        return len(chunks)

    def get_document(self, doc_id: str) -> Optional[dict]:
        r = self._first_row("SELECT * FROM documents WHERE id=?", (doc_id,))
        return dict(r) if r else None

    def list_documents(self, town: str = "", meeting_id: str = "",
                       limit: int = 300) -> List[dict]:
        sql, args = "SELECT * FROM documents", []
        conds = []
        if town:
            conds.append("town=?")
            args.append(town)
        if meeting_id:
            conds.append("meeting_id=?")
            args.append(meeting_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY (date='') ASC, date DESC, added_at DESC LIMIT ?"
        args.append(limit)
        with self._con() as con:
            rows = con.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def doc_chunks_of(self, doc_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT id, doc_id, meeting_id, idx, page, text, emb "
                "FROM doc_chunks WHERE doc_id=? ORDER BY idx",
                (doc_id,)).fetchall()
        return [dict(r) for r in rows]

    def forget_document(self, doc_id: str) -> bool:
        with self._con() as con:
            hit = con.execute("SELECT id FROM documents WHERE id=?",
                              (doc_id,)).fetchone()
            if not hit:
                return False
            con.execute("DELETE FROM issue_documents WHERE doc_id=?", (doc_id,))
            con.execute("DELETE FROM doc_chunks WHERE doc_id=?", (doc_id,))
            con.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            con.commit()
        return True

    def link_doc_chunks(self, issue_id: str, links: List[tuple]) -> int:
        """Attach document chunks to an issue: links is
        [(chunk_id, doc_id, score, why)] — the paper twin of link_segments."""
        with self._con() as con:
            for chunk_id, doc_id, score, why in links:
                con.execute(
                    "INSERT INTO issue_documents (issue_id, chunk_id, doc_id, "
                    "score, why) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(issue_id, chunk_id) "
                    "DO UPDATE SET score=excluded.score, why=excluded.why",
                    (issue_id, chunk_id, doc_id, float(score), why))
            con.commit()
        return len(links)

    def clear_doc_links(self, doc_id: str) -> None:
        """Drop one document's issue links — the first step of re-linking it."""
        with self._con() as con:
            con.execute("DELETE FROM issue_documents WHERE doc_id=?", (doc_id,))
            con.commit()

    def issue_paper(self, issue_id: str) -> List[dict]:
        """The documents an issue's timeline interleaves: one node per linked
        document, each with its cited chunks (page-numbered) — the written
        record beside the spoken one."""
        with self._con() as con:
            docs = con.execute(
                "SELECT DISTINCT g.doc_id, d.meeting_id, d.town, d.kind, "
                "d.title, d.date, d.url, d.source, d.pages "
                "FROM issue_documents g JOIN documents d ON d.id=g.doc_id "
                "WHERE g.issue_id=? AND d.status='live' "
                "ORDER BY (d.date='') ASC, d.date, d.added_at",
                (issue_id,)).fetchall()
            nodes = []
            for dr in docs:
                cites = con.execute(
                    "SELECT c.id AS chunk_id, c.page, c.text, g.score, g.why "
                    "FROM issue_documents g JOIN doc_chunks c ON c.id=g.chunk_id "
                    "WHERE g.issue_id=? AND g.doc_id=? ORDER BY c.idx",
                    (issue_id, dr["doc_id"])).fetchall()
                node = dict(dr)
                node["cites"] = [dict(c) for c in cites]
                node["n"] = len(cites)
                nodes.append(node)
        return nodes

    # -- the vote ledger: roll calls, verbatim and timestamped -------------

    def replace_votes(self, meeting_id: str, votes: List[dict]) -> int:
        """Swap in a meeting's votes (delete-then-insert, idempotent). Each
        vote: {t, motion, outcome, tally, roll, origin} — roll is a list of
        {name, vote, t, quote} entries, stored as JSON."""
        now = time.time()
        with self._con() as con:
            con.execute("DELETE FROM votes WHERE meeting_id=?", (meeting_id,))
            for v in votes:
                roll = v.get("roll") or []
                if not isinstance(roll, str):
                    roll = json.dumps(roll)
                con.execute(
                    "INSERT INTO votes (meeting_id, t, motion, outcome, tally, "
                    "roll, origin, added_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (meeting_id, float(v.get("t", 0)),
                     str(v.get("motion", ""))[:400], str(v.get("outcome", "")),
                     str(v.get("tally", "")), roll,
                     str(v.get("origin", "extractive")), now, now))
            con.commit()
        return len(votes)

    def votes_of(self, meeting_id: str) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM votes WHERE meeting_id=? ORDER BY t",
                (meeting_id,)).fetchall()
        return [self._vote_dict(r) for r in rows]

    def all_votes(self, town: str = "") -> List[dict]:
        """Every roll call on the record (live meetings), oldest first — the
        raw material of per-member voting records."""
        sql = ("SELECT v.*, m.title, m.date, m.body, m.town, m.video_id, "
               "m.source_kind FROM votes v JOIN meetings m ON m.id=v.meeting_id "
               "WHERE m.status='live'")
        args: list = []
        if town:
            sql += " AND m.town=?"
            args.append(town)
        sql += " ORDER BY (m.date='') ASC, m.date, v.t"
        with self._con() as con:
            rows = con.execute(sql, args).fetchall()
        return [self._vote_dict(r) for r in rows]

    def _vote_dict(self, r) -> dict:
        d = dict(r)
        d["roll"] = _loads(d.get("roll", "")) or []
        return d

    # -- helpers -----------------------------------------------------------

    def _issue_dict(self, r) -> dict:
        d = dict(r)
        d["aliases"] = _loads(d.pop("aliases", "")) or []
        d["keywords"] = _loads(d.pop("keywords", "")) or []
        d["related"] = _loads(d.pop("related", "")) or []
        d.pop("centroid", None)
        roll = self._first_row(
            "SELECT COUNT(DISTINCT g.meeting_id) AS n_meetings, "
            "COUNT(g.seg_id) AS n_segments, MIN(NULLIF(m.date,'')) AS first_seen, "
            "MAX(NULLIF(m.date,'')) AS last_seen FROM issue_segments g "
            "JOIN meetings m ON m.id=g.meeting_id WHERE g.issue_id=?", (r["id"],))
        d.update({k: (roll[k] if roll else None) for k in
                  ("n_meetings", "n_segments", "first_seen", "last_seen")})
        d["n_meetings"] = d["n_meetings"] or 0
        d["n_segments"] = d["n_segments"] or 0
        d["following"] = self.get_thread(r["id"]) is not None
        return d

    def _count(self, sql: str, args=()) -> int:
        r = self._first_row(sql, args)
        return int(r["n"]) if r else 0

    def _writes(self) -> int:
        r = self._first_row("SELECT value FROM meta WHERE key='writes'")
        return int(r["value"]) if r else 0

    @staticmethod
    def _bump(con) -> None:
        con.execute(
            "INSERT INTO meta (key, value) VALUES ('writes','1') "
            "ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")

    def _first(self, sql: str, args=()) -> Optional[dict]:
        r = self._first_row(sql, args)
        if not r:
            return None
        return self.get_meeting(r["id"]) if "id" in r.keys() else dict(r)

    def _first_row(self, sql: str, args=()):
        with self._con() as con:
            return con.execute(sql, args).fetchone()


# The record's judgement calls now live in policy.py, shared with the Studio's
# store. These stay as this module's names for the callers that already use them.
_loads = policy.loads
_dedupe_keep_order = policy.dedupe_keep_order
_keyword_set = policy.keyword_set


def _fts_query(q: str) -> str:
    """FTS5's prefix syntax over the shared tokenizer. Postgres spells the same
    query `tok:*`; the tokens are policy, the punctuation is dialect."""
    return " ".join(f'"{t}"*' for t in policy.query_tokens(q))
