"""The pure heart of a publish kit — candidates + copy, assembled from a
transcript, labeled so, with no filesystem and no model in sight.

This module holds what the desk's Publisher (`publisher/kit.py`) and the
record's press (`web/kit.py`) both need and must agree on: the extractive copy
writer and the shape of a kit dict. Publisher reads its inputs from the
sidecars a producer's suite wrote beside a local video; the press reads its
inputs from the planes it already baked out of the hosted corpus. Everything
downstream of "here are the candidates and here is the insight" is identical,
and identical means shared — one implementation, so a kit opened at the desk
and a kit read on the record are the same object described the same way.

Pure by construction: only `re`, only dicts and lists in and out. The
generative path (one guarded model call on the user's own key) stays at the
desk in `publisher.kit.copy_generative`, because the press calls no model —
it is the one pipeline stage with no AI in it, and this module keeps that true
by not importing one.
"""

from __future__ import annotations

import re
from typing import List

RATIO_NAMES = ("16x9", "1x1", "9x16")


# -- small text helpers -------------------------------------------------------

def clip_label(c: dict) -> str:
    """A human handle for a clip — its first strong words, tidied."""
    text = re.sub(r"\s+", " ", str(c.get("text", ""))).strip()
    text = re.sub(r"^\W+", "", text)
    return (text[:64].rsplit(" ", 1)[0] + "…") if len(text) > 64 else text


def sentences(text: str, limit: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    out = ""
    for s in parts:
        if len(out) + len(s) + 1 > limit:
            break
        out = (out + " " + s).strip()
    return out or text[:limit].strip()


def fmt_t(t: float) -> str:
    """0:42 · 14:59 · 3:27:31 — hours only when the meeting earns them."""
    t = int(t)
    return (f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600
            else f"{t // 60}:{t % 60:02d}")


def top_entities(insight: dict, k: int = 4) -> List[str]:
    ents = (insight.get("entities") or {})
    ranked: List[tuple] = []
    for kind in ("people", "places", "organizations", "things"):
        for e in ents.get(kind) or []:
            name = str(e.get("name", "")) if isinstance(e, dict) else str(e)
            count = int(e.get("count", 1)) if isinstance(e, dict) else 1
            if name:
                ranked.append((count, name))
    return [n for _, n in sorted(ranked, reverse=True)[:k]]


def brief_text(insight: dict) -> str:
    """The extractive brief as prose — insight ships it as [{t, text}]
    sentences; older shapes were dict or plain string. Join, don't invent."""
    b = insight.get("brief")
    if isinstance(b, list):
        return " ".join(str(s.get("text", "")).strip().rstrip(".") + "."
                        for s in b if isinstance(s, dict) and s.get("text"))
    if isinstance(b, dict):
        return str(b.get("text") or b.get("summary") or "")
    return str(b or "")


# -- copy: extractive always --------------------------------------------------

def copy_extractive(meta: dict, cands: List[dict], insight: dict) -> dict:
    """Copy assembled from the record itself, labeled so. Every field is a
    working draft a producer can ship or rewrite — never placeholder-speak."""
    title = meta.get("title") or "Community program"
    when = meta.get("date", "")
    names = top_entities(insight)
    brief = brief_text(insight)
    top = cands[0] if cands else {}

    dated = bool(re.search(r"\d{4}|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|"
                           r"oct|nov|dec)", title, re.I))
    titles = [t for t in [
        sentences(str(top.get("text", "")), 70) if top else "",
        title + (f" — {when}" if when and not dated else ""),
        (f"{names[0]} and {names[1]}: {title}" if len(names) > 1 else ""),
    ] if t]
    chapters = [{"t": float(c["start"]), "label": clip_label(c)}
                for c in cands]
    desc_lines = [title + (f" · {when}" if when and not dated else ""), ""]
    if brief:
        desc_lines += [sentences(brief, 500), ""]
    if chapters:
        desc_lines += ["Moments:"] + [
            f"{fmt_t(ch['t'])} — {ch['label']}" for ch in chapters] + [""]
    desc_lines += ["Full program and record at the station. "
                   "Assembled from the transcript."]
    alt = [f"Video clip from {title}: {clip_label(c)}" for c in cands]
    blurb = sentences(brief or (top.get("text") or title), 320)
    social = {
        "vertical": (clip_label(top) if top else title)
        + (f" — {title}" if top else ""),
        "feed": sentences(brief or str(top.get("text") or ""), 200)
        + " (full program at the station)",
    }
    return {"origin": "extractive — assembled from the transcript, no model",
            "titles": titles, "description": "\n".join(desc_lines),
            "chapters": chapters, "alt_text": alt,
            "newsletter": blurb, "social": social}


# -- the kit dict, minus wherever the inputs came from ------------------------

def kit_from_parts(meta: dict, cands: List[dict], insight: dict) -> dict:
    """A kit built from parts already gathered — the pure core of a fresh kit.

    Candidates picked, extractive copy drafted, nothing rendered yet: `files`
    is empty and stays that way until a desk render fills it. The desk reads
    its parts from sidecars (`publisher.kit.new_kit`); the record reads them
    from the pressed moments plane (`web.kit.kit_from_meeting`); from here on
    the two are the same dict. The top three candidates default to `keep` —
    the same starting point a producer sees in Publisher's review page.
    """
    return {
        "version": 1,
        "meta": meta,
        "candidates": cands,
        "clips": [{**c, "keep": i < 3, "ratios": ["16x9", "9x16"],
                   "offset": 0.0, "label": clip_label(c)}
                  for i, c in enumerate(cands)],
        "copy": copy_extractive(meta, cands, insight),
        "files": [],
    }
