"""Room tone: profile a quiet region, synthesize matching tone forever.

Shaped-noise resynthesis: Welch PSD of the profile region -> white noise
filtered to that spectrum in overlap-add blocks -> seamless loop. The editor
gets a 30 s bed and gap-fills that actually match the room. (RX's Ambience
Match is the paywalled equivalent.)
"""

from __future__ import annotations


def find_quietest(audio, sr: int, length_s: float = 2.0) -> tuple:
    """(start_sample, end_sample) of the lowest-RMS window."""
    import numpy as np

    x = audio.mean(axis=1) if audio.ndim == 2 else audio
    win = int(sr * length_s)
    if len(x) <= win:
        return 0, len(x)
    hop = max(1, sr // 4)
    rms = np.array([
        float(np.sqrt(np.mean(x[i:i + win] ** 2)))
        for i in range(0, len(x) - win, hop)
    ])
    i = int(rms.argmin()) * hop
    return i, i + win


def profile(audio, sr: int, nperseg: int = 2048):
    """Welch PSD of the (mono-folded) region -> the room's spectral signature."""
    import numpy as np
    from scipy.signal import welch

    x = audio.mean(axis=1) if audio.ndim == 2 else audio
    freqs, psd = welch(x, fs=sr, nperseg=min(nperseg, len(x)))
    return {"freqs": freqs, "psd": np.maximum(psd, 1e-18), "sr": sr,
            "rms": float(np.sqrt(np.mean(x ** 2)))}


def generate(prof, seconds: float, seed: int = 7):
    """Synthesize matching tone: constant magnitude sqrt(PSD), random phase.

    Random-phase synthesis reproduces the spectral envelope exactly (no
    Rayleigh magnitude noise, no shaped-white coloration) and sounds like
    stationary room air, which is what room tone is."""
    import numpy as np

    sr = prof["sr"]
    n = int(seconds * sr)
    rng = np.random.default_rng(seed)
    block = (len(prof["freqs"]) - 1) * 2
    hop = block // 2
    out = np.zeros(n + block, dtype=np.float64)
    win = np.hanning(block)
    shape = np.sqrt(prof["psd"])
    norm = np.zeros_like(out)
    for start in range(0, n, hop):
        phase = rng.uniform(0, 2 * np.pi, len(shape))
        phase[0] = 0.0
        phase[-1] = 0.0  # DC and Nyquist stay real
        spec = shape * np.exp(1j * phase)
        chunk = np.fft.irfft(spec, block)
        out[start:start + block] += chunk * win
        norm[start:start + block] += win
    out = out[:n] / np.maximum(norm[:n], 1e-9)
    rms = np.sqrt(np.mean(out ** 2)) + 1e-12
    out = out * (prof["rms"] / rms)
    # loop-safe: short equal-power crossfade baked into the tail
    xf = min(int(0.25 * sr), n // 4)
    if xf > 0:
        t = np.linspace(0, np.pi / 2, xf)
        out[-xf:] = out[-xf:] * np.cos(t) ** 2 + out[:xf] * np.sin(t) ** 2
    return out.astype(np.float32)
