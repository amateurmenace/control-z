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

SEG_MODEL = "pyannote_seg"
EMB_MODEL = "speaker_embed"


def _paths():
    """Where the pair lives — without downloading anything."""
    d = model_store.models_dir()
    return (d / model_store.REGISTRY[SEG_MODEL].filename,
            d / model_store.REGISTRY[EMB_MODEL].filename)


def available() -> bool:
    """True when both are on disk and match their pinned hashes."""
    for name in (SEG_MODEL, EMB_MODEL):
        try:
            model_store.model_path(name, auto_download=False)
        except FileNotFoundError:
            return False
    return True


def install_hint() -> str:
    seg = model_store.REGISTRY[SEG_MODEL]
    emb = model_store.REGISTRY[EMB_MODEL]
    return (
        "speaker labels need two models — they download on first use "
        f"({seg.license.split('(')[0].strip()} / "
        f"{emb.license.split('(')[0].strip()}, ~44 MB together), or from the "
        "Suite's Models page. Everything else in Scribe works without them."
    )


def diarize(transcript: Transcript, wav_path: str,
            num_speakers: int = -1, progress=None) -> Transcript:
    """Assign a speaker label to every segment (majority overlap). In place."""
    import numpy as np
    import sherpa_onnx
    import soundfile  # ships with sherpa-onnx dependency chain

    # first use downloads the pair (license card printed, hash verified)
    if progress and not available():
        progress("fetching the speaker models (~44 MB, first use only)…")
    seg_path = model_store.model_path(SEG_MODEL)
    emb_path = model_store.model_path(EMB_MODEL)

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
