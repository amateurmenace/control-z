"""The reading — what the meeting was about, with receipts.

Extractive by default: brief, entities, topics, decisions, participation all
come from Highlighter's local insight engine, which reads the transcript itself
and quotes it verbatim. No key, no network, stands alone — the covenant's
default.

Generative only on top: a one-paragraph summary through czcore.llm *when the
user has brought a key*, always labeled with its model and always beside — not
instead of — the extractive reading. With no key the same call returns the
extractive brief, so every surface has something true to show. Memory
supplements the official record; it never replaces it, and it never speaks
without saying who is speaking.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from czcore import llm
from highlighter import insight

_SUMMARY_SYS = (
    "You summarize public civic meetings for residents. Be plain, neutral, and "
    "concrete. One short paragraph. Name what was discussed and any decisions, "
    "using the [MM:SS] timestamps from the transcript so a reader can check you. "
    "Never invent a vote or a name that is not in the passages. This supplements "
    "the official record; it does not replace it."
)


def read(segments: List[dict], info: Optional[dict] = None) -> dict:
    """The full extractive reading, cached beside the meeting. Every value is
    quoted or counted from the transcript — nothing modeled, nothing inferred
    about people's positions (a hard non-goal)."""
    meta = info or {}
    return {
        "brief": insight.brief(segments),
        "entities": insight.entities(segments),
        "topics": insight.topics(segments),
        "decisions": insight.decisions(segments),
        "questions": insight.questions(segments),
        "participation": insight.participation(segments),
        "wordfreq": insight.word_freq(segments),
        "agenda": insight.agenda(meta),
    }


def extractive_summary(segments: List[dict], n: int = 5) -> str:
    """The brief, joined — verbatim sentences from the meeting, in order."""
    return " ".join(r.get("text", "") for r in insight.brief(segments, n=n)).strip()


def summary(segments: List[dict],
            info: Optional[dict] = None) -> Tuple[str, str]:
    """One-paragraph summary → (text, origin). Generative when a key is set
    (origin 'ai:<model>'), extractive fallback otherwise (origin 'extractive').
    Never raises for lack of a key — that is the whole point."""
    if not segments:
        return "", "none"
    if llm.enabled():
        try:
            text = llm.complete(_prompt(segments, info), system=_SUMMARY_SYS,
                                max_tokens=400)
            if text.strip():
                model = llm.status().get("model", "a cloud model")
                return text.strip(), f"ai:{model}"
        except Exception:
            pass  # the extractive path stands alone — fall through to it
    return extractive_summary(segments), "extractive"


def _prompt(segments: List[dict], info: Optional[dict], budget: int = 40000) -> str:
    title = (info or {}).get("title", "")
    lines = [f"[{int(s.get('start', 0) // 60):02d}:{int(s.get('start', 0) % 60):02d}] "
             f"{(s.get('speaker') + ': ') if s.get('speaker') else ''}"
             f"{s.get('text', '')}" for s in segments]
    body = "\n".join(lines)
    if len(body) > budget:  # stride-sample long meetings, keep the whole arc
        stride = max(2, len(body) // budget + 1)
        body = "\n".join(lines[::stride])
    head = f"Meeting: {title}\n\n" if title else ""
    return f"{head}Transcript passages:\n{body}\n\nWrite the summary paragraph."
