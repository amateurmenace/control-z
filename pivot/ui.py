"""Pivot's local web app: routes over the same functions the CLI uses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import Body
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from .analyze import Analysis, analyze
from .aspect import CropGeometry, rect_for_center
from .render import render
from .solver import PRESETS, SolvedPath, solve


def _sidecar(path: str) -> Path:
    return Path(path).with_suffix(".pivot.json")


def cache_dir(path: str) -> Path:
    p = Path(path)
    tag = hashlib.md5(f"{p.resolve()}:{p.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    d = Path.home() / "Library" / "Caches" / "control-z" / "pivot" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


def register(app, jobs):
    @app.post("/api/open")
    def api_open(body: dict = Body(...)):
        path = body.get("path", "").strip()
        p = Path(path).expanduser()
        if not p.is_file():
            return JSONResponse({"error": f"no such file: {p}"}, status_code=404)
        sc = _sidecar(str(p))
        out = {"path": str(p), "sidecar": sc.exists()}
        if sc.exists():
            out["analysis"] = json.loads(sc.read_text())
        return out

    @app.post("/api/analyze")
    def api_analyze(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        aspects = body.get("aspects", ["9:16"])
        preset = body.get("preset", "standard")

        def work(job):
            cache = cache_dir(path)
            job.message = "analyzing…"

            def prog(n):
                job.message = f"{n} frames analyzed"

            a = analyze(path, aspects=aspects, preset=preset,
                        frame_cache=str(cache), progress=prog)
            _sidecar(path).write_text(a.to_json())
            return json.loads(a.to_json())

        return jobs.start("analyze", work).to_dict()

    @app.get("/api/frame")
    def api_frame(path: str, i: int):
        f = cache_dir(str(Path(path).expanduser())) / f"f_{i:05d}.jpg"
        if not f.exists():
            return JSONResponse({"error": "frame not cached — analyze first"},
                                status_code=404)
        return FileResponse(f, media_type="image/jpeg")

    @app.post("/api/override")
    def api_override(body: dict = Body(...)):
        """Force a shot's mode (auto/punch/follow/center) and re-solve in place."""
        path = str(Path(body["path"]).expanduser())
        aspect, shot_i, mode = body["aspect"], int(body["shot"]), body["mode"]
        a = Analysis.from_json(_sidecar(path).read_text())
        sol = a.aspects[aspect]
        s, e = a.shots[shot_i]
        geom = CropGeometry(a.width, a.height, sol.crop_w, sol.crop_h, sol.axis)
        hw = geom.half_width_norm
        targets = sol.targets[s:e] if sol.targets else [None] * (e - s)
        if mode == "center":
            solved = SolvedPath("punch", [min(max(0.5, hw), 1 - hw)] * (e - s), 0)
        else:
            solved = solve(targets, hw, fps=a.fps, params=PRESETS[a.preset],
                           mode=(mode if mode != "auto" else "auto"))
        sol.centers[s:e] = solved.centers
        sol.shot_modes[shot_i] = solved.mode if mode != "center" else "center"
        for row in a.subjects:
            if row["shot"] == shot_i:
                row["mode"] = sol.shot_modes[shot_i]
                row["moves"] = solved.moves
        _sidecar(path).write_text(a.to_json())
        return {"centers": solved.centers, "mode": sol.shot_modes[shot_i],
                "moves": solved.moves}

    @app.post("/api/render")
    def api_render(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        aspect = body.get("aspect", "9:16")
        codec = body.get("codec", "h264")
        enhance = bool(body.get("enhance", False))
        out_size = None
        if body.get("out_size"):
            w, h = str(body["out_size"]).lower().split("x")
            out_size = (int(w), int(h))
        a = Analysis.from_json(_sidecar(path).read_text())
        total = max(1, a.n_frames)
        ext = ".mov" if codec == "prores" else ".mp4"
        tag = aspect.replace(":", "x")
        out = str(Path(path).with_name(f"{Path(path).stem}.pivot-{tag}{ext}"))

        def work(job):
            def prog(n):
                job.progress = min(0.99, n / total)
                job.message = f"{n}/{total} frames"

            return render(a, aspect, out, codec=codec, out_size=out_size,
                          enhance=enhance, progress=prog)

        return jobs.start("render", work).to_dict()

    @app.post("/api/export_fusion")
    def api_export_fusion(body: dict = Body(...)):
        from czcore.exports.fusion_setting import animated_crop_setting

        path = str(Path(body["path"]).expanduser())
        aspect = body.get("aspect", "9:16")
        a = Analysis.from_json(_sidecar(path).read_text())
        sol = a.aspects[aspect]
        geom = CropGeometry(a.width, a.height, sol.crop_w, sol.crop_h, sol.axis)
        rects = [rect_for_center(geom, c) for c in sol.centers]
        tag = aspect.replace(":", "x")
        out = Path(path).with_name(f"{Path(path).stem}.pivot-{tag}.setting")
        out.write_text(animated_crop_setting(
            rects, a.width, a.height,
            comment=f"control-z Pivot — {Path(path).name} {aspect}"))
        return {"out": str(out), "keyframes": len(rects)}

    @app.get("/api/presets")
    def api_presets():
        return PlainTextResponse(json.dumps(list(PRESETS)), media_type="application/json")
