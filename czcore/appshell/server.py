"""FastAPI factory + launcher shared by every control-z tool."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def create_app(tool_name: str, static_dir: Path, register: Callable):
    """register(app, jobs) adds the tool's routes; static_dir holds index.html."""
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from .jobs import JobManager

    app = FastAPI(title=f"control-z {tool_name}", docs_url=None, redoc_url=None)
    jobs = JobManager()

    @app.get("/api/job/{job_id}")
    def job_status(job_id: str):
        j = jobs.get(job_id)
        return j.to_dict() if j else {"error": "unknown job"}

    register(app, jobs)

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


def run(app, port: int = 8330, open_window: bool = False, host: str = "127.0.0.1"):
    import uvicorn

    if open_window:  # packaged double-click path; --serve skips it
        try:
            import threading

            import webview  # pywebview

            def serve():
                uvicorn.run(app, host=host, port=port, log_level="warning")

            threading.Thread(target=serve, daemon=True).start()
            webview.create_window(app.title, f"http://{host}:{port}")
            webview.start()
            return
        except ImportError:
            pass
    print(f"control-z — open http://{host}:{port} in your browser (Ctrl-C to quit)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
