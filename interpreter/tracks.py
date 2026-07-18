"""Caption track writers — timed cues out as .srt and .vtt, provenance on.

Pure text generation, golden-tested. The timecode math is Scribe's
(scribe.timecode — read-only reuse; one clock for the whole suite). The
VTT carries its provenance as a NOTE block right in the file, because a
track that leaves this app should keep saying what it is.
"""

from __future__ import annotations

import re
import textwrap
from typing import List, Optional

from scribe.timecode import srt_time, vtt_time

# a cue's text must never impersonate timing or markup
_ARROW = re.compile(r"-->")


def _clean(text: str) -> str:
    return _ARROW.sub("→", str(text)).replace("\r", " ").replace("\n", " ").strip()


def _wrap(text: str, width: int = 42, lines: int = 2) -> str:
    got = textwrap.wrap(_clean(text), width=width) or [""]
    if len(got) > lines:
        got = got[:lines - 1] + [" ".join(got[lines - 1:])]
    return "\n".join(got)


def to_srt(cues: List[dict]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{srt_time(float(c['start']))} --> "
                   f"{srt_time(float(c['end']))}\n{_wrap(c['text'])}\n")
    return "\n".join(out)


def to_vtt(cues: List[dict], note: Optional[str] = None) -> str:
    out = ["WEBVTT", ""]
    if note:
        out += ["NOTE", _clean(note), ""]
    for c in cues:
        out.append(f"{vtt_time(float(c['start']))} --> "
                   f"{vtt_time(float(c['end']))}\n{_wrap(c['text'])}\n")
    return "\n".join(out)
