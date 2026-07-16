"""Pivot inside the suite — same engine functions as pivot/ui.py, now with the
persistent queue, export presets, and the suite frame cache.

Analyze writes its scrub JPEGs straight into the suite frame cache (h=360),
so the pass that analyzed the clip has already warmed the viewer.
"""

from __future__ import annotations

import json
from pathlib import Path

from pivot.analyze import Analysis, analyze
from pivot.aspect import CropGeometry, rect_for_center
from pivot.render import render
from pivot.solver import PRESETS, SolvedPath, solve

from ..frames import clip_cache_dir


def _sidecar(path: str) -> Path:
    return Path(path).with_suffix(".pivot.json")


def register_pivot(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore.media import resolve_preset

    @app.post("/api/pivot/load")
    def api_load(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        sc = _sidecar(path)
        if not sc.exists():
            return {"analysis": None}
        try:
            return {"analysis": json.loads(sc.read_text())}
        except ValueError:
            return {"analysis": None,
                    "warning": "sidecar exists but couldn't be parsed — re-analyze"}

    @app.post("/api/pivot/analyze")
    def api_analyze(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        aspects = body.get("aspects", ["9:16"])
        preset = body.get("preset", "standard")
        name = Path(path).name

        def work(job):
            job.message = "analyzing…"
            cache = clip_cache_dir(path, 360)  # warms the suite scrub cache

            def prog(n):
                job.message = f"{n} frames analyzed"

            job.check_cancel()
            a = analyze(path, aspects=aspects, preset=preset,
                        frame_cache=str(cache), progress=prog)
            _sidecar(path).write_text(a.to_json())
            job.message = f"{a.n_frames} frames · {len(a.shots)} shots"
            return json.loads(a.to_json())

        return jobs.start("analyze", work, tool="pivot",
                          label=f"{name} — analyze {'+'.join(aspects)}").to_dict()

    @app.post("/api/pivot/override")
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

    @app.post("/api/pivot/render")
    def api_render(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        aspect = body.get("aspect", "9:16")
        preset_id = body.get("preset", "h264")
        enhance = bool(body.get("enhance", False))
        enhance_model = body.get("enhance_model", "auto")
        denoise = bool(body.get("denoise", False))
        out_size = None
        if body.get("out_size"):
            try:
                w, h = str(body["out_size"]).lower().split("x")
                out_size = (int(w), int(h))
            except ValueError:
                return JSONResponse(
                    {"error": f"out size should look like 1080x1920, "
                              f"got {body['out_size']!r}"}, status_code=422)
        try:
            spec = resolve_preset(preset_id)
        except KeyError:
            return JSONResponse({"error": f"unknown export preset {preset_id!r}"},
                                status_code=422)
        sc = _sidecar(path)
        if not sc.exists():
            return JSONResponse({"error": "analyze first — no sidecar for this clip"},
                                status_code=409)
        a = Analysis.from_json(sc.read_text())
        if aspect not in a.aspects:
            return JSONResponse(
                {"error": f"aspect {aspect} wasn't analyzed — re-analyze with it"},
                status_code=409)
        total = max(1, a.n_frames)
        tag = aspect.replace(":", "x")
        out = str(Path(path).with_name(
            f"{Path(path).stem}.pivot-{tag}.{spec['container']}"))

        def work(job):
            def prog(n):
                job.progress = min(0.99, n / total)
                job.message = f"{n}/{total} frames · {spec['label']}"

            return render(a, aspect, out, out_size=out_size,
                          enhance=enhance, enhance_model=enhance_model,
                          denoise=denoise,
                          codec_spec=spec, progress=prog,
                          should_stop=lambda: job.cancel_requested)

        label = (f"{Path(path).name} → {aspect}"
                 f"{' · cleaned' if denoise else ''} {spec['label']}")
        return jobs.start("render", work, tool="pivot", label=label).to_dict()

    @app.post("/api/pivot/export_fusion")
    def api_export_fusion(body: dict = Body(...)):
        from czcore.exports.fusion_setting import animated_crop_setting

        path = str(Path(body["path"]).expanduser())
        aspect = body.get("aspect", "9:16")
        sc = _sidecar(path)
        if not sc.exists():
            return JSONResponse({"error": "analyze first — no sidecar for this clip"},
                                status_code=409)
        a = Analysis.from_json(sc.read_text())
        sol = a.aspects[aspect]
        geom = CropGeometry(a.width, a.height, sol.crop_w, sol.crop_h, sol.axis)
        rects = [rect_for_center(geom, c) for c in sol.centers]
        tag = aspect.replace(":", "x")
        out = Path(path).with_name(f"{Path(path).stem}.pivot-{tag}.setting")
        out.write_text(animated_crop_setting(
            rects, a.width, a.height,
            comment=f"control-z Pivot — {Path(path).name} {aspect}"))
        return {"out": str(out), "keyframes": len(rects)}

    @app.get("/api/pivot/solver-presets")
    def api_solver_presets():
        return list(PRESETS)
