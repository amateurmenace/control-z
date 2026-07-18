"""The Vote Ledger — roll calls read straight off the record.

A roll-call vote is the most accountable moment a public body has: a motion is
read, and each member says their name's worth out loud. This module reads those
moments back out of the transcript — verbatim and timestamped — into a structured
ledger: what was moved, who voted how, and how it came out.

Three covenant guarantees hold by construction:

1. **Officials only.** A roll call *is* the officials voting — private citizens
   are never called by name to vote. Because this extractor only reads names
   that appear inside a roll-call window (a "call the roll" / "all in favor"
   trigger, then short name→"aye"/"no" pairs), it can only ever surface the
   people the chair called — the board. specs/14 §8's officials-only rule is
   automatic here, not a filter bolted on.

2. **Verbatim, never inferred.** Every roll entry carries the timestamp and the
   spoken word it was read from — a receipt, not a judgement. We record that a
   member said "aye" at 105:37; we never infer a stance, a position, or a
   pattern. specs/14 §3's no-stance-inference non-goal.

3. **Extractive first.** The default path is pure pattern-matching over the
   transcript — no key, no network. An optional LLM pass can clean a messy
   window, but it is labeled ('ai:<model>') and never required; the extractive
   ledger stands alone.

The town's own agenda (memory/documents.py) supplies the canonical roster, so
the ASR's "John Vancoyak" reads back as "John VanScoyoc" — the paper correcting
the tape. Without an agenda, the spoken names stand as heard.
"""

from __future__ import annotations

import difflib
import re
from typing import List, Optional

# what opens a roll call
_TRIGGER = re.compile(
    r"\b(all (those )?in favor|those in favor|call the roll|roll call|"
    r"take (a|the) (roll[- ]call )?vote|by roll call|"
    r"all those opposed|indicate by saying)\b", re.I)
# a lone vote token — a member's answer. ASR mangles "Aye" to "I"/"I.".
_AYE = {"i", "aye", "ayes", "yes", "yea", "yeah", "yep", "in favor"}
_NAY = {"no", "nay", "nays", "opposed", "against"}
_ABSTAIN = {"abstain", "abstains", "present", "recuse", "recused", "recusing",
            "pass", "passing"}
# outcome language in the resolution window
_OUTCOME = (("unanimous", "passes"), ("carries", "passes"), ("carried", "passes"),
            ("passes", "passes"), ("passed", "passes"), ("approved", "passes"),
            ("adopted", "passes"), ("motion passes", "passes"),
            ("so voted", "passes"), ("fails", "fails"), ("failed", "fails"),
            ("denied", "fails"), ("does not carry", "fails"),
            ("tabled", "tabled"), ("postponed", "tabled"), ("withdrawn", "tabled"))
# words that make a "name-shaped" token not a name
_NOT_NAME = {"the", "and", "for", "yes", "aye", "nay", "no", "all", "in",
             "favor", "opposed", "motion", "second", "seconded", "so", "okay",
             "thank", "you", "chair", "madam", "mister", "please", "indicate",
             "saying", "next", "item", "number", "vote", "abstain", "present",
             "great", "right", "good", "thanks", "yeah", "yep", "now", "that",
             "hey", "hi", "um", "uh", "alright", "yep", "well", "sure", "here",
             "any", "none", "carried", "unanimous", "against", "abstaining"}
_MOTION_HINT = re.compile(
    r"\b(move|moved|motion|approve|approv|adopt|second|article|amend|"
    r"minutes|appropriat|authoriz|refer|recommend|warrant|resolution|"
    r"appoint|award|accept|grant|waive)\w*", re.I)
