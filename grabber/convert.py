"""Conform for air — the download becomes something a playout server takes.

Zoom hands back variable-frame-rate screen-capture-ish files; broadcast
wants constant rate, a real codec, sane audio. One ffmpeg pass: constant
fps, optional height, encoder from the shared presets (hardware when the
box has it), PCM audio into mov / AAC into mp4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from czcore import ffrun
from czcore.media import probe, resolve_preset

CONFORM_PRESETS = ("prores-422", "prores-hq", "dnxhr-hqx", "h264", "hevc")


def convert(src: str, out_dir: str, preset: str = "prores-422",
            fps: Optional[float] = None, height: Optional[int] = None,
            progress: Optional[Callable[[float, str], None]] = None,
            cancelled: Optional[Callable[[], bool]] = None) -> dict:
    info = probe(src)
    spec = resolve_preset(preset)
    p = Path(src)
    out = str(Path(out_dir) / f"{p.stem}.{preset}.{spec['container']}")

    vf = []
    if height:
        vf.append(f"scale=-2:{int(height)}:flags=lanczos")
    if fps:
        vf.append(f"fps={fps}")
    args = ["-i", src]
    if vf:
        args += ["-vf", ",".join(vf)]
    elif fps is None:
        # VFR screen captures make editors seek badly — conform to the
        # measured average rate even when no explicit rate was asked for
        r = info.video.fps if info.video and info.video.fps else None
        if r:
            args += ["-vf", f"fps={r:.5g}"]
    args += ffrun.encoder_args(spec, audio=info.audio_streams > 0)
    args += [out]
    ffrun.run(args, duration=info.duration or None,
              progress=progress, cancelled=cancelled)
    return {"out": out, "encoder": spec["codec"], "hardware": spec["hardware"],
            "label": spec["label"]}
