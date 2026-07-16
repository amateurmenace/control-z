"""Rise inside the suite: probe + interlace guard, patch preview with the
detail heatmap (|model − bicubic|), and batch upscales through the queue.

Honesty rules carried from the engine: the backend that actually ran is in
every response; synthesis is labeled synthesis; combed sources are refused
(with an override that says what it's overriding).
"""

from __future__ import annotations

import base64
from pathlib import Path

from rise.engine import resolve_model, upscale_frame
from rise.video import InterlacedSourceError, interlace_verdict, upscale_video

from czcore import models

BACKEND_NOTES = {
    "lanczos": "honest resampling + edge-masked sharpen — no invented detail",
    "realesrgan-x2": "Real-ESRGAN ×2 — synthesizes texture (labeled synthesis)",
    "realesrgan-x4": "Real-ESRGAN ×4 — synthesizes texture (labeled synthesis)",
}


def backend_status() -> list:
    """Every known backend with true on-disk availability — the model picker."""
    out = [{"id": "lanczos", "present": True, "synthesized": False,
            "note": BACKEND_NOTES["lanczos"]}]
    for name in ("realesrgan-x2", "realesrgan-x4"):
        if name not in models.REGISTRY:
            continue
        try:
            models.model_path(name, auto_download=False)
            present = True
        except FileNotFoundError:
            present = False
        spec = models.REGISTRY[name]
        out.append({"id": name, "present": present, "synthesized": True,
                    "note": BACKEND_NOTES.get(name, spec.card),
                    "hint": spec.hint if not present else ""})
    return out


def _jpeg_data_uri(img, quality=88) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def register_rise(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore.media import probe, resolve_preset

    @app.post("/api/rise/probe")
    def api_probe(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"}, status_code=404)
        info = probe(path)
        v = info.video
        if not v:
            return JSONResponse({"error": "no video stream in that file"},
                                status_code=415)
        targets = []
        for label, target_h in (("1080p", 1080), ("4K", 2160)):
            if v.height < target_h:
                f = target_h / v.height
                targets.append({"label": label, "factor": round(f, 2),
                                "model_scale": 2 if f <= 2 else 4})
        return {"width": v.width, "height": v.height, "fps": v.fps,
                "codec": v.codec, "interlace": interlace_verdict(info),
                "punch_targets": targets, "backends": backend_status()}

    @app.post("/api/rise/preview")
    def api_preview(body: dict = Body(...)):
        """SR a native-res patch around (cx, cy); return src/bicubic/model/heat.

        The heatmap is |model − bicubic| — where the model added energy beyond
        honest interpolation. That difference is the covenant surface.
        With denoise on, the patch is cleaned (Hush core, neighbors from the
        adjacent frames) before BOTH sides — the A/B compares the scalers on
        what the render will actually feed them.
        """
        import cv2
        import numpy as np

        path = str(Path(body["path"]).expanduser())
        i = int(body.get("i", 0))
        cx = float(body.get("cx", 0.5))
        cy = float(body.get("cy", 0.5))
        scale = int(body.get("scale", 2))
        model = body.get("model") or "auto"
        use_denoise = bool(body.get("denoise", False))
        if scale not in (2, 4):
            return JSONResponse({"error": "scale must be 2 or 4"}, status_code=422)

        img = frames.native_frame(path, i)
        if img is None:
            return JSONResponse({"error": f"couldn't decode frame {i}"},
                                status_code=404)
        h, w = img.shape[:2]
        pw, ph = (320, 180) if scale == 2 else (192, 108)
        x0 = int(min(max(cx * w - pw / 2, 0), max(w - pw, 0)))
        y0 = int(min(max(cy * h - ph / 2, 0), max(h - ph, 0)))
        patch = img[y0:y0 + ph, x0:x0 + pw]

        denoise_info = None
        if use_denoise:
            from czcore.denoise import denoise_trio
            prev_f = frames.native_frame(path, i - 1) if i > 0 else None
            next_f = frames.native_frame(path, i + 1)
            patch, denoise_info = denoise_trio(
                prev_f[y0:y0 + ph, x0:x0 + pw] if prev_f is not None else None,
                patch,
                next_f[y0:y0 + ph, x0:x0 + pw] if next_f is not None else None)

        name = resolve_model(model)
        up, einfo = upscale_frame(patch, scale, model=name)
        bicubic = cv2.resize(patch, (patch.shape[1] * scale, patch.shape[0] * scale),
                             interpolation=cv2.INTER_CUBIC)
        diff = np.abs(up.astype(np.int16) - bicubic.astype(np.int16)).mean(axis=2)
        heat = np.clip(diff * 4.0, 0, 255).astype(np.uint8)
        added = float(diff.mean())

        return {
            "backend": einfo.backend, "synthesized": einfo.synthesized,
            "added_energy": round(added, 2),
            "denoise": denoise_info or "off",
            "rect": [x0, y0, pw, ph], "src_size": [w, h],
            "src": _jpeg_data_uri(patch),
            "bicubic": _jpeg_data_uri(bicubic),
            "up": _jpeg_data_uri(up),
            "heat": _jpeg_data_uri(heat),
        }

    @app.post("/api/rise/batch")
    def api_batch(body: dict = Body(...)):
        paths = [str(Path(p).expanduser()) for p in body.get("files", [])]
        scale = int(body.get("scale", 2))
        model = body.get("model") or "auto"
        stabilize = bool(body.get("stabilize", False))
        force = bool(body.get("force", False))
        denoise = "hush" if body.get("denoise", True) else "off"
        preset_id = body.get("preset", "prores-hq")
        if scale not in (2, 4):
            return JSONResponse({"error": "scale must be 2 or 4"}, status_code=422)
        try:
            spec = resolve_preset(preset_id)
        except KeyError:
            return JSONResponse({"error": f"unknown export preset {preset_id!r}"},
                                status_code=422)
        missing = [p for p in paths if not Path(p).is_file()]
        if missing:
            return JSONResponse({"error": f"no such file: {missing[0]}"},
                                status_code=404)
        if not paths:
            return JSONResponse({"error": "no files given"}, status_code=422)

        started = []
        for p in paths:
            out = str(Path(p).with_name(
                f"{Path(p).stem}.rise-x{scale}.{spec['container']}"))

            def work(job, p=p, out=out):
                def prog(n, total):
                    job.progress = min(0.99, n / max(1, total))
                    job.message = f"{n}/{total} frames · {spec['label']}"

                try:
                    return upscale_video(
                        p, out, scale=scale, model=model, stabilize=stabilize,
                        codec_spec=spec, force=force, denoise=denoise,
                        progress=prog,
                        should_stop=lambda: job.cancel_requested)
                except InterlacedSourceError as e:
                    raise RuntimeError(str(e)) from None

            label = (f"{Path(p).name} ×{scale}"
                     f"{' · cleaned' if denoise == 'hush' else ''}"
                     f" → {spec['label']}")
            started.append(jobs.start("upscale", work, tool="rise",
                                      label=label).to_dict())
        return {"jobs": started}
