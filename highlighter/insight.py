"""The meeting, read locally — brief, entities, topics, questions, answers.

The web app asks a cloud model; this reads the transcript itself and shows
receipts. The brief is extractive (the meeting's own sentences, chosen and
time-stamped, never paraphrased); entities are pattern-harvested; "ask the
meeting" is retrieval — it points at what was said, it doesn't make prose
up. Every card in the UI says which kind of reading it got.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from .highlights import KEYWORD_CLASSES, score_segments

STOPWORDS = set("""a about above after again against all am an and any are as
at be because been before being below between both but by could did do does
doing down during each few for from further had has have having he her here
hers herself him himself his how i if in into is it its itself just me more
most my myself no nor not now of off on once only or other our ours ourselves
out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up
very was we were what when where which while who whom why will with you your
yours yourself yourselves would can may might must shall going go get got
know think say said says see right okay ok yeah yes um uh like well really
just actually also one two three want make made need look looking thing
things time way lot bit dont don didnt cant wont let lets us thank thanks
gonna kind sort mr mrs ms dr item items next new motion second meeting board
committee town public comment agenda minutes vote member members chair year
percent question questions""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_MONEY = re.compile(r"\$[\d,.]+(?:\s*(?:million|billion|thousand|k|m))?", re.I)
_CAP_RUN = re.compile(r"\b([A-Z][a-z]+(?:\s+(?:of|the|and|for)?\s*[A-Z][a-z]+){1,4})\b")
_ORG_TAIL = ("committee", "board", "commission", "department", "school",
             "district", "association", "authority", "council", "group",
             "society", "center", "club", "coalition")
_PLACE_TAIL = ("street", "st", "avenue", "ave", "road", "rd", "park", "square",
               "place", "lane", "drive", "hill", "path", "playground",
               "library", "hall")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def word_freq(segments: List[dict], top: int = 80) -> List[dict]:
    """The word cloud's data: civic stopwords out, counts + first mention."""
    counts: Counter = Counter()
    first: Dict[str, float] = {}
    for s in segments:
        for w in _WORD.findall(str(s.get("text", ""))):
            lw = w.lower()
            if lw in STOPWORDS or len(lw) < 3:
                continue
            counts[lw] += 1
            first.setdefault(lw, float(s.get("start", 0)))
    return [{"word": w, "count": c, "t": first[w]}
            for w, c in counts.most_common(top) if c > 1]


def brief(segments: List[dict], n: int = 5) -> List[dict]:
    """Executive brief, extractive: the n most load-bearing sentences, spread
    across the meeting, each with its timestamp. The meeting's own words."""
    if not segments:
        return []
    scored = score_segments(segments)
    cands = []
    for k, s in enumerate(scored):
        for sent in _sentences(str(s.get("text", ""))):
            words = [w.lower() for w in _WORD.findall(sent)]
            info = len([w for w in words if w not in STOPWORDS])
            if info < 4 or len(sent) < 25:
                continue
            cands.append({"t": float(s.get("start", 0)), "text": sent,
                          "score": s["score"] * 2 + min(info, 18) / 18.0,
                          "k": k})
    if not cands:
        return []
    total = max(c["t"] for c in cands) or 1.0
    picks: List[dict] = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if len(picks) >= n:
            break
        # spread: no two brief lines from the same tenth of the meeting
        if any(abs(c["t"] - p["t"]) < total / (n * 2) for p in picks):
            continue
        picks.append(c)
    picks.sort(key=lambda c: c["t"])
    return [{"t": round(p["t"], 1), "text": p["text"]} for p in picks]


def entities(segments: List[dict], top: int = 12) -> Dict[str, List[dict]]:
    """People / places / organizations / money, pattern-harvested with
    counts and a first-mention timestamp. Heuristic and labeled as such."""
    buckets: Dict[str, Counter] = {k: Counter() for k in
                                   ("people", "places", "organizations", "money")}
    first: Dict[str, float] = {}
    for s in segments:
        text = str(s.get("text", ""))
        t = float(s.get("start", 0))
        for m in _MONEY.findall(text):
            key = m.strip()
            buckets["money"][key] += 1
            first.setdefault(key, t)
        for m in _CAP_RUN.findall(text):
            phrase = m.strip()
            words = phrase.split()
            lw = phrase.lower()
            if words[0].lower() in ("the", "a", "i") or len(phrase) < 6:
                continue
            last = words[-1].lower()
            if last in _ORG_TAIL or any(w.lower() in _ORG_TAIL for w in words):
                buckets["organizations"][phrase] += 1
            elif last in _PLACE_TAIL or any(w.lower() in _PLACE_TAIL for w in words):
                buckets["places"][phrase] += 1
            elif len(words) == 2 and all(w[0].isupper() for w in words) \
                    and not any(w.lower() in STOPWORDS for w in words):
                buckets["people"][phrase] += 1
            first.setdefault(phrase, t)
        spk = s.get("speaker")
        if spk and not str(spk).lower().startswith("speaker"):
            buckets["people"][str(spk)] += 1
            first.setdefault(str(spk), t)
    return {k: [{"name": n_, "count": c, "t": round(first.get(n_, 0), 1)}
                for n_, c in v.most_common(top)]
            for k, v in buckets.items()}


