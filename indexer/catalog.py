"""The catalog: one SQLite file, FTS5 when the build has it, LIKE when not.

Scan is incremental — a clip is re-probed only when its size/mtime moved,
and re-indexed when its Scribe sidecar does. Files that vanish are kept but
marked missing (archives live on unplugged drives; forgetting them would be
lying about the library).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Callable, List, Optional

from czcore.paths import support_dir

VIDEO_EXTS = {".mov", ".mp4", ".mkv", ".mxf", ".avi", ".m4v", ".mts", ".m2ts",
              ".webm", ".mpg", ".mpeg", ".wmv", ".flv", ".dv"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aif", ".aiff", ".flac"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    path TEXT PRIMARY KEY, added_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS clips (
    path TEXT PRIMARY KEY, folder TEXT NOT NULL, name TEXT NOT NULL,
    size INTEGER, mtime REAL, sidecar_mtime REAL,
    duration REAL, fps REAL, width INTEGER, height INTEGER,
    codec TEXT, audio INTEGER, transcript TEXT DEFAULT '',
    scanned_at REAL, missing INTEGER DEFAULT 0);
"""


class Catalog:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or support_dir("index") / "catalog.db")
        with self._con() as con:
            con.executescript(_SCHEMA)
            try:
                con.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS clips_fts USING fts5("
                    "path UNINDEXED, name, folder, transcript)")
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False  # search falls back to LIKE, and says so

    def _con(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    # -- folders ---------------------------------------------------------

    def add_folder(self, path: str) -> dict:
        p = Path(path).expanduser()
        if not p.is_dir():
            raise ValueError(f"not a folder: {p}")
        with self._con() as con:
            con.execute("INSERT OR IGNORE INTO folders VALUES (?,?)",
                        (str(p), time.time()))
            con.commit()
        return {"path": str(p)}

    def remove_folder(self, path: str, drop_clips: bool = True):
        with self._con() as con:
            con.execute("DELETE FROM folders WHERE path=?", (path,))
            if drop_clips:
                like = path.rstrip("/") + "/%"
                if self.fts:
                    con.execute("DELETE FROM clips_fts WHERE path IN "
                                "(SELECT path FROM clips WHERE path LIKE ?)",
                                (like,))
                con.execute("DELETE FROM clips WHERE path LIKE ?", (like,))
            con.commit()

    def folders(self) -> List[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT f.path, COUNT(c.path) AS clips, "
                "COALESCE(SUM(c.duration),0) AS seconds "
                "FROM folders f LEFT JOIN clips c "
                "ON c.folder=f.path AND c.missing=0 "
                "GROUP BY f.path ORDER BY f.path").fetchall()
        return [dict(r) for r in rows]

    # -- scan --------------------------------------------------------------

    @staticmethod
    def _sidecar_text(p: Path) -> tuple:
        sc = p.with_suffix(".scribe.json")
        if not sc.exists():
            return "", 0.0
        try:
            t = json.loads(sc.read_text())
            text = " ".join(s.get("text", "") for s in t.get("segments", []))
            return text.strip(), sc.stat().st_mtime
        except (ValueError, OSError):
            return "", 0.0

    def scan(self, progress: Optional[Callable[[str], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None) -> dict:
        from czcore.media import probe

        stats = {"seen": 0, "added": 0, "updated": 0, "missing": 0,
                 "unreadable": 0}
        with self._con() as con:
            folders = [r["path"] for r in
                       con.execute("SELECT path FROM folders")]
            known = {r["path"]: r for r in con.execute(
                "SELECT path, size, mtime, sidecar_mtime FROM clips")}
            seen = set()
            for folder in folders:
                for p in sorted(Path(folder).rglob("*")):
                    if cancelled and cancelled():
                        con.commit()
                        return stats
                    ext = p.suffix.lower()
                    if not p.is_file() or ext not in VIDEO_EXTS | AUDIO_EXTS:
                        continue
                    seen.add(str(p))
                    stats["seen"] += 1
                    st = p.stat()
                    text, sc_m = self._sidecar_text(p)
                    old = known.get(str(p))
                    fresh = (old and old["size"] == st.st_size
                             and old["mtime"] == st.st_mtime
                             and (old["sidecar_mtime"] or 0.0) == sc_m)
                    if fresh:
                        con.execute("UPDATE clips SET missing=0 WHERE path=?",
                                    (str(p),))
                        continue
                    if progress:
                        progress(f"{'re-' if old else ''}logging {p.name}")
                    try:
                        info = probe(str(p))
                        v = info.video
                    except Exception:
                        stats["unreadable"] += 1
                        continue
                    row = (str(p), folder, p.name, st.st_size, st.st_mtime,
                           sc_m, info.duration,
                           v.fps if v else None, v.width if v else None,
                           v.height if v else None,
                           v.codec if v else "audio", info.audio_streams,
                           text, time.time(), 0)
                    con.execute(
                        "INSERT INTO clips VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(path) DO UPDATE SET size=excluded.size, "
                        "mtime=excluded.mtime, sidecar_mtime=excluded.sidecar_mtime, "
                        "duration=excluded.duration, fps=excluded.fps, "
                        "width=excluded.width, height=excluded.height, "
                        "codec=excluded.codec, audio=excluded.audio, "
                        "transcript=excluded.transcript, "
                        "scanned_at=excluded.scanned_at, missing=0", row)
                    if self.fts:
                        con.execute("DELETE FROM clips_fts WHERE path=?", (str(p),))
                        con.execute("INSERT INTO clips_fts VALUES (?,?,?,?)",
                                    (str(p), p.name, folder, text))
                    stats["updated" if old else "added"] += 1
            gone = set(known) - seen
            for path in gone:
                con.execute("UPDATE clips SET missing=1 WHERE path=?", (path,))
            stats["missing"] = len(gone)
            con.commit()
        return stats

    # -- search --------------------------------------------------------------

    @staticmethod
    def _fts_query(q: str) -> str:
        toks = [t for t in re.findall(r"\w+", q) if t]
        return " ".join(f'"{t}"*' for t in toks)

    def search(self, q: str, limit: int = 60) -> List[dict]:
        q = (q or "").strip()
        with self._con() as con:
            if not q:
                rows = con.execute(
                    "SELECT * FROM clips ORDER BY mtime DESC LIMIT ?",
                    (limit,)).fetchall()
            elif self.fts and self._fts_query(q):
                rows = con.execute(
                    "SELECT c.* FROM clips_fts f JOIN clips c ON c.path=f.path "
                    "WHERE clips_fts MATCH ? ORDER BY bm25(clips_fts, 0, 8, 2, 1) "
                    "LIMIT ?", (self._fts_query(q), limit)).fetchall()
            else:
                like = f"%{q}%"
                rows = con.execute(
                    "SELECT * FROM clips WHERE name LIKE ? OR folder LIKE ? "
                    "OR transcript LIKE ? ORDER BY mtime DESC LIMIT ?",
                    (like, like, like, limit)).fetchall()
        out = []
        toks = [t.lower() for t in re.findall(r"\w+", q)]
        for r in rows:
            d = {k: r[k] for k in r.keys() if k != "transcript"}
            d["matches"] = self._transcript_hits(r["path"], toks) if toks else []
            d["name_hit"] = any(t in r["name"].lower() for t in toks)
            out.append(d)
        return out

    @staticmethod
    def _transcript_hits(path: str, toks: List[str], cap: int = 3) -> List[dict]:
        """Time-coded snippets, read from the sidecar only for actual hits."""
        if not toks:
            return []
        sc = Path(path).with_suffix(".scribe.json")
        if not sc.exists():
            return []
        try:
            segs = json.loads(sc.read_text()).get("segments", [])
        except (ValueError, OSError):
            return []
        hits = []
        for s in segs:
            low = str(s.get("text", "")).lower()
            if any(t in low for t in toks):
                hits.append({"t": s.get("start", 0.0),
                             "text": s.get("text", "")[:160]})
                if len(hits) >= cap:
                    break
        return hits

    def stats(self) -> dict:
        with self._con() as con:
            r = con.execute(
                "SELECT COUNT(*) AS clips, COALESCE(SUM(duration),0) AS seconds, "
                "COALESCE(SUM(size),0) AS bytes, "
                "SUM(CASE WHEN transcript!='' THEN 1 ELSE 0 END) AS transcribed, "
                "SUM(missing) AS missing FROM clips").fetchone()
            n_folders = con.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
        d = dict(r)
        d["folders"] = n_folders
        d["fts"] = self.fts
        return d

    def get_clips(self, paths: List[str]) -> List[dict]:
        with self._con() as con:
            rows = [con.execute("SELECT * FROM clips WHERE path=?", (p,)).fetchone()
                    for p in paths]
        return [dict(r) for r in rows if r is not None]
