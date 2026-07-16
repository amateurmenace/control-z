"""Background jobs: thread workers, optional persistent SQLite queue.

Two modes, one class:

- ``JobManager()`` — in-memory, jobs start immediately. The per-tool
  micro-UIs (pivot.app) keep exactly the old behavior.
- ``JobManager(db_path=…, queued=True)`` — the suite: FIFO worker, persistent
  history that survives restarts, cooperative cancel, update listeners
  (the WebSocket bridge subscribes here).

Cancel is cooperative: long loops call ``job.check_cancel()`` (or test
``job.cancel_requested``) once per frame and clean up after themselves.
Honesty rule: a job interrupted by an app quit is recorded as exactly that.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class JobCancelled(Exception):
    """Raised inside a job fn when cancel was requested (not an error)."""


# The kinds we raise on purpose, each carrying a sentence someone wrote. An
# OSError raised by the OS has errno set; one of ours (raise OSError("…")) does
# not — that's how we tell a written sentence from a system code below.
_WRITTEN = (RuntimeError, ValueError, OSError)


def _sentence(e: BaseException) -> str:
    """The job error as the UI shows it: a sentence, never a bare code. The
    traceback still prints to the console for whoever is debugging."""
    msg = str(e).strip()
    if isinstance(e, OSError) and e.errno is not None:
        what = (e.strerror or msg or "the operation failed").rstrip(".")
        where = f": {e.filename}" if e.filename else ""
        return f"the system wouldn't allow it — {what.lower()}{where}."
    if isinstance(e, _WRITTEN) and msg:
        return msg
    if msg:
        return f"this stopped on an unexpected {e.__class__.__name__} — {msg}"
    return (f"this stopped on an unexpected {e.__class__.__name__} that came "
            "with no message — the console has the traceback.")


class _Con:
    """sqlite3 connection that commits AND closes on context exit."""

    def __init__(self, path: str):
        self.con = sqlite3.connect(path, timeout=5)

    def __enter__(self):
        return self.con

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.con.commit()
        finally:
            self.con.close()
        return False


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"          # queued | running | done | error | cancelled
    progress: float = 0.0            # 0..1 when knowable, else -1
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    tool: str = ""                   # which tool owns it (suite queue grouping)
    label: str = ""                  # human line, e.g. "clip.mov → 9:16 ProRes"
    created_at: float = 0.0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, repr=False)

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def check_cancel(self):
        if self._cancel.is_set():
            raise JobCancelled()

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status,
                "progress": self.progress, "message": self.message,
                "result": self.result, "error": self.error,
                "tool": self.tool, "label": self.label,
                "created_at": self.created_at, "started_at": self.started_at,
                "finished_at": self.finished_at}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    tool TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    result TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL
);
"""


