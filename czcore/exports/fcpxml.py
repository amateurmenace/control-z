"""FCPXML stringout — the selects leave as a timeline Resolve just imports.

One project, one spine, the chosen clips back to back at full length.
Written as FCPXML 1.8 with `src` directly on the asset — the oldest form
every importer still reads. EDL can't do a multi-source stringout (one reel
per event, relink pain); this can, which is why Index speaks it.
"""

from __future__ import annotations

from fractions import Fraction
from typing import List, Optional
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

# editorial rates get their exact NTSC rationals; anything else is rounded
# to a rational over 1000 (Resolve accepts arbitrary rationals)
_NTSC = {23.976: Fraction(1001, 24000), 29.97: Fraction(1001, 30000),
         59.94: Fraction(1001, 60000)}


def frame_duration(fps: Optional[float]) -> Fraction:
    if not fps or fps <= 0:
        return Fraction(1, 25)
    for known, frac in _NTSC.items():
        if abs(fps - known) < 0.005:
            return frac
    if abs(fps - round(fps)) < 1e-6:
        return Fraction(1, int(round(fps)))
    return Fraction(round(1000 / fps), 1000).limit_denominator(100000)


def _rat(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}s" if x.denominator != 1 else f"{x.numerator}s"


def _secs(t: float) -> str:
    return _rat(Fraction(round(float(t) * 1000), 1000))


def stringout(clips: List[dict], name: str = "control-z selects") -> str:
    """clips: [{path, name?, duration, fps?, width?, height?, audio?}] ->
    FCPXML text. Raises ValueError on an empty list."""
    if not clips:
        raise ValueError("nothing selected — pick clips first")
    first = clips[0]
    fd = frame_duration(first.get("fps"))
    w = int(first.get("width") or 1920)
    h = int(first.get("height") or 1080)

    assets, spine = [], []
    offset = Fraction(0)
    for i, c in enumerate(clips):
        rid = f"r{i + 2}"
        dur = Fraction(round(float(c.get("duration") or 1.0) * 1000), 1000)
        label = c.get("name") or str(c["path"]).rsplit("/", 1)[-1]
        src = "file://" + quote(str(c["path"]))
        assets.append(
            f'    <asset id={quoteattr(rid)} name={quoteattr(label)} start="0s" '
            f'duration="{_rat(dur)}" hasVideo="1" '
            f'hasAudio="{1 if c.get("audio") else 0}" src={quoteattr(src)}/>')
        spine.append(
            f'          <asset-clip ref={quoteattr(rid)} offset="{_rat(offset)}" '
            f'start="0s" duration="{_rat(dur)}" name={quoteattr(label)}/>')
        offset += dur

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.8">
  <resources>
    <format id="r1" frameDuration="{_rat(fd)}" width="{w}" height="{h}"/>
{chr(10).join(assets)}
  </resources>
  <library>
    <event name={quoteattr(name)}>
      <project name={quoteattr(name)}>
        <sequence format="r1" duration="{_rat(offset)}" tcStart="0s">
          <spine>
{chr(10).join(spine)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""


def selects_csv(clips: List[dict]) -> str:
    """The spreadsheet form of the same list."""
    import csv
    import io

    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["path", "name", "duration_s", "fps", "width", "height",
                 "codec", "transcribed"])
    for c in clips:
        wr.writerow([c.get("path"), c.get("name"),
                     round(float(c.get("duration") or 0), 2), c.get("fps"),
                     c.get("width"), c.get("height"), c.get("codec"),
                     "yes" if c.get("sidecar_mtime") else ""])
    return buf.getvalue()
