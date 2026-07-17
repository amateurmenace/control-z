"""Shared model store: download-on-first-use with pinned hashes and license cards.

Covenant: every model we ship is permissively licensed, downloaded transparently
(license shown, hash verified), and stored once for the whole suite at
~/Library/Application Support/control-z/models (macOS) or %APPDATA%/control-z.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ModelUnusable(FileNotFoundError):
    """This model can't be used right now — absent, or present with the wrong
    hash. Subclasses FileNotFoundError so callers that already degrade on a
    missing model degrade the same way on a corrupt one; str(e) is a sentence
    that names which case it is and what to do about it.
    """


@dataclass(frozen=True)
class ModelSpec:
    name: str
    filename: str
    url: Optional[str]     # None = produced locally (e.g. rise.convert)
    sha256: Optional[str]  # of the FILE WE KEEP; None only during development
    license: str
    card: str  # one-line honest description
    hint: str = ""         # how to obtain when url is None
    archive_member: str = ""  # url is a .tar.*: keep this member as `filename`


REGISTRY = {
    "realesrgan-x4": ModelSpec(
        name="realesrgan-x4",
        filename="realesrgan-x4.onnx",
        url=None,  # converted locally from official BSD-3 weights until we host our own
        sha256="dd1d2f07a16673d1ae02ae9576ff8465ceb87f7bc2f2fa7c99fe3c9eebd42750",
        license="BSD-3-Clause (xinntao/Real-ESRGAN)",
        card="Real-ESRGAN x4 — reconstructs detail when upscaling. Synthesizes texture (labeled).",
        # An honest hint, not a command a packaged app can't run: rise.convert
        # needs torch, which the .app deliberately doesn't bundle (specs/09
        # §5). Until the converted ONNX is hosted as a release asset, only a
        # source checkout can produce it — and Rise says what it falls back to.
        hint=("not hosted for download yet. From a source checkout: "
              "python -m rise.convert (needs torch). Without it, Rise "
              "upscales with plain Lanczos resampling and says so."),
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
    "pyannote_seg": ModelSpec(
        name="pyannote_seg",
        filename="pyannote-segmentation-3-0.onnx",
        url=("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
             "speaker-segmentation-models/"
             "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"),
        archive_member="sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
        sha256="220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
        license="MIT (pyannote segmentation-3.0 weights, via sherpa-onnx)",
        card="pyannote segmentation 3.0 — finds where each voice starts and "
             "stops. Half of Scribe's speaker labels. 6 MB, on-device.",
    ),
    "speaker_embed": ModelSpec(
        name="speaker_embed",
        filename="3dspeaker_speech_eres2net_base_sv.onnx",
        url=("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
             "speaker-recongition-models/"
             "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"),
        sha256="1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
        license="Apache-2.0 (3D-Speaker, Alibaba DAMO)",
        card="3D-Speaker embeddings — tells one voice from another so the turns "
             "get names. The other half of Scribe's speaker labels. 38 MB, "
             "on-device.",
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
            if spec.url:
                fix = ("Delete it and it downloads again on next use, or check "
                       "where it came from.")
            else:
                fix = ("This one is built on your machine rather than downloaded, "
                       "so delete it and build it again"
                       + (f" — {spec.hint}." if spec.hint else "."))
            raise ModelUnusable(
                f"{dest} exists but its hash doesn't match the pinned release "
                f"hash. {fix}")
        return dest
    if not auto_download or spec.url is None:
        raise ModelUnusable(
            f"model {name!r} not present (expected at {dest})"
            + (f" — {spec.hint}" if spec.hint else ""))
    if not quiet:
        print(f"[control-z] downloading model: {spec.name}")
        print(f"            {spec.card}")
        print(f"            license: {spec.license}")
        print(f"            from: {spec.url}")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(spec.url, tmp)  # nosec - pinned URL, hash-verified below
    if spec.archive_member:
        tmp = _extract(tmp, spec, dest)
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


def _extract(archive: Path, spec: ModelSpec, dest: Path) -> Path:
    """Pull spec.archive_member out of a downloaded tarball; return the temp
    file holding it (hashed by the caller, exactly like a direct download).

    Some upstreams only publish a model inside a tarball. Extraction is by
    exact member name — never a blanket extractall, which would let an archive
    write anywhere it likes.
    """
    import tarfile

    out = dest.with_suffix(".member")
    try:
        with tarfile.open(archive) as tf:
            try:
                member = tf.getmember(spec.archive_member)
            except KeyError:
                raise RuntimeError(
                    f"{spec.name}: the download doesn't contain "
                    f"{spec.archive_member!r} — upstream changed the archive's "
                    "layout, so this needs a code fix rather than a retry."
                ) from None
            if not member.isfile():
                raise RuntimeError(
                    f"{spec.name}: {spec.archive_member!r} isn't a regular file")
            src = tf.extractfile(member)
            with open(out, "wb") as f:
                shutil.copyfileobj(src, f)
    finally:
        archive.unlink(missing_ok=True)
    return out
