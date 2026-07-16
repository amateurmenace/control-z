"""Pivot analysis: one decode pass -> shots, face tracks, solved paths, sidecar.

Needs the pipeline deps (PyAV, OpenCV, numpy) and the YuNet model (auto-downloaded,
hash-verified). Everything downstream of detection is pure python from
pivot.tracking / pivot.solver — this module is the only place pixels meet math.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from czcore import models
from czcore.shots import cuts_from_diffs, shots_from_cuts

from . import __version__
from .aspect import CropGeometry, crop_geometry, parse_aspect
from .solver import PRESETS, SolvedPath, solve
from .tracking import Tracker, select_subject, targets_from_track

SIDE_CAR_VERSION = 1


@dataclass
class AspectSolve:
    aspect: str
    crop_w: int
    crop_h: int
    axis: str
    centers: List[float]
    shot_modes: List[str]
    moves: int
    max_punch_in: float = 1.0  # vs a 1080x1920-class delivery, filled by CLI
    targets: List[Optional[float]] = field(default_factory=list)  # raw, pre-solve


@dataclass
class Analysis:
    source: str
    width: int
    height: int
    fps: float
    n_frames: int
    shots: List[List[int]]
    aspects: Dict[str, AspectSolve]
    preset: str
    subjects: List[dict] = field(default_factory=list)  # per-shot QC report rows
    version: str = __version__
    sidecar_version: int = SIDE_CAR_VERSION

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=1)

    @staticmethod
    def from_json(text: str) -> "Analysis":
        d = json.loads(text)
        d["aspects"] = {k: AspectSolve(**v) for k, v in d["aspects"].items()}
        return Analysis(**d)


def _geometry_for(width: int, height: int, aspect_str: str) -> CropGeometry:
    return crop_geometry(width, height, parse_aspect(aspect_str))


def analyze(
    path: str,
    aspects: List[str],
    preset: str = "standard",
    det_step: int = 2,
    analysis_height: int = 360,
    score_threshold: float = 0.6,
    cut_threshold: float = 0.14,
    persons: str = "auto",  # auto = run YOLOX only where no face was found
    frame_cache: Optional[str] = None,  # dir for UI scrub JPEGs (analysis res)
    progress=None,
) -> Analysis:
    import av
    import cv2
    import numpy as np

    params = PRESETS[preset]
    detector_path = str(models.model_path("yunet"))

    diffs: List[float] = []
    prev_gray: Optional["np.ndarray"] = None
    tracker = Tracker()
    person_tracker = Tracker(dist_mult=0.8)  # person boxes are big; keep reach sane
    person_detector = None
    detector = None
    src_w = src_h = 0
    fps = 24.0
    n = 0

    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        if stream.average_rate:
            fps = float(stream.average_rate)
        src_w, src_h = stream.codec_context.width, stream.codec_context.height
        ah = analysis_height
        aw = max(2, int(round(src_w * ah / max(1, src_h) / 2)) * 2)
        for frame in container.decode(stream):
            img = frame.to_ndarray(format="bgr24")
            small = cv2.resize(img, (aw, ah), interpolation=cv2.INTER_AREA)
            if frame_cache:
                cv2.imwrite(f"{frame_cache}/f_{n:05d}.jpg", small,
                            [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
            if prev_gray is not None:
                diffs.append(float(np.abs(gray - prev_gray).mean()) / 255.0)
            prev_gray = gray

            if n % det_step == 0:
                if detector is None:
                    detector = cv2.FaceDetectorYN.create(
                        detector_path, "", (aw, ah), score_threshold
                    )
                _, faces = detector.detect(small)
                dets = []
                if faces is not None:
                    for f in faces:
                        x, y, w, h = f[0] / aw, f[1] / ah, f[2] / aw, f[3] / ah
                        dets.append(((float(x), float(y), float(w), float(h)),
                                     float(f[14])))
                tracker.update(n, dets)
                if persons == "always" or (persons == "auto" and not dets):
                    if person_detector is None:
                        from .persons import PersonDetector
                        person_detector = PersonDetector()
                    person_tracker.update(n, person_detector.detect(small))
            n += 1
            if progress and n % 240 == 0:
                progress(n)

    shots = shots_from_cuts(
        cuts_from_diffs(diffs, threshold=cut_threshold), n
    )

    aspect_solves: Dict[str, AspectSolve] = {}
    subjects: List[dict] = []
    for aspect_str in aspects:
        geom = _geometry_for(src_w, src_h, aspect_str)
        centers: List[float] = []
        targets_full: List[Optional[float]] = []
        modes: List[str] = []
        moves = 0
        for si, (s, e) in enumerate(shots):
            subject = select_subject([t.slice(s, e) for t in tracker.tracks])
            source = "face" if subject else None
            if subject is None:
                subject = select_subject(
                    [t.slice(s, e) for t in person_tracker.tracks]
                )
                source = "person" if subject else None
            axis = geom.axis if geom.axis in ("x", "y") else "x"
            targets = targets_from_track(subject, s, e, axis=axis)
            if geom.axis == "none":
                path_solved = SolvedPath("punch", [0.5] * (e - s), 0)
            else:
                path_solved = solve(targets, geom.half_width_norm, fps=fps, params=params)
            centers.extend(path_solved.centers)
            targets_full.extend(targets)
            modes.append(path_solved.mode)
            moves += path_solved.moves
            if aspect_str == aspects[0]:
                subjects.append({
                    "shot": si, "start": s, "end": e,
                    "subject_track": subject.tid if subject else None,
                    "subject_source": source,
                    "detections": len(subject.frames) if subject else 0,
                    "mode": path_solved.mode, "moves": path_solved.moves,
                    "fallback_center": subject is None,
                })
        aspect_solves[aspect_str] = AspectSolve(
            aspect=aspect_str, crop_w=geom.crop_w, crop_h=geom.crop_h,
            axis=geom.axis, centers=centers, shot_modes=modes, moves=moves,
            targets=targets_full,
        )

    return Analysis(
        source=path, width=src_w, height=src_h, fps=fps, n_frames=n,
        shots=[list(s) for s in shots], aspects=aspect_solves, preset=preset,
        subjects=subjects,
    )
