"""Slate's exports: the same frames, three honest containers.

ProRes 4444 carries the real 10-bit alpha — that's the one you cut with.
PNG is the hold frame at full quality. GIF is 256 colors and 1-bit alpha
by format law; it exists for the web and the export panel says so.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .lowerthird import LowerThird, Renderer


def write_prores4444(p: LowerThird, out_path: str,
                     progress: Optional[Callable[[float, str], None]] = None,
                     cancelled: Optional[Callable[[], bool]] = None) -> dict:
    import av
    import numpy as np

    from czcore.media import resolve_preset

    spec = resolve_preset("prores-4444", alpha=True)
    if not spec["alpha"]:
        raise RuntimeError("this ffmpeg build's prores_ks can't carry alpha — "
                           "reinstall the bundled ffmpeg")
    out = str(Path(out_path).with_suffix(".mov"))
    r = Renderer(p)
    n = p.n_frames()
    # NTSC-ish rates need a rational, not a float
    rate = {23.976: "24000/1001", 29.97: "30000/1001",
            59.94: "60000/1001"}.get(round(p.fps, 3), None)
    container = av.open(out, "w")
    stream = container.add_stream(spec["codec"], rate=rate or round(p.fps))
    stream.width, stream.height = p.width, p.height
    stream.pix_fmt = spec["pix_fmt"]
    stream.options = {str(k): str(v) for k, v in spec["options"].items()}
    for i, frame in r.frames():
        if cancelled and cancelled():
            container.close()
            Path(out).unlink(missing_ok=True)
            raise RuntimeError("cancelled")
        vf = av.VideoFrame.from_ndarray(np.asarray(frame), format="rgba")
        for pkt in stream.encode(vf):
            container.mux(pkt)
        if progress and i % 5 == 0:
            progress(i / n, f"frame {i + 1}/{n}")
    for pkt in stream.encode():
        container.mux(pkt)
    container.close()
    return {"out": out, "frames": n, "alpha": True, "codec": spec["codec"]}


def write_png(p: LowerThird, out_path: str) -> dict:
    out = str(Path(out_path).with_suffix(".png"))
    Renderer(p).hold_frame().save(out)
    return {"out": out, "alpha": True}


def write_gif(p: LowerThird, out_path: str, max_fps: float = 20.0,
              progress: Optional[Callable[[float, str], None]] = None,
              cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """Animated GIF: adaptive palette per clip, hard alpha at 128."""
    from PIL import Image

    out = str(Path(out_path).with_suffix(".gif"))
    q = LowerThird.from_dict({**p.to_dict(), "fps": min(p.fps, max_fps)})
    r = Renderer(q)
    n = q.n_frames()
    frames = []
    for i, im in r.frames():
        if cancelled and cancelled():
            raise RuntimeError("cancelled")
        alpha = im.split()[3]
        pal = im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
        mask = alpha.point(lambda a: 255 if a < 128 else 0)
        pal.paste(255, mask)
        frames.append(pal)
        if progress and i % 5 == 0:
            progress(i / n * 0.9, f"frame {i + 1}/{n}")
    if progress:
        progress(0.95, "writing palette + loop")
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=round(1000 / q.fps), loop=0, transparency=255,
                   disposal=2, optimize=False)
    return {"out": out, "frames": n, "fps": q.fps,
            "note": "GIF is 256 colors + hard-edge alpha — web use; "
                    "cut with the ProRes"}
