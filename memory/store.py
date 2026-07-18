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

from . import embed

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
"""

# columns that are big or JSON — kept out of the light list view
_HEAVY = {"info_json", "analysis_json", "shingles", "summary"}


class Corpus:
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
            if exists:
                cols = [k for k in m if k != "id"]
                if cols:
                    sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=?"
                    con.execute(f"UPDATE meetings SET {sets} WHERE id=?",
                                [m[c] for c in cols] + [now, m["id"]])
            else:
                m = {"added_at": now, "updated_at": now, **m}
                cols = list(m)
                con.execute(
                    f"INSERT INTO meetings ({', '.join(cols)}) "
                    f"VALUES ({', '.join('?' for _ in cols)})",
                    [m[c] for c in cols])
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
            have = set((r["shingles"] or "").split())
            if not have:
                continue
            inter = len(want & have)
            union = len(want | have)
            if union and inter / union >= threshold:
                return self.get_meeting(r["id"])
        return None

    # -- search ------------------------------------------------------------

    def search(self, q: str, limit: int = 60) -> List[dict]:
        """Cross-corpus search: FTS keyword hits, blended with related-language
        (vector) hits, every hit time-coded to a segment for jump-to-play."""
        q = (q or "").strip()
        if not q:
            return []
        by_id: dict = {}
        # 1) keyword — exact, ordered by relevance
        for seg, score in self._keyword(q, limit):
            by_id[seg["id"]] = {**self._hit(seg), "score": score, "why": "word"}
        # 2) related language — vector neighbours the words missed
        qvec = embed.embed(q)
        for seg_id, sim in self._semantic(qvec, limit):
            if seg_id in by_id:
                by_id[seg_id]["score"] = max(by_id[seg_id]["score"], sim)
                by_id[seg_id]["why"] = "both"
            else:
                seg = self._segment(seg_id)
                if seg:
                    by_id[seg_id] = {**self._hit(seg), "score": round(sim, 4),
                                     "why": "related"}
        hits = sorted(by_id.values(), key=lambda h: h["score"], reverse=True)
        return hits[:limit]

    def semantic(self, qvec, limit: int = 40) -> List[dict]:
        """Vector-only search — the context API's prior-appearances feed."""
        out = []
        for seg_id, sim in self._semantic(qvec, limit):
            seg = self._segment(seg_id)
            if seg:
                out.append({**self._hit(seg), "score": round(sim, 4)})
        return out

    def _keyword(self, q: str, limit: int):
        with self._con() as con:
            if self.fts and _fts_query(q):
                rows = con.execute(
                    "SELECT s.* FROM segments_fts f JOIN segments s "
                    "ON s.id=f.seg_id WHERE segments_fts MATCH ? "
                    "ORDER BY bm25(segments_fts, 1, 1, 8) LIMIT ?",
                    (_fts_query(q), limit)).fetchall()
            else:
                like = f"%{q}%"
                rows = con.execute(
                    "SELECT * FROM segments WHERE text LIKE ? "
                    "ORDER BY meeting_id LIMIT ?", (like, limit)).fetchall()
        n = len(rows) or 1
        # bm25 order → a descending 1.0..~0.5 score so keyword beats vector ties
        return [(r, round(1.0 - 0.5 * i / n, 4)) for i, r in enumerate(rows)]

    def _semantic(self, qvec, limit: int):
        if qvec is None or embed.np is None:
            return []
        mat, ids = self._matrix()
        if mat is None or not len(ids):
            return []
        sims = mat @ qvec
        k = min(limit, len(ids))
        top = sims.argsort()[::-1][:k]
        return [(ids[i], float(sims[i])) for i in top if sims[i] > 0.05]

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
            "media_path, duration FROM meetings WHERE id=?",
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
        return d

    # -- helpers -----------------------------------------------------------

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


_MEETING_COLS = [
    "id", "town", "body", "title", "date", "url", "url_canon", "source_kind",
    "video_id", "media_path", "duration", "uploader", "origin", "n_segments",
    "n_speakers", "status", "error", "source_hash", "shingles", "info_json",
    "analysis_json", "summary", "summary_origin", "added_at", "updated_at",
]


def _loads(s: str):
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def _fts_query(q: str) -> str:
    import re
    toks = [t for t in re.findall(r"\w+", q) if t]
    return " ".join(f'"{t}"*' for t in toks)
