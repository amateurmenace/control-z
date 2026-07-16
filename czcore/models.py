"""Shared model store: download-on-first-use with pinned hashes and license cards.

Covenant: every model we ship is permissively licensed, downloaded transparently
(license shown, hash verified), and stored once for the whole suite at
~/Library/Application Support/control-z/models (macOS) or %APPDATA%/control-z.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ModelSpec:
    name: str
    filename: str
    url: Optional[str]     # None = produced locally (e.g. rise.convert)
    sha256: Optional[str]  # None only during development; releases must pin
    license: str
    card: str  # one-line honest description
    hint: str = ""         # how to obtain when url is None


REGISTRY = {
    "realesrgan-x4": ModelSpec(
        name="realesrgan-x4",
        filename="realesrgan-x4.onnx",
        url=None,  # converted locally from official BSD-3 weights until we host our own
        sha256="dd1d2f07a16673d1ae02ae9576ff8465ceb87f7bc2f2fa7c99fe3c9eebd42750",
        license="BSD-3-Clause (xinntao/Real-ESRGAN)",
        card="Real-ESRGAN x4 — reconstructs detail when upscaling. Synthesizes texture (labeled).",
        hint="run: python -m rise.convert",
    ),
    "midas_small": ModelSpec(
        name="midas_small",
        filename="midas-small.onnx",
        url="https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx",
        sha256="2d8c6cb8f415229daf1eb041024208e2608c9f98e17c81cc7c6ecb449c56fd58",
        license="MIT (Intel ISL, MiDaS v2.1)",
        card="MiDaS-small monocular depth — relative depth per frame, 256px. Depth v0.1 backend "
             "(Video-Depth-Anything-Small planned for v0.2).",
    ),
    "sam21_small": ModelSpec(
        name="sam21_small",
        filename="sam2.1_hiera_small.pt",
        url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        sha256="6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
        license="Apache-2.0 (Meta)",
        card="SAM 2.1 hiera-small — click an object, get a matte for the whole shot. 176 MB, on-device.",
    ),
    "yolox_s": ModelSpec(
        name="yolox_s",
        filename="yolox_s.onnx",
        url=(
            "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/"
            "0.1.1rc0/yolox_s.onnx"
        ),
        sha256="c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
        license="Apache-2.0 (Megvii)",
        card="YOLOX-s person detector — finds people when faces aren't visible. 34 MB, on-device.",
    ),
    "yunet": ModelSpec(
        name="yunet",
        filename="face_detection_yunet_2023mar.onnx",
        url=(
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        license="MIT (OpenCV Zoo)",
        card="YuNet face detector — finds faces so Pivot can follow them. Tiny (2 MB), on-device.",
    ),
}


def models_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":  # pragma: no cover
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:  # pragma: no cover
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "control-z" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_path(name: str, auto_download: bool = True, quiet: bool = False) -> Path:
    spec = REGISTRY[name]
    dest = models_dir() / spec.filename
    if dest.exists():
        if spec.sha256 and _sha256(dest) != spec.sha256:
            raise RuntimeError(
                f"{dest} exists but its hash doesn't match the pinned release hash. "
                "Delete it to re-download, or check where it came from."
            )
        return dest
    if not auto_download or spec.url is None:
        raise FileNotFoundError(
            f"model {name!r} not present (expected at {dest})"
            + (f" — {spec.hint}" if spec.hint else ""))
    if not quiet:
        print(f"[control-z] downloading model: {spec.name}")
        print(f"            {spec.card}")
        print(f"            license: {spec.license}")
        print(f"            from: {spec.url}")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(spec.url, tmp)  # nosec - pinned URL, hash-verified below
    got = _sha256(tmp)
    if spec.sha256 and got != spec.sha256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"downloaded {spec.name} hash mismatch (got {got[:16]}…, "
            f"expected {spec.sha256[:16]}…) — refusing to use it."
        )
    tmp.rename(dest)
    if not quiet:
        print(f"            ok, sha256 verified → {dest}")
    return dest
