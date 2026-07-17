"""faster-whisper wrapper -> Transcript. Local, word timestamps, VAD on."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from czcore import models as model_store

from .transcript import Segment, Transcript, Word

DEFAULT_MODEL = "large-v3-turbo"


def whisper_cache() -> str:
    d = model_store.models_dir() / "whisper"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def transcribe(
    path: str,
    model: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    device: str = "auto",
    progress=None,
    hotwords: Optional[str] = None,
) -> Transcript:
    """hotwords: names and terms the audio is likely to carry — board
    members, streets, the town itself. Whisper's decoder is biased toward
    them in every window, which is what stops "Councilor Vitolo" landing
    as "counselor of it all". Callers harvest these from the meeting's own
    captions/metadata; ~1000 chars is plenty."""
    from faster_whisper import WhisperModel

    if progress:
        progress(f"loading whisper {model} (first run downloads it)")
    wm = WhisperModel(model, device="cpu" if device == "auto" else device,
                      compute_type="int8", download_root=whisper_cache())
    segments, info = wm.transcribe(
        path, language=language, word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        hotwords=(hotwords or None),
    )
    segs = []
    for s in segments:
        words = [Word(w=w.word.strip(), s=w.start, e=w.end, p=w.probability)
                 for w in (s.words or [])]
        segs.append(Segment(start=s.start, end=s.end, text=s.text.strip(),
                            words=words))
        if progress:
            progress(f"{s.end:5.1f}s  {s.text.strip()[:60]}")
    return Transcript(
        source=str(Path(path).resolve()), language=info.language,
        duration=float(info.duration), segments=segs, model=model,
    )
