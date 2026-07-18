"""The auto-ducked mix — program under, narration over, one ffmpeg pass.

The graph is built as a pure string (tested without ffmpeg) and run
through czcore.ffrun like every shell-out in the suite. Three outputs in
one decode: the standalone narration track (program-length, silence
between cues), the broadcast-ready mixed audio, and — when the source
has video — the same mix muxed under an untouched video stream.

Ducking is a sidechain compressor keyed by the narration itself:
program audio drops ~18 dB while the voice speaks and breathes back in
400 ms after — the standard AD mix, not a novelty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

RATE = 48000
_FMT = f"aformat=sample_fmts=fltp:sample_rates={RATE}:channel_layouts=stereo"


def build_graph(starts_ms: List[int], duration: float) -> str:
    """filter_complex for n cues starting at the given milliseconds.
    Inputs: 0 = the program, 1..n = one wav per cue, in order."""
    n = len(starts_ms)
    if n < 1:
        raise ValueError("a mix needs at least one cue")
    parts = []
    for k, ms in enumerate(starts_ms):
        parts.append(f"[{k + 1}:a]{_FMT},adelay={int(ms)}:all=1[c{k}]")
    ins = "".join(f"[c{k}]" for k in range(n))
    parts.append(f"{ins}amix=inputs={n}:duration=longest:normalize=0[ad]")
    parts.append("[ad]asplit=3[sc][adm][adf0]")
    parts.append(f"[adf0]apad=whole_dur={max(0.1, duration):.3f}[adfile]")
    parts.append(f"[0:a]{_FMT}[pa]")
    parts.append("[pa][sc]sidechaincompress=threshold=0.032:ratio=8:"
                 "attack=20:release=400[dk]")
    parts.append("[dk][adm]amix=inputs=2:duration=longest:normalize=0[mixed]")
    parts.append("[mixed]asplit=2[mixa][mixv]")
    return ";".join(parts)


def run_mix(program: str, cues: List[Tuple[str, float]], outs: dict,
            duration: float, want_video: bool = True,
            progress: Optional[Callable[[float, str], None]] = None,
            cancelled: Optional[Callable[[], bool]] = None) -> dict:
    """cues = [(wav_path, start_seconds)...]. Returns {ad, mix_audio,
    mix_video?} with the written paths."""
    from czcore import ffrun

    cues = sorted(cues, key=lambda c: c[1])
    graph = build_graph([int(round(s * 1000)) for _, s in cues], duration)
    args: List[str] = ["-i", str(program)]
    for wav, _ in cues:
        args += ["-i", str(wav)]
    args += ["-filter_complex", graph,
             "-map", "[adfile]", "-c:a", "pcm_s16le", str(outs["ad"]),
             "-map", "[mixa]", "-c:a", "aac", "-b:a", "192k",
             str(outs["mix_audio"])]
    written = {"ad": str(outs["ad"]), "mix_audio": str(outs["mix_audio"])}
    if want_video:
        args += ["-map", "0:v", "-map", "[mixv]", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", str(outs["mix_video"])]
        written["mix_video"] = str(outs["mix_video"])
    for p in written.values():
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    ffrun.run(args, duration=duration, progress=progress, cancelled=cancelled)
    return written
