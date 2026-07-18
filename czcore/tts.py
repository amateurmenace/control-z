"""Text-to-speech for the wing — one clear voice, local, honest.

Narrator's speech engine, in czcore because spoken output is a thing the
whole wing will eventually ask for (Interpreter's translated audio is
specs/15 P1). sherpa-onnx is already a suite dependency (Scribe's
diarization rides it); the VOICE is a model, and models arrive the
suite's way — downloaded transparently or placed by hand, never bundled.

Discovery, not registry: any sherpa VITS voice directory placed under
the shared models folder (czcore.models.models_dir()) is found by shape
— a directory containing exactly one .onnx plus tokens.txt, with
espeak-ng-data/ or lexicon.txt as the voice requires. The suite's
model store doesn't carry TTS entries yet (that's a lane-C handoff ask);
until it does, ``available()`` returns the manual-install sentence and
the page says it instead of pretending.

Stdlib-only at import time; sherpa_onnx loads inside synth.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import List, Optional

# the voice we verify against and name in the install sentence: LJSpeech
# (public-domain corpus), lexicon-based — no espeak data needed
SUGGESTED = "vits-ljs"
_INSTALL = ("no voice installed — download a sherpa-onnx VITS voice (the "
            f"suite is tested with “{SUGGESTED}”, public-domain LJSpeech) "
            "from github.com/k2-fsa/sherpa-onnx releases (tag tts-models), "
            "untar it into the suite's models folder, and this page finds "
            "it by itself")


def _voice_dirs(root: Optional[Path] = None) -> List[Path]:
    if root is None:
        from .models import models_dir
        root = models_dir()
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and list(d.glob("*.onnx")) and (d / "tokens.txt").exists():
            out.append(d)
    return out


def voice_config(voice_dir: Path) -> dict:
    """What this voice needs, read off its own contents — {model, tokens,
    lexicon, data_dir, name}. Raises RuntimeError (a sentence) when the
    directory doesn't hold a usable voice."""
    onnx = sorted(voice_dir.glob("*.onnx"))
    if not onnx or not (voice_dir / "tokens.txt").exists():
        raise RuntimeError(f"{voice_dir.name} doesn't look like a sherpa "
                           "VITS voice (needs one .onnx + tokens.txt)")
    data_dir = voice_dir / "espeak-ng-data"
    lexicon = voice_dir / "lexicon.txt"
    return {"name": voice_dir.name, "model": str(onnx[0]),
            "tokens": str(voice_dir / "tokens.txt"),
            "lexicon": str(lexicon) if lexicon.exists() else "",
            "data_dir": str(data_dir) if data_dir.is_dir() else ""}


def available(root: Optional[Path] = None) -> dict:
    """{ok, voice, sentence} — what the page shows, never a shrug."""
    try:
        import sherpa_onnx  # noqa: F401
    except ImportError:
        return {"ok": False, "voice": None,
                "sentence": "sherpa-onnx isn't installed in this "
                            "environment — pip install -r requirements.txt"}
    voices = _voice_dirs(root)
    if not voices:
        return {"ok": False, "voice": None, "sentence": _INSTALL}
    name = voices[0].name
    return {"ok": True, "voice": name,
            "sentence": f"speaking with {name} — local, on-device"}


_TTS_CACHE: dict = {}


def synth(text: str, out_wav: str, voice: Optional[str] = None,
          speed: float = 1.0, root: Optional[Path] = None) -> dict:
    """Speak text into out_wav (16-bit PCM). Returns {path, seconds,
    sample_rate, voice}. Raises RuntimeError with a sentence when there is
    no engine or no voice — callers show it, never guess."""
    try:
        import sherpa_onnx
    except ImportError as e:
        raise RuntimeError("sherpa-onnx isn't installed — pip install -r "
                           "requirements.txt") from e
    voices = _voice_dirs(root)
    if not voices:
        raise RuntimeError(_INSTALL)
    vdir = next((v for v in voices if v.name == voice), voices[0])
    cfg = voice_config(vdir)
    key = cfg["model"]
    tts = _TTS_CACHE.get(key)
    if tts is None:
        tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=cfg["model"], tokens=cfg["tokens"],
                    lexicon=cfg["lexicon"], data_dir=cfg["data_dir"]),
                num_threads=2)))
        _TTS_CACHE[key] = tts
    audio = tts.generate(str(text), sid=0, speed=float(speed))
    samples = list(audio.samples)
    rate = int(audio.sample_rate)
    if not samples:
        raise RuntimeError("the voice answered with silence — the text may "
                           "be empty or all symbols")
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        ints = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, float(s)))
            iv = int(v * 32767)
            ints += iv.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(ints))
    return {"path": str(out_wav), "seconds": round(len(samples) / rate, 3),
            "sample_rate": rate, "voice": cfg["name"]}
