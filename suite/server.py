"""The suite server: one FastAPI app, one job queue, one frame service.

Local only (127.0.0.1), no accounts, no telemetry — covenant. The UI is a
single page served from suite/static; tools register namespaced routes.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# NOTE: fastapi names used in ANNOTATIONS (WebSocket) must be module-level —
# with `from __future__ import annotations`, FastAPI resolves type hints
# against module globals; a function-local import silently un-types the
# websocket param and every /ws connect gets a 403. Learned the hard way.
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from czcore.appshell.jobs import JobManager

from . import __version__
from .frames import FrameService
from .sessions import Session, app_support

STATIC = Path(__file__).parent / "static"


def create_suite_app():
    from czcore.media import presets_report, probe
    from czcore.tools import ToolNotFound

    # job updates arrive on worker threads; they need the serving loop to hand
    # the send off to, and the only place that knows it is a running server
    sockets: set = set()
    loop_box: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop_box["loop"] = asyncio.get_running_loop()
        yield
        loop_box.clear()

    app = FastAPI(title="control-z Suite", docs_url=None, redoc_url=None,
                  lifespan=lifespan)
    jobs = JobManager(db_path=str(app_support() / "jobs.db"), queued=True)
    frames = FrameService()
    session = Session()

    app.state.jobs = jobs
    app.state.frames = frames
    app.state.session = session

    # -- job events over WebSocket ---------------------------------------------

    async def _send_all(payload: dict):
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)

    def _on_job_update(job_dict: dict):
        loop = loop_box.get("loop")
        if loop is not None and sockets:
            asyncio.run_coroutine_threadsafe(
                _send_all({"type": "job", "job": job_dict}), loop)

    jobs.on_update(_on_job_update)

    @app.websocket("/ws")
    async def ws_events(ws: WebSocket):
        await ws.accept()
        sockets.add(ws)
        try:
            await ws.send_json({"type": "hello", "jobs": jobs.list(limit=50)})
            while True:
                await ws.receive_text()  # keepalive pings from the client
        except WebSocketDisconnect:
            pass
        finally:
            sockets.discard(ws)

    # -- app/session -------------------------------------------------------------

    @app.get("/api/app")
    def api_app():
        import platform
        return {"version": __version__, "platform": platform.system(),
                "presets": presets_report()}

    @app.get("/api/session")
    def api_session():
        return session.snapshot()

    @app.post("/api/session")
    def api_session_patch(body: dict = Body(...)):
        session.patch(body)
        return {"ok": True}

    # -- media ---------------------------------------------------------------------

    @app.post("/api/media/open")
    def api_media_open(body: dict = Body(...)):
        path = str(Path(body.get("path", "").strip()).expanduser())
        tool = body.get("tool", "")
        p = Path(path)
        if not p.is_file():
            return JSONResponse(
                {"error": f"no such file: {p}"}, status_code=404)
        try:
            info = probe(str(p))
        except ToolNotFound as e:
            # A missing dependency is OUR failure, not the file's — labeling
            # it 415 "couldn't read that file" blamed the wrong thing on
            # every open (specs/09 §5, "failures are sentences" inverted).
            return JSONResponse({"error": str(e)}, status_code=500)
        except Exception as e:
            return JSONResponse(
                {"error": f"couldn't read that file as media: {e}"},
                status_code=415)
        v = info.video
        session.add_recent(str(p), tool)
        n_frames = None
        if v:
            n_frames = v.nb_frames or (
                int(info.duration * v.fps) if v.fps and info.duration else None)
        field = next((s.get("field_order") for s in info.raw.get("streams", [])
                      if s.get("codec_type") == "video"), None)
        return {
            "path": str(p), "name": p.name, "duration": info.duration,
            "container": info.container, "timecode": info.timecode,
            "audio_streams": info.audio_streams,
            "video": None if not v else {
                "width": v.width, "height": v.height, "fps": v.fps,
                "codec": v.codec, "pix_fmt": v.pix_fmt,
                "n_frames_estimate": n_frames,
                "field_order": field or "untagged",
            },
            "sidecars": {
                "pivot": p.with_suffix(".pivot.json").exists(),
            },
        }

    @app.post("/api/media/reveal")
    def api_media_reveal(body: dict = Body(...)):
        """Show a finished file where it landed — Finder on the Mac, the
        file manager elsewhere. Refuses paths that don't exist rather than
        opening an empty window."""
        import subprocess
        p = Path(str(body.get("path", "")).strip()).expanduser()
        if not p.exists():
            return JSONResponse({"error": f"nothing at {p} to reveal"},
                                status_code=404)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(p)], check=True, timeout=10)
            elif sys.platform.startswith("win"):
                subprocess.run(["explorer", "/select,", str(p)], timeout=10)
            else:
                subprocess.run(["xdg-open", str(p.parent)], check=True,
                               timeout=10)
        except Exception as e:
            return JSONResponse({"error": f"couldn't open the file browser "
                                          f"({e.__class__.__name__})"},
                                status_code=500)
        return {"ok": True}

    @app.get("/api/media/frame")
    def api_media_frame(path: str, i: int, h: int = 540):
        p = str(Path(path).expanduser())
        if not Path(p).is_file():
            return JSONResponse({"error": "file moved or deleted"}, status_code=404)
        h = max(54, min(1080, int(h)))
        f = frames.frame_path(p, max(0, int(i)), height=h)
        if f is None:
            return JSONResponse(
                {"error": f"frame {i} is past the end of this clip"},
                status_code=404)
        return FileResponse(f, media_type="image/jpeg",
                            headers={"Cache-Control": "max-age=3600"})

    # -- jobs -------------------------------------------------------------------------

    @app.get("/api/jobs")
    def api_jobs():
        return jobs.list(limit=200)

    @app.get("/api/job/{job_id}")
    def api_job(job_id: str):
        j = jobs.get(job_id)
        if j:
            return j.to_dict()
        for row in jobs.list(limit=500):
            if row["id"] == job_id:
                return row
        return JSONResponse({"error": "unknown job"}, status_code=404)

    @app.post("/api/jobs/{job_id}/cancel")
    def api_job_cancel(job_id: str):
        ok = jobs.cancel(job_id)
        return {"ok": ok} if ok else JSONResponse(
            {"error": "job already finished (or unknown)"}, status_code=409)

    # -- export presets ------------------------------------------------------------------

    @app.get("/api/export/presets")
    def api_export_presets():
        return presets_report()

    # -- native file dialog (pywebview window mode only) ---------------------------------

    @app.post("/api/dialog/open-file")
    def api_dialog():
        try:
            import webview
            if webview.windows:
                result = webview.windows[0].create_file_dialog(
                    webview.OPEN_DIALOG, allow_multiple=True)
                return {"paths": list(result or [])}
        except ImportError:
            pass
        return JSONResponse(
            {"error": "native file dialog needs the app window — "
                      "in a browser, paste a path instead"},
            status_code=501)

    # -- tools ----------------------------------------------------------------------------

    from .tools.clear import register_clear
    from .tools.depth import register_depth
    from .tools.grabber import register_grabber
    from .tools.highlighter import register_highlighter
    from .tools.indexer import register_indexer
    from .tools.modelstore import register_modelstore
    from .tools.ofx import register_ofx
    from .tools.pivot import register_pivot
    from .tools.rise import register_rise
    from .tools.scribe import register_scribe
    from .tools.settings import register_settings
    from .tools.slate import register_slate
    from .tools.stencil import register_stencil

    register_clear(app, jobs, frames)
    register_depth(app, jobs, frames)
    register_grabber(app, jobs, frames)
    register_highlighter(app, jobs, frames)
    register_indexer(app, jobs, frames)
    register_modelstore(app, jobs, frames)
    register_ofx(app, jobs, frames)
    register_pivot(app, jobs, frames)
    register_rise(app, jobs, frames)
    register_scribe(app, jobs, frames)
    register_settings(app, jobs, frames)
    register_slate(app, jobs, frames)
    register_stencil(app, jobs, frames)

    # -- static UI (registered last so /api wins) ------------------------------------------

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def run(app, port: int = 8300, open_window: bool = True, host: str = "127.0.0.1"):
    import uvicorn

    if open_window:
        try:
            import threading

            import webview

            def serve():
                uvicorn.run(app, host=host, port=port, log_level="warning")

            threading.Thread(target=serve, daemon=True).start()
            webview.create_window("control-z Suite", f"http://{host}:{port}",
                                  width=1480, height=940, min_size=(1100, 700))
            webview.start()
            return
        except ImportError:
            pass
    print(f"control-z Suite — open http://{host}:{port} (Ctrl-C to quit)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