def hotwords(segments: List[dict], meta: Optional[dict] = None,
             cap: int = 1000) -> str:
    """Names the recording likely carries, as one comma-joined string for
    Whisper's decoder — people first (they mis-transcribe worst), then
    places and organizations, then names scraped from the title. Built
    from the meeting's own captions/metadata; nothing invented, and the
    caller can edit before it's used."""
    ent = entities(segments, top=16)
    seen, out = set(), []

    def add(name: str):
        n = " ".join(str(name).split())
        if len(n) < 3 or n.lower() in seen:
            return
        seen.add(n.lower())
        out.append(n)

    # every bucket is tail-word- or shape-verified upstream, and a hotword
    # the audio never says biases nothing — so one mention is enough
    for bucket in ("people", "places", "organizations"):
        for row in ent.get(bucket, []):
            add(row["name"])
    for key in ("title", "uploader"):
        for m in _CAP_RUN.findall(str((meta or {}).get(key) or "")):
            add(m)
    s = ", ".join(out)
    return s[:cap].rsplit(", ", 1)[0] if len(s) > cap else s


def pace(segments: List[dict], bins: int = 50) -> dict:
    """Words per minute across the meeting, counted into bins — the fast
    stretches read fast, the procedural stretches read slow. Counted, not
    modeled."""
    if not segments:
        return {"bins": [], "duration": 0, "wpm_avg": 0}
    dur = max(float(s.get("end", 0)) for s in segments) or 1.0
    words = [0.0] * bins
    for s in segments:
        n = len(str(s.get("text", "")).split())
        b = min(bins - 1, int(float(s.get("start", 0)) / dur * bins))
        words[b] += n
    per_bin_min = (dur / bins) / 60.0 or 1.0
    wpm = [round(w / per_bin_min, 1) for w in words]
    total_words = sum(words)
    return {"bins": wpm, "duration": round(dur, 1),
            "wpm_avg": round(total_words / (dur / 60.0), 1)}


def dynamics(segments: List[dict], bins: int = 50) -> dict:
    """Three thin lanes over the hour — questions asked, decision words,
    tension words — counted per bin from the same keyword classes the
    scorer shows its reasons with. A shape of the meeting, not a mood
    model."""
    lanes = {"questions": [0] * bins, "decisions": [0] * bins,
             "tension": [0] * bins}
    if not segments:
        return {"bins": bins, "lanes": lanes}
    dur = max(float(s.get("end", 0)) for s in segments) or 1.0
    dec_words = KEYWORD_CLASSES["decision"][1]
    ten_words = KEYWORD_CLASSES["tension"][1]
    for s in segments:
        text = str(s.get("text", ""))
        low = text.lower()
        b = min(bins - 1, int(float(s.get("start", 0)) / dur * bins))
        lanes["questions"][b] += text.count("?")
        lanes["decisions"][b] += sum(1 for w in dec_words if w in low)
        lanes["tension"][b] += sum(1 for w in ten_words if w in low)
    return {"bins": bins, "lanes": lanes, "duration": round(dur, 1)}


_AGENDA_LINE = re.compile(
    r"^\s*[•\-–—*]?\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–—:.]?\s*(.{3,90})\s*$")


