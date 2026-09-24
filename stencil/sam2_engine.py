"""SAM 2.1, self-contained — imported in-process from a source checkout, and
run as a HELPER SCRIPT inside a managed runtime by the signed app.

Why the second shape exists: the signed app's hardened runtime refuses to
load torch (library validation, zero entitlements — packaging/sign_suite.sh),
so it runs THIS FILE with the runtime's own Python (czcore.pyruntime) and
talks to it over stdin/stdout, one JSON object per line. That is why this
file imports nothing from the suite — no czcore, no stencil package. Keep it
that way: a suite import here breaks the helper.

Protocol (one request per line in; progress lines, then one answer, out):

  {"op": "hello"}
      -> {"ok": true, "torch": "2.x", "device": "mps"}
  {"op": "preview", "ckpt", "config", "image": <png/jpg>, "points": [[x, y]…]
   (0..1 of the image), "labels": [1|0…], "out": <png path>}
      -> {"ok": true, "conf": 0.97}
  {"op": "propagate", "ckpt", "config", "frames_dir", "prompts":
   [{"frame", "x", "y", "label", "obj"}…], "out_dir", "obj": 1}
      -> {"progress": "propagating 25/300"} …
      -> {"ok": true, "n": 300, "confidence": [...], "written": 297}
  any failure -> {"ok": false, "error": "<sentence>"}

The model loads once per process and stays warm, so the second click's
preview answers in well under a second.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

CONFIG = "configs/sam2.1/sam2.1_hiera_s.yaml"

# SAM2 preloads EVERY frame of a state at its own 1024² working size (~12.6
# MB a frame), so a static-camera meeting (one shot, thousands of frames)
# asks Metal for a buffer it refuses ("invalid buffer size: 62 GB",
# measured). Long shots propagate in windows this wide (~3 GB each),
# chained by every object's last mask.
WINDOW_FRAMES = 240


def device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _free(dev: str):
    import torch

    if dev == "mps":
        torch.mps.empty_cache()
    elif dev == "cuda":
        torch.cuda.empty_cache()


def group(prompts):
    """{(frame, obj): [prompt…]} — SAM2's add_new_points_or_box clears old
    points by default, so every point for one frame+object MUST go in a
    single call (fed one at a time, only the last survives: an exclude
    point alone = an empty matte). Prompts are dicts: frame, x, y, label,
    obj (x/y normalized 0..1)."""
    out = {}
    for p in prompts:
        out.setdefault((int(p["frame"]), int(p.get("obj", 1))), []).append(p)
    return out


class Engine:
    """The video predictor, warm. run_shot -> (masks, confidence): per
    object, one uint8 mask (or None) and one confidence per frame."""

    def __init__(self, ckpt: str, config: str = CONFIG):
        from sam2.build_sam import build_sam2_video_predictor

        self.device = device()
        self.predictor = build_sam2_video_predictor(config, str(ckpt),
                                                    device=self.device)

    def run_shot(self, frames_dir, prompts, progress=None):
        frames = sorted(Path(frames_dir).glob("*.jpg"))
        n = len(frames)
        grouped = sorted(group(prompts).items())
        masks, conf = {}, {}
        if not grouped or not n:
            return masks, conf
        if n <= WINDOW_FRAMES:
            self._run_window(frames, 0, grouped, {}, masks, conf, progress, n)
            return masks, conf
        # the long-shot path: windows chained by their last masks, tracking
        # forward from the first click's window (backward reach lives inside
        # that window — the alternative was Metal refusing the buffer)
        first = min(f for (f, _), _ in grouped)
        pos = (first // WINDOW_FRAMES) * WINDOW_FRAMES
        seeds = {}
        while pos < n:
            end = min(pos + WINDOW_FRAMES, n)
            local = [((f - pos, o), pts) for (f, o), pts in grouped
                     if pos <= f < end]
            seeds = self._run_window(frames[pos:end], pos, local, seeds,
                                     masks, conf, progress, n)
            pos = end
        return masks, conf

    def _run_window(self, frame_files, offset, local_prompts, seed_masks,
                    masks, conf, progress, n_total):
        """One SAM2 state over one slice of the shot. Objects with no local
        click are seeded at the slice's first frame with their last mask
        from the previous window. Returns each object's final-frame mask."""
        import numpy as np
        import torch

        n_local = len(frame_files)
        with tempfile.TemporaryDirectory(prefix="stencil-win-") as td:
            # SAM2's loader reads a directory — hand it just this slice
            for k, f in enumerate(frame_files):
                os.symlink(f, Path(td) / f"{k:05d}.jpg")
            state = self.predictor.init_state(video_path=td)
            scale = np.array([[state["video_width"], state["video_height"]]],
                             dtype=np.float32)
            for (frame_idx, obj_id), pts in local_prompts:
                self.predictor.add_new_points_or_box(
                    state, frame_idx=frame_idx, obj_id=obj_id,
                    points=np.array([[float(p["x"]), float(p["y"])]
                                     for p in pts], dtype=np.float32) * scale,
                    labels=np.array([int(p.get("label", 1)) for p in pts],
                                    dtype=np.int32),
                )
            prompted_here = {o for (_, o), _ in local_prompts}
            for obj, mask in (seed_masks or {}).items():
                if obj not in prompted_here:
                    self.predictor.add_new_mask(state, frame_idx=0,
                                                obj_id=obj, mask=mask)
            last = {}
            with torch.inference_mode():
                for fidx, obj_ids, logits in \
                        self.predictor.propagate_in_video(state):
                    for oi, obj in enumerate(obj_ids):
                        prob = torch.sigmoid(logits[oi]).squeeze()
                        mask = (prob > 0.5).cpu().numpy()
                        # confidence = how certain the model is INSIDE its
                        # own matte
                        c = float(prob[prob > 0.5].mean()) if mask.any() else 0.0
                        g = offset + fidx
                        masks.setdefault(obj, [None] * n_total)[g] = \
                            (mask * 255).astype("uint8")
                        conf.setdefault(obj, [0.0] * n_total)[g] = c
                        if fidx == n_local - 1:
                            last[obj] = mask
                    if progress and fidx % 25 == 0:
                        progress(f"propagating {offset + fidx}/{n_total}")
            self.predictor.reset_state(state)
            del state
            _free(self.device)
            return last


