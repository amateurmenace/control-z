"""Transcript data model (versioned JSON — Minutes builds on this later)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import List, Optional

SCHEMA_VERSION = 1


@dataclass
class Word:
    w: str
    s: float          # start seconds
    e: float          # end seconds
    p: float = 1.0    # confidence


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: List[Word] = field(default_factory=list)
    speaker: Optional[str] = None


@dataclass
class Transcript:
    source: str
    language: str
    duration: float
    segments: List[Segment]
    model: str = ""
    speakers: List[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "Transcript":
        d = json.loads(text)
        d["segments"] = [
            Segment(start=s["start"], end=s["end"], text=s["text"],
                    words=[Word(**w) for w in s.get("words", [])],
                    speaker=s.get("speaker"))
            for s in d["segments"]
        ]
        d.pop("schema_version", None)
        return Transcript(**{k: v for k, v in d.items()})

    def full_text(self) -> str:
        out, last = [], None
        for s in self.segments:
            if s.speaker != last and s.speaker:
                out.append(f"\n{s.speaker}:")
                last = s.speaker
            out.append(s.text.strip())
        return " ".join(out).strip()
