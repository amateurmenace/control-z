"""Media probing (ffprobe wrapper) with a pure parser for tests."""

from __future__ import annotations

import json
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
    """Probe a media file. czcore.tools resolves ffprobe (bundled or PATH)."""
    from czcore.tools import ffprobe_path

    exe = ffprobe_path()
    out = subprocess.run(
        [exe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return parse_probe(path, json.loads(out))


# --- export presets (the suite's delivery contract, specs/08 §4) -------------
#
# A preset maps to an ordered list of encoder candidates; the first one whose
# encoder exists in the linked FFmpeg (and opens) wins. Hardware ProRes on
# Apple Silicon is preferred where it matches the profile; prores_ks is the
# always-there software path. Every render reports which encoder actually ran.

@dataclass(frozen=True)
class EncoderChoice:
    codec: str                    # FFmpeg encoder name
    pix_fmt: str                  # no-alpha pixel format
    options: tuple                # (key, value) pairs — hashable, dict() when used
    hardware: bool = False
    pix_fmt_alpha: str = ""       # set when this encoder can carry alpha


@dataclass(frozen=True)
class ExportPreset:
    id: str
    label: str
    container: str                # output extension, no dot
    candidates: tuple             # EncoderChoice, first available wins
    alpha: bool = False           # preset can carry an alpha channel
    note: str = ""                # honest one-liner shown in the UI


EXPORT_PRESETS = {
    "prores-422": ExportPreset(
        id="prores-422", label="ProRes 422", container="mov",
        candidates=(
            EncoderChoice("prores_videotoolbox", "p210le",
                          (("profile", "standard"),), hardware=True),
            EncoderChoice("prores_ks", "yuv422p10le", (("profile", "2"),)),
        ),
        note="10-bit 4:2:2 — the everyday finishing master."),
    "prores-hq": ExportPreset(
        id="prores-hq", label="ProRes 422 HQ", container="mov",
        candidates=(
            EncoderChoice("prores_videotoolbox", "p210le",
                          (("profile", "hq"),), hardware=True),
            EncoderChoice("prores_ks", "yuv422p10le", (("profile", "3"),)),
        ),
        note="Higher-bitrate 4:2:2 — grade-ready."),
    "prores-4444": ExportPreset(
        id="prores-4444", label="ProRes 4444", container="mov",
        candidates=(
            EncoderChoice("prores_ks", "yuv444p10le", (("profile", "4"),),
                          pix_fmt_alpha="yuva444p10le"),
        ),
        alpha=True,
        note="Full 4:4:4 + alpha — mattes and keys travel in this."),
    "dnxhr-hqx": ExportPreset(
        id="dnxhr-hqx", label="DNxHR HQX", container="mov",
        candidates=(
            EncoderChoice("dnxhd", "yuv422p10le", (("profile", "dnxhr_hqx"),)),
        ),
        note="10-bit Avid-world master."),
    "h264": ExportPreset(
        id="h264", label="H.264", container="mp4",
        candidates=(
            # Hardware only, deliberately: the software fallbacks that used to
            # sit here were libx264/libx265, which are GPL — shipping them
            # relicenses the whole app (specs/09 §3). No candidate may ever be
            # a GPL encoder; tests/test_export_presets.py pins this.
            EncoderChoice("h264_videotoolbox", "yuv420p",
                          (("q:v", "55"),), hardware=True),
        ),
        note="Delivery/social — hardware encode."),
    "hevc": ExportPreset(
        id="hevc", label="HEVC", container="mp4",
        candidates=(
            EncoderChoice("hevc_videotoolbox", "yuv420p",
                          (("q:v", "55"),), hardware=True),
        ),
        note="Half the size of H.264 — slower players."),
}

_encoder_ok: dict = {}


def encoder_available(name: str) -> bool:
    """True when the linked FFmpeg has this encoder (cached)."""
    if name not in _encoder_ok:
        try:
            import av.codec
            av.codec.Codec(name, "w")
            _encoder_ok[name] = True
        except Exception:
            _encoder_ok[name] = False
    return _encoder_ok[name]


def resolve_preset(preset_id: str, alpha: bool = False) -> dict:
    """Preset id -> concrete encode spec: the first available candidate.

    Returns {codec, pix_fmt, options, hardware, container, label, alpha}.
    alpha=True asks for an alpha-capable pixel format; only presets with
    alpha support honor it (others ignore it — never silently promise alpha).
    """
    p = EXPORT_PRESETS[preset_id]
    for c in p.candidates:
        if encoder_available(c.codec):
            with_alpha = bool(alpha and p.alpha and c.pix_fmt_alpha)
            return {
                "codec": c.codec,
                "pix_fmt": c.pix_fmt_alpha if with_alpha else c.pix_fmt,
                "options": dict(c.options),
                "hardware": c.hardware,
                "container": p.container,
                "label": p.label,
                "alpha": with_alpha,
            }
    raise RuntimeError(
        f"no encoder available for preset {preset_id!r} "
        f"(tried {[c.codec for c in p.candidates]})")


_COLOR_ATTRS = ("color_primaries", "color_trc", "colorspace", "color_range")

_PRIMARIES = {1: "bt709", 5: "bt470bg", 6: "smpte170m", 9: "bt2020"}
_RANGE = {0: "untagged", 1: "limited", 2: "full"}


def copy_color_tags(src_codec_context, dst_codec_context) -> str:
    """Pass color metadata through untouched; return an honest report string.

    Never converts — Rise/Pivot masters keep their source tagging (601 stays
    601 and says so; the report is the covenant surface for color).
    """
    seen = {}
    for attr in _COLOR_ATTRS:
        v = getattr(src_codec_context, attr, None)
        if v is None:
            continue
        try:
            setattr(dst_codec_context, attr, v)
            seen[attr] = int(v)
        except (AttributeError, ValueError):
            pass
    if not seen:
        return "color tags: none readable (left untagged)"
    prim = _PRIMARIES.get(seen.get("color_primaries", 2), f"code {seen.get('color_primaries')}")
    rng = _RANGE.get(seen.get("color_range", 0), f"code {seen.get('color_range')}")
    return f"color tags passed through: primaries {prim}, range {rng}"


def presets_report() -> list:
    """What the export panel shows: every preset + which encoder would run."""
    out = []
    for p in EXPORT_PRESETS.values():
        chosen = None
        for c in p.candidates:
            if encoder_available(c.codec):
                chosen = c
                break
        out.append({
            "id": p.id, "label": p.label, "container": p.container,
            "alpha": p.alpha, "note": p.note,
            "encoder": chosen.codec if chosen else None,
            "hardware": chosen.hardware if chosen else False,
            "available": chosen is not None,
        })
    return out