class Preview:
    """The image predictor, warm — one frame, one answer, the moment the
    subject is clicked."""

    def __init__(self, ckpt: str, config: str = CONFIG):
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        self.pred = SAM2ImagePredictor(build_sam2(config, str(ckpt),
                                                  device=device()))

    def mask(self, img_rgb, points_norm, labels):
        """img_rgb: HxWx3 uint8 (RGB). points_norm: [(x, y)] 0..1.
        Returns (mask uint8 0/255, confidence)."""
        import numpy as np
        import torch

        h, w = img_rgb.shape[:2]
        pts = np.array([[x * w, y * h] for x, y in points_norm],
                       dtype=np.float32)
        with torch.inference_mode():
            self.pred.set_image(np.ascontiguousarray(img_rgb))
            masks, scores, _ = self.pred.predict(
                point_coords=pts, point_labels=np.array(labels, dtype=np.int32),
                multimask_output=False)
        return (masks[0] > 0.5).astype("uint8") * 255, float(scores[0])


# -- the helper process -----------------------------------------------------------

def _say(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def serve():
    """The helper loop: read a request line, answer with one JSON line (and
    progress lines before it). Ends when the app closes our stdin."""
    import numpy as np
    from PIL import Image

    engines, previews = {}, {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = req.get("op")
            if op == "hello":
                import torch
                _say({"ok": True, "torch": torch.__version__,
                      "device": device()})
            elif op == "preview":
                key = (req["ckpt"], req.get("config", CONFIG))
                if key not in previews:
                    previews[key] = Preview(*key)
                img = np.asarray(Image.open(req["image"]).convert("RGB"))
                m, c = previews[key].mask(
                    img, [tuple(p) for p in req["points"]], req["labels"])
                Image.fromarray(m).save(req["out"])
                _say({"ok": True, "conf": c})
            elif op == "propagate":
                key = (req["ckpt"], req.get("config", CONFIG))
                if key not in engines:
                    _say({"progress": "loading SAM 2.1…"})
                    engines[key] = Engine(*key)
                masks, conf = engines[key].run_shot(
                    req["frames_dir"], req["prompts"],
                    progress=lambda m: _say({"progress": m}))
                obj = int(req.get("obj", 1))
                out = Path(req["out_dir"])
                out.mkdir(parents=True, exist_ok=True)
                written = 0
                for i, m in enumerate(masks.get(obj, [])):
                    if m is None:
                        continue
                    Image.fromarray(m).save(out / f"m_{i:05d}.png")
                    written += 1
                _say({"ok": True, "n": len(masks.get(obj, [])),
                      "confidence": [round(float(c), 5)
                                     for c in conf.get(obj, [])],
                      "written": written})
            else:
                _say({"ok": False, "error": f"unknown op {op!r}"})
        except Exception as e:           # the answer IS the error report
            _say({"ok": False,
                  "error": f"{e.__class__.__name__}: {str(e)[:300]}"})


if __name__ == "__main__":
    serve()
