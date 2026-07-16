"""Rise's video loop: decode → upscale (→ stabilize) → encode, shared by the
CLI and the suite queue. The engine math lives in rise.engine; this module owns
the honesty around it: the interlace guard, the backend label in every report,
and color tags passed through untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class InterlacedSourceError(RuntimeError):
    """Combed/telecined input — upscaling would sharpen the combs."""


def interlace_verdict(info) -> dict:
    """field_order verdict from a czcore.media.MediaInfo. The guard's evidence."""
    field = next((s.get("field_order") for s in info.raw.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    interlaced = bool(field and field not in ("progressive",))
    return {"field_order": field or "untagged",
            "interlaced": interlaced,
            "verdict": ("looks interlaced — deinterlace first (QTGMC or "
                        "Resolve's deinterlacer), or Rise will sharpen the combs"
                        if interlaced else "progressive — safe to upscale")}


def upscale_video(
    input_path: str,
    out_path: str,
    scale: int = 2,
    model: str = "auto",
    tile: int = 512,
    stabilize: bool = False,
    codec_spec: Optional[dict] = None,
    force: bool = False,
    denoise: str = "off",
    progress=None,
    should_stop=None,
) -> dict:
    """Upscale a whole clip. Returns an honest report dict.

    codec_spec comes from czcore.media.resolve_preset (defaults to ProRes HQ).
    denoise="hush" cleans each frame (Hush core, 3-frame temporal + fine NLM)
    BEFORE scaling — upscaling amplifies noise, and a synthesis model fed
    noise invents texture from it. Adds a 1-frame lookahead, roughly halves
    throughput, and is named in the report.
    progress(n, total_estimate) fires every few frames. should_stop() -> True
    aborts, removes the partial file, and raises JobCancelled.
    """
    import av
    import cv2
    import numpy as np

    from czcore.appshell.jobs import JobCancelled
    from czcore.media import copy_color_tags, probe, resolve_preset

    from .engine import resolve_model, upscale_frame

    info = probe(input_path)
    v = info.video
    if v is None:
        raise ValueError(f"no video stream in {input_path}")
    guard = interlace_verdict(info)
    if guard["interlaced"] and not force:
        raise InterlacedSourceError(
            f"refusing: field_order={guard['field_order']} looks interlaced — "
            "deinterlace first, or force if you know better. (Honesty > silence.)")

    name = resolve_model(model)
    spec = codec_spec or resolve_preset("prores-hq")
    ow, oh = v.width * scale, v.height * scale
    total = v.nb_frames or (int(info.duration * v.fps) if v.fps else 0) or 1
    backend_seen = None
    synthesized = False
    use_denoise = denoise == "hush"
    denoise_info = None

    state = {"prev_out": None, "prev_small": None, "n": 0}
    try:
        with av.open(input_path) as inp, av.open(out_path, "w") as out:
            vin = inp.streams.video[0]
            vin.thread_type = "AUTO"
            vout = out.add_stream(spec["codec"], rate=vin.average_rate or 24,
                                  options=dict(spec["options"]))
            vout.width, vout.height = ow, oh
            vout.pix_fmt = spec["pix_fmt"]
            color_note = copy_color_tags(vin.codec_context, vout.codec_context)

            def process(prev_img, img, next_img):
                nonlocal backend_seen, synthesized, denoise_info
                src = img
                if use_denoise:
                    from czcore.denoise import denoise_trio
                    src, denoise_info = denoise_trio(prev_img, img, next_img)
                up, einfo = upscale_frame(src, scale, model=name, tile=tile)
                backend_seen = einfo.backend
                synthesized = einfo.synthesized
                if stabilize and state["prev_out"] is not None:
                    # flow on quarter-res input frames, gate by warp error
                    small = cv2.resize(src, (v.width // 4, v.height // 4))
                    flow = cv2.calcOpticalFlowFarneback(
                        cv2.cvtColor(state["prev_small"], cv2.COLOR_BGR2GRAY),
                        cv2.cvtColor(small, cv2.COLOR_BGR2GRAY),
                        None, 0.5, 3, 21, 3, 5, 1.2, 0)
                    flow_up = cv2.resize(flow, (ow, oh)) * (4 * scale)
                    grid = np.mgrid[0:oh, 0:ow].astype(np.float32)
                    map_x = grid[1] - flow_up[..., 0]
                    map_y = grid[0] - flow_up[..., 1]
                    warped = cv2.remap(state["prev_out"], map_x, map_y,
                                       cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_REPLICATE)
                    err = np.abs(warped.astype(np.int16) - up.astype(np.int16)
                                 ).mean(axis=2, keepdims=True)
                    gate = np.clip(1.0 - err / 24.0, 0.0, 1.0) * 0.5
                    up = (up * (1 - gate) + warped * gate).astype(np.uint8)
                if stabilize:
                    state["prev_small"] = cv2.resize(
                        src, (v.width // 4, v.height // 4))
                    state["prev_out"] = up
                vf = av.VideoFrame.from_ndarray(up, format="bgr24")
                for pkt in vout.encode(vf):
                    out.mux(pkt)
                state["n"] += 1
                if progress and state["n"] % 4 == 0:
                    progress(state["n"], total)
                if should_stop and should_stop():
                    raise JobCancelled()

            # 1-frame lookahead so the denoiser sees (prev, cur, next)
            prev_img = None
            pending = None
            for packet in inp.demux(vin):
                for frame in packet.decode():
                    img = frame.to_ndarray(format="bgr24")
                    if pending is not None:
                        process(prev_img, pending, img)
                        prev_img = pending
                    pending = img
            if pending is not None:
                process(prev_img, pending, None)
            for pkt in vout.encode():
                out.mux(pkt)
    except JobCancelled:
        Path(out_path).unlink(missing_ok=True)
        raise

    return {"frames": state["n"], "out": out_path, "size": [ow, oh],
            "scale": scale, "backend": backend_seen, "synthesized": synthesized,
            "stabilized": stabilize, "encoder": spec["codec"],
            "color": color_note, "interlace": guard,
            "denoise": denoise_info or "off"}
