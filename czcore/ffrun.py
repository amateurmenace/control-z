"""Run ffmpeg with honest progress — shared by every tool that shells out.

PyAV owns the frame-accurate loops (Pivot, Rise, Stencil renders); this is
for the jobs where ffmpeg's own graph is the right tool (concat reels,
conform passes, lavfi generators). `-progress pipe:1` gives machine-readable
out_time, which becomes a 0..1 fraction against a known duration.
"""

from __future__ import annotations

import re
import subprocess
from typing import Callable, Optional

from .tools import ffmpeg_path


def encoder_args(spec: dict, audio: bool = True) -> list:
    """czcore.media.resolve_preset() spec -> ffmpeg output args.

    Audio: PCM into mov (broadcast conform wants it), AAC into mp4 — both
    encoders live in LGPL ffmpeg; nothing here may ever name a GPL one.
    audio=False writes -an (sources with no track, mattes).
    """
    args = ["-c:v", spec["codec"], "-pix_fmt", spec["pix_fmt"]]
    for k, v in spec["options"].items():
        args += [f"-{k}", str(v)]
    if not audio:
        args += ["-an"]
    elif spec["container"] == "mov":
        args += ["-c:a", "pcm_s16le"]
    else:
        args += ["-c:a", "aac", "-b:a", "192k"]
    return args


_OUT_TIME = re.compile(r"out_time_ms=(\d+)")
_OUT_TIME_S = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def run(args: list, duration: Optional[float] = None,
        progress: Optional[Callable[[float, str], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None) -> None:
    """ffmpeg with the given args (input→output section, no exe, no -y).

    Raises RuntimeError carrying ffmpeg's last useful line on failure.
    """
    cmd = [ffmpeg_path(), "-y", "-hide_banner", "-nostdin",
           "-progress", "pipe:1", "-v", "error"] + [str(a) for a in args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1)
    for line in proc.stdout:
        if cancelled and cancelled():
            proc.terminate()
            proc.wait(timeout=10)
            raise RuntimeError("cancelled")
        if not (progress and duration):
            continue
        m = _OUT_TIME.search(line)
        t = int(m.group(1)) / 1e6 if m else None
        if t is None:
            m = _OUT_TIME_S.search(line)
            if m:
                t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        if t is not None:
            progress(max(0.0, min(1.0, t / max(duration, 0.01))), "")
    err = proc.stderr.read()
    if proc.wait() != 0:
        last = next((ln for ln in reversed(err.strip().splitlines()) if ln.strip()),
                    "ffmpeg failed with no message")
        raise RuntimeError(f"render failed — {last.strip()[:300]}")
