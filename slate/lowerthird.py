"""The lower-third maker — broadcast type, rendered honestly.

Everything draws at 2× supersample and comes down through Lanczos, so
edges stay clean on air. The composition is a *group* (plates, accent,
two lines of type, soft shadow) built once per look; animation transforms
the finished group per frame — slide, rise, fade — with an eased curve.
Four styles cover the classics; position is stated in title-safe terms.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterator, Optional, Tuple

STYLES = ("bar", "block", "line", "clean")
ANIMS = ("slide", "rise", "fade", "none")


@dataclass
class LowerThird:
    line1: str = "Firstname Lastname"
    line2: str = "Title, Organization"
    style: str = "bar"               # bar | block | line | clean
    anim: str = "slide"              # slide | rise | fade | none
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    in_dur: float = 0.6
    hold: float = 4.0
    out_dur: float = 0.5
    text_color: str = "#F5F3EE"
    sub_color: str = "#D9D6CC"
    accent: str = "#E5A835"
    plate_color: str = "#14141A"
    plate_opacity: float = 0.82
    x: float = 0.08                  # left edge, fraction of width (title-safe ≥ .05)
    y: float = 0.80                  # group baseline area, fraction of height
    scale: float = 1.0               # multiplies both type sizes
    font: str = ""                   # name or path; "" = system default
    font2: str = ""                  # second line (defaults to font)
    supersample: int = 2

    def duration(self) -> float:
        return self.in_dur + self.hold + self.out_dur

    def n_frames(self) -> int:
        return max(1, round(self.duration() * self.fps))

    @classmethod
    def from_dict(cls, d: dict) -> "LowerThird":
        allowed = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        p = cls(**allowed)
        p.style = p.style if p.style in STYLES else "bar"
        p.anim = p.anim if p.anim in ANIMS else "slide"
        p.width = max(320, min(7680, int(p.width)))
        p.height = max(180, min(4320, int(p.height)))
        p.fps = max(1.0, min(120.0, float(p.fps)))
        p.in_dur = max(0.0, min(5.0, float(p.in_dur)))
        p.out_dur = max(0.0, min(5.0, float(p.out_dur)))
        p.hold = max(0.2, min(600.0, float(p.hold)))
        p.x = max(0.0, min(0.9, float(p.x)))
        p.y = max(0.05, min(0.95, float(p.y)))
        p.scale = max(0.3, min(3.0, float(p.scale)))
        p.plate_opacity = max(0.0, min(1.0, float(p.plate_opacity)))
        p.supersample = 2 if int(p.supersample) != 1 else 1
        return p

    def to_dict(self) -> dict:
        return asdict(self)


def _rgba(hexcolor: str, alpha: float = 1.0) -> Tuple[int, int, int, int]:
    c = hexcolor.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        r, g, b = 245, 243, 238
    return (r, g, b, max(0, min(255, round(alpha * 255))))


def ease_out_cubic(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return 1 - (1 - k) ** 3


def phase_at(p: LowerThird, t: float) -> Tuple[float, str]:
    """(k, phase) — k is 0..1 presence with easing applied."""
    if t < p.in_dur and p.in_dur > 0:
        return ease_out_cubic(t / p.in_dur), "in"
    if t <= p.in_dur + p.hold:
        return 1.0, "hold"
    if p.out_dur <= 0:
        return 0.0, "out"
    k = (t - p.in_dur - p.hold) / p.out_dur
    return 1.0 - ease_out_cubic(k), "out"


class Renderer:
    """Builds the group once, animates it per frame. Needs Pillow."""

    def __init__(self, p: LowerThird):
        from PIL import ImageFont

        from .fonts import find
        self.p = p
        S = p.supersample
        base = p.height * S
        f1 = find(p.font)
        f2 = find(p.font2 or p.font)
        self.font1 = ImageFont.truetype(f1, size=round(base * 0.050 * p.scale))
        self.font2 = ImageFont.truetype(f2, size=round(base * 0.030 * p.scale))
        self.group, self.anchor = self._build_group()

    # -- the composition ---------------------------------------------------

    def _build_group(self):
        """The full-opacity lower third as one RGBA image + its target
        top-left position (supersampled space)."""
        from PIL import Image, ImageDraw, ImageFilter

        p, S = self.p, self.p.supersample
        W, H = p.width * S, p.height * S
        d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        b1 = d0.textbbox((0, 0), p.line1 or " ", font=self.font1)
        b2 = d0.textbbox((0, 0), p.line2 or " ", font=self.font2)
        w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
        w2, h2 = b2[2] - b2[0], b2[3] - b2[1]
        pad = round(H * 0.016)
        gap = round(H * 0.010)
        bar_w = round(W * 0.004)

        if p.style == "bar":
            gw = max(w1, w2) + pad * 3 + bar_w
            gh = h1 + h2 + gap + pad * 2
        elif p.style == "block":
            gw = max(w1, w2) + pad * 4
            gh = h1 + h2 + gap + pad * 3
        else:  # line, clean
            gw = max(w1, w2) + pad
            gh = h1 + h2 + gap * 2 + pad
        margin = round(H * 0.02)
        img = Image.new("RGBA", (gw + margin * 2, gh + margin * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        ox = oy = margin

        text1_pos: Tuple[int, int]
        if p.style == "bar":
            plate = [ox, oy, ox + gw, oy + gh]
            dr.rounded_rectangle(plate, radius=round(H * 0.006),
                                 fill=_rgba(p.plate_color, p.plate_opacity))
            dr.rectangle([ox, oy, ox + bar_w, oy + gh], fill=_rgba(p.accent))
            tx = ox + bar_w + pad
            text1_pos = (tx, oy + pad - b1[1])
            text2_pos = (tx, oy + pad + h1 + gap - b2[1])
        elif p.style == "block":
            blk1 = [ox, oy, ox + w1 + pad * 2, oy + h1 + pad * 2]
            dr.rectangle(blk1, fill=_rgba(p.accent))
            blk2_y = oy + h1 + pad * 2
            dr.rectangle([ox, blk2_y, ox + w2 + pad * 2, blk2_y + h2 + pad],
                         fill=_rgba(p.plate_color, min(1.0, p.plate_opacity + 0.1)))
            text1_pos = (ox + pad, oy + pad - b1[1])
            text2_pos = (ox + pad, blk2_y + pad // 2 - b2[1])
        elif p.style == "line":
            text1_pos = (ox, oy - b1[1])
            rule_y = oy + h1 + gap
            dr.rectangle([ox, rule_y, ox + max(w1, w2), rule_y + max(2, round(H * 0.0022))],
                         fill=_rgba(p.accent))
            text2_pos = (ox, rule_y + gap - b2[1] + round(H * 0.002))
        else:  # clean — a small accent tick ahead of line 1
            tick_w = round(H * 0.005)
            dr.rectangle([ox, oy + round(h1 * 0.12), ox + tick_w, oy + h1],
                         fill=_rgba(p.accent))
            text1_pos = (ox + tick_w + pad, oy - b1[1])
            text2_pos = (ox + tick_w + pad, oy + h1 + gap - b2[1])

        dr.text(text1_pos, p.line1 or "", font=self.font1, fill=_rgba(p.text_color))
        dr.text(text2_pos, p.line2 or "", font=self.font2, fill=_rgba(p.sub_color))

        # a soft shadow keeps the type legible on bright footage — drawn from
        # the group's own alpha so every style gets exactly its own outline
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        alpha = img.split()[3].point(lambda a: a * 0.5)
        shadow.paste((10, 10, 14, 255), (0, round(H * 0.0035)), alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=H * 0.004))
        out = Image.alpha_composite(shadow, img)

        gx = round(p.x * W) - margin
        gy = round(p.y * H) - gh - margin
        return out, (gx, gy)

    # -- frames --------------------------------------------------------------

    def frame(self, t: float):
        """RGBA PIL Image at final size for time t."""
        from PIL import Image

        p, S = self.p, self.p.supersample
        W, H = p.width * S, p.height * S
        k, _phase = phase_at(p, t)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if k > 0.001:
            dx = dy = 0
            if p.anim == "slide":
                dx = round((k - 1.0) * W * 0.035)
            elif p.anim == "rise":
                dy = round((1.0 - k) * H * 0.045)
            g = self.group
            if k < 0.999:
                a = g.split()[3].point(lambda v: round(v * k))
                g = g.copy()
                g.putalpha(a)
            canvas.alpha_composite(g, (self.anchor[0] + dx, self.anchor[1] + dy))
        if S != 1:
            canvas = canvas.resize((p.width, p.height), Image.LANCZOS)
        return canvas

    def hold_frame(self):
        return self.frame(self.p.in_dur + self.p.hold * 0.5)

    def frames(self) -> Iterator:
        n = self.p.n_frames()
        for i in range(n):
            yield i, self.frame(i / self.p.fps)


def draw_safe_areas(img):
    """Action (90%) and title (80%) safe cages, for previews only."""
    from PIL import ImageDraw

    d = ImageDraw.Draw(img)
    w, h = img.size
    for frac, col in ((0.90, (229, 168, 53, 110)), (0.80, (229, 168, 53, 70))):
        mx, my = round(w * (1 - frac) / 2), round(h * (1 - frac) / 2)
        d.rectangle([mx, my, w - mx, h - my], outline=col, width=1)
    return img
