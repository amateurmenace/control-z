"""Matte exports free Resolve actually uses.

luma  — black/white ProRes 422: Media Pool -> right-click node -> Add Matte
        (Color page external matte), or Fusion loader. The universal path.
rgba  — ProRes 4444: source RGB with the matte as alpha, drop on a track.
"""

from __future__ import annotations

from typing import Iterator, List, Optional


def _open_out(out_path: str, w: int, h: int, fps, pix_fmt: str):
    import av

    out = av.open(out_path, "w")
    stream = out.add_stream("prores_ks", rate=fps)
    stream.width, stream.height = w, h
    stream.pix_fmt = pix_fmt
    stream.options = {"profile": "4" if pix_fmt.startswith("yuva") else "3"}
    return out, stream


def write_luma(masks: Iterator, src_path: str, out_path: str, progress=None) -> int:
    """masks: per-frame uint8 (analysis res) or None. Upscaled to source size."""
    import av
    import cv2
    import numpy as np

    n = 0
    with av.open(src_path) as inp:
        vin = inp.streams.video[0]
        w, h = vin.codec_context.width, vin.codec_context.height
        fps = vin.average_rate or 24
        out, vout = _open_out(out_path, w, h, fps, "yuv422p10le")
        for m in masks:
            if m is None:
                full = np.zeros((h, w), np.uint8)
            else:
                full = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
            rgb = np.repeat(full[..., None], 3, axis=2)
            vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            for pkt in vout.encode(vf):
                out.mux(pkt)
            n += 1
            if progress and n % 50 == 0:
                progress(f"writing {n}")
        for pkt in vout.encode():
            out.mux(pkt)
        out.close()
    return n


def write_rgba(masks: List, src_path: str, out_path: str, start: int = 0,
               progress=None) -> int:
    """Source RGB + matte alpha (ProRes 4444). masks indexed clip-relative."""
    import av
    import cv2
    import numpy as np

    n = 0
    with av.open(src_path) as inp:
        vin = inp.streams.video[0]
        vin.thread_type = "AUTO"
        w, h = vin.codec_context.width, vin.codec_context.height
        fps = vin.average_rate or 24
        out, vout = _open_out(out_path, w, h, fps, "yuva444p10le")
        i = 0
        for packet in inp.demux(vin):
            for frame in packet.decode():
                idx = i - start
                if 0 <= idx < len(masks):
                    img = frame.to_ndarray(format="rgb24")
                    m = masks[idx]
                    a = (np.zeros((h, w), np.uint8) if m is None else
                         cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR))
                    rgba = np.dstack([img, a])
                    vf = av.VideoFrame.from_ndarray(rgba, format="rgba")
                    for pkt in vout.encode(vf):
                        out.mux(pkt)
                    n += 1
                    if progress and n % 50 == 0:
                        progress(f"writing {n}")
                i += 1
        for pkt in vout.encode():
            out.mux(pkt)
        out.close()
    return n