_TOKENS = re.compile(r"[A-Za-z][A-Za-z.'-]*")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _looks_like_name(text: str) -> Optional[str]:
    """A short run of 1–3 words that reads as a person's name, or None. Every
    word must be capitalized (a name is not 'I have a' or 'Got it') and none may
    be a procedural word. 'John Warren' yes; 'All in favor' no; 'Got it' no."""
    words = _TOKENS.findall(text.strip())
    # the ASR merges a prior member's "Aye" echo onto the next voter's name
    # ("I. John Warren,"): drop a leading lone vote-echo token so the name is
    # the name, not "I. John Warren" (which would fragment an official's record)
    if len(words) > 1 and words[0].lower().strip(".") in (_AYE | _NAY | _ABSTAIN):
        words = words[1:]
    if not (1 <= len(words) <= 3):
        return None
    cand = " ".join(words).strip(" .,")
    low = [w.lower().strip(".") for w in words]
    if any(w in _NOT_NAME for w in low):
        return None
    # EVERY word must be capitalized-alphabetic (a middle initial "W." counts) —
    # this is what keeps 'I have a' and 'Got it' out when no roster is gating
    for w in words:
        core = w.strip(".")
        if not core or not core[0].isupper() or not core.isalpha():
            return None
    if len(cand) < 3 or len(cand) > 26:
        return None
    return cand


def _vote_of(text: str) -> Optional[str]:
    """The vote a short answer segment carries, or None if it isn't one."""
    words = _TOKENS.findall(text.lower())
    if not words or len(words) > 4:
        return None
    joined = " ".join(w.strip(".") for w in words)
    toks = set(w.strip(".") for w in words)
    if toks & _NAY or "opposed" in joined:
        return "no"
    if toks & _ABSTAIN:
        return "abstain"
    if toks & _AYE or joined in _AYE:
        return "yes"
    return None


def _canon_name(name: str, roster: List[str]) -> Optional[str]:
    """Map a spoken (often ASR-garbled) name to the roster's canonical spelling.
    Returns the canonical name when one is close enough; None when a roster
    exists but nothing matches (so junk like 'Hey' is dropped, not recorded);
    the name as heard when there is no roster at all."""
    if not roster:
        return name
    keys = {_norm(r): r for r in roster}
    n = _norm(name)
    if n in keys:
        return keys[n]
    # last-name match first (roll calls often drop or garble the first name)
    ln = _norm(name.split()[-1]) if name.split() else n
    best, best_r = 0.0, None
    for r in roster:
        rn = _norm(r)
        ratio = difflib.SequenceMatcher(None, n, rn).ratio()
        # boost when the last names align
        rln = _norm(r.split()[-1]) if r.split() else rn
        if ln and rln and difflib.SequenceMatcher(None, ln, rln).ratio() >= 0.8:
            ratio = max(ratio, 0.85)
        if ratio > best:
            best, best_r = ratio, r
    return best_r if best >= 0.72 and best_r else None


def _motion_before(segments: List[dict], i: int) -> str:
    """The motion a roll call resolves: the nearest lines before the trigger,
    preferring ones that read like a motion ('move to approve …')."""
    lo = max(0, i - 6)
    window = segments[lo:i]
    hinted = [s for s in window if _MOTION_HINT.search(str(s.get("text", "")))]
    picks = hinted[-2:] if hinted else window[-2:]
    text = " ".join(str(s.get("text", "")).strip() for s in picks)
    return re.sub(r"\s+", " ", text).strip()[:300]


