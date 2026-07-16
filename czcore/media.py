"""Media probing (ffprobe wrapper) with a pure parser for tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from typing import List, Optional


@dataclass
class VideoStreamInfo:
    width: int
    height: int
    fps: float
    codec: str = ""
    pix_fmt: str = ""
    nb_frames: Optional[int] = None


@dataclass
class MediaInfo:
    path: str
    duration: float
    video: Optional[VideoStreamInfo]
    audio_streams: int = 0
    timecode: Optional[str] = None
    container: str = ""
    raw: dict = field(default_factory=dict, repr=False)


def _parse_rate(rate: str) -> float:
    try:
        return float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        return 0.0


def parse_probe(path: str, data: dict) -> MediaInfo:
    """Pure parser for ffprobe -print_format json output (testable offline)."""
    fmt = data.get("format", {})
    video = None
    audio = 0
    timecode = fmt.get("tags", {}).get("timecode")
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and video is None:
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            if rate in ("0/0", "0/1"):
                rate = s.get("r_frame_rate", "0/1")
            nb = s.get("nb_frames")
            video = VideoStreamInfo(
                width=int(s.get("width", 0)),
                height=int(s.get("height", 0)),
                fps=_parse_rate(rate),
                codec=s.get("codec_name", ""),
                pix_fmt=s.get("pix_fmt", ""),
                nb_frames=int(nb) if nb and str(nb).isdigit() else None,
            )
            timecode = timecode or s.get("tags", {}).get("timecode")
        elif s.get("codec_type") == "audio":
            audio += 1
    return MediaInfo(
        path=path,
        duration=float(fmt.get("duration", 0.0) or 0.0),
        video=video,
        audio_streams=audio,
        timecode=timecode,
        container=fmt.get("format_name", ""),
        raw=data,
    )


def probe(path: str) -> MediaInfo:
    """Probe a media file. Needs ffprobe on PATH (bundled in packaged builds)."""
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError(
            "ffprobe not found. Install ffmpeg (brew install ffmpeg) or use a "
            "packaged control-z build, which bundles it."
        )
    out = subprocess.run(
        [exe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return parse_probe(path, json.loads(out))
