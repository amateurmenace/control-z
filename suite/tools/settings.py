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

    # -- fetch network: the Webshare residential proxy (shared with the
    #    community-highlighter web app — same env var names, one account) ----

    @app.get("/api/settings/proxy")
    def api_proxy_get():
        from czcore import proxy
        return proxy.status()

    @app.post("/api/settings/proxy")
    def api_proxy_set(body: dict = Body(...)):
        from czcore import proxy
        if "relay" in body and "username" not in body:
            return proxy.set_relay(bool(body["relay"]))
        st = proxy.get_config()
        if st["source"] == "env" and body.get("username"):
            return JSONResponse(
                {"error": "the proxy is set by environment variables — "
                          "change WEBSHARE_PROXY_USERNAME/PASSWORD there"},
                status_code=409)
        return proxy.set_config(str(body.get("username", "")),
                                str(body.get("password", "")),
                                str(body.get("host", "")))

    # -- outputs: where finished files land ---------------------------------

    @app.get("/api/settings/outputs")
    def api_outputs_get():
        from czcore.paths import media_root
        return {"root": str(media_root())}

    @app.post("/api/settings/outputs")
    def api_outputs_set(body: dict = Body(...)):
        from czcore.paths import set_media_root
        root = str(body.get("root", "")).strip()
        if root and not Path(root).expanduser().parent.exists():
            return JSONResponse({"error": f"the folder above {root} doesn't "
                                          "exist — pick a real place"},
                                status_code=422)
        return {"root": str(set_media_root(root))}

    # -- runtimes: the optional heavies, installable from inside the app ----

    def _runtime_rows():
        import sys as _sys
        try:
            import sam2  # noqa: F401
            import torch  # noqa: F401
            sam_ok = True
        except ImportError:
            sam_ok = False
        from clear import isolate as dfn
        return [
            {"id": "stencil-sam2", "label": "Stencil click-to-matte",
             "what": "PyTorch + Meta's SAM 2 — clicks become subject mattes",
             "size": "~1 GB", "installed": sam_ok,
             "command": f"{_sys.executable} -m pip install torch "
                        "\"sam2 @ git+https://github.com/facebookresearch/sam2.git\""},
            {"id": "clear-dfn", "label": "Clear voice isolation",
             "what": "the official DeepFilterNet3 binary (MIT/Apache) — "
                     "everything else in Clear works without it",
             "size": "~40 MB", "installed": dfn.available(),
             "command": f"curl -L {dfn.BIN_URL} -o '{dfn.binary_path()}' "
                        f"&& chmod +x '{dfn.binary_path()}'"},
        ]

    @app.get("/api/settings/runtimes")
    def api_runtimes():
        return {"runtimes": _runtime_rows()}

    @app.post("/api/settings/runtimes/install")
    def api_runtimes_install(body: dict = Body(...)):
        import sys as _sys
        which = str(body.get("id", ""))
        if getattr(_sys, "frozen", False):
            return JSONResponse({"error": "this signed build can't install "
                                          "runtimes yet — run from a source "
                                          "checkout"}, status_code=501)

        def work(job):
            import subprocess
            if which == "stencil-sam2":
                job.message = "pip installing torch + SAM 2 — ~1 GB…"
                proc = subprocess.Popen(
                    [_sys.executable, "-m", "pip", "install", "torch",
                     "sam2 @ git+https://github.com/facebookresearch/sam2.git"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1)
                for line in proc.stdout:
                    if line.strip():
                        job.message = line.strip()[:110]
                    job.check_cancel()
                if proc.wait() != 0:
                    raise RuntimeError("pip couldn't finish — the Queue "
                                       "holds its last line")
            elif which == "clear-dfn":
                import hashlib
                import urllib.request
                from clear import isolate as dfn
                job.message = "downloading DeepFilterNet3…"
                dest = dfn.binary_path()
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(".part")
                with urllib.request.urlopen(dfn.BIN_URL, timeout=120) as r, \
                        open(tmp, "wb") as f:
                    got, total = 0, int(r.headers.get("Content-Length") or 0)
                    while chunk := r.read(1 << 18):
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            job.progress = got / total
                        job.check_cancel()
                sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
                if sha != dfn.BIN_SHA256:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("download didn't match its published "
                                       "sha256 — refused")
                tmp.chmod(0o755)
                tmp.rename(dest)
            else:
                raise RuntimeError(f"unknown runtime: {which}")
            job.message = "installed — reload the app to light it up"
            return {"ok": True, "id": which}

        return jobs.start("install", work, tool="suite",
                          label=f"install runtime — {which}").to_dict()

    # -- AI: the user's own Anthropic key, optional, never the default -------

    @app.get("/api/settings/llm")
    def api_llm_get():
        from czcore import llm
        return llm.status()

    @app.post("/api/settings/llm")
    def api_llm_set(body: dict = Body(...)):
        from czcore import llm
        if llm.get_config()["source"] == "env" and body.get("api_key"):
            return JSONResponse(
                {"error": "the key is set by ANTHROPIC_API_KEY in the "
                          "environment — change it there"}, status_code=409)
        return llm.set_config(str(body.get("api_key", "")).strip(),
                              str(body.get("model", "")).strip())
