"""The control-z app shell: FastAPI + local-only server + background jobs.

Every standalone tool serves a hand-written HTML UI at 127.0.0.1:<port>
(double-click app wraps it in a pywebview window; --serve exposes it to a lab
browser). No cloud, no accounts, no telemetry — covenant.
"""

from .jobs import Job, JobCancelled, JobManager
from .server import create_app, run

__all__ = ["Job", "JobCancelled", "JobManager", "create_app", "run"]