def extract(segments: List[dict], roster: Optional[List[str]] = None,
            max_votes: int = 40) -> List[dict]:
    """Read the roll calls out of a transcript. Returns a list of votes:
    {t, motion, outcome, tally, roll:[{name, vote, t, quote}], origin}. Pure
    pattern-matching — no key, no network, officials-only by construction."""
    roster = roster or []
    gated = bool(roster)      # a roster present ⇒ names are checked against it
    votes: List[dict] = []
    n = len(segments)
    i = 0
    while i < n and len(votes) < max_votes:
        s = segments[i]
        text = str(s.get("text", ""))
        if not _TRIGGER.search(text):
            i += 1
            continue
        t0 = float(s.get("start", 0) or 0)
        # walk the window after the trigger, pairing names with vote tokens
        roll: List[dict] = []
        pending_name = None
        j = i + 1
        end = min(n, i + 26)
        outcome = ""
        while j < end:
            tj = str(segments[j].get("text", ""))
            # a fresh trigger closes this one
            if _TRIGGER.search(tj) and (j - i) > 2:
                break
            low = " " + tj.lower() + " "
            for w, tag in _OUTCOME:
                if w in low:
                    outcome = outcome or tag
            v = _vote_of(tj)
            nm = _looks_like_name(tj)
            if nm:
                # a segment carrying a name (even alongside a stray vote token,
                # e.g. the ASR's "I. John Vancoyak,") sets the next voter — the
                # token here is a prior member's echo; the next lone token pairs
                # to this name.
                pending_name = nm
            elif v is not None and pending_name is not None:
                # without a roster to verify against, only accept a full
                # (≥2-word) name — a lone first name in a roll call is too weak
                # to record as an official's vote
                if not gated and len(pending_name.split()) < 2:
                    pending_name = None
                    j += 1
                    continue
                canon = _canon_name(pending_name, roster)
                # officials only, BY CONSTRUCTION: without a roster to verify a
                # name against, we do not manufacture an official — a misheard
                # public-comment speaker inside a roll-call window must never
                # become a voting record. A body's roll calls appear once its
                # agenda roster is on the record (fetch the documents).
                if canon and gated:
                    roll.append({
                        "name": canon, "vote": v,
                        # store the raw start: the web deep-link floors with
                        # int(), and round(t,1) can cross a whole second
                        # (12.97 → 13.0) and mint a #t link with no anchor
                        "t": round(float(segments[j].get("start", 0) or 0), 3),
                        "quote": tj.strip()[:40]})
                pending_name = None
            j += 1
        # keep named roll calls (≥2 members named) — that is the ledger's value;
        # a voice vote with no names is already a 'decision' milestone elsewhere
        named = [r for r in roll if r["name"]]
        if len(named) < 2:
            i = j
            continue
        ayes = sum(1 for r in named if r["vote"] == "yes")
        nays = sum(1 for r in named if r["vote"] == "no")
        abst = sum(1 for r in named if r["vote"] == "abstain")
        tally = f"{ayes}–{nays}" + (f"–{abst}" if abst else "")
        if not outcome:
            outcome = "passes" if ayes > nays else ("fails" if nays > ayes
                                                    else "tied")
        votes.append({
            "t": round(t0, 3),   # 3dp: int()-floors to the transcript anchor
            "motion": _motion_before(segments, i),
            "outcome": outcome, "tally": tally,
            "roll": named, "origin": "extractive"})
        i = j
    return votes


# --------------------------------------------------------------------------
# roster from the town's own paper (memory/documents), then the pipeline hook
# --------------------------------------------------------------------------

