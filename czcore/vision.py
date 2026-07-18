"""Local vision for Narrator — the last API door for audio description.

Narrator drafts descriptions of what's on screen. Today that draft rides the
user's API key (czcore.llm.complete_vision). This module is the on-device
alternative: a small vision-language model (Moondream-class, exported to ONNX)
run through onnxruntime — already a suite dependency — so a described track
needs no key and spends no tokens.

**Discovery by shape, namespaced away from TTS.** A VLM is a directory under
``models_dir()/vlm/`` holding the exported ONNX graphs (a vision encoder and a
text decoder) plus a tokenizer. It lives under ``vlm/`` deliberately: czcore.tts
claims any top-level model dir with ``*.onnx`` + ``tokens.txt`` as a voice, and
a VLM tokenizer would collide — the ``vlm/`` namespace keeps the two apart.

**Local first, key as fallback, honest either way.** narrator/describe.py tries
this engine before the key; a description carries which engine drew it, and the
track's provenance NOTE names it. Local inference spends no API tokens, so it
adds nothing to the AI audit — the audit stays a true record of key spend.

The model is Apache-2.0 (Moondream 2) — permissive, so it can be a real Models-
page card, unlike the CC-BY-NC translation weights. Nothing is bundled; the
operator installs it and the license is shown at download.

Stdlib-only at import time — onnxruntime, numpy, and PIL load inside functions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

# named model + install path, in tts.py's _INSTALL voice — the pinned Models-
# page card is a follow-up (it needs a hosted, sha-pinned bundle), the way the
# vits-ljs voice card followed its by-shape discovery.
_INSTALL = ("no on-device vision model installed — place a Moondream-class "
            "ONNX VLM (Apache-2.0: a vision encoder + text decoder .onnx and a "
            "tokenizer.json) in a folder under the suite's models/vlm/ "
            "directory, and Narrator drafts descriptions with no key and no "
            "tokens")

_SESSIONS = {}      # model dir -> loaded engine, so onnxruntime loads once


def _vlm_root(root: Optional[Path] = None) -> Path:
    from .models import models_dir
    return (root or models_dir()) / "vlm"


def _model_dirs(root: Optional[Path] = None) -> List[Path]:
    """VLM directories: under models_dir()/vlm/, each holding a vision encoder
    and a text decoder ONNX graph plus a tokenizer. Sorted for a stable
    default, and separate from the TTS voice namespace by construction."""
    base = _vlm_root(root)
    if not base.is_dir():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        onnx = {f.name for f in d.glob("*.onnx")}
        has_vision = any("vision" in n or "encoder" in n for n in onnx)
        has_text = any("text" in n or "decoder" in n for n in onnx)
        has_tok = (d / "tokenizer.json").exists() or (d / "tokenizer.model").exists()
        if has_vision and has_text and has_tok:
            out.append(d)
    return out


def model_name(root: Optional[Path] = None) -> Optional[str]:
    dirs = _model_dirs(root)
    return dirs[0].name if dirs else None


def available(root: Optional[Path] = None) -> dict:
    """{ok, model, sentence} — the same probe shape tts.available() uses, so
    the status line reads the same way. ok only when a model is installed AND
    onnxruntime imports."""
    dirs = _model_dirs(root)
    if not dirs:
        return {"ok": False, "model": None, "sentence": _INSTALL}
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return {"ok": False, "model": None,
                "sentence": "a vision model is installed but onnxruntime isn't "
                            "available in this environment"}
    name = dirs[0].name
    return {"ok": True, "model": name,
            "sentence": f"describing on-device — {name}, no key, no tokens"}


def _providers(device: str = "auto"):
    import onnxruntime as ort
    provs = ["CPUExecutionProvider"]
    if device in ("auto", "coreml") and "CoreMLExecutionProvider" in ort.get_available_providers():
        provs = ["CoreMLExecutionProvider"] + provs
    return provs


def _engine(root: Optional[Path] = None, device: str = "auto"):
    """The loaded VLM engine (sessions + tokenizer + config), cached per dir.
    Raises RuntimeError (a sentence) when nothing usable is installed."""
    dirs = _model_dirs(root)
    if not dirs:
        raise RuntimeError(_INSTALL)
    d = dirs[0]
    key = str(d)
    if key in _SESSIONS:
        return _SESSIONS[key]
    import json

    import onnxruntime as ort
    onnx = {f.name: f for f in d.glob("*.onnx")}
    vname = next((n for n in onnx if "vision" in n or "encoder" in n), None)
    tname = next((n for n in onnx if "text" in n or "decoder" in n), None)
    if not vname or not tname:
        raise RuntimeError(f"{d.name} is missing a vision or text ONNX graph")
    provs = _providers(device)
    vision = ort.InferenceSession(str(onnx[vname]), providers=provs)
    text = ort.InferenceSession(str(onnx[tname]), providers=provs)
    tok = _load_tokenizer(d)
    cfg = {}
    cj = d / "config.json"
    if cj.exists():
        try:
            cfg = json.loads(cj.read_text())
        except Exception:
            cfg = {}
    eng = {"dir": d, "vision": vision, "text": text, "tok": tok, "cfg": cfg}
    _SESSIONS[key] = eng
    return eng


def _load_tokenizer(d: Path):
    tj = d / "tokenizer.json"
    if tj.exists():
        from tokenizers import Tokenizer
        return Tokenizer.from_file(str(tj))
    raise RuntimeError(f"{d.name} has no readable tokenizer.json")


def _preprocess(jpeg: bytes, size: int):
    """JPEG bytes -> a normalized CHW float32 batch at the model's input size.
    Center-cropped to square then resized — the VLM wants a fixed square."""
    import io

    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    im = im.resize((size, size), Image.BILINEAR)
    arr = np.asarray(im, dtype="float32") / 255.0
    arr = (arr - 0.5) / 0.5                       # [-1, 1], the common VLM norm
    return arr.transpose(2, 0, 1)[None]           # NCHW


def describe(jpeg: bytes, prompt: str, system: str = "",
             max_tokens: int = 300, root: Optional[Path] = None,
             device: str = "auto") -> str:
    """Describe a frame with the on-device VLM. Returns a clean non-empty
    string, or raises RuntimeError (a sentence) — so narrator/describe.py can
    fall back to the API on any local failure and the contract never changes.

    The generation targets the Moondream-class ONNX export contract (a vision
    encoder producing an image embedding, a text decoder consuming
    [image-embed || prompt-tokens] autoregressively). A model whose graph
    doesn't match this contract raises here and the caller falls back — the
    covenant's honesty rule: a mechanism that can't run says so, never pretends.
    """
    import numpy as np
    eng = _engine(root, device)
    vision, text, tok, cfg = eng["vision"], eng["text"], eng["tok"], eng["cfg"]
    size = int(cfg.get("image_size", 378))
    try:
        pix = _preprocess(jpeg, size)
        vin = vision.get_inputs()[0].name
        img_embed = vision.run(None, {vin: pix})[0]      # (1, n_patches, dim)
    except Exception as e:
        raise RuntimeError(f"the on-device vision encoder didn't run ({type(e).__name__}) "
                           "— falling back") from e

    full = (system + "\n\n" + prompt).strip() if system else prompt
    try:
        prompt_ids = tok.encode(full).ids
    except Exception as e:
        raise RuntimeError(f"the vision tokenizer failed ({type(e).__name__})") from e

    eos = int(cfg.get("eos_token_id", 50256))
    out_ids: List[int] = []
    tin = {i.name for i in text.get_inputs()}
    try:
        cur = list(prompt_ids)
        for _ in range(max_tokens):
            feed = {}
            if "image_embeds" in tin:
                feed["image_embeds"] = img_embed
            if "input_ids" in tin:
                feed["input_ids"] = np.asarray([cur], dtype="int64")
            logits = text.run(None, feed)[0]
            nxt = int(np.asarray(logits)[0, -1].argmax())
            if nxt == eos:
                break
            out_ids.append(nxt)
            cur.append(nxt)
    except Exception as e:
        raise RuntimeError(f"the on-device text decoder didn't run ({type(e).__name__}) "
                           "— falling back") from e

    try:
        raw = tok.decode(out_ids)
    except Exception as e:
        raise RuntimeError(f"the vision decode failed ({type(e).__name__})") from e
    out = re.sub(r"\s+", " ", raw or "").strip()
    if not out:
        raise RuntimeError("the on-device model answered with no description")
    return out
