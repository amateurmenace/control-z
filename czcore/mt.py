"""Machine translation for the wing — chunked, timed, glossary-constrained.

Interpreter's engine, kept in czcore because translation is a thing the
whole wing will eventually ask for (Memory's cross-language search, the
site's panel languages). Three honest layers:

  - The user's own guarded key (czcore.llm — Anthropic or OpenAI by key
    shape) is the quality path today. Same covenant as every generative
    surface: no key ships, nothing runs without the user's own.
  - A local MT runtime slots in behind ``available()`` the day one fits
    the dep set without a casual heavy add (NLLB-class models want a
    tokenizer we don't ship; that door stays drawn, not forced).
  - Without any engine, callers get a sentence to show, never a pretend.

The unit of work is the **cue** — rolling ASR/caption fragments are
coalesced into caption-sized, sentence-shaped cues first (translating
half-sentences is how names get mangled), then translated in numbered
chunks with the N| line protocol Highlighter's translate proved out:
one line in, one line out, prefixes kept, a dropped line falls back to
English and says so. Timing never leaves the cue.

Stdlib-only at import time, per the house dep-guard convention.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

# The seven panel languages from the project site's accessibility panel —
# Simple English is a first-class target (plain-language intralingual
# captions: same pipeline, different instruction), not a footnote.
LANGUAGES = [
    {"code": "es", "name": "Español", "english": "Spanish", "srclang": "es"},
    {"code": "simple", "name": "Simple English", "english": "Simple English",
     "srclang": "en"},
    {"code": "zh", "name": "中文", "english": "Chinese (Simplified)",
     "srclang": "zh"},
    {"code": "pt", "name": "Português", "english": "Portuguese",
     "srclang": "pt"},
    {"code": "ht", "name": "Kreyòl Ayisyen", "english": "Haitian Creole",
     "srclang": "ht"},
    {"code": "vi", "name": "Tiếng Việt", "english": "Vietnamese",
     "srclang": "vi"},
    {"code": "ru", "name": "Русский", "english": "Russian", "srclang": "ru"},
]


def lang(code: str) -> Optional[dict]:
    return next((l for l in LANGUAGES if l["code"] == code), None)


def engine_for(code: str) -> dict:
    """The engine that will ACTUALLY carry one language — {engine, model}.
    'simple' (an intralingual English rewrite) has no local target, so it stays
    on the key path even when a local model is installed; every other panel
    language prefers the local engine. Returns engine None (with a sentence)
    when nothing can carry that code — the caller skips it honestly rather than
    crashing mid-job or mislabeling the track."""
    if code != "simple":
        try:
            from . import mt_local
            loc = mt_local.available()
            if loc.get("engine") == "local":
                return {"engine": "local", "model": loc["model"]}
        except Exception:
            pass
    # simple, or no local model: the key path
    from . import llm
    st = llm.status()
    if st["enabled"]:
        return {"engine": "key", "model": st["model"]}
    return {"engine": None, "model": None,
            "sentence": ("Simple English is an English rewrite — it needs your "
                         "API key (Settings → AI), even with a local model")
            if code == "simple" else
            "no translation engine — install a local model or add your key"}


def available() -> dict:
    """What can translate today, as the UI shows it: {engine, model,
    sentence}. engine is "local" (an on-device model, no key), "key" (the
    user's API key), or None. Local wins when present — it spends no tokens
    and needs no account, the covenant's preference; the key remains the
    quality path and the fallback."""
    # local first: an on-device model needs no key and spends nothing
    try:
        from . import mt_local
        loc = mt_local.available()
        if loc.get("engine") == "local":
            return {"engine": "local", "model": loc["model"], "provider": None,
                    "sentence": loc["sentence"]}
    except Exception:
        pass

    from . import llm
    st = llm.status()
    if st["enabled"]:
        return {"engine": "key", "model": st["model"],
                "provider": st.get("provider"),
                "sentence": f"translation runs on your key — {st['model']}"}
    return {"engine": None, "model": None, "provider": None,
            "sentence": "no translation engine yet — install a local model on "
                        "the Models page, or add your API key in Settings → AI"}


# -- cue math: rolling fragments -> caption-shaped cues ----------------------

_SENT_END = re.compile(r"[.?!…][\"'”’)\]]?$")


def coalesce(segments: List[dict], max_chars: int = 84, max_dur: float = 7.0,
             max_gap: float = 1.4, min_break: int = 24) -> List[dict]:
    """Rolling caption/ASR fragments -> cues [{start, end, text}].

    A cue closes when the next fragment would overflow max_chars, when the
    audio gap says the thought ended, when the clock says the caption held
    long enough (max_dur), or at a sentence end once there's enough text to
    stand alone (min_break). Timing is carried, never invented: a cue spans
    exactly its first fragment's start to its last fragment's end.
    """
    cues: List[dict] = []
    cur_text: List[str] = []
    cur_start = cur_end = 0.0

    def close():
        nonlocal cur_text
        text = " ".join(cur_text).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            cues.append({"start": round(cur_start, 3),
                         "end": round(cur_end, 3), "text": text})
        cur_text = []

    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        s, e = float(seg.get("start", 0)), float(seg.get("end", 0))
        if cur_text:
            joined = len(" ".join(cur_text)) + 1 + len(text)
            gap = s - cur_end
            if joined > max_chars or gap > max_gap \
                    or (e - cur_start) > max_dur:
                close()
        if not cur_text:
            cur_start, cur_end = s, e
        cur_text.append(text)
        cur_end = max(cur_end, e)
        if _SENT_END.search(text) and len(" ".join(cur_text)) >= min_break:
            close()
    close()
    return cues


def chunks(cues: List[dict], per: int = 40) -> List[List[dict]]:
    """Cue list -> N|-protocol-sized chunks (per cues each, order kept)."""
    per = max(1, int(per))
    return [cues[i:i + per] for i in range(0, len(cues), per)]


# -- glossary: do-not-translate + vetted terms, applied on every pass --------

def glossary_prompt(glossary: Optional[dict], code: str, text: str) -> str:
    """The constraint block for one chunk — only the terms that actually
    appear in this chunk's text, so the prompt stays small and the model
    stays pointed. Empty string when nothing applies."""
    if not glossary:
        return ""
    low = text.lower()
    lines = []
    keep = [t for t in glossary.get("keep", [])
            if t and t.lower() in low]
    if keep:
        lines.append("Never translate these names — copy them exactly: "
                     + "; ".join(sorted(set(keep))) + ".")
    for term, renders in (glossary.get("terms") or {}).items():
        if term.lower() not in low:
            continue
        want = (renders or {}).get(code) or {}
        out = want.get("text") if isinstance(want, dict) else want
        if out:
            lines.append(f'Render "{term}" as "{out}".')
    return "\n".join(lines)


def check_kept(src: str, out: str, keep_terms: List[str]) -> List[str]:
    """Which do-not-translate terms were in the source but lost on the way
    — the review queue's cheapest honest signal."""
    low_src, low_out = src.lower(), out.lower()
    return [t for t in keep_terms
            if t and t.lower() in low_src and t.lower() not in low_out]


# -- the translation pass ----------------------------------------------------

def _system_for(code: str, glossary_block: str) -> str:
    entry = lang(code) or {"english": code, "name": code}
    if code == "simple":
        head = ("You rewrite English civic-meeting captions into Simple "
                "English — plain language for cognitive accessibility. "
                "Short sentences. Everyday words. Expand jargon and "
                "acronyms the first time they appear. Keep names, numbers, "
                "dollar amounts and times exact.")
    else:
        head = (f"You translate English civic-meeting captions into "
                f"{entry['english']} ({entry['name']}). Natural, plain "
                f"{entry['english']} at a general reading level. Keep "
                "names, numbers, dollar amounts and times exact.")
    rules = ("Answer with EXACTLY one line per input line, keeping each "
             "N| prefix unchanged. No commentary, no blank lines.")
    return "\n".join(x for x in (head, glossary_block, rules) if x)


def translate_cues(cues: List[dict], code: str,
                   glossary: Optional[dict] = None,
                   progress: Optional[Callable[[float, str], None]] = None,
                   check_cancel: Optional[Callable[[], None]] = None,
                   complete: Optional[Callable] = None,
                   per: int = 40) -> List[dict]:
    """Translate cues into one language. Returns new cues:
    [{start, end, text, src, fallback?, miss?}] — text is the translation,
    src the English it came from, fallback marks lines the model dropped
    (kept English, honestly), miss lists do-not-translate terms that got
    lost (review-queue bait). Timing rides through untouched.
    """
    if lang(code) is None:
        raise RuntimeError(f"unknown language code “{code}” — the panel "
                           "speaks " + ", ".join(l["code"] for l in LANGUAGES))
    if complete is None:
        # a local on-device model translates every panel language but Simple
        # English (an intralingual rewrite NLLB has no target for) — that one
        # stays on the key path. Local wins when it can carry the language.
        if code != "simple":
            try:
                from . import mt_local
                if mt_local.available().get("engine") == "local":
                    complete = mt_local.adapter(code, glossary)
            except Exception:
                complete = None
        if complete is None:
            from . import llm
            if not llm.enabled():
                raise RuntimeError(
                    "no translation engine — install a local model on the "
                    "Models page, or add your API key in Settings → AI")
            complete = llm.complete
    keep_terms = list((glossary or {}).get("keep") or [])
    out: List[dict] = []
    parts = chunks(cues, per=per)
    name = (lang(code) or {}).get("name", code)
    for ci, chunk in enumerate(parts):
        if check_cancel:
            check_cancel()
        if progress:
            progress(ci / max(1, len(parts)),
                     f"{name} — chunk {ci + 1}/{len(parts)}")
        numbered = "\n".join(f"{k}|{c['text']}" for k, c in enumerate(chunk))
        block = glossary_prompt(glossary, code, numbered)
        got: Dict[int, str] = {}
        try:
            raw = complete(prompt=numbered,
                           system=_system_for(code, block),
                           max_tokens=3600)
            for ln in raw.splitlines():
                if "|" not in ln:
                    continue
                k, txt = ln.split("|", 1)
                try:
                    got[int(k.strip())] = txt.strip()
                except ValueError:
                    pass
        except RuntimeError:
            got = {}   # the whole chunk fell — every line says so below
        for k, c in enumerate(chunk):
            txt = got.get(k, "").strip()
            cue = {"start": c["start"], "end": c["end"],
                   "text": txt or c["text"], "src": c["text"]}
            if not txt:
                cue["fallback"] = True
            else:
                miss = check_kept(c["text"], txt, keep_terms)
                if miss:
                    cue["miss"] = miss
            out.append(cue)
    if progress:
        progress(1.0, f"{name} — {len(out)} cues")
    return out
