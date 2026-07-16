"""Caption + Resolve roundtrip writers. Pure text generation, golden-tested.

SRT/VTT with broadcast-style line presets; marker EDL (Timeline → Import →
Timeline Markers From EDL — works in free Resolve); CMX3600 selects EDL from a
pull list (conforms against the source clip in the media pool).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import List, Optional

from .timecode import frames_to_tc, seconds_to_frames, srt_time, vtt_time
from .transcript import Transcript

SPEAKER_COLORS = ["Blue", "Green", "Yellow", "Red", "Purple", "Cyan", "Pink"]


@dataclass(frozen=True)
class CaptionPreset:
    max_chars: int = 38     # per line
    max_lines: int = 2

    def wrap(self, text: str) -> List[str]:
        lines = textwrap.wrap(text.strip(), width=self.max_chars)
        return lines[: self.max_lines] if lines else [""]


PRESETS = {
    "broadcast": CaptionPreset(32, 2),
    "standard": CaptionPreset(38, 2),
    "social": CaptionPreset(24, 1),
}


def _caption_blocks(t: Transcript, preset: CaptionPreset):
    """Split segments into blocks that fit the preset (by words when needed)."""
    blocks = []
    for seg in t.segments:
        lines = textwrap.wrap(seg.text.strip(), width=preset.max_chars)
        if len(lines) <= preset.max_lines or not seg.words:
            blocks.append((seg.start, seg.end, preset.wrap(seg.text)))
            continue
        # too long: split by words into caption-sized chunks with real timings
        max_chunk = preset.max_chars * preset.max_lines
        cur, cur_len = [], 0
        for w in seg.words:
            if cur and cur_len + len(w.w) + 1 > max_chunk:
                blocks.append((cur[0].s, cur[-1].e,
                               preset.wrap(" ".join(x.w for x in cur))))
                cur, cur_len = [], 0
            cur.append(w)
            cur_len += len(w.w) + 1
        if cur:
            blocks.append((cur[0].s, cur[-1].e,
                           preset.wrap(" ".join(x.w for x in cur))))
    return blocks


def to_srt(t: Transcript, preset: str = "standard") -> str:
    p = PRESETS[preset]
    out = []
    for i, (s, e, lines) in enumerate(_caption_blocks(t, p), 1):
        out.append(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n" + "\n".join(lines) + "\n")
    return "\n".join(out)


def to_vtt(t: Transcript, preset: str = "standard") -> str:
    p = PRESETS[preset]
    out = ["WEBVTT", ""]
    for s, e, lines in _caption_blocks(t, p):
        out.append(f"{vtt_time(s)} --> {vtt_time(e)}\n" + "\n".join(lines) + "\n")
    return "\n".join(out)


def to_marker_edl(t: Transcript, fps: float, record_start_tc: str = "01:00:00:00",
                  color_by_speaker: bool = True) -> str:
    """One Resolve marker per segment, colored per speaker, at the segment start."""
    from .timecode import tc_to_frames

    base = tc_to_frames(record_start_tc, fps)
    speakers = [s for s in t.speakers] or \
        sorted({seg.speaker for seg in t.segments if seg.speaker})
    color_of = {sp: SPEAKER_COLORS[i % len(SPEAKER_COLORS)]
                for i, sp in enumerate(speakers)}
    lines = ["TITLE: Scribe markers", "FCM: NON-DROP FRAME", ""]
    for i, seg in enumerate(t.segments, 1):
        f = base + seconds_to_frames(seg.start, fps)
        tc_in, tc_out = frames_to_tc(f, fps), frames_to_tc(f + 1, fps)
        color = color_of.get(seg.speaker, "Blue") if color_by_speaker else "Blue"
        name = (f"{seg.speaker}: " if seg.speaker else "") + seg.text.strip()
        name = name[:80].replace("|", "/")
        lines.append(f"{i:03d}  001      V     C        "
                     f"{tc_in} {tc_out} {tc_in} {tc_out}")
        lines.append(f" |C:ResolveColor{color} |M:{name} |D:1")
        lines.append("")
    return "\n".join(lines)


@dataclass
class Select:
    start: float            # source seconds
    end: float
    label: str = ""


def to_selects_edl(selects: List[Select], fps: float, reel: str = "AX",
                   source_start_tc: str = "00:00:00:00",
                   record_start_tc: str = "01:00:00:00",
                   handles: float = 0.0, clip_name: Optional[str] = None) -> str:
    """CMX3600 cut list: each select becomes an event, record TC accumulates."""
    from .timecode import tc_to_frames

    src_base = tc_to_frames(source_start_tc, fps)
    rec = tc_to_frames(record_start_tc, fps)
    lines = ["TITLE: Scribe selects", "FCM: NON-DROP FRAME", ""]
    for i, sel in enumerate(selects, 1):
        s = max(0.0, sel.start - handles)
        e = sel.end + handles
        sf = src_base + seconds_to_frames(s, fps)
        ef = src_base + seconds_to_frames(e, fps)
        dur = ef - sf
        lines.append(f"{i:03d}  {reel:<8} V     C        "
                     f"{frames_to_tc(sf, fps)} {frames_to_tc(ef, fps)} "
                     f"{frames_to_tc(rec, fps)} {frames_to_tc(rec + dur, fps)}")
        if clip_name:
            lines.append(f"* FROM CLIP NAME: {clip_name}")
        if sel.label:
            lines.append(f"* COMMENT: {sel.label[:70]}")
        lines.append("")
        rec += dur
    return "\n".join(lines)
