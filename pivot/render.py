"""Pivot renderer: solved centers -> reframed video, audio passed through untouched."""

from __future__ import annotations

from typing import Optional, Tuple

from .analyze import Analysis
from .aspect import CropGeometry, rect_for_center

CODECS = {
    "h264": dict(codec="libx264", pix_fmt="yuv420p",
                 options={"crf": "18", "preset": "medium"}),
    "hevc": dict(codec="libx265", pix_fmt="yuv420p",
                 options={"crf": "20", "preset": "medium"}),
    "prores": dict(codec="prores_ks", pix_fmt="yuv422p10le",
                   options={"profile": "3"}),  # ProRes 422 HQ
}


def render(
    analysis: Analysis,
    aspect: str,
    out_path: str,
    codec: str = "h264",
    out_size: Optional[Tuple[int, int]] = None,
    audio: bool = True,
    enhance: bool = False,
    enhance_model: str = "auto",
    progress=None,
) -> dict:
    """Render one aspect. Returns a small report dict (frames, punch-in, output)."""
    import av
    import cv2

    solve = analysis.aspects[aspect]
    geom = CropGeometry(analysis.width, analysis.height,
                        solve.crop_w, solve.crop_h, solve.axis)
    if out_size is None:
        out_size = (geom.crop_w, geom.crop_h)  # native: never upscale silently
    ow, oh = out_size
    punch_in = ow / geom.crop_w
    spec = CODECS[codec]

    with av.open(analysis.source) as inp, av.open(out_path, "w") as out:
        vin = inp.streams.video[0]
        vin.thread_type = "AUTO"
        rate = vin.average_rate or 24
        vout = out.add_stream(spec["codec"], rate=rate, options=dict(spec["options"]))
        vout.width, vout.height = ow, oh
        vout.pix_fmt = spec["pix_fmt"]

        ain = aout = None
        audio_note = "none"
        if audio and inp.streams.audio:
            ain = inp.streams.audio[0]
            try:
                aout = out.add_stream_from_template(ain)
                audio_note = "copied"
            except Exception:
                # v0.1 honest limitation: stream-copy or nothing (no silent re-encode)
                ain = None
                audio_note = "skipped (codec/container combo not stream-copyable)"

        centers = solve.centers
        enhance_backend = None
        n = 0
        streams = [vin] + ([ain] if ain else [])
        for packet in inp.demux(streams):
            if ain is not None and packet.stream == ain:
                if aout is not None and packet.dts is not None:
                    packet.stream = aout
                    out.mux(packet)
                continue
            # NOTE: dts-None packets are PyAV's EOF flush — they drain the
            # threaded decoder's buffered frames. Never skip them before decode.
            for frame in packet.decode():
                img = frame.to_ndarray(format="bgr24")
                c = centers[min(n, len(centers) - 1)] if centers else 0.5
                x, y, w, h = rect_for_center(geom, c)
                crop = img[y:y + h, x:x + w]
                if (w, h) != (ow, oh):
                    if enhance and ow > w:
                        from rise import engine as rise_engine
                        scale = 2 if ow <= 2 * w else 4
                        crop, einfo = rise_engine.upscale_frame(
                            crop, scale, model=enhance_model)
                        enhance_backend = einfo.backend
                        interp = (cv2.INTER_AREA if crop.shape[1] >= ow
                                  else cv2.INTER_LANCZOS4)
                    else:
                        interp = cv2.INTER_LANCZOS4 if (ow > w) else cv2.INTER_AREA
                    crop = cv2.resize(crop, (ow, oh), interpolation=interp)
                vf = av.VideoFrame.from_ndarray(crop, format="bgr24")
                for pkt in vout.encode(vf):
                    out.mux(pkt)
                n += 1
                if progress and n % 120 == 0:
                    progress(n)
        for pkt in vout.encode():
            out.mux(pkt)

    return {"frames": n, "out": out_path, "size": [ow, oh],
            "punch_in": round(punch_in, 3), "codec": codec, "audio": audio_note,
            "enhance": enhance_backend or "off"}
