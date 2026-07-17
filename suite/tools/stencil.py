"""Stencil inside the suite — click-to-prompt mattes with the confidence QC
loop (specs/02 → 08): per-frame confidence strip, coverage %, low-confidence
frames named, luma / ProRes 4444 alpha exports.

The SAM 2.1 runtime (PyTorch) is a heavy optional: when it's missing the page
stays honest — everything is visible, the propagate button says exactly what
to install, and nothing pretends.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path

_engine = None
_engine_lock = threading.Lock()


def runtime_status() -> dict:
    try:
        import torch  # noqa: F401
        from sam2.build_sam import build_sam2_video_predictor  # noqa: F401
    except ImportError as e:
        import sys
        if getattr(sys, "frozen", False):
            # A frozen .app has no venv and no pip — telling the user to run
            # them would be an instruction they physically cannot follow
            # (specs/09 §5). The on-demand runtime component is v1.1.
            return {"available": False,
                    "hint": "Stencil's GPU runtime (torch + SAM 2, ~900 MB) "
                            "isn't bundled in this app, and this build can't "
                            "download it yet — that lands in v1.1. To use "
                            "Stencil today, run the suite from a source "
                            "checkout: github.com/amateurmenace/control-z "
                            "(README: 'Stencil runtime'). Every other tool "
                            "in this app is fully functional without it."}
        return {"available": False,
                "hint": f"Stencil's runtime isn't installed ({e.name} missing). "
                        "In the suite's venv, in this order: "
                        "pip install torch setuptools — with its dependencies "
                        "torch is about 700 MB on Apple silicon and 2.5 GB or "
                        "more on a CUDA machine — then "
                        "pip install --no-build-isolation "
                        "git+https://github.com/facebookresearch/sam2.git. That "
                        "git URL is Meta's own SAM 2; the package called sam2 on "
                        "PyPI is a different author's code and we don't send you "
                        "there. --no-build-isolation builds against the torch you "
                        "just installed instead of downloading a second copy. The "
                        "SAM 2.1 checkpoint (176 MB, Apache-2.0) downloads on the "
                        "first propagate."}
    from czcore import models
    try:
        models.model_path("sam21_small", auto_download=False)
        ckpt = True
    except FileNotFoundError:
        ckpt = False
    return {"available": True, "checkpoint_present": ckpt,
            "hint": None if ckpt else
            "SAM 2.1 checkpoint (176 MB, Apache-2.0) downloads on the first "
            "propagate — the queue shows its card and license while it does."}


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from stencil.core import StencilEngine
            _engine = StencilEngine()
        return _engine


def _cache_dir(path: str, start: int, end: int) -> Path:
    """The clip's cache: analysis frames only. They depend on the clip and the
    range, never on where you clicked, so every run of a shot reuses them."""
    p = Path(path)
    tag = hashlib.md5(f"{p.resolve()}:{p.stat().st_mtime_ns}:{start}:{end}"
                      .encode()).hexdigest()[:16]
    d = Path.home() / "Library" / "Caches" / "control-z" / "suite" / "stencil" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_tag(prompts: list, height: int) -> str:
    """Mattes belong to the clicks that made them. Different points, or a
    different analysis height, mean a different run: its own directory, its own
    mask URLs. Without this a second propagate over the same range would land on
    top of the first and any frame it couldn't matte would keep the old
    subject's — an export silently mixing two subjects."""
    key = json.dumps([[int(p["frame"]), float(p["x"]), float(p["y"]),
                       int(p.get("label", 1))] for p in prompts] + [int(height)])
    return hashlib.md5(key.encode()).hexdigest()[:12]


