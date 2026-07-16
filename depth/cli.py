"""depth-cli — run / templates.

Two-decode design: pass 1 decodes once, runs inference at 256px and caches raw
depth (small); pass 2 decodes again only to upsample each cached depth against
its full-res frame (edge-guided) and encode. Inference happens once.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__

# The Fusion template pack. "depth" templates consume a Depth matte; "stencil"
# ones consume a Stencil matte; "hush" reads Hush's clean-confidence alpha.
# Every template pastes into free Resolve's Fusion page and is paste-tested live.
TEMPLATES = ["fog", "rack-focus", "depth-grade", "parallax", "haze-light"]
STENCIL_TEMPLATES = ["veil-blur", "cutout", "matte-tune", "confidence-grain",
                     "social-vertical"]
ALL_TEMPLATES = TEMPLATES + STENCIL_TEMPLATES


def cmd_run(args) -> int:
    import av
    import cv2
    import numpy as np

    from czcore.shots import cuts_from_diffs, shots_from_cuts

    from .engine import DepthEngine, normalize_shot

    src = args.input
    engine = DepthEngine()
    say = print

    # pass 1: diffs (for shots) + 256px depth per frame
    depths, diffs = [], []
    prev = None
    say(f"Depth — {Path(src).name}: estimating…")
    with av.open(src) as inp:
        vin = inp.streams.video[0]
        vin.thread_type = "AUTO"
        fps = vin.average_rate or 24
        for i, frame in enumerate(inp.decode(vin)):
            if args.range and not (args.range[0] <= i < args.range[1]):
                if i >= (args.range[1] if args.range else 1 << 60):
                    break
                continue
            img = frame.to_ndarray(format="bgr24")
            small = cv2.resize(img, (160, 90))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
            if prev is not None:
                d = float(np.abs(gray - prev).mean()) / 255.0
                diffs.append(d)
                if d > 0.14:          # probable cut: don't smooth across it
                    engine.reset_temporal()
            prev = gray
            depths.append(engine.estimate(img, ema=args.ema, refine=False,
                                          native=True))
            if i % 25 == 0:
                say(f"  …{i}", end="\r", flush=True)
    n = len(depths)
    shots = shots_from_cuts(cuts_from_diffs(diffs, threshold=0.14), n)
    say(f"\n  {n} frames, {len(shots)} shot(s)")

    # normalize per shot on the raw 256px maps
    normalized: list = [None] * n
    ranges = []
    for (s, e) in shots:
        norm, rng = normalize_shot(depths[s:e], invert=args.invert,
                                   gamma=args.gamma)
        normalized[s:e] = norm
        ranges.append(rng)

    # pass 2: upsample against full-res frames, encode 10-bit gray ProRes
    out_path = args.output or str(Path(src).with_name(
        f"{Path(src).stem}.depth.mov"))
    start = args.range[0] if args.range else 0
    from .engine import guided_filter
    with av.open(src) as inp, av.open(out_path, "w") as out:
        vin = inp.streams.video[0]
        vin.thread_type = "AUTO"
        w, h = vin.codec_context.width, vin.codec_context.height
        vout = out.add_stream("prores_ks", rate=fps, options={"profile": "3"})
        vout.width, vout.height = w, h
        vout.pix_fmt = "yuv444p10le"
        j = 0
        for i, frame in enumerate(inp.decode(vin)):
            idx = i - start
            if idx < 0:
                continue
            if idx >= n:
                break
            img = frame.to_ndarray(format="bgr24")
            up = cv2.resize(normalized[idx], (w, h), interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            up = np.clip(guided_filter(gray, up, radius=max(4, w // 240)), 0, 1)
            d16 = (up * 65535.0).astype(np.uint16)
            rgb48 = np.dstack([d16, d16, d16])
            vf = av.VideoFrame.from_ndarray(rgb48, format="rgb48le")
            for pkt in vout.encode(vf):
                out.mux(pkt)
            j += 1
            if j % 25 == 0:
                say(f"  writing {j}/{n}", end="\r", flush=True)
            if args.preview_every and idx % args.preview_every == 0:
                fc = cv2.applyColorMap((up * 255).astype(np.uint8),
                                       cv2.COLORMAP_TURBO)
                cv2.imwrite(str(Path(out_path).with_suffix(f".f{idx:05d}.jpg")), fc)
        for pkt in vout.encode():
            out.mux(pkt)
    say(f"\n  → {out_path} (10-bit gray ProRes; near = "
        + ("black" if args.invert else "white") + ")")
    say("  Resolve: import as matte (Color page ‘Add Matte’) or use the "
        "template pack: depth-cli templates -o <dir>")
    return 0


# Filename prefix per template, so the pack is self-describing in Fusion's dir.
_PREFIX = {t: "cz-depth" for t in TEMPLATES}
_PREFIX.update({t: "cz-stencil" for t in
                ["veil-blur", "cutout", "matte-tune", "social-vertical"]})
_PREFIX["confidence-grain"] = "cz-hush"


def cmd_templates(args) -> int:
    src_dir = Path(__file__).parent / "templates"
    out_dir = Path(args.output).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    which = TEMPLATES if args.pack == "depth" else \
        STENCIL_TEMPLATES if args.pack == "stencil" else ALL_TEMPLATES
    for t in which:
        (out_dir / f"{_PREFIX[t]}-{t}.setting").write_text(
            (src_dir / f"{t}.setting").read_text())
    print(f"{len(which)} Fusion templates → {out_dir}")
    print("Open one in a text editor, copy all, paste into the Fusion page, "
          "then wire the inputs as the sticky note in each file says.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="depth-cli",
        description="Depth measures the scene — depth mattes for free Resolve. "
                    "Part of control-z (https://control-z.org).")
    p.add_argument("--version", action="version", version=f"depth {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="clip → 10-bit depth matte clip")
    pr.add_argument("input")
    pr.add_argument("--invert", action="store_true", help="near = black")
    pr.add_argument("--gamma", type=float, default=1.0)
    pr.add_argument("--ema", type=float, default=0.7,
                    help="temporal smoothing 0..1 (reset at cuts)")
    pr.add_argument("--range", type=lambda s: tuple(int(x) for x in s.split(":")),
                    default=None, help="frame range s:e")
    pr.add_argument("--preview-every", type=int, default=0,
                    help="write a false-color JPEG every N frames")
    pr.add_argument("-o", "--output")
    pr.set_defaults(fn=cmd_run)

    pt = sub.add_parser("templates", help="write the Fusion template pack")
    pt.add_argument("-o", "--output", default="~/Documents/control-z-templates")
    pt.add_argument("--pack", choices=["all", "depth", "stencil"], default="all",
                    help="which templates to write (default: all ten)")
    pt.set_defaults(fn=cmd_templates)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
