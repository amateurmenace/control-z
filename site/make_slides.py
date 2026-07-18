#!/usr/bin/env python3
"""Regenerate the site's demo imagery from real tool output.

    .venv/bin/python site/make_slides.py

FOOTAGE LICENSING (why this file exists): never publish client/member footage
here — we don't hold public rights to it. Everything on the site comes from
clips that are free to publish, and the people shown should reflect the
communities these tools are built for:

  px-portrait.mp4  Pexels 8496259 — curly-hair portrait   (stencil, speak)
  px-face.mp4      Pexels 5251978 — freckled close-up     (rise)
  px-street.mp4    Pexels 4483661 — man walking a city    (pivot, depth)
                   Pexels License: free to use, attribution not required
                   (we credit anyway). https://www.pexels.com/license/

Hush's before/after pair is its own synthetic validation test card, rendered by
the plugin's MIT test suite. Tears of Steel (CC-BY, Blender Foundation) is kept
in Test Footage as a spare scope-format source.

Prep (once), after downloading the clips to Test Footage:
    .venv/bin/python -m pivot.cli analyze px-street.mp4 --aspect 9:16
    .venv/bin/python -m stencil.cli run px-portrait.mp4 --prompts <pts> --range 24:80
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
PORTRAIT = MEDIA / "px-portrait.mp4"      # 1920x1080 — curly-hair portrait
FACE = MEDIA / "px-face.mp4"              # 1920x1080 — freckled close-up
STREET = MEDIA / "px-street.mp4"          # 1920x1080 — walking (pivot)
DEPTHCLIP = MEDIA / "px-depth.mp4"        # 1920x1080 — street canyon (depth)
PORTRAIT_MATTE = MEDIA / "px-portrait.stencil.mov"
MATTE_START = 24                          # the --range start used for the matte
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
    """A real face, downsampled to 240px, then 4x by Lanczos vs Real-ESRGAN.

    Freckles and hair are the point: fine detail either survives or it doesn't.
    """
    from rise.engine import upscale_frame

    f = grab(FACE, {30})[30]
    # square crop centred on the detected face (0.51, 0.43 of a 1920x1080 frame)
    cx, cy, half = int(.51 * 1920), int(.47 * 1080), 400
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
    """The real SAM 2.1 matte, tinted over the frame it was solved on.

    Curly hair on purpose — it's the classic roto hard case, and the tool's
    own honest limitations call it out.
    """
    idx = 50  # inside the propagated range (24:80)
    img = fit(grab(PORTRAIT, {idx})[idx])
    m = fit(grab(PORTRAIT_MATTE, {idx - MATTE_START})[idx - MATTE_START])[:, :, 0] > 127
    ov = img.astype(np.float32)
    ov[m] = ov[m] * .40 + np.array(PLUM) * .60
    edge = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) - m.astype(np.uint8)
    ov[edge > 0] = PLUM
    cv2.imwrite(str(A / "slide-stencil.jpg"), ov.astype(np.uint8), Q)


def slide_pivot():
    """The real solved 9:16 crop, drawn on the native 16:9 frame it came from."""
    d = json.load(open(STREET.with_suffix(".pivot.json")))
    sol = d["aspects"]["9:16"]
    idx = 150  # mid-walk, inside the solved follow
    frame = grab(STREET, {idx})[idx]
    fw = W
    fh = int(round(frame.shape[0] * fw / frame.shape[1]))
    band = cv2.resize(frame, (fw, fh), interpolation=cv2.INTER_AREA)
    canvas = np.full((H, W, 3), DARK, np.uint8)
    y0 = (H - fh) // 2
    canvas[y0:y0 + fh] = band
    cx = sol["centers"][idx]
    cw = int(sol["crop_w"] / d["width"] * fw)
    x = int(np.clip(cx * fw - cw / 2, 0, fw - cw))
    # dim what the reframe discards
    canvas[y0:y0 + fh, :x] = (canvas[y0:y0 + fh, :x] * .38).astype(np.uint8)
    canvas[y0:y0 + fh, x + cw:] = (canvas[y0:y0 + fh, x + cw:] * .38).astype(np.uint8)
    cv2.rectangle(canvas, (x, y0), (x + cw, y0 + fh), SLATE, 3)
    tx = sol["targets"][idx]
    if tx:
        cv2.circle(canvas, (int(tx * fw), y0 + int(fh * .30)), 9, AMBER, -1)
    moves = sol["moves"]
    cv2.putText(canvas, f"16:9  ->  9:16   following the subject, {moves} camera moves",
                (18, H - 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (190, 190, 190), 1,
                cv2.LINE_AA)
    cv2.imwrite(str(A / "slide-pivot.jpg"), canvas, Q)


def slide_depth():
    """Real depth on a street canyon: glass towers near, subject mid, block far."""
    from depth.engine import DepthEngine, normalize_shot

    idx = 120
    frame = grab(DEPTHCLIP, {idx})[idx]
    eng = DepthEngine()
    d = eng.estimate(frame, ema=0, refine=True)
    nd = normalize_shot([d])[0][0]
    fc = cv2.applyColorMap((nd * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    cv2.imwrite(str(A / "depth-frame.jpg"), cv2.resize(fc, (880, 495),
                interpolation=cv2.INTER_AREA), [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    cv2.imwrite(str(A / "slide-depth.jpg"), fit(fc), Q)
    grid = cv2.resize(nd, (96, 54), interpolation=cv2.INTER_AREA)
    json.dump({"w": 96, "h": 54, "d": [round(float(v), 2) for v in grid.ravel()]},
              open(A / "depth-grid.json", "w"))


def slide_speak():
    """Film-character LOOK STUDY — not Speak's own render.

    Speak is an OpenFX plugin, so its real output has to come out of Resolve;
    this is an approximation of the look on the same frame, and the slide
    caption says so. Replace with a true Speak render once one is exported.
    """
    idx = 50
    sp = fit(grab(PORTRAIT, {idx})[idx]).astype(np.float32) / 255
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


SUITE_URL = "http://127.0.0.1:8301"   # a running dev server (suite-8301)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9333
# per-page setup clicks so the slide shows the tool DOING something, not
# an empty form: (javascript, seconds to wait after)
SUITE_PAGES = {
    "highlighter": [],
    "grabber": [("document.querySelector('#gb-search').click()", 14)],
    "index": [("document.querySelector('#ix-q').value='school committee';"
               "document.querySelector('#ix-go').click()", 4)],
    "slate": [],
    "kb": [],
}


def suite_slides():
    """The suite pages' slides are the real app, driven headlessly: Chrome
    opens each room through its /#page deep link, clicks what makes the
    page show its work, and screenshots at 2× the slide canvas. Needs the
    dev server up (python -m suite --serve --port 8301) and Chrome."""
    import asyncio
    import base64
    import subprocess
    import time
    import urllib.request

    import websockets

    try:
        urllib.request.urlopen(SUITE_URL + "/api/settings/info", timeout=3)
    except Exception:
        raise FileNotFoundError(f"no suite server at {SUITE_URL}")
    if not Path(CHROME).exists():
        raise FileNotFoundError("Chrome not installed — suite slides need "
                                "its headless mode")

    async def cap(name, steps):
        with urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{CDP_PORT}/json/new?{SUITE_URL}/%23{name}",
                method="PUT")) as r:
            tab = json.load(r)
        async with websockets.connect(tab["webSocketDebuggerUrl"],
                                      max_size=50_000_000) as ws:
            mid = 0

            async def send(method, params=None):
                nonlocal mid
                mid += 1
                await ws.send(json.dumps({"id": mid, "method": method,
                                          "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == mid:
                        return msg.get("result", {})

            await send("Page.enable")
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": 1760, "height": 1240,
                        "deviceScaleFactor": 1, "mobile": False})
            await asyncio.sleep(7)      # app boot + first data
            for js, wait_s in steps:
                await send("Runtime.evaluate", {"expression": js})
                await asyncio.sleep(wait_s)
            shot = await send("Page.captureScreenshot", {"format": "png"})
            png = cv2.imdecode(
                np.frombuffer(base64.b64decode(shot["data"]), np.uint8),
                cv2.IMREAD_COLOR)
            cv2.imwrite(str(A / f"slide-{name}.jpg"),
                        cv2.resize(png, (W, H),
                                   interpolation=cv2.INTER_AREA), Q)
            print(f"  slide-{name}.jpg (live capture)")
        urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{CDP_PORT}/json/close/{tab['id']}",
            method="GET"))

    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
         "--disable-gpu", "--hide-scrollbars",
         f"--user-data-dir={SCRATCH}/chrome-prof", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.3)
        for name, steps in SUITE_PAGES.items():
            asyncio.run(cap(name, steps))
    finally:
        proc.terminate()


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
    try:
        suite_slides()
    except (FileNotFoundError, ImportError) as e:
        print(f"  (suite slides skipped: {e})")
    sizes = {f.name: f.stat().st_size // 1024 for f in sorted(A.glob("slide-*.jpg"))}
    print("slides:", sizes, f"→ total {sum(sizes.values())} KB")


if __name__ == "__main__":
    main()