# a person's name in an agenda header: First [M.] Last (optionally a middle
# initial or a two-word surname like "Van Scoyoc"). Matched non-overlapping so
# a flattened "John VanScoyoc Paul Warren Michael Rubenstein" run resolves to
# consecutive First-Last pairs rather than one blob.
_NAME_RUN = re.compile(
    r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-zA-Z'’-]+\b")
# words that mark a match as a role/venue/logistics line, not a person
_ROSTER_STOP = {
    "chair", "vice", "board", "committee", "town", "administrator", "clerk",
    "superintendent", "member", "members", "room", "hall", "hearing", "meeting",
    "register", "zoom", "watch", "golf", "course", "parkway", "hill", "click",
    "here", "call", "id", "street", "avenue", "floor", "office", "select",
    "school", "public", "regular", "special", "session", "agenda", "minutes",
    "recording", "webinar", "passcode", "join", "phone", "brookline", "boston",
    "chestnut", "roxbury", "ouimet", "greene chair", "present", "remote",
    "planning", "advisory", "zoning", "commission", "department", "notice"}


def _clean_names(text: str) -> List[str]:
    out = []
    for m in _NAME_RUN.finditer(text):
        nm = re.sub(r"\s+", " ", m.group(0)).strip()
        toks = [w.lower().strip(".") for w in nm.split()]
        if any(t in _ROSTER_STOP for t in toks):
            continue
        if len(nm) > 30 or len(nm) < 5:
            continue
        out.append(nm)
    return out


def roster_from_agenda(corpus, meeting_id: str) -> List[str]:
    """Harvest the board's member names from this meeting's agenda documents —
    the header block reads 'Bernard W. Greene – Chair, David Pearlman – Vice
    Chair, John VanScoyoc, Paul Warren, Michael Rubenstein, …'. The town naming
    its own board; officials only. Overcapture is harmless — the roster only
    gates and canonicalizes roll-call names."""
    names: List[str] = []
    seen = set()
    for d in corpus.list_documents(meeting_id=meeting_id, limit=20):
        if d.get("kind") != "Agenda":
            continue
        chunks = corpus.doc_chunks_of(d["id"])
        # the roster lives in the first page's header, before the logistics
        head = " ".join(c.get("text", "") for c in chunks[:2])[:400]
        for nm in _clean_names(head):
            k = _norm(nm)
            if k and k not in seen:
                seen.add(k)
                names.append(nm)
        if names:
            break
    return names


def body_roster(corpus, town: str, body: str) -> List[str]:
    """The union of every agenda roster for a (town, body) — so a meeting whose
    own agenda is thin still gates its roll call against the full board. A name
    is kept when it reads like a member on the town's own paper."""
    names: List[str] = []
    seen = set()
    for m in corpus.list_meetings(limit=2000):
        if m.get("status") != "live":
            continue
        if town and m.get("town") != town:
            continue
        if body and m.get("body") != body:
            continue
        for nm in roster_from_agenda(corpus, m["id"]):
            k = _norm(nm)
            if k not in seen:
                seen.add(k)
                names.append(nm)
    return names


def assign_meeting_votes(corpus, meeting_id: str,
                         roster: Optional[List[str]] = None) -> dict:
    """Extract and store a meeting's roll calls. Called after documents land
    (so the agenda roster can canonicalize names) — fail-open like issue
    assignment: a bad window never blocks the meeting."""
    m = corpus.get_meeting(meeting_id)
    if not m:
        return {"votes": 0}
    segs = corpus.transcript(meeting_id)
    if not segs:
        return {"votes": 0}
    if roster is None:
        # the whole board, learned from every one of its agendas — not just
        # this meeting's, so a thin agenda still gates against the full roster
        roster = body_roster(corpus, m.get("town", ""), m.get("body", "")) \
            or roster_from_agenda(corpus, meeting_id)
    votes = extract(segs, roster)
    corpus.replace_votes(meeting_id, votes)
    return {"votes": len(votes),
            "roll_entries": sum(len(v["roll"]) for v in votes),
            "roster": roster}


def member_records(corpus, town: str = "") -> List[dict]:
    """Per-member voting records across the record — every official's roll-call
    history, each cell a receipt (meeting + timestamp). Officials only: the
    names come only from roll calls. Returns
    [{name, yes, no, abstain, total, votes:[{meeting_id, date, motion, vote,
    t, outcome}]}] sorted by participation."""
    by_name: dict = {}
    for v in corpus.all_votes(town):
        for r in (v.get("roll") or []):
            nm = r.get("name") or ""
            if not nm:
                continue
            rec = by_name.setdefault(nm, {
                "name": nm, "yes": 0, "no": 0, "abstain": 0, "total": 0,
                "votes": []})
            vote = r.get("vote", "")
            if vote in ("yes", "no", "abstain"):
                rec[vote] += 1
            rec["total"] += 1
            rec["votes"].append({
                "meeting_id": v.get("meeting_id"), "date": v.get("date", ""),
                "title": v.get("title", ""), "body": v.get("body", ""),
                "town": v.get("town", ""),
                "motion": v.get("motion", ""), "vote": vote,
                "t": r.get("t"), "outcome": v.get("outcome", ""),
                "video_id": v.get("video_id", "")})
    out = sorted(by_name.values(), key=lambda r: -r["total"])
    return out
