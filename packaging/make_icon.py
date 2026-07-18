"""The Civic Media Studio icon — the civicmedia.studio keycap.

Renders the macOS app icon (the brand's ink keycap: two green clips under a
purple playhead — "clips under the playhead") at 2× supersample, emits the full
.iconset, and compiles packaging/icon.icns via iconutil. Also writes
logo-512.png for any surface that wants the mark. Deterministic: same inputs,
same bytes — rerun any time, commit the .icns.

Geometry is the civicmedia mark from brand/logos/civicmedia-mark.svg, drawn (not
rasterized) so it stays crisp at every icon size.

    .venv/bin/python packaging/make_icon.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

# civicmedia palette (brand/tokens/colors.css)
KEYCAP = (15, 23, 42, 255)      # ink     #0f172a
CLIP_HI = (34, 197, 94, 255)    # bright  #22c55e
CLIP_LO = (74, 222, 128, 255)   # soft    #4ade80
PLAYHEAD = (168, 85, 247, 255)  # purple  #a855f7


def render_master(size=1024, ss=2):
    """The civicmedia keycap on a transparent tile, at Apple's artwork footprint."""
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    L = S * 0.812                      # 832/1024 — Big-Sur-era artwork footprint
    ox = oy = (S - L) / 2
    sc = L / 96.0                      # the mark's own viewBox is 96×96

    def box(x, y, w, h):               # mark-space rect → device pixels
        return [ox + x * sc, oy + y * sc, ox + (x + w) * sc, oy + (y + h) * sc]

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box(0, 0, 96, 96), radius=22 * sc, fill=KEYCAP)
    d.rectangle(box(18, 40, 46, 11), fill=CLIP_HI)    # top clip
    d.rectangle(box(18, 58, 30, 11), fill=CLIP_LO)    # bottom clip
    d.rectangle(box(54, 24, 6, 56), fill=PLAYHEAD)    # playhead stem
    d.rectangle(box(46, 16, 22, 12), fill=PLAYHEAD)   # playhead head
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
