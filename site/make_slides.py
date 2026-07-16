#!/usr/bin/env python3
"""Regenerate the site's demo imagery from real tool output.

    .venv/bin/python site/make_slides.py

FOOTAGE LICENSING (why this file exists): every frame published on the site
comes from **Tears of Steel** © Blender Foundation, CC-BY 3.0
(mango.blender.org) — freely usable with attribution, which the site carries.
Never publish client/member footage here. Hush's before/after pair is its own
synthetic validation test card, rendered by the plugin's MIT test suite.

Prep (once):
    ffmpeg -y -ss 316 -i tears-of-steel-1920.mov -t 8 -an -c:v prores_ks \
        -profile:v 3 tos-celia.mov          # Celia close-up  (stencil, rise)
    ffmpeg -y -ss 516 -i tears-of-steel-1920.mov -t 8 -an -c:v prores_ks \
        -profile:v 3 tos-thom.mov           # Thom on the canal (pivot, depth)
    .venv/bin/python -m pivot.cli analyze tos-thom.mov --aspect 9:16
    .venv/bin/python -m stencil.cli run tos-celia.mov --prompts <pts> --range 96:148
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import the tools

import av
import cv2
import numpy as np

A = Path(__file__).parent / "content" / "assets"
MEDIA = Path("/Users/stephen/Hush/Test Footage")
CELIA = MEDIA / "tos-celia.mov"          # 1920x800, starts at 316s
THOM = MEDIA / "tos-thom.mov"            # 1920x800, starts at 516s
CELIA_MATTE = MEDIA / "tos-celia.stencil.mov"
SCRATCH = os.environ.get(
    "CZ_SCRATCH",
    "/private/tmp/claude-502/-Users-stephen-Hush/4fd2e596-a96a-4fe8-9ebb-5cce1e56e198/scratchpad",
)
W, H = 880, 620
Q = [int(cv2.IMWRITE_JPEG_QUALITY), 76]
DARK = (33, 25, 25)      # BGR #191921
AMBER = (53, 168, 229)
SLATE = (158, 122, 91)   # Pivot accent, BGR
PLUM = (158, 106, 142)   # Stencil accent, BGR


def fit(img, w=W, h=H):
    """Cover-crop to the slide canvas."""
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LANCZOS4
    r = cv2.resize(img, (int(iw * s) + 1, int(ih * s) + 1), interpolation=interp)
    y0 = (r.shape[0] - h) // 2
    x0 = (r.shape[1] - w) // 2
    return r[y0:y0 + h, x0:x0 + w].copy()


def grab(path, wanted):
    got = {}
    with av.open(str(path)) as c:
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


def slide_hush():
    """The plugin's own synthetic validation card — noisy | denoised."""
    split_slide(cv2.imread(str(A / "before.jpg")), cv2.imread(str(A / "after.jpg")),
                A / "slide-hush.jpg")


