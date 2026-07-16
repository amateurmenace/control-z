"""Thread-backed background jobs with polled progress (simple > clever)."""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"          # running | done | error
    progress: float = 0.0            # 0..1 when knowable, else -1
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    _thread: Optional[threading.Thread] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status,
                "progress": self.progress, "message": self.message,
                "result": self.result, "error": self.error}


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, fn: Callable[[Job], Any]) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], kind=kind, progress=-1)

        def runner():
            try:
                job.result = fn(job)
                job.status = "done"
                job.progress = 1.0
            except Exception as e:  # surfaced to the UI, never swallowed
                job.status = "error"
                job.error = f"{e.__class__.__name__}: {e}"
                traceback.print_exc()

        t = threading.Thread(target=runner, daemon=True)
        job._thread = t
        with self._lock:
            self._jobs[job.id] = job
        t.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)
