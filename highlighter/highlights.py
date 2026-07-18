"""Highlighter's name for the shared detection engine.

The scorer moved to czcore/moments.py (specs/12 §2: detection-as-a-service
— Publisher's clip candidates and Memory's issue engine call the same
scorer Highlighter always used). These explicit re-exports keep every
existing import working; new code should import czcore.moments directly.
"""

from czcore.moments import (  # noqa: F401
    KEYWORD_CLASSES,
    _EMPHASIS,
    _words_from_tagged,
    audio_energy,
    blend_energy,
    build_reel,
    parse_vtt,
    score_segments,
    transcript_dict,
)
