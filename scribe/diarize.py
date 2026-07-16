"""Speaker diarization behind one function, so the implementation can change
without touching anything else (specs/03-scribe.md names this the flakiest
piece — it's deliberately optional in v0.1).

Backend: sherpa-onnx offline speaker diarization (pyannote segmentation-3.0,
MIT weights + 3D-Speaker embeddings, Apache). Models land in the shared store;
if they're missing we say exactly how to get them and continue without.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from czcore import models as model_store

from .transcript import Transcript

SEG_FILE = "pyannote-segmentation-3-0.onnx"
EMB_FILE = "3dspeaker_speech_eres2net_base_sv.onnx"

SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
EMB_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")


def _paths():
    d = model_store.models_dir()
    return d / SEG_FILE, d / EMB_FILE


def available() -> bool:
    seg, emb = _paths()
    return seg.exists() and emb.exists()


def install_hint() -> str:
    seg, emb = _paths()
    return (
        "diarization models not installed. Two files go in "
        f"{seg.parent}:\n"
        f"  1. {SEG_FILE} — from {SEG_URL} (extract model.onnx from the tar, "
        "rename)\n"
        f"  2. {EMB_FILE} — from {EMB_URL}\n"
        "Licenses: MIT (pyannote weights) / Apache-2.0 (3D-Speaker)."
    )


def diarize(transcript: Transcript, wav_path: str,
            num_speakers: int = -1, progress=None) -> Transcript:
    """Assign a speaker label to every segment (majority overlap). In place."""
    import numpy as np
    import sherpa_onnx
    import soundfile  # ships with sherpa-onnx dependency chain

    seg_path, emb_path = _paths()
    if not available():
        raise FileNotFoundError(install_hint())

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_path))),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb_path)),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers),
    )
    sd = sherpa_onnx.OfflineSpeakerDiarization(config)
    audio, sr = soundfile.read(wav_path, dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != sd.sample_rate:
        import scipy.signal as ss
        audio = ss.resample_poly(audio, sd.sample_rate, sr).astype(np.float32)
    if progress:
        progress("diarizing…")
    result = sd.process(audio).sort_by_start_time()
    turns = [(t.start, t.end, f"Speaker {t.speaker + 1}") for t in result]

    for seg in transcript.segments:
        best, best_ov = None, 0.0
        for s, e, name in turns:
            ov = min(seg.end, e) - max(seg.start, s)
            if ov > best_ov:
                best, best_ov = name, ov
        seg.speaker = best
    transcript.speakers = sorted({s for _, _, s in turns})
    return transcript
