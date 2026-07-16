"""Classical DSP modules: de-hum, de-click, de-ess. No models, golden-tested.

All functions take/return float32 mono or (n, ch) arrays in -1..1.
"""

from __future__ import annotations

from typing import Optional, Tuple


def _mono(audio):
    return audio.mean(axis=1) if audio.ndim == 2 else audio


def detect_hum(audio, sr: int) -> Optional[float]:
    """Find mains hum: strongest of 50/60 Hz (and near-bins) above the floor."""
    import numpy as np

    x = _mono(audio)
    n = min(len(x), sr * 20)
    if n < sr:
        return None
    spec = np.abs(np.fft.rfft(x[:n] * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1 / sr)

    def power_near(f0):
        band = (freqs > f0 - 1.5) & (freqs < f0 + 1.5)
        return spec[band].max() if band.any() else 0.0

    floor = np.median(spec[(freqs > 20) & (freqs < 400)]) + 1e-12
    best, best_p = None, 0.0
    for base in (50.0, 60.0):
        # a real hum shows harmonics, not just the fundamental
        p = power_near(base) + power_near(base * 2) + power_near(base * 3)
        if p > best_p:
            best, best_p = base, p
    if best_p / (3 * floor) < 8.0:  # not convincingly hummy
        return None
    return best


def dehum(audio, sr: int, base: float, harmonics: int = 8, q: float = 35.0):
    """Zero-phase notch cascade at base and its harmonics below Nyquist."""
    import numpy as np
    from scipy.signal import filtfilt, iirnotch

    out = audio.astype(np.float64, copy=True)
    for k in range(1, harmonics + 1):
        f = base * k
        if f >= sr / 2 * 0.95:
            break
        b, a = iirnotch(f, q, fs=sr)
        if out.ndim == 2:
            for c in range(out.shape[1]):
                out[:, c] = filtfilt(b, a, out[:, c])
        else:
            out = filtfilt(b, a, out)
    return out.astype(np.float32)


def declick(audio, sr: int, sensitivity: float = 10.0,
             max_gap_ms: float = 2.0) -> Tuple["object", int]:
    """Impulse repair via second-difference detection + interpolation.

    The second difference is huge at a click and small for anything band-
    limited, and — unlike a zero-phase IIR high-pass — it doesn't ring, so a
    click flags ~3 samples, not 200 (bug fixed 2026-07-16). A rarity guard
    refuses to "repair" material where >1% of samples flag (that's texture or
    damage, not clicks — RX-style spectral repair territory, out of scope).

    Returns (repaired, n_samples_actually_repaired)."""
    import numpy as np

    x = audio.astype(np.float64, copy=True)
    mono = _mono(x)
    d2 = np.zeros_like(mono)
    d2[1:-1] = mono[2:] - 2 * mono[1:-1] + mono[:-2]
    mad = np.median(np.abs(d2)) + 1e-12
    bad = np.abs(d2) > sensitivity * mad * 1.4826
    if not bad.any():
        return audio, 0
    if bad.mean() > 0.01:  # rarity guard: not click-like material
        return audio, 0
    # widen by 2 samples so the full impulse body is covered
    kernel = np.ones(5, dtype=bool)
    bad = np.convolve(bad, kernel, mode="same") > 0
    max_gap = int(sr * max_gap_ms / 1000)

    idx = np.arange(len(mono))
    runs = np.split(idx[bad], np.where(np.diff(idx[bad]) != 1)[0] + 1)
    n_fixed = 0

    def repair(ch):
        nonlocal n_fixed
        y = ch.copy()
        for run in runs:
            if len(run) == 0 or len(run) > max_gap:
                continue
            a, b = run[0] - 1, run[-1] + 1
            if a < 0 or b >= len(y):
                continue
            y[run] = np.interp(run, [a, b], [y[a], y[b]])
            n_fixed += len(run)
        return y

    if x.ndim == 2:
        for c in range(x.shape[1]):
            x[:, c] = repair(x[:, c])
        n_fixed //= x.shape[1]
    else:
        x = repair(x)
    return x.astype(np.float32), n_fixed


def deess(audio, sr: int, amount: float = 0.5, lo: float = 5000.0,
          hi: float = 9000.0):
    """Split-band compressor keyed on the sibilant band. amount 0..1."""
    import numpy as np
    from scipy.signal import butter, sosfilt, sosfiltfilt

    if amount <= 0:
        return audio
    x = audio.astype(np.float64, copy=True)
    sos = butter(4, [lo, min(hi, sr / 2 * 0.95)], "bandpass", fs=sr, output="sos")

    def one(ch):
        band = sosfiltfilt(sos, ch)
        env = np.abs(band)
        # ~5 ms smoothing
        k = max(1, int(sr * 0.005))
        env = np.convolve(env, np.ones(k) / k, mode="same")
        thresh = np.percentile(env, 90) + 1e-9
        over = np.maximum(env / thresh, 1.0)
        gain = over ** (-amount)          # compress the band above threshold
        return ch - band + band * gain

    if x.ndim == 2:
        for c in range(x.shape[1]):
            x[:, c] = one(x[:, c])
    else:
        x = one(x)
    return x.astype(np.float32)
