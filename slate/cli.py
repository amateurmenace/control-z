"""slate-cli — station graphics without opening a window.

    slate-cli l3 "Jane Q. Public" "Select Board Chair" --style bar \\
        --formats prores,png,gif --out ~/Movies/control-z/slate/jane
    slate-cli bars --duration 30 --out bars
    slate-cli countdown --seconds 8 --out leader
    slate-cli card --program "Select Board 7/15" --trt "1:42:00" --out slate
    slate-cli fonts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from czcore.paths import media_dir


def _out(arg, stem):
    return str(Path(arg).expanduser()) if arg else str(media_dir("slate") / stem)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="slate-cli", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    l3 = sub.add_parser("l3", help="lower third → ProRes 4444 / PNG / GIF")
    l3.add_argument("line1")
    l3.add_argument("line2", nargs="?", default="")
    l3.add_argument("--style", default="bar", help="bar | block | line | clean")
    l3.add_argument("--anim", default="slide", help="slide | rise | fade | none")
    l3.add_argument("--accent", default="#E5A835")
    l3.add_argument("--font", default="")
    l3.add_argument("--size", default="1920x1080")
    l3.add_argument("--fps", type=float, default=30.0)
    l3.add_argument("--hold", type=float, default=4.0)
    l3.add_argument("--formats", default="prores,png")
    l3.add_argument("--out", default=None)

    b = sub.add_parser("bars", help="SMPTE HD bars + 1 kHz tone")
    b.add_argument("--duration", type=float, default=30.0)
    b.add_argument("--out", default=None)

    cd = sub.add_parser("countdown", help="counting leader with beeps")
    cd.add_argument("--seconds", type=int, default=8)
    cd.add_argument("--out", default=None)

    card = sub.add_parser("card", help="program slate card (PNG + optional still)")
    for f in ("program", "episode", "producer", "station", "date", "trt",
              "audio", "notes"):
        card.add_argument(f"--{f}", default="")
    card.add_argument("--still", type=float, default=0.0,
                      help="also render N seconds of held ProRes")
    card.add_argument("--out", default=None)

    sub.add_parser("fonts", help="list the fonts Slate can see")

    a = ap.parse_args(argv)
    prog = lambda p, m: print(f"\r{m or f'{p*100:5.1f}%':60}", end="", flush=True)  # noqa: E731

    if a.cmd == "fonts":
        from .fonts import discover
        for f in discover():
            print(f"{f['name']:36} {f['path']}")
        return
    if a.cmd == "l3":
        from .lowerthird import LowerThird
        w, h = (int(x) for x in a.size.lower().split("x"))
        p = LowerThird.from_dict(dict(
            line1=a.line1, line2=a.line2, style=a.style, anim=a.anim,
            accent=a.accent, font=a.font, width=w, height=h, fps=a.fps,
            hold=a.hold))
        stem = _out(a.out, "".join(c for c in a.line1 if c.isalnum()) or "l3")
        wrote = []
        kinds = {k.strip() for k in a.formats.split(",")}
        from . import render
        if "prores" in kinds or "mov" in kinds:
            wrote.append(render.write_prores4444(p, stem, progress=prog)["out"])
        if "png" in kinds:
            wrote.append(render.write_png(p, stem)["out"])
        if "gif" in kinds:
            wrote.append(render.write_gif(p, stem, progress=prog)["out"])
        print("\n" + "\n".join(f"→ {w}" for w in wrote))
        return
    from . import generators
    if a.cmd == "bars":
        r = generators.bars_tone(_out(a.out, "bars-tone"), duration=a.duration,
                                 progress=prog)
    elif a.cmd == "countdown":
        r = generators.countdown(_out(a.out, "countdown"), seconds=a.seconds,
                                 progress=prog)
    else:
        fields = {k: getattr(a, k) for k in
                  ("program", "episode", "producer", "station", "date", "trt",
                   "audio", "notes")}
        r = generators.slate_card(fields, _out(a.out, "slate-card"),
                                  still_seconds=a.still, progress=prog)
    print("\n" + "\n".join(f"→ {v}" for v in
                           ([r["out"]] if "out" in r else list(r.values())
                            if isinstance(r, dict) else [r])
                           if isinstance(v, str)))


if __name__ == "__main__":
    sys.exit(main())
