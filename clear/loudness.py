"""Loudness measure/normalize (BS.1770 via pyloudnorm) with an honest limiter."""

from __future__ import annotations

TARGETS = {"broadcast": -24.0, "podcast": -16.0, "streaming": -14.0}


def measure_lufs(audio, sr: int) -> float:
    import pyloudnorm as pyln

    meter = pyln.Meter(sr)
    return float(meter.integrated_loudness(audio))


def normalize(audio, sr: int, target_lufs: float = -24.0,
              true_peak_ceiling_db: float = -2.0):
    """Gain to target; if the ceiling would clip, back off and SAY so.

    Returns (audio, report dict). No sneaky limiting in v0.1 — a station
    should know when material needs real dynamics work.
    """
    import numpy as np

    lufs = measure_lufs(audio, sr)
    gain_db = target_lufs - lufs
    # 4x oversampled peak ≈ true peak, good enough to be honest about
    x = audio if audio.ndim == 1 else audio.mean(axis=1)
    up = np.interp(np.arange(len(x) * 4) / 4.0, np.arange(len(x)), x)
    peak_db = 20 * np.log2(np.max(np.abs(up)) + 1e-12) / np.log2(10)
    headroom = true_peak_ceiling_db - peak_db
    applied_db = min(gain_db, headroom)
    out = (audio * (10 ** (applied_db / 20))).astype(audio.dtype)
    return out, {
        "measured_lufs": round(lufs, 2),
        "target_lufs": target_lufs,
        "gain_db": round(gain_db, 2),
        "applied_db": round(applied_db, 2),
        "limited_by_peak": applied_db < gain_db - 0.01,
    }
