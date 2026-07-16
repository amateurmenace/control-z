"""Voice isolation via the official DeepFilterNet3 binary (MIT/Apache).

We run `deep-filter` as a subprocess — same pattern as ffmpeg — because the
PyPI python package is unmaintained (pins numpy<2, imports removed torchaudio
modules; learned 2026-07-16). The binary embeds the DF3 model, runs real-time
on CPU, and keeps our environment clean.

Mix-back is ours: 100% wet is rarely right, the default leaves some room in.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

BIN_SHA256 = "4601e7f4e4c03e59a4c5b5000216ef3add3e808799cfccd95e14e83ea4611081"
BIN_URL = ("https://github.com/Rikorose/DeepFilterNet/releases/download/"
           "v0.5.6/deep-filter-0.5.6-aarch64-apple-darwin")


def binary_path() -> Path:
    from czcore.models import models_dir

    return models_dir().parent / "bin" / "deep-filter"


def available() -> bool:
    return binary_path().exists()


def install_hint() -> str:
    return (f"deep-filter binary not installed. Download {BIN_URL} to "
            f"{binary_path()}, chmod +x it. License: MIT/Apache (Rikorose/"
            f"DeepFilterNet). Expected sha256 {BIN_SHA256[:16]}….")


def isolate(audio, sr: int, mix_back: float = 0.35, atten_db: float = 60.0):
    """Run DF3 on (n,) or (n, ch) float32; return same shape at same sr.

    mix_back: 0 = fully isolated, 1 = untouched. Default keeps 35% room.
    """
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    if not available():
        raise FileNotFoundError(install_hint())

    x = audio.astype(np.float32)
    stereo_in = x.ndim == 2
    work = x if stereo_in else x[:, None]

    # DF3 wants 48 kHz
    if sr != 48000:
        work = resample_poly(work, 48000, sr, axis=0).astype(np.float32)

    with tempfile.TemporaryDirectory(prefix="clear-df-") as td:
        inp = Path(td) / "in.wav"
        sf.write(inp, work, 48000)
        subprocess.run(
            [str(binary_path()), "-a", str(atten_db), "-o", td, str(inp)],
            check=True, capture_output=True,
        )
        outs = [p for p in Path(td).glob("*.wav") if p.name != "in.wav"]
        wet_path = outs[0] if outs else inp
        wet, _ = sf.read(wet_path, dtype="float32", always_2d=True)

    n = min(len(wet), len(work))
    blended = wet[:n] * (1.0 - mix_back) + work[:n] * mix_back
    if sr != 48000:
        blended = resample_poly(blended, sr, 48000, axis=0).astype(np.float32)
    n_out = min(len(blended), len(x))
    out = blended[:n_out]
    if not stereo_in:
        out = out[:, 0]
    # pad tail if resampling shaved samples, keeps A/B null tests aligned
    if len(out) < len(x):
        pad = [(0, len(x) - len(out))] + ([(0, 0)] if out.ndim == 2 else [])
        out = np.pad(out, pad)
    return out.astype(np.float32)
