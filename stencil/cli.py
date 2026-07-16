"""stencil-cli — prompt-file driven roto for one clip (UI arrives in v0.2).

Prompts JSON:
{
  "objects": [
    {"id": 1, "points": [
      {"frame": 0, "xy": [0.34, 0.42], "label": 1},
      {"frame": 120, "xy": [0.8, 0.5], "label": 0}
    ]}
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import __version__
from .post import PostParams, apply_chain


def load_prompts(path: str):
    from .core import Prompt

    data = json.loads(Path(path).read_text())
    prompts = []
    for obj in data.get("objects", []):
        oid = int(obj.get("id", 1))
        for p in obj.get("points", []):
            xy = p["xy"]
            if not (0 <= xy[0] <= 1 and 0 <= xy[1] <= 1):
                raise ValueError(f"prompt xy must be normalized 0..1, got {xy}")
            prompts.append(Prompt(frame=int(p["frame"]), xy=(float(xy[0]), float(xy[1])),
                                  label=int(p.get("label", 1)), obj=oid))
    if not prompts:
        raise ValueError("no prompts in file")
    return prompts


def cmd_run(args) -> int:
    import numpy as np

    from czcore.media import probe

    from .core import StencilEngine, extract_frames
    from .export import write_luma, write_rgba

    src = args.input
    info = probe(src)
    n_frames = info.video.nb_frames or 10 ** 9
    start, end = 0, n_frames
    if args.range:
        s, e = args.range.split(":")
        start, end = int(s), int(e)

    say = print if not args.quiet else (lambda *a, **k: None)
    say(f"Stencil — {Path(src).name}  frames [{start}:{end})")
    with tempfile.TemporaryDirectory(prefix="stencil-") as td:
        frames_dir = Path(td) / "frames"
        say("  extracting analysis frames…")
        extract_frames(src, start, end, frames_dir,
                       progress=lambda m: say(f"  {m}", end="\r"))
        say("\n  loading SAM 2.1 (first run downloads the model)…")
        engine = StencilEngine()
        prompts = load_prompts(args.prompts)
        say(f"  propagating {len(prompts)} prompt(s) on device {engine.device}…")
        result = engine.run_shot(frames_dir, prompts,
                                 progress=lambda m: say(f"  {m}", end="\r"))
        say("")

    params = PostParams(grow=args.grow, feather=args.feather,
                        despeckle=args.despeckle, temporal=not args.no_temporal)
    rc = 0
    session = {"source": src, "range": [start, end], "prompts": args.prompts,
               "post": vars(params) if hasattr(params, "__dict__") else {
                   "grow": params.grow, "feather": params.feather,
                   "despeckle": params.despeckle, "temporal": params.temporal},
               "objects": {}, "version": __version__}
    for obj, masks in result.masks.items():
        masks = [m if m is not None else None for m in masks]
        processed = list(apply_chain(
            [m if m is not None else np.zeros_like(next(x for x in masks if x is not None))
             for m in masks], params))
        conf = result.confidence[obj]
        low = [i + start for i, c in enumerate(conf) if c < args.confidence_floor]
        stem = Path(src).stem
        suffix = f".stencil-obj{obj}" if len(result.masks) > 1 else ".stencil"
        out = args.output or str(Path(src).with_name(f"{stem}{suffix}.mov"))
        say(f"  object {obj}: exporting {args.out_mode} matte…")
        if args.out_mode == "rgba":
            n = write_rgba(processed, src, out, start=start,
                           progress=lambda m: say(f"  {m}", end="\r"))
        else:
            n = write_luma(iter(processed), src, out,
                           progress=lambda m: say(f"  {m}", end="\r"))
        say(f"\n  object {obj}: {n} frames → {out}")
        mean_conf = sum(conf) / max(1, len(conf))
        say(f"    confidence mean {mean_conf:.2f}; "
            f"{len(low)} frame(s) below {args.confidence_floor} "
            + (f"— CHECK: {low[:12]}{'…' if len(low) > 12 else ''}" if low else "— clean"))
        session["objects"][str(obj)] = {
            "out": out, "frames": n, "confidence_mean": round(mean_conf, 4),
            "low_confidence_frames": low,
        }
    sc = Path(src).with_suffix(".stencil.json")
    sc.write_text(json.dumps(session, indent=1))
    say(f"  session → {sc}")
    say("  Resolve: Media Pool → import matte → right-click grade node → Add Matte "
        "(or drop the rgba on a video track).")
    return rc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="stencil-cli",
        description="Stencil traces the subject — AI roto mattes for free Resolve. "
                    "Part of control-z (https://control-z.org).")
    p.add_argument("--version", action="version", version=f"stencil {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="propagate prompts, export mattes")
    pr.add_argument("input")
    pr.add_argument("--prompts", required=True, help="prompts JSON (see --help)")
    pr.add_argument("--range", help="frame range s:e (default: whole clip)")
    pr.add_argument("--out-mode", choices=["luma", "rgba"], default="luma")
    pr.add_argument("--grow", type=int, default=0)
    pr.add_argument("--feather", type=float, default=3.0)
    pr.add_argument("--despeckle", type=int, default=64)
    pr.add_argument("--no-temporal", action="store_true")
    pr.add_argument("--confidence-floor", type=float, default=0.75)
    pr.add_argument("-o", "--output")
    pr.add_argument("-q", "--quiet", action="store_true")
    pr.set_defaults(fn=cmd_run)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
