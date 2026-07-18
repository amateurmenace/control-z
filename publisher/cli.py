"""publisher-cli — every UI control, scriptable by hand (the house rule).

  publisher-cli candidates MEETING.mp4
  publisher-cli kit MEETING.mp4 [--ai] [--instruction "shorter, warmer"]
  publisher-cli render MEETING.mp4 --start 120 --end 150 [--ratios 16x9,9x16]
  publisher-cli bundle MEETING.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import brand as brandmod
from . import bundle as bundlemod
from . import kit as kitmod
from . import render as rendermod


def _err(msg: str) -> int:
    print(f"publisher: {msg}", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="publisher-cli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("candidates", help="score the program, print the picks")
    c.add_argument("source")
    c.add_argument("-n", type=int, default=5)

    k = sub.add_parser("kit", help="build (or rebuild) the kit sidecar")
    k.add_argument("source")
    k.add_argument("-n", type=int, default=5)
    k.add_argument("--ai", action="store_true",
                   help="also draft generative copy with your configured key")
    k.add_argument("--instruction", default="",
                   help="a note to the generative pass ('shorter, warmer')")

    r = sub.add_parser("render", help="cut one span in one or more ratios")
    r.add_argument("source")
    r.add_argument("--start", type=float, required=True)
    r.add_argument("--end", type=float, required=True)
    r.add_argument("--ratios", default="16x9",
                   help="comma list of 16x9,1x1,9x16")
    r.add_argument("--offset", type=float, default=0.0,
                   help="crop slide -1..1 for the square/vertical cuts")
    r.add_argument("--no-captions", action="store_true")
    r.add_argument("--out", default="", help="output stem (default: beside "
                   "the publisher media dir)")

    b = sub.add_parser("bundle", help="assemble the export folder + zip "
                       "from the saved kit")
    b.add_argument("source")

    a = p.parse_args(argv)
    src = str(Path(a.source).expanduser())

    if a.cmd == "candidates":
        cands = kitmod.candidates(src, n=a.n)
        if not cands:
            return _err("no transcript or highlights beside that source — "
                        "run it through Highlighter or Scribe first")
        print(json.dumps(cands, indent=1))
        return 0

    if a.cmd == "kit":
        kit = kitmod.new_kit(src, n=a.n)
        if not kit["candidates"]:
            return _err("no transcript or highlights beside that source — "
                        "run it through Highlighter or Scribe first")
        if a.ai:
            voice = brandmod.VOICES[brandmod.get_brand()["voice"]]
            try:
                gen = kitmod.copy_generative(kit["meta"], kit["candidates"],
                                             kitmod._read_json(
                                                 kitmod.sidecars(src)["insight"])
                                             or {}, voice, a.instruction)
                kit["copy_ai"] = gen
            except RuntimeError as e:
                print(f"generative pass skipped — {e}", file=sys.stderr)
        path = kitmod.save_kit(src, kit)
        print(f"kit → {path}  ({len(kit['candidates'])} candidates)")
        return 0

    if a.cmd == "render":
        video = kitmod.video_path(src)
        if not video:
            return _err("no video file behind that source")
        segs = kitmod.segments(src)
        cues = [] if a.no_captions else rendermod.cues_for_span(
            segs, a.start, a.end)
        brand = brandmod.get_brand()
        stem = a.out or str(bundlemod.media_dir("publisher")
                            / f"{video.stem}-{int(a.start)}-{int(a.end)}")
        for ratio in [x.strip() for x in a.ratios.split(",") if x.strip()]:
            res = rendermod.render_clip(
                str(video), a.start, a.end, stem, ratio=ratio, cues=cues,
                brand=brand, offset=a.offset,
                progress=lambda f, _m: print(f"\r{ratio} {f * 100:3.0f}%",
                                             end="", flush=True))
            print(f"\r{ratio} → {res['out']}  ({res['captions']} captions"
                  f"{', lower-third' if res['lower_third'] else ''})")
        return 0

    if a.cmd == "bundle":
        kit = kitmod.load_kit(src)
        if not kit:
            return _err("no kit sidecar yet — run `publisher-cli kit` first")
        rendered = [f for f in kit.get("files", [])
                    if isinstance(f, dict) and f.get("kind") == "clip"]
        thumbs = [f for f in kit.get("files", [])
                  if isinstance(f, dict) and f.get("kind") == "thumb"]
        out = bundlemod.assemble(src, kit, rendered, thumbs)
        print(f"bundle → {out['dir']}\nzip    → {out['zip']}\n"
              f"({out['clips']} clips, {out['thumbs']} thumbs)")
        return 0

    return _err("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
