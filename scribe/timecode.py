"""Timecode math shared by every Scribe export. Pure, golden-tested.

Non-drop-frame throughout v0.1 (drop-frame export is a documented limitation:
markers land within a frame at 23.976/29.97 over typical program lengths when
the source TC is NDF, which is the norm for file-based community workflows).
"""

from __future__ import annotations


def tc_rate(fps: float) -> int:
    """Nominal TC base (24 for 23.976, 30 for 29.97…)."""
    return int(round(fps))


def seconds_to_frames(seconds: float, fps: float) -> int:
    return int(round(seconds * fps))


def frames_to_tc(frames: int, fps: float) -> str:
    base = tc_rate(fps)
    f = frames % base
    s = (frames // base) % 60
    m = (frames // (base * 60)) % 60
    h = frames // (base * 3600)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def seconds_to_tc(seconds: float, fps: float) -> str:
    return frames_to_tc(seconds_to_frames(seconds, fps), fps)


def tc_to_frames(tc: str, fps: float) -> int:
    h, m, s, f = (int(x) for x in tc.replace(";", ":").split(":"))
    base = tc_rate(fps)
    return ((h * 3600 + m * 60 + s) * base) + f


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(seconds: float) -> str:
    return srt_time(seconds).replace(",", ".")
