"""Settings page — caches (sizes + clear), store paths, about. Everything on
this page is regenerable; nothing here can lose work.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .. import __version__

CACHES = {
    "frames": ("Preview frames", "suite scrub/filmstrip JPEGs",
               Path.home() / "Library" / "Caches" / "control-z" / "suite" / "frames"),
    "clear": ("Clear audio", "extracted audio, residuals, room tone",
              Path.home() / "Library" / "Caches" / "control-z" / "suite" / "clear"),
    "stencil": ("Stencil mattes", "analysis frames + propagated masks",
                Path.home() / "Library" / "Caches" / "control-z" / "suite" / "stencil"),
    "pivot-legacy": ("Pivot (legacy page)", "the old standalone page's scrub cache",
                     Path.home() / "Library" / "Caches" / "control-z" / "pivot"),
}

# Tools whose running jobs write into each cache — clearing it under them would
# throw away work in progress, so we refuse while one is active. None means any
# tool (every job decodes preview frames); () means no job of ours writes there
# (the legacy page is a separate process with its own cache).
CACHE_OWNERS = {
    "frames": None,
    "clear": ("clear",),
    "stencil": ("stencil",),
    "pivot-legacy": (),
}


def _size(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def register_settings(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore import models as reg
    from ..sessions import app_support

    @app.get("/api/settings/info")
    def api_info():
        return {
            "version": __version__,
            "python": sys.version.split()[0],
            "caches": [{"id": k, "label": v[0], "what": v[1],
                        "path": str(v[2]), "size": _size(v[2])}
                       for k, v in CACHES.items()],
            "model_store": {"path": str(reg.models_dir()),
                            "size": _size(reg.models_dir())},
            "app_support": str(app_support()),
            "jobs_db_size": _size(app_support() / "jobs.db") or (
                (app_support() / "jobs.db").stat().st_size
                if (app_support() / "jobs.db").exists() else 0),
        }

    @app.post("/api/settings/clear-cache")
    def api_clear(body: dict = Body(...)):
        which = body.get("which")
        if which not in CACHES:
            return JSONResponse({"error": f"unknown cache {which!r}"},
                                status_code=422)
        owners = CACHE_OWNERS[which]
        busy = jobs.active() if owners is None else [
            j for t in owners for j in jobs.active(tool=t)]
        if busy:
            what = busy[0].label or busy[0].kind
            return JSONResponse(
                {"error": f"{CACHES[which][0]} is being written to right now by "
                          f"{what} — clearing it would throw that work away. "
                          "Let it finish (or cancel it in the queue) and try again."},
                status_code=409)
        p = CACHES[which][2]
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "note": f"{CACHES[which][0]} cleared — it rebuilds "
                                    "as you work"}

    @app.post("/api/jobs/clear-history")
    def api_clear_history():
        n = jobs.clear_finished()
        return {"ok": True, "removed": n}
