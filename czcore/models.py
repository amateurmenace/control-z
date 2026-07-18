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


# The covenant's licence rule, executable. Every registered model must name a
# licence containing one of these permissive markers, and none of the
# forbidden ones — so the day someone reaches for NLLB-200 (CC-BY-NC) the
# registry refuses at import time with a sentence, instead of the rule living
# only in a docstring nobody re-reads. (That exact decision is on the books:
# packaging/RELEASE-NOTES-1.9.0.md defers the MT card because of this rule.)
_PERMISSIVE_MARKS = ("MIT", "BSD", "Apache-2.0", "MPL-2.0", "CC0",
                     "ISC", "Unlicense", "public domain", "public-domain")
_FORBIDDEN_MARKS = ("NC", "NonCommercial", "non-commercial", "GPL",
                    "research only", "no commercial")


def _licence_is_permissive(text: str) -> bool:
    # GPL check must not trip on "LGPL"-free registry (models never link), and
    # NC must not trip on words like "once" — match the marks as tokens.
    low = text.lower()
    if any(m.lower() in low for m in _FORBIDDEN_MARKS if len(m) > 2):
        return False
    if "nc" in low.replace("-nc", " nc ").split() or "-nc-" in low:
        return False
    return any(m.lower() in low for m in _PERMISSIVE_MARKS)


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
    archive_dir: str = ""  # url is a .tar.*: keep every file under this member
    #                        directory; `filename` then names a DIRECTORY (a
    #                        voice is model + tokens + lexicon, not one file)

    def __post_init__(self):
        if not _licence_is_permissive(self.license):
            raise ValueError(
                f"model {self.name!r} declares licence {self.license!r}, "
                "which the covenant doesn't allow — every shipped model is "
                "permissive (MIT/BSD/Apache/MPL/CC0). A non-commercial or "
                "GPL model needs a deliberate covenant amendment, not a "
                "registry entry.")


REGISTRY = {
    "realesrgan-x4": ModelSpec(
        name="realesrgan-x4",
        filename="realesrgan-x4.onnx",
        # Hosted as a control-z release asset since v1.0.0: converted from the
        # official BSD-3 weights by `python -m rise.convert` (deterministic —
        # the sha below is both the pin and the reproducibility proof).
        url=("https://github.com/amateurmenace/control-z/releases/download/"
             "v1.0.0/realesrgan-x4.onnx"),
        sha256="dd1d2f07a16673d1ae02ae9576ff8465ceb87f7bc2f2fa7c99fe3c9eebd42750",
        license="BSD-3-Clause (xinntao/Real-ESRGAN)",
        card="Real-ESRGAN x4 — reconstructs detail when upscaling. Synthesizes texture (labeled).",
        hint=("downloads from the v1.0.0 release (sha256-pinned). Or convert "
              "it yourself from a source checkout: python -m rise.convert "
              "(needs torch). Without it, Rise upscales with plain Lanczos "
              "resampling and says so."),
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
    "vits-ljs": ModelSpec(
        name="vits-ljs",
        filename="vits-ljs",  # a directory: the voice is .onnx + tokens + lexicon
        url=("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
             "tts-models/vits-ljs.tar.bz2"),
        archive_dir="vits-ljs",
        # manifest hash (_sha256_dir): verified against both a fresh download
        # of the release asset and the voice Narrator was proven with
        sha256="a9adc2ae51e1307f63dad201f4bd4c3ebbf71517d659462637db4abbc8286556",
        license="Apache-2.0 (k2-fsa sherpa-onnx export; VITS weights trained "
                "on the public-domain LJSpeech corpus)",
        card="vits-ljs — the Narrator's voice. One clear English speaker, "
             "CMU-lexicon based, so no GPL espeak-ng data rides along. "
             "112 MB, on-device.",
        hint=("czcore.tts finds any sherpa VITS voice placed under the models "
              "folder by shape; this entry just makes the tested one a "
              "click."),
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


def _sha256_dir(path: Path) -> str:
    """One pin for a directory model: the sha256 of a manifest — one line per
    regular file, ``relpath\\0sha256(file)``, sorted by path. Deterministic
    across platforms, and auditable: print the same lines and compare."""
    lines = []
    for f in sorted(path.rglob("*")):
        if f.is_file():
            lines.append(f"{f.relative_to(path).as_posix()}\0{_sha256(f)}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def model_path(name: str, auto_download: bool = True, quiet: bool = False) -> Path:
    spec = REGISTRY[name]
    dest = models_dir() / spec.filename
    if dest.exists():
        pin = _sha256_dir(dest) if dest.is_dir() else _sha256(dest)
        if spec.sha256 and pin != spec.sha256:
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
    if spec.archive_dir:
        tmp = _extract_dir(tmp, spec, dest)
    elif spec.archive_member:
        tmp = _extract(tmp, spec, dest)
    got = _sha256_dir(tmp) if tmp.is_dir() else _sha256(tmp)
    if spec.sha256 and got != spec.sha256:
        shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink(missing_ok=True)
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


def _extract_dir(archive: Path, spec: ModelSpec, dest: Path) -> Path:
    """Pull every regular file under spec.archive_dir out of a downloaded
    tarball into a temp directory (manifest-hashed by the caller, exactly like
    a single file). Member paths are vetted one component at a time — never an
    extractall, and a name that tries to walk out of the prefix is skipped."""
    import tarfile

    prefix = spec.archive_dir.rstrip("/") + "/"
    out = dest.with_suffix(".member")
    if out.exists():
        shutil.rmtree(out)
    kept = 0
    try:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile() or not member.name.startswith(prefix):
                    continue
                rel = member.name[len(prefix):]
                parts = Path(rel).parts
                if not parts or any(p in ("..", "") or "/" in p or "\\" in p
                                    for p in parts) or Path(rel).is_absolute():
                    continue
                target = out.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(member)
                with open(target, "wb") as f:
                    shutil.copyfileobj(src, f)
                kept += 1
        if not kept:
            shutil.rmtree(out, ignore_errors=True)
            raise RuntimeError(
                f"{spec.name}: the download holds nothing under "
                f"{spec.archive_dir!r}/ — upstream changed the archive's "
                "layout, so this needs a code fix rather than a retry.")
    finally:
        archive.unlink(missing_ok=True)
    return out
