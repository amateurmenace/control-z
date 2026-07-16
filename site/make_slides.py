#!/usr/bin/env python3
"""Regenerate the hero-carousel slides from real tool output.

    .venv/bin/python site/make_slides.py

Sources: the Sabby test clip + sidecars (Pivot/Stencil outputs), the site's
own baked assets (Hush before/after, Rise pair, Depth frame), and the
scratch audio demos when present. Every slide is real output except Speak,
which is a treated concept frame and captioned as such on the page.
"""

import json
import os
from pathlib import Path

import av
import cv2
import numpy as np

A = Path(__file__).parent / "content" / "assets"
SRC = "/Users/stephen/Hush/Test Footage/NR Test SHort Sabby.mov"
SCRATCH = os.environ.get(
    "CZ_SCRATCH",
    "/private/tmp/claude-502/-Users-stephen-Hush/4fd2e596-a96a-4fe8-9ebb-5cce1e56e198/scratchpad",
)
W, H = 880, 620
Q = [int(cv2.IMWRITE_JPEG_QUALITY), 76]
DARK = (33, 25, 25)  # BGR #191921
AMBER = (53, 168, 229)


def fit(img, w=W, h=H):
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    r = cv2.resize(img, (int(iw * s) + 1, int(ih * s) + 1), interpolation=cv2.INTER_AREA
                   if s < 1 else cv2.INTER_LANCZOS4)
    y0 = (r.shape[0] - h) // 2
    x0 = (r.shape[1] - w) // 2
    return r[y0:y0 + h, x0:x0 + w].copy()


def grab(path, wanted):
    got = {}
    with av.open(path) as c:
        st = c.streams.video[0]
        st.thread_type = "AUTO"
        for i, f in enumerate(c.decode(st)):
            if i in wanted:
                got[i] = f.to_ndarray(format="bgr24")
            if i >= max(wanted):
                break
    return got


def split_slide(left, right, out):
    L, R = fit(left, W // 2, H), fit(right, W - W // 2, H)
    img = np.hstack([L, R])
    img[:, W // 2 - 2:W // 2 + 2] = AMBER
    cv2.imwrite(str(out), img, Q)


def main():
    frames = grab(SRC, {30, 48})

    split_slide(cv2.imread(str(A / "before.jpg")), cv2.imread(str(A / "after.jpg")),
                A / "slide-hush.jpg")
    split_slide(cv2.imread(str(A / "rise-before.jpg")), cv2.imread(str(A / "rise-after.jpg")),
                A / "slide-rise.jpg")

    # pivot: the real solved crop on frame 48
    d = json.load(open(Path(SRC).with_suffix(".pivot.json")))
    sol = d["aspects"]["9:16"]
    img = fit(frames[48])
    cx, tx = sol["centers"][48], sol["targets"][48]
    cw = int(sol["crop_w"] / d["width"] * W)
    x = int(np.clip(cx * W - cw / 2, 0, W - cw))
    ov = img.copy()
    ov[:, :x] //= 2
    ov[:, x + cw:] //= 2
    cv2.rectangle(ov, (x, 2), (x + cw, H - 3), (158, 122, 91)[::-1], 3)
    if tx:
        cv2.circle(ov, (int(tx * W), int(H * .42)), 10, AMBER, -1)
    cv2.imwrite(str(A / "slide-pivot.jpg"), ov, Q)

    # stencil: the real matte tint on frame 30
    mat = grab(str(Path(SRC).with_name(Path(SRC).stem + ".stencil.mov")), {30})[30]
    img = fit(frames[30])
    m = fit(mat)[:, :, 0] > 127
    plum = np.array((158, 106, 142))[::-1]
    ov = img.astype(np.float32)
    ov[m] = ov[m] * .35 + plum * .65
    edges = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) - m.astype(np.uint8)
    ov[edges > 0] = plum
    cv2.imwrite(str(A / "slide-stencil.jpg"), ov.astype(np.uint8), Q)

    cv2.imwrite(str(A / "slide-depth.jpg"), fit(cv2.imread(str(A / "depth-frame.jpg"))), Q)

    # speak: treated concept frame (captioned as concept on the page)
    sp = fit(cv2.imread(str(A / "after.jpg"))).astype(np.float32) / 255
    sp = sp ** 0.92
    sp[:, :, 2] = np.clip(sp[:, :, 2] * 1.07 + .015, 0, 1)
    sp[:, :, 0] = np.clip(sp[:, :, 0] * .96, 0, 1)
    glow = cv2.GaussianBlur(sp, (0, 0), 9)
    sp = 1 - (1 - sp) * (1 - glow * .22)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - .28 * (((xx / W - .5) ** 2 + (yy / H - .5) ** 2) * 2.2)
    sp *= vig[..., None]
    g = np.random.default_rng(3).standard_normal((H, W, 1)) * .02
    cv2.imwrite(str(A / "slide-speak.jpg"),
                np.clip((sp + g) * 255, 0, 255).astype(np.uint8), Q)

    # audio slides need the scratch demos (skip gracefully when absent)
    try:
        import soundfile as sf

        def env(path, n=W):
            a, _ = sf.read(path, always_2d=True)
            a = a.mean(axis=1)
            seg = len(a) // n
            return np.array([np.abs(a[i * seg:(i + 1) * seg]).max() for i in range(n)])

        def wave_img(rows):
            img = np.full((H, W, 3), DARK, np.uint8)
            for (path, color, y0, hh) in rows:
                e = env(path)
                e = e / (e.max() + 1e-9)
                for x in range(W):
                    h2 = int(e[x] * hh / 2)
                    cv2.line(img, (x, y0 - h2), (x, y0 + h2), color, 1)
            return img

        ink = (140, 103, 82)[::-1]
        teal = (126, 140, 74)[::-1]
        img = wave_img([(f"{SCRATCH}/meeting.wav", ink, H // 2 + 40, 380)])
        segs = json.load(open(A / "scribe-demo.json"))
        dur = max(w["e"] for s in segs for w in s["words"])
        cols = {"Speaker 1": ink, "Speaker 2": teal}
        for s in segs:
            a = int(s["words"][0]["s"] / dur * W)
            b = int(s["words"][-1]["e"] / dur * W)
            cv2.rectangle(img, (a, 52), (b, 100), cols[s["speaker"]], -1)
        cv2.imwrite(str(A / "slide-scribe.jpg"), img, Q)

        img = wave_img([(f"{SCRATCH}/meeting-hum.wav", AMBER, H // 4 + 30, 240),
                        (f"{SCRATCH}/meeting-clean.wav", teal, 3 * H // 4 - 16, 240)])
        cv2.imwrite(str(A / "slide-clear.jpg"), img, Q)
    except FileNotFoundError as e:
        print(f"  (audio slides skipped: {e})")

    sizes = {f.name: f.stat().st_size // 1024 for f in sorted(A.glob("slide-*.jpg"))}
    print("slides:", sizes, f"→ total {sum(sizes.values())} KB")


if __name__ == "__main__":
    main()