class JobManager:
    def __init__(self, db_path: Optional[str] = None, queued: bool = False):
        self._jobs: Dict[str, Job] = {}
        self._fns: Dict[str, Callable[[Job], Any]] = {}
        self._lock = threading.Lock()
        self._listeners: List[Callable[[dict], None]] = []
        self._snapshots: Dict[str, tuple] = {}   # id -> last flushed state
        self._queued = queued
        self._db_path = str(db_path) if db_path else None
        self._queue: "queue.Queue[str]" = queue.Queue()
        if self._db_path:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._db() as con:
                con.executescript(_SCHEMA)
                # jobs left mid-flight by a quit are recorded as exactly that
                con.execute(
                    "UPDATE jobs SET status='error', "
                    "error='interrupted — the app quit while this was running', "
                    "finished_at=? WHERE status IN ('running','queued')",
                    (time.time(),))
        if queued:
            self._worker = threading.Thread(target=self._work_loop, daemon=True)
            self._worker.start()
            self._flusher = threading.Thread(target=self._flush_loop, daemon=True)
            self._flusher.start()

    # -- public API -----------------------------------------------------------

    def start(self, kind: str, fn: Callable[[Job], Any], tool: str = "",
              label: str = "") -> Job:
        job = Job(id=uuid.uuid4().hex[:10], kind=kind, progress=-1,
                  tool=tool, label=label, created_at=time.time())
        with self._lock:
            self._jobs[job.id] = job
        if self._queued:
            job.status = "queued"
            job.message = "queued"
            self._fns[job.id] = fn
            self._flush(job)
            self._queue.put(job.id)
        else:
            # legacy immediate mode — unchanged behavior for the micro-UIs
            t = threading.Thread(target=self._run, args=(job, fn), daemon=True)
            job._thread = t
            t.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status not in ("queued", "running"):
            return False
        job._cancel.set()
        if job.status == "queued":
            job.status = "cancelled"
            job.message = "cancelled before it started"
            job.finished_at = time.time()
            self._flush(job)
        return True

    def list(self, limit: int = 200) -> List[dict]:
        """Active + finished jobs, newest first. History from DB when persistent."""
        with self._lock:
            live = {j.id: j.to_dict() for j in self._jobs.values()}
        rows: List[dict] = []
        if self._db_path:
            with self._db() as con:
                cur = con.execute(
                    "SELECT id, kind, tool, label, status, progress, message, "
                    "result, error, created_at, started_at, finished_at "
                    "FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
                for r in cur.fetchall():
                    d = {"id": r[0], "kind": r[1], "tool": r[2], "label": r[3],
                         "status": r[4], "progress": r[5], "message": r[6],
                         "result": json.loads(r[7]) if r[7] else None,
                         "error": r[8], "created_at": r[9], "started_at": r[10],
                         "finished_at": r[11]}
                    rows.append(live.pop(d["id"], d))  # live state wins
        out = list(live.values()) + rows
        out.sort(key=lambda d: d["created_at"] or 0, reverse=True)
        return out[:limit]

    def on_update(self, cb: Callable[[dict], None]):
        """cb(job_dict) fires on state transitions and throttled progress."""
        self._listeners.append(cb)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values()
                       if j.status in ("queued", "running"))

    def active(self, tool: Optional[str] = None) -> List[Job]:
        """Jobs still queued or running, optionally only one tool's — callers
        that are about to delete something a job is writing into ask first."""
        with self._lock:
            return [j for j in self._jobs.values()
                    if j.status in ("queued", "running")
                    and (tool is None or j.tool == tool)]

    def clear_finished(self) -> int:
        """Drop finished jobs from history (memory + DB). Active jobs stay."""
        done = ("done", "error", "cancelled")
        with self._lock:
            gone = [jid for jid, j in self._jobs.items() if j.status in done]
            for jid in gone:
                del self._jobs[jid]
                self._snapshots.pop(jid, None)
        n = len(gone)
        if self._db_path:
            with self._db() as con:
                cur = con.execute(
                    "DELETE FROM jobs WHERE status IN ('done','error','cancelled')")
                n = max(n, cur.rowcount)
        return n

    # -- internals ------------------------------------------------------------

    def _db(self):
        """One short-lived connection per operation; commits and closes."""
        return _Con(self._db_path)

    def _run(self, job: Job, fn: Callable[[Job], Any]):
        job.status = "running"
        job.started_at = time.time()
        job.message = job.message if job.message not in ("", "queued") else "running"
        self._flush(job)
        try:
            # a fn that finishes its work is "done" even if cancel raced the
            # last frame — fns signal a real early stop by raising JobCancelled
            job.result = fn(job)
            job.status = "done"
            job.progress = 1.0
        except JobCancelled:
            job.status = "cancelled"
            job.message = "cancelled"
        except Exception as e:  # surfaced to the UI, never swallowed
            job.status = "error"
            job.error = _sentence(e)
            traceback.print_exc()
        job.finished_at = time.time()
        self._flush(job)

    def _work_loop(self):
        while True:
            job_id = self._queue.get()
            job = self.get(job_id)
            fn = self._fns.pop(job_id, None)
            if job is None or fn is None or job.status != "queued":
                continue  # cancelled while waiting
            self._run(job, fn)

    def _flush_loop(self):
        """Persist + broadcast progress of running jobs a few times a second."""
        while True:
            time.sleep(0.3)
            with self._lock:
                running = [j for j in self._jobs.values() if j.status == "running"]
            for j in running:
                snap = (j.status, round(j.progress, 4), j.message)
                if self._snapshots.get(j.id) != snap:
                    self._flush(j)

    def _flush(self, job: Job):
        self._snapshots[job.id] = (job.status, round(job.progress, 4), job.message)
        if self._db_path:
            d = job.to_dict()
            try:
                result = json.dumps(d["result"], default=str) if d["result"] is not None else None
            except (TypeError, ValueError):
                result = None
            with self._db() as con:
                con.execute(
                    "INSERT INTO jobs (id, kind, tool, label, status, progress, "
                    "message, result, error, created_at, started_at, finished_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                    "progress=excluded.progress, message=excluded.message, "
                    "result=excluded.result, error=excluded.error, "
                    "started_at=excluded.started_at, finished_at=excluded.finished_at",
                    (d["id"], d["kind"], d["tool"], d["label"], d["status"],
                     d["progress"], d["message"], result, d["error"],
                     d["created_at"], d["started_at"], d["finished_at"]))
        payload = job.to_dict()
        for cb in list(self._listeners):
            try:
                cb(payload)
            except Exception:
                pass
