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
    denoise: bool = False,
    progress=None,
    codec_spec: Optional[dict] = None,
    should_stop=None,
) -> dict:
    """Render one aspect. Returns a small report dict (frames, punch-in, output).

    codec_spec (from czcore.media.resolve_preset) overrides the legacy CODECS
    table — the suite's export-panel path. should_stop() -> True aborts the
    render, removes the partial file, and raises JobCancelled.

    denoise=True cleans each crop with the Hush core BEFORE any scaling —
    punch-ins amplify noise, and Rise's synthesis model fed noise invents
    texture from it. The temporal neighbors are the adjacent frames cropped
    at THIS frame's rect, so the stack stays registered while the camera
    path moves. Adds a 1-frame lookahead; named in the report.
    """
    import av
    import cv2

    from czcore.appshell.jobs import JobCancelled
    from czcore.media import copy_color_tags

    solve = analysis.aspects[aspect]
    geom = CropGeometry(analysis.width, analysis.height,
                        solve.crop_w, solve.crop_h, solve.axis)
    if out_size is None:
        out_size = (geom.crop_w, geom.crop_h)  # native: never upscale silently
    ow, oh = out_size
    punch_in = ow / geom.crop_w
    spec = codec_spec or CODECS[codec]

    try:
        with av.open(analysis.source) as inp, av.open(out_path, "w") as out:
            vin = inp.streams.video[0]
            vin.thread_type = "AUTO"
            rate = vin.average_rate or 24
            vout = out.add_stream(spec["codec"], rate=rate,
                                  options=dict(spec["options"]))
            vout.width, vout.height = ow, oh
            vout.pix_fmt = spec["pix_fmt"]
            color_note = copy_color_tags(vin.codec_context, vout.codec_context)

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
            denoise_info = None
            n = 0

            def process(prev_full, img, next_full):
                nonlocal enhance_backend, denoise_info, n
                c = centers[min(n, len(centers) - 1)] if centers else 0.5
                x, y, w, h = rect_for_center(geom, c)
                crop = img[y:y + h, x:x + w]
                if denoise:
                    # neighbors cropped at THIS frame's rect: registered stack
                    from czcore.denoise import denoise_trio
                    p_crop = prev_full[y:y + h, x:x + w] if prev_full is not None else None
                    n_crop = next_full[y:y + h, x:x + w] if next_full is not None else None
                    crop, denoise_info = denoise_trio(p_crop, crop, n_crop)
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
                if progress and n % 24 == 0:
                    progress(n)
                if should_stop and should_stop():
                    raise JobCancelled()

            # 1-frame lookahead so the denoiser sees (prev, cur, next)
            prev_full = None
            pending = None
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
                    if pending is not None:
                        process(prev_full, pending, img)
                        prev_full = pending if denoise else None
                    pending = img
            if pending is not None:
                process(prev_full, pending, None)
            for pkt in vout.encode():
                out.mux(pkt)
    except JobCancelled:
        # containers are closed by now; a half-written master helps no one
        from pathlib import Path
        Path(out_path).unlink(missing_ok=True)
        raise

    return {"frames": n, "out": out_path, "size": [ow, oh],
            "punch_in": round(punch_in, 3),
            "codec": spec["label"] if codec_spec else codec,
            "audio": audio_note,
            "enhance": enhance_backend or "off", "encoder": spec["codec"],
            "denoise": denoise_info or "off",
            "color": color_note}
