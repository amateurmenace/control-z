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
            registry.append({
                "name": name, "filename": spec.filename,
                "card": spec.card, "license": spec.license,
                "present": dest.exists(),
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

        diar = []
        for label, fn in (("pyannote segmentation-3.0 (MIT)",
                           "pyannote-segmentation-3-0.onnx"),
                          ("3D-Speaker embeddings (Apache-2.0)",
                           "3dspeaker_speech_eres2net_base_sv.onnx")):
            f = store / fn
            diar.append({"name": label, "filename": fn,
                         "present": f.exists(),
                         "size": _size(f) if f.exists() else None})

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
            "diarization": diar,
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
            target = store / "whisper" / str(name)
            if not str(target.resolve()).startswith(str((store / "whisper").resolve())):
                return JSONResponse({"error": "bad path"}, status_code=422)
        elif kind == "diarization":
            if name not in ("pyannote-segmentation-3-0.onnx",
                            "3dspeaker_speech_eres2net_base_sv.onnx"):
                return JSONResponse({"error": "bad name"}, status_code=422)
            target = store / str(name)
        else:
            return JSONResponse({"error": f"unknown kind {kind!r}"}, status_code=422)
        if not target.exists():
            return {"ok": True, "note": "already gone"}
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"ok": True, "note": f"removed — it re-downloads on next use"}