def _to_seconds(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    parts = [0] * (3 - len(parts)) + parts
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def agenda(info: Optional[dict]) -> List[dict]:
    """The meeting's own agenda: yt-dlp chapters when the upload carries
    them, else timestamp lines in the description (the civic upload habit).
    Two items minimum — one timestamp is a link, not an agenda."""
    if not info:
        return []
    chapters = info.get("chapters") or []
    out = [{"t": round(float(c.get("start_time", 0)), 1),
            "label": str(c.get("title", "")).strip()}
           for c in chapters if str(c.get("title", "")).strip()]
    if len(out) >= 2:
        return out
    desc = str(info.get("description") or "")
    hits = []
    for line in desc.splitlines():
        m = _AGENDA_LINE.match(line)
        if m:
            hits.append({"t": _to_seconds(m.group(1)),
                         "label": m.group(2).strip(" -–—:.")})
    hits = [h for h in hits if h["label"]]
    return hits if len(hits) >= 2 else []


def participation(segments: List[dict]) -> List[dict]:
    """Talk time per labeled speaker. Empty when nobody ran diarization."""
    talk: Dict[str, float] = defaultdict(float)
    turns: Counter = Counter()
    for s in segments:
        spk = s.get("speaker")
        if not spk:
            continue
        talk[spk] += max(0.0, float(s.get("end", 0)) - float(s.get("start", 0)))
        turns[spk] += 1
    total = sum(talk.values()) or 1.0
    rows = [{"speaker": k, "seconds": round(v, 1), "turns": turns[k],
             "share": round(v / total, 3)} for k, v in talk.items()]
    rows.sort(key=lambda r: -r["seconds"])
    return rows


_QTYPES = (
    ("budget", ("cost", "budget", "pay", "fund", "money", "dollar", "price",
                "afford", "expense")),
    ("timeline", ("when", "how long", "timeline", "deadline", "schedule",
                  "date", "soon")),
    ("accountability", ("who", "responsible", "accountab", "enforce",
                        "oversight", "report")),
    ("rationale", ("why", "reason", "how come", "justif", "basis")),
)


def questions(segments: List[dict], top: int = 30) -> List[dict]:
    """Every question asked, typed by its words, with its moment."""
    out = []
    for s in segments:
        for sent in _sentences(str(s.get("text", ""))):
            if not sent.endswith("?") or len(sent) < 12:
                continue
            low = sent.lower()
            qtype = next((name for name, keys in _QTYPES
                          if any(k in low for k in keys)), "information")
            out.append({"t": round(float(s.get("start", 0)), 1),
                        "speaker": s.get("speaker"), "text": sent,
                        "type": qtype})
    return out[:top]


def topics(segments: List[dict], top: int = 8) -> List[dict]:
    """The meeting's recurring two-word subjects, with a first mention."""
    counts: Counter = Counter()
    first: Dict[str, float] = {}
    for s in segments:
        words = [w.lower() for w in _WORD.findall(str(s.get("text", "")))]
        for a, b in zip(words, words[1:]):
            if a in STOPWORDS or b in STOPWORDS or len(a) < 3 or len(b) < 3:
                continue
            key = f"{a} {b}"
            counts[key] += 1
            first.setdefault(key, float(s.get("start", 0)))
    return [{"topic": k, "count": c, "t": round(first[k], 1)}
            for k, c in counts.most_common(top) if c >= 3]


def ask(segments: List[dict], question: str, k: int = 4) -> dict:
    """Retrieval, not generation: the passages that best answer the words of
    the question, each with its timestamp — plus follow-up suggestions."""
    q_words = [w.lower() for w in _WORD.findall(question)
               if w.lower() not in STOPWORDS and len(w) > 2]
    if not q_words:
        return {"passages": [], "suggestions": _suggest(segments),
                "note": "ask with a few content words — names, places, topics"}
    scored = []
    for i, s in enumerate(segments):
        low = " " + str(s.get("text", "")).lower() + " "
        hits = sum(low.count(" " + w) + low.count(w) for w in q_words) / 2
        exact = 1.5 if all(w in low for w in q_words) else 0.0
        if hits <= 0:
            continue
        scored.append((hits + exact, i))
    scored.sort(key=lambda x: -x[0])
    passages = []
    used = set()
    for _, i in scored:
        if len(passages) >= k:
            break
        if any(abs(i - j) <= 1 for j in used):
            continue
        used.add(i)
        ctx = " ".join(str(segments[j].get("text", ""))
                       for j in range(max(0, i - 1), min(len(segments), i + 2)))
        passages.append({"t": round(float(segments[i].get("start", 0)), 1),
                         "speaker": segments[i].get("speaker"),
                         "text": ctx[:420]})
    passages.sort(key=lambda p: p["t"])
    return {"passages": passages, "suggestions": _suggest(segments),
            "note": None if passages else
            "nothing in the transcript matches those words — try the ones "
            "people actually used"}


def _suggest(segments: List[dict]) -> List[str]:
    tops = topics(segments, top=4)
    outs = [f"What was said about {t['topic']}?" for t in tops[:3]]
    ent = entities(segments, top=3)
    if ent["money"]:
        outs.append(f"Where does {ent['money'][0]['name']} come up?")
    return outs[:4]


def decisions(segments: List[dict], top: int = 12) -> List[dict]:
    """Motions and votes with their apparent outcome — the decision tracker."""
    out = []
    outcome_words = (("carried", "passes"), ("passed", "passes"),
                     ("carries", "passes"), ("unanimous", "passes"),
                     ("approved", "passes"), ("adopted", "passes"),
                     ("fails", "fails"), ("failed", "fails"),
                     ("denied", "fails"), ("tabled", "tabled"),
                     ("postponed", "tabled"))
    decide_words = KEYWORD_CLASSES["decision"][1]
    for i, s in enumerate(segments):
        low = " " + str(s.get("text", "")).lower() + " "
        if not any(w in low for w in decide_words):
            continue
        window = " ".join(str(segments[j].get("text", "")).lower()
                          for j in range(i, min(len(segments), i + 3)))
        outcome = next((tag for w, tag in outcome_words if w in window), "discussed")
        out.append({"t": round(float(s.get("start", 0)), 1),
                    "text": str(s.get("text", ""))[:300],
                    "outcome": outcome})
    # collapse near-duplicates (the same motion echoes across segments)
    dedup: List[dict] = []
    for d in out:
        if dedup and d["t"] - dedup[-1]["t"] < 20 and d["outcome"] == dedup[-1]["outcome"]:
            continue
        dedup.append(d)
    return dedup[:top]
