"""Models page — every model the suite uses: license card, hash policy,
true on-disk state, download and remove. The covenant's transparency
applied to weights, as a page.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from czcore import models as reg


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return 0


def register_modelstore(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.get("/api/models/list")
    def api_list():
        store = reg.models_dir()
        registry = []
        for name, spec in reg.REGISTRY.items():
            dest = store / spec.filename
            # "present" has to mean the tools can actually load it, not just
            # that bytes are on disk — a file that fails its pinned hash is a
            # third state, and saying so is the whole point of this page.
            # Hashing the entire store costs ~0.2s.
            problem = None
            if dest.exists():
                try:
                    reg.model_path(name, auto_download=False)
                except reg.ModelUnusable as e:
                    problem = str(e)
            registry.append({
                "name": name, "filename": spec.filename,
                "card": spec.card, "license": spec.license,
                "present": dest.exists() and problem is None,
                "problem": problem,
                "size": _size(dest) if dest.exists() else None,
                "downloadable": spec.url is not None,
                "hint": spec.hint or None,
                "pinned": spec.sha256 is not None,
            })

        whisper = []
        wdir = store / "whisper"
        if wdir.exists():
            for d in sorted(wdir.glob("models--*")):
                whisper.append({"name": d.name.split("--")[-1],
                                "size": _size(d), "path": d.name})

        stencil_rt = {"torch": None, "sam2": False}
        try:
            import torch
            stencil_rt["torch"] = torch.__version__
            stencil_rt["mps"] = bool(torch.backends.mps.is_available())
        except ImportError:
            pass
        try:
            import sam2  # noqa: F401
            stencil_rt["sam2"] = True
        except ImportError:
            pass

        return {
            "store": str(store),
            "total_size": _size(store),
            "registry": registry,
            "whisper": whisper,
            "stencil_runtime": stencil_rt,
        }

    @app.post("/api/models/download")
    def api_download(body: dict = Body(...)):
        name = body.get("name")
        if name not in reg.REGISTRY:
            return JSONResponse({"error": f"unknown model {name!r}"}, status_code=422)
        spec = reg.REGISTRY[name]
        if spec.url is None:
            return JSONResponse(
                {"error": f"{name} isn't hosted — {spec.hint}"}, status_code=409)

        def work(job):
            job.message = f"{spec.card.split('—')[0].strip()} · {spec.license}"
            p = reg.model_path(name, quiet=True)  # downloads + verifies the hash
            return {"path": str(p), "size": _size(p),
                    "license": spec.license, "sha256_verified": bool(spec.sha256)}

        return jobs.start("model-download", work, tool="suite",
                          label=f"model: {name}").to_dict()

    @app.post("/api/models/delete")
    def api_delete(body: dict = Body(...)):
        store = reg.models_dir()
        name = body.get("name")
        kind = body.get("kind", "registry")
        if kind == "registry":
            if name not in reg.REGISTRY:
                return JSONResponse({"error": f"unknown model {name!r}"},
                                    status_code=422)
            target = store / reg.REGISTRY[name].filename
        elif kind == "whisper":
            # a name is one directory inside the whisper store, nothing else:
            # no separators, no traversal, no symlink pointing out of it
            wdir = (store / "whisper").resolve()
            target = (store / "whisper" / str(name))
            if (Path(str(name)).name != str(name) or str(name) in ("", ".", "..")
                    or target.resolve().parent != wdir):
                return JSONResponse({"error": "bad path"}, status_code=422)
        else:
            return JSONResponse({"error": f"unknown kind {kind!r}"}, status_code=422)
        if not target.exists():
            return {"ok": True, "note": "already gone"}
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"ok": True, "note": f"removed — it re-downloads on next use"}
