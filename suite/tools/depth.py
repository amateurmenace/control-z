"""Depth inside the suite — false-color scrub previews with a probe, the
histogram with in/out handles, and the matte render through the queue.

Honesty note carried into the UI: scrub previews are PER-FRAME estimates
(random access has no history); the render adds the temporal EMA with
shot-boundary resets, so the matte is steadier than the preview.
"""

from __future__ import annotations

import base64
import threading
from pathlib import Path

_engine = None
_engine_lock = threading.Lock()
_last_small = {}   # path -> (frame_index, small depth) for the stability readout


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from depth.engine import DepthEngine
            _engine = DepthEngine()
        return _engine


def _jpeg_uri(img, quality=85) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def register_depth(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.post("/api/depth/preview")
    def api_preview(body: dict = Body(...)):
        """Per-frame depth for the scrubbed frame: false color + histogram +
        a small raw map the client probes locally."""
        import cv2
        import numpy as np

        path = str(Path(body["path"]).expanduser())
        i = int(body.get("i", 0))
        invert = bool(body.get("invert", False))
        gamma = float(body.get("gamma", 1.0))
        lo_h = float(body.get("lo", 0.0))   # display handles 0..1
        hi_h = float(body.get("hi", 1.0))

        img = frames.native_frame(path, i)
        if img is None:
            return JSONResponse({"error": f"couldn't decode frame {i}"},
                                status_code=404)
        h, w = img.shape[:2]
        if w > 960:
            img = cv2.resize(img, (960, int(960 * h / w)), interpolation=cv2.INTER_AREA)

        eng = _get_engine()
        with _engine_lock:
            eng.reset_temporal()           # random access: per-frame, no history
            raw = eng.estimate(img, ema=0.0, refine=True)
        lo = float(np.percentile(raw, 2.0))
        hi = float(np.percentile(raw, 98.0))
        norm = np.clip((raw - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
        if invert:
            norm = 1.0 - norm
        if gamma != 1.0:
            norm = norm ** gamma

        # display mapping through the user's in/out handles
        span = max(hi_h - lo_h, 1e-6)
        disp = np.clip((norm - lo_h) / span, 0.0, 1.0)
        fc = cv2.applyColorMap((disp * 255).astype(np.uint8), cv2.COLORMAP_TURBO)

        hist = np.bincount((norm * 63).astype(np.int32).ravel(), minlength=64)
        small = cv2.resize(norm, (96, 54), interpolation=cv2.INTER_AREA)

        prev = _last_small.get(path)
        stability = None
        if prev is not None and abs(prev[0] - i) == 1:
            stability = round(float(np.abs(small - prev[1]).mean()), 4)
        _last_small[path] = (i, small)

        return {
            "falsecolor": _jpeg_uri(fc),
            "hist": [int(x) for x in hist],
            "depth_small": [[round(float(v), 3) for v in row] for row in small],
            "stability": stability,
            "range": {"lo": round(lo, 4), "hi": round(hi, 4)},
            "note": "per-frame preview — the render adds temporal smoothing",
        }

    @app.post("/api/depth/render")
    def api_render(body: dict = Body(...)):
        path = str(Path(body["path"]).expanduser())
        invert = bool(body.get("invert", False))
        gamma = float(body.get("gamma", 1.0))
        ema = float(body.get("ema", 0.7))
        name = Path(path).name
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"}, status_code=404)
        out_path = str(Path(path).with_name(f"{Path(path).stem}.depth.mov"))

        def work(job):
            import av
            import cv2
            import numpy as np

            from czcore.appshell.jobs import JobCancelled
            from czcore.shots import cuts_from_diffs, shots_from_cuts
            from depth.engine import guided_filter, normalize_shot

            eng = _get_engine()
            depths, diffs = [], []
            prev = None
            job.message = "pass 1/2: estimating depth…"
            with _engine_lock:
                eng.reset_temporal()
                with av.open(path) as inp:
                    vin = inp.streams.video[0]
                    vin.thread_type = "AUTO"
                    fps = vin.average_rate or 24
                    for i, frame in enumerate(inp.decode(vin)):
                        img = frame.to_ndarray(format="bgr24")
                        small = cv2.resize(img, (160, 90))
                        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
                        if prev is not None:
                            d = float(np.abs(gray - prev).mean()) / 255.0
                            diffs.append(d)
                            if d > 0.14:      # probable cut: never smooth across
                                eng.reset_temporal()
                        prev = gray
                        depths.append(eng.estimate(img, ema=ema, refine=False,
                                                   native=True))
                        if i % 10 == 0:
                            job.message = f"pass 1/2: {i} frames estimated"
                        if job.cancel_requested:
                            raise JobCancelled()
            n = len(depths)
            shots = shots_from_cuts(cuts_from_diffs(diffs, threshold=0.14), n)

            normalized = [None] * n
            for (s, e) in shots:
                norm, _rng = normalize_shot(depths[s:e], invert=invert, gamma=gamma)
                normalized[s:e] = norm

            job.message = "pass 2/2: upsampling + encoding…"
            try:
                with av.open(path) as inp, av.open(out_path, "w") as out:
                    vin = inp.streams.video[0]
                    vin.thread_type = "AUTO"
                    w, h = vin.codec_context.width, vin.codec_context.height
                    vout = out.add_stream("prores_ks", rate=vin.average_rate or 24,
                                          options={"profile": "3"})
                    vout.width, vout.height = w, h
                    vout.pix_fmt = "yuv444p10le"
                    for i, frame in enumerate(inp.decode(vin)):
                        if i >= n:
                            break
                        img = frame.to_ndarray(format="bgr24")
                        up = cv2.resize(normalized[i], (w, h),
                                        interpolation=cv2.INTER_LINEAR)
                        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        up = np.clip(guided_filter(gray, up,
                                                   radius=max(4, w // 240)), 0, 1)
                        d16 = (up * 65535.0).astype(np.uint16)
                        vf = av.VideoFrame.from_ndarray(
                            np.dstack([d16, d16, d16]), format="rgb48le")
                        for pkt in vout.encode(vf):
                            out.mux(pkt)
                        job.progress = min(0.99, i / max(1, n))
                        if i % 10 == 0:
                            job.message = f"pass 2/2: {i}/{n} frames"
                        if job.cancel_requested:
                            raise JobCancelled()
                    for pkt in vout.encode():
                        out.mux(pkt)
            except JobCancelled:
                Path(out_path).unlink(missing_ok=True)
                raise
            return {"out": out_path, "frames": n, "shots": len(shots),
                    "near": "black" if invert else "white",
                    "note": "Resolve: Color page → Add Matte, or paste a "
                            "template from the pack"}

        return jobs.start("depth", work, tool="depth",
                          label=f"{name} — depth matte").to_dict()

    @app.post("/api/depth/templates")
    def api_templates(body: dict = Body(default={})):
        src_dir = Path(__file__).resolve().parents[2] / "depth" / "templates"
        out_dir = Path(body.get("dir", "~/Documents/control-z-templates")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        names = ["fog", "rack-focus", "depth-grade", "parallax", "haze-light"]
        for t in names:
            (out_dir / f"cz-depth-{t}.setting").write_text(
                (src_dir / f"{t}.setting").read_text())
        return {"dir": str(out_dir), "templates": names,
                "note": "open one in a text editor, copy all, paste into the "
                        "Fusion page, wire MediaIn + the matte as commented"}