def slide_rise():
    """Celia's face, downsampled to 240px, then 4x by Lanczos vs Real-ESRGAN."""
    from rise.engine import upscale_frame

    f = grab(CELIA, {120})[120]
    # square crop centred on the detected face (0.60, 0.47 of a 1920x800 frame)
    cx, cy, half = int(.60 * 1920), int(.47 * 800), 190
    crop = f[max(0, cy - half):cy + half, cx - half:cx + half]
    base = cv2.resize(crop, (240, 240), interpolation=cv2.INTER_AREA)
    esr, info = upscale_frame(base, 4, model="realesrgan-x4")
    lz, _ = upscale_frame(base, 4, model="lanczos")
    print(f"  rise backend: {info.backend} (synthesized={info.synthesized})")
    for name, img in (("rise-before.jpg", lz), ("rise-after.jpg", esr)):
        cv2.imwrite(str(A / name),
                    cv2.resize(img, (720, 720), interpolation=cv2.INTER_AREA),
                    [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    split_slide(cv2.imread(str(A / "rise-before.jpg")),
                cv2.imread(str(A / "rise-after.jpg")), A / "slide-rise.jpg")


def slide_stencil():
    """The real SAM 2.1 matte, tinted over the frame it was solved on."""
    idx = 110  # inside the propagated range (96:148)
    img = fit(grab(CELIA, {idx})[idx])
    m = fit(grab(CELIA_MATTE, {idx - 96})[idx - 96])[:, :, 0] > 127
    ov = img.astype(np.float32)
    ov[m] = ov[m] * .40 + np.array(PLUM) * .60
    edge = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) - m.astype(np.uint8)
    ov[edge > 0] = PLUM
    cv2.imwrite(str(A / "slide-stencil.jpg"), ov.astype(np.uint8), Q)


def slide_pivot():
    """The real solved 9:16 crop, shown inside the full scope frame."""
    d = json.load(open(THOM.with_suffix(".pivot.json")))
    sol = d["aspects"]["9:16"]
    idx = 96
    frame = grab(THOM, {idx})[idx]
    # ToS is 2.4:1 scope; centre-crop to a true 16:9 so the slide's
    # "16:9 -> 9:16" claim is literally what's drawn.
    src_h = frame.shape[0]
    keep_w = int(src_h * 16 / 9)
    x_off = (frame.shape[1] - keep_w) // 2
    frame = frame[:, x_off:x_off + keep_w]
    fw = W
    fh = int(round(frame.shape[0] * fw / frame.shape[1]))
    band = cv2.resize(frame, (fw, fh), interpolation=cv2.INTER_AREA)
    canvas = np.full((H, W, 3), DARK, np.uint8)
    y0 = (H - fh) // 2
    canvas[y0:y0 + fh] = band
    # re-express the solved centre in the cropped frame's coordinates
    cx = (sol["centers"][idx] * d["width"] - x_off) / keep_w
    cw = int(sol["crop_w"] / keep_w * fw)
    x = int(np.clip(cx * fw - cw / 2, 0, fw - cw))
    # dim what the reframe discards
    canvas[y0:y0 + fh, :x] = (canvas[y0:y0 + fh, :x] * .38).astype(np.uint8)
    canvas[y0:y0 + fh, x + cw:] = (canvas[y0:y0 + fh, x + cw:] * .38).astype(np.uint8)
    cv2.rectangle(canvas, (x, y0), (x + cw, y0 + fh), SLATE, 3)
    tx = sol["targets"][idx]
    if tx:
        tx_c = (tx * d["width"] - x_off) / keep_w
        if 0 <= tx_c <= 1:
            cv2.circle(canvas, (int(tx_c * fw), y0 + int(fh * .42)), 9, AMBER, -1)
    cv2.putText(canvas, "16:9  ->  9:16   solved crop", (18, H - 20),
                cv2.FONT_HERSHEY_SIMPLEX, .55, (190, 190, 190), 1, cv2.LINE_AA)
    cv2.imwrite(str(A / "slide-pivot.jpg"), canvas, Q)


def slide_depth():
    """Real depth on the canal shot: statue foreground, subject, houses, trees."""
    from depth.engine import DepthEngine, normalize_shot

    idx = 96
    frame = grab(THOM, {idx})[idx]
    eng = DepthEngine()
    d = eng.estimate(frame, ema=0, refine=True)
    nd = normalize_shot([d])[0][0]
    fc = cv2.applyColorMap((nd * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    cv2.imwrite(str(A / "depth-frame.jpg"), cv2.resize(fc, (880, 367),
                interpolation=cv2.INTER_AREA), [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    cv2.imwrite(str(A / "slide-depth.jpg"), fit(fc), Q)
    grid = cv2.resize(nd, (96, 40), interpolation=cv2.INTER_AREA)
    json.dump({"w": 96, "h": 40, "d": [round(float(v), 2) for v in grid.ravel()]},
              open(A / "depth-grid.json", "w"))


def slide_speak():
    """Film-character concept treatment (Speak is an OFX plugin; this is a
    look study on the same frame, and the site labels it as such)."""
    idx = 120
    sp = fit(grab(CELIA, {idx})[idx]).astype(np.float32) / 255
    sp = sp ** 0.92
    sp[:, :, 2] = np.clip(sp[:, :, 2] * 1.10 + .02, 0, 1)   # warm the reds
    sp[:, :, 0] = np.clip(sp[:, :, 0] * .94, 0, 1)          # cool the blues down
    glow = cv2.GaussianBlur(sp, (0, 0), 11)
    sp = 1 - (1 - sp) * (1 - glow * .26)                    # halation-ish screen
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - .30 * (((xx / W - .5) ** 2 + (yy / H - .5) ** 2) * 2.2)
    sp *= vig[..., None]
    g = np.random.default_rng(3).standard_normal((H, W, 1)) * .022
    cv2.imwrite(str(A / "slide-speak.jpg"),
                np.clip((sp + g) * 255, 0, 255).astype(np.uint8), Q)


def audio_slides():
    """Scribe/Clear waveforms from the synthesized meeting demo (our own audio)."""
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


def main():
    slide_hush()
    slide_rise()
    slide_stencil()
    slide_pivot()
    slide_depth()
    slide_speak()
    try:
        audio_slides()
    except (FileNotFoundError, ImportError) as e:
        print(f"  (audio slides skipped: {e})")
    sizes = {f.name: f.stat().st_size // 1024 for f in sorted(A.glob("slide-*.jpg"))}
    print("slides:", sizes, f"→ total {sum(sizes.values())} KB")


if __name__ == "__main__":
    main()