def register_stencil(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import FileResponse, JSONResponse

    @app.get("/api/stencil/status")
    def api_status():
        return runtime_status()

    @app.post("/api/stencil/click-preview")
    def api_click_preview(body: dict = Body(...)):
        """The instant answer: run SAM 2.1's image predictor on the ONE
        frame being clicked, so a mask appears the moment the subject is
        chosen — propagation stays the follow-through, not the reveal."""
        import base64

        import cv2

        path = str(body.get("path", ""))
        frame = int(body.get("frame", 0))
        pts = body.get("points") or []
        pos = [(float(p["x"]), float(p["y"])) for p in pts]
        labels = [int(p.get("label", 1)) for p in pts]
        if not pos:
            return JSONResponse({"error": "click the subject first"},
                                status_code=422)
        img = frames.native_frame(path, frame)
        if img is None:
            return JSONResponse({"error": "couldn't read that frame"},
                                status_code=415)
        h, w = img.shape[:2]
        if h > 720:                       # preview at analysis res: speed
            nw = max(2, int(round(w * 720 / h / 2)) * 2)
            img = cv2.resize(img, (nw, 720), interpolation=cv2.INTER_AREA)
        try:
            from stencil.core import preview_mask
            mask, conf = preview_mask(img, pos, labels)
        except (ImportError, ModuleNotFoundError):
            return JSONResponse(
                {"error": "click-to-matte needs the optional runtime — "
                          ".venv/bin/pip install torch "
                          "'git+https://github.com/facebookresearch/sam2.git'"},
                status_code=501)
        except Exception as e:
            return JSONResponse({"error": f"the preview pass failed "
                                          f"({e.__class__.__name__}: "
                                          f"{str(e)[:120]})"}, status_code=500)
        ok, buf = cv2.imencode(".png", mask)
        if not ok:
            return JSONResponse({"error": "couldn't encode the mask"},
                                status_code=500)
        return {"png": base64.b64encode(buf.tobytes()).decode(),
                "conf": round(conf, 3), "frame": frame}

    @app.post("/api/stencil/propagate")
    def api_propagate(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        start = int(body.get("start", 0))
        end = int(body["end"])
        prompts_in = body.get("prompts", [])
        height = int(body.get("height", 720))
        if not prompts_in:
            return JSONResponse({"error": "click the subject first — at least "
                                          "one prompt point"}, status_code=422)
        st = runtime_status()
        if not st["available"]:
            return JSONResponse({"error": st["hint"]}, status_code=501)
        name = Path(path).name

        def work(job):
            import cv2

            from czcore import models
            from czcore.appshell.jobs import JobCancelled
            from stencil.core import Prompt, extract_frames

            cache = _cache_dir(path, start, end)
            tag = _run_tag(prompts_in, height)
            fdir = cache / f"frames{height}"
            job.message = "extracting analysis frames…"
            if not (fdir.exists() and any(fdir.glob("*.jpg"))):
                extract_frames(path, start, end, fdir, height=height,
                               progress=lambda m: setattr(job, "message", m))
            job.check_cancel()
            spec = models.REGISTRY["sam21_small"]
            job.message = f"{spec.card} · license: {spec.license}"
            models.model_path("sam21_small", quiet=True)  # the card is on screen
            job.check_cancel()
            job.message = "loading SAM 2.1…"
            eng = _get_engine()
            prompts = [Prompt(frame=int(p["frame"]) - start,
                              xy=(float(p["x"]), float(p["y"])),
                              label=int(p.get("label", 1)), obj=1)
                       for p in prompts_in]
            with _engine_lock:
                sm = eng.run_shot(fdir, prompts,
                                  progress=lambda m: setattr(job, "message", m))
            if job.cancel_requested:
                raise JobCancelled()
            masks = sm.masks.get(1, [])
            conf = sm.confidence.get(1, [])
            mdir = cache / f"masks-{tag}"
            shutil.rmtree(mdir, ignore_errors=True)  # only once the run survived
            mdir.mkdir()
            coverage = []
            for i, m in enumerate(masks):
                if m is None:
                    coverage.append(0.0)
                    continue
                cv2.imwrite(str(mdir / f"m_{i:05d}.png"), m)
                coverage.append(round(float((m > 127).mean()), 4))
            low = [i + start for i, c in enumerate(conf) if c < 0.85]
            result = {
                "start": start, "end": end, "tag": tag, "frames": len(masks),
                "confidence": [round(float(c), 4) for c in conf],
                "coverage": coverage,
                "low_confidence": low[:20],
                "low_count": len(low),
                "note": (f"{len(low)} frame(s) under 0.85 confidence — scrub "
                         "those before export" if low else
                         "every frame ≥ 0.85 confidence"),
            }
            (cache / f"result-{tag}.json").write_text(json.dumps(result))
            job.message = f"{len(masks)} mattes · {len(low)} low-confidence"
            return result

        return jobs.start("propagate", work, tool="stencil",
                          label=f"{name} — matte [{start}:{end}]").to_dict()

    @app.get("/api/stencil/mask")
    def api_mask(path: str, start: int, end: int, i: int, tag: str):
        p = str(Path(path).expanduser())
        f = (_cache_dir(p, int(start), int(end)) / f"masks-{tag}"
             / f"m_{int(i):05d}.png")
        if not f.exists():
            return JSONResponse({"error": "no matte for that frame — propagate first"},
                                status_code=404)
        return FileResponse(str(f), media_type="image/png",
                            headers={"Cache-Control": "max-age=600"})

    @app.post("/api/stencil/export")
    def api_export(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        start = int(body.get("start", 0))
        end = int(body["end"])
        kind = body.get("kind", "rgba")   # rgba (4444+alpha) | luma
        post = body.get("post", {})
        tag = body.get("tag", "")
        name = Path(path).name
        cache = _cache_dir(path, start, end)
        mdir = cache / f"masks-{tag}"
        if not tag or not mdir.exists():
            return JSONResponse({"error": "propagate first — no mattes cached"},
                                status_code=409)

        def work(job):
            import cv2

            from stencil.export import write_luma, write_rgba
            from stencil.post import PostParams, apply_chain

            n = end - start
            masks = []
            for i in range(n):
                f = mdir / f"m_{i:05d}.png"
                masks.append(cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                             if f.exists() else None)
            pp = PostParams(grow=int(post.get("grow", 0)),
                            feather=float(post.get("feather", 1.5)),
                            despeckle=int(post.get("despeckle", 64)),
                            temporal=bool(post.get("temporal", True)))
            job.message = "matte post chain…"
            cooked = list(apply_chain(masks, pp))
            tag = "matte" if kind == "luma" else "alpha"
            out = str(Path(path).with_name(f"{Path(path).stem}.stencil-{tag}.mov"))

            def prog(m):
                job.message = m

            job.check_cancel()
            if kind == "luma":
                nf = write_luma(iter(cooked), path, out, progress=prog)
            else:
                nf = write_rgba(cooked, path, out, start=start, progress=prog)
            return {"out": out, "frames": nf, "kind": kind,
                    "post": {"grow": pp.grow, "feather": pp.feather,
                             "despeckle": pp.despeckle, "temporal": pp.temporal},
                    "note": ("import as a matte (Color page → Add Matte)"
                             if kind == "luma" else
                             "ProRes 4444 with alpha — drops straight on a track")}

        label = f"{name} — export {kind} matte"
        return jobs.start("export", work, tool="stencil", label=label).to_dict()
