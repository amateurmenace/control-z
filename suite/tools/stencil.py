"""Stencil inside the suite — click-to-prompt mattes with the confidence QC
loop (specs/02 → 08): per-frame confidence strip, coverage %, low-confidence
frames named, luma / ProRes 4444 alpha exports.

The SAM 2.1 runtime (PyTorch) is a heavy optional, and it runs one of two
ways:

  in-process — a source checkout with torch + SAM 2 in its own venv.
  helper     — its own Python in app support (czcore.pyruntime), driven over
               pipes. The ONLY way in the signed app: its hardened runtime
               refuses to load torch's libraries (zero entitlements, by
               design — packaging/sign_suite.sh), so the model lives in a
               separate process running stencil/sam2_engine.py.

Settings → optional runtimes installs the helper runtime in one click (or
prints the three terminal lines that do the same); "Check again" verifies.
When neither exists, the page stays honest — everything visible, the
propagate button naming exactly what to install.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

_engine = None
_engine_lock = threading.Lock()

# -- the helper runtime recipe (czcore.pyruntime) ------------------------------

RUNTIME = "stencil"
SAM2_ZIP = ("sam-2 @ https://github.com/facebookresearch/sam2/archive/"
            "refs/heads/main.zip")   # Meta's own SAM 2 — the PyPI "sam2" is
                                     # a stranger's; a zip needs no git
STEPS = [
    ["install", "--upgrade", "pip"],
    ["install", "torch", "torchvision", "numpy", "pillow", "setuptools",
     "wheel"],
    # --no-build-isolation: build against the torch just installed instead
    # of downloading a second ~700 MB copy into a throwaway build env
    ["install", "--no-build-isolation", SAM2_ZIP],
]
STEP_ENV = {"SAM2_BUILD_CUDA": "0"}   # Apple silicon: no CUDA kernels to build
VERIFY = ("import torch, sam2; "
          "from sam2.build_sam import build_sam2_video_predictor; "
          "print('torch ' + torch.__version__ + ' · ' + "
          "('Apple GPU (MPS)' if torch.backends.mps.is_available() else 'CPU'))")


def _inproc_ok() -> bool:
    if os.environ.get("CZ_STENCIL_FORCE_HELPER"):
        return False              # exercise the helper road from a checkout
    try:
        import torch  # noqa: F401
        from sam2.build_sam import build_sam2_video_predictor  # noqa: F401
        return True
    except ImportError:
        return False


def helper_python():
    """The helper runtime's Python when it's installed AND verified —
    CZ_STENCIL_PYTHON overrides (tests, or a runtime someone built by hand
    somewhere else)."""
    from czcore import pyruntime
    env = os.environ.get("CZ_STENCIL_PYTHON")
    if env and Path(env).is_file():
        return env
    if pyruntime.verify(RUNTIME, VERIFY)["ok"]:
        return str(pyruntime.venv_python(RUNTIME))
    return None


def runtime_status() -> dict:
    from czcore import models, pyruntime
    mode = "in-process" if _inproc_ok() else (
        "helper" if helper_python() else None)
    if mode is None:
        frozen = pyruntime.frozen()
        return {"available": False, "mode": None, "frozen": frozen,
                "hint": ("Click-to-matte needs its GPU runtime (PyTorch + "
                         "Meta's SAM 2, about 1 GB). Install it in one click: "
                         "Settings → optional runtimes → Stencil click-to-matte "
                         "(or follow the manual steps there). Every other tool "
                         "works without it."),
                "install_path": str(pyruntime.venv_dir(RUNTIME))}
    try:
        models.model_path("sam21_small", auto_download=False)
        ckpt = True
    except FileNotFoundError:
        ckpt = False
    return {"available": True, "mode": mode, "checkpoint_present": ckpt,
            "hint": None if ckpt else
            "SAM 2.1 checkpoint (176 MB, Apache-2.0) downloads on the first "
            "propagate — the queue shows its card and license while it does."}


def _engine_script() -> Path:
    """stencil/sam2_engine.py as a FILE the helper's Python can run — in
    the frozen app it ships as data beside the package (suite.spec)."""
    import stencil
    cands = [Path(stencil.__file__).parent / "sam2_engine.py"]
    if getattr(sys, "_MEIPASS", None):
        cands.append(Path(sys._MEIPASS) / "stencil" / "sam2_engine.py")
    for c in cands:
        if c.is_file():
            return c
    raise RuntimeError("the Stencil engine file is missing from this build "
                       "(stencil/sam2_engine.py) — reinstall the app")


class Helper:
    """The helper process: one warm SAM 2.1 in the runtime's own Python.
    Requests go down stdin as JSON lines; progress and one answer come
    back on stdout. A cancel kills it (the next call starts a fresh one —
    the model reloads in seconds). stderr lands in a log beside the
    runtime, the first place to look when it misbehaves."""

    def __init__(self, python: str):
        self.python = python
        self.proc = None
        self.lock = threading.Lock()

    def log_path(self) -> Path:
        from czcore import pyruntime
        return pyruntime.root() / "stencil-helper.log"

    def _start(self):
        lp = self.log_path()
        try:
            if lp.exists() and lp.stat().st_size > 5_000_000:
                lp.unlink()               # a log, not an archive
        except OSError:
            pass
        with open(lp, "a") as log:        # the child keeps its own copy
            self.proc = subprocess.Popen(
                [self.python, "-u", str(_engine_script())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=log, text=True, bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1",
                     "PYTORCH_ENABLE_MPS_FALLBACK": "1"})

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def call(self, req: dict, progress=None, cancelled=None,
             wait: bool = True) -> dict:
        """One request, one answer. wait=False (the click preview) answers
        "busy" at once instead of queueing behind a propagate that may run
        for minutes — one helper process serves one request at a time."""
        from czcore.appshell.jobs import JobCancelled
        if not self.lock.acquire(blocking=wait):
            raise RuntimeError("Stencil is busy propagating — the instant "
                               "preview comes back when that finishes")
        try:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            proc = self.proc
            stop = threading.Event()

            def watch():
                while not stop.is_set() and proc.poll() is None:
                    if cancelled and cancelled():
                        stop.set()
                        # THIS request's process — never a later one's
                        try:
                            proc.terminate()
                            proc.wait(timeout=8)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        return
                    stop.wait(0.4)

            if cancelled is not None:
                threading.Thread(target=watch, daemon=True).start()
            try:
                proc.stdin.write(json.dumps(req) + "\n")
                proc.stdin.flush()
                for line in proc.stdout:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue          # a library printed to stdout
                    if "progress" in d:
                        if progress:
                            progress(str(d["progress"]))
                        continue
                    if not d.get("ok"):
                        raise RuntimeError(f"the Stencil runtime answered: "
                                           f"{d.get('error', 'an error')}")
                    return d
            except (BrokenPipeError, OSError):
                pass
            finally:
                cancelled_now = stop.is_set()
                stop.set()
            if self.proc is proc:
                self.proc = None          # it's gone; the next call restarts
            if cancelled_now:
                raise JobCancelled()
            raise RuntimeError("the Stencil runtime stopped unexpectedly — "
                               f"its log is at {self.log_path()}")
        finally:
            self.lock.release()


_helper = None


def get_helper() -> Helper:
    global _helper
    py = helper_python()
    if not py:
        raise RuntimeError(runtime_status()["hint"])
    with _engine_lock:
        if _helper is None or _helper.python != py:
            if _helper:
                _helper.stop()
            _helper = Helper(py)
        return _helper


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from stencil.core import StencilEngine
            _engine = StencilEngine()
        return _engine


def install_job(jobs):
    """Install the helper runtime as a queue job: a Python of its own
    (the managed download in the signed app; this checkout's interpreter
    from source), a venv, torch + Meta's SAM 2, verified at the end.
    Resumable — a failed or cancelled run picks up where it stopped."""
    from czcore import pyruntime

    def work(job):
        job.message = ("installing PyTorch + SAM 2 — about 1 GB; minutes, "
                       "not seconds…")
        base = None if pyruntime.frozen() else sys.executable
        v = pyruntime.install(RUNTIME, STEPS, VERIFY, job=job, env=STEP_ENV,
                              base_python=base)
        if not v["ok"]:
            raise RuntimeError("installed, but the check failed — "
                               f"{v['detail']}")
        global _helper
        if _helper:
            _helper.stop()
            _helper = None
        job.message = f"ready — {v['detail']}. Stencil can matte now."
        return {"ok": True, "detail": v["detail"],
                "path": str(pyruntime.venv_dir(RUNTIME))}

    return jobs.start("install", work, tool="stencil",
                      label="install click-to-matte runtime (PyTorch + SAM 2)")


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

    @app.post("/api/stencil/install-runtime")
    def api_install_runtime():
        """The gate's button — the same one-click install Settings offers."""
        return install_job(jobs).to_dict()

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
        st = runtime_status()
        if not st["available"]:
            return JSONResponse({"error": st["hint"], "need": "runtime",
                                 "runtime": "stencil-sam2"}, status_code=501)
        try:
            if st["mode"] == "in-process":
                from stencil.core import preview_mask
                mask, conf = preview_mask(img, pos, labels)
            else:
                import tempfile

                from czcore import models
                with tempfile.TemporaryDirectory(prefix="stencil-pv-") as td:
                    src, dst = Path(td) / "f.png", Path(td) / "m.png"
                    cv2.imwrite(str(src), img)
                    r = get_helper().call(wait=False, req={
                        "op": "preview",
                        "ckpt": str(models.model_path("sam21_small", quiet=True)),
                        "image": str(src), "points": [list(p) for p in pos],
                        "labels": labels, "out": str(dst)})
                    mask = cv2.imread(str(dst), cv2.IMREAD_GRAYSCALE)
                    conf = float(r.get("conf", 0.0))
                if mask is None:
                    raise RuntimeError("the runtime wrote no mask")
        except Exception as e:
            return JSONResponse({"error": f"the preview pass failed "
                                          f"({e.__class__.__name__}: "
                                          f"{str(e)[:160]})"}, status_code=500)
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
            return JSONResponse({"error": st["hint"], "need": "runtime",
                                 "runtime": "stencil-sam2"}, status_code=501)
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
            ckpt = models.model_path("sam21_small", quiet=True)  # card on screen
            job.check_cancel()
            job.message = "loading SAM 2.1…"
            mdir = cache / f"masks-{tag}"
            if st["mode"] == "in-process":
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
                shutil.rmtree(mdir, ignore_errors=True)  # only once the run survived
                mdir.mkdir()
                coverage = []
                for i, m in enumerate(masks):
                    if m is None:
                        coverage.append(0.0)
                        continue
                    cv2.imwrite(str(mdir / f"m_{i:05d}.png"), m)
                    coverage.append(round(float((m > 127).mean()), 4))
            else:
                # the helper writes the mattes itself into a staging folder;
                # it replaces the old run's only once this run survived
                stage = cache / f"masks-{tag}.part"
                shutil.rmtree(stage, ignore_errors=True)
                r = get_helper().call(
                    {"op": "propagate", "ckpt": str(ckpt),
                     "frames_dir": str(fdir), "out_dir": str(stage), "obj": 1,
                     "prompts": [{"frame": int(p["frame"]) - start,
                                  "x": float(p["x"]), "y": float(p["y"]),
                                  "label": int(p.get("label", 1)), "obj": 1}
                                 for p in prompts_in]},
                    progress=lambda m: setattr(job, "message", m),
                    cancelled=lambda: job.cancel_requested)
                conf = list(r.get("confidence") or [])
                shutil.rmtree(mdir, ignore_errors=True)
                stage.rename(mdir) if stage.exists() else mdir.mkdir()
                masks = [None] * int(r.get("n") or len(conf))
                coverage = []
                for i in range(len(masks)):
                    f = mdir / f"m_{i:05d}.png"
                    m = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) \
                        if f.exists() else None
                    masks[i] = True if m is not None else None
                    coverage.append(0.0 if m is None
                                    else round(float((m > 127).mean()), 4))
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
