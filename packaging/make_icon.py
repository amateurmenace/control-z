"""The control-z icon — the brand as a rebus: a caret over an amber z.

Renders the macOS app icon (squircle, ink surface, cream ⌃ above the amber
z — "control z" read aloud) at 2× supersample, emits the full .iconset, and
compiles packaging/icon.icns via iconutil. Also writes logo-512.png for any
surface that wants the mark. Deterministic: same inputs, same bytes-ish
(font rendering aside) — rerun any time, commit the .icns.

    .venv/bin/python packaging/make_icon.py
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from slate.fonts import find  # noqa: E402  (the suite's own font discovery)

INK_TOP = (32, 32, 43, 255)
INK_BOT = (21, 21, 27, 255)
CREAM = (245, 243, 238, 255)
AMBER = (229, 168, 53, 255)
HAIRLINE = (245, 243, 238, 20)


def squircle_points(cx, cy, a, n=4.6, steps=720):
    pts = []
    for k in range(steps):
        t = 2 * math.pi * k / steps
        c, s = math.cos(t), math.sin(t)
        x = cx + a * math.copysign(abs(c) ** (2 / n), c)
        y = cy + a * math.copysign(abs(s) ** (2 / n), s)
        pts.append((x, y))
    return pts


def render_master(size=1024, ss=2):
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx = cy = S / 2
    a = S * 0.406          # 832/1024 — Apple's Big-Sur-era artwork footprint
    pts = squircle_points(cx, cy, a)

    # vertical gradient clipped to the squircle
    grad = Image.new("RGBA", (S, S))
    top, bot = INK_TOP, INK_BOT
    px = grad.load()
    for y in range(S):
        f = y / (S - 1)
        row = tuple(round(top[i] + (bot[i] - top[i]) * f) for i in range(4))
        for x in range(0, S, 1):
            px[x, y] = row
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.line(pts + [pts[0]], fill=HAIRLINE, width=max(2, 3 * ss))

    # the caret — drawn, not typeset, so it's crisp at 16 px
    car_w = S * 0.30
    car_h = S * 0.115
    car_cy = cy - S * 0.208
    stroke = round(S * 0.052)
    d.line([(cx - car_w / 2, car_cy + car_h / 2), (cx, car_cy - car_h / 2),
            (cx + car_w / 2, car_cy + car_h / 2)],
           fill=CREAM, width=stroke, joint="curve")

    # the amber z — the brand's own letter
    font = ImageFont.truetype(find("HelveticaNeue"), size=round(S * 0.46))
    bb = d.textbbox((0, 0), "z", font=font)
    zw, zh = bb[2] - bb[0], bb[3] - bb[1]
    d.text((cx - zw / 2 - bb[0], cy + S * 0.042 - zh / 2 - bb[1]), "z",
           font=font, fill=AMBER)

    return img.resize((size, size), Image.LANCZOS)


def main():
    master = render_master(1024)
    out_icns = HERE / "icon.icns"
    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    sizes = [16, 32, 128, 256, 512]
    for s in sizes:
        master.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
        master.resize((s * 2, s * 2), Image.LANCZOS).save(
            iconset / f"icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)],
                   check=True)
    master.resize((512, 512), Image.LANCZOS).save(HERE / "logo-512.png")
    print(f"→ {out_icns} ({out_icns.stat().st_size} bytes)")
    print(f"→ {HERE / 'logo-512.png'}")


if __name__ == "__main__":
    main()
