"""What a town's channel is allowed to put in the record — and what it isn't.

A municipal YouTube channel is not a meeting feed. Brookline Interactive Group
posts Select Board meetings beside *TV on TV* and a retirement party; Boston
City TV carries the School Committee, the BPDA and the zoning board beside a
library dedication and a public-service announcement about staying cool indoors.
Point a nightly poll at either one and it will faithfully file all of it.

That matters for two reasons at once, and they push the same way. A steward's
review queue full of retirement parties is a queue nobody reads. And every
meeting that reaches ingest costs money — embeddings at minimum, ASR if it has
no captions — so a connector that files everything is a connector that spends
on everything.

So this module is **default-deny**. A video enters the queue only if its title
matches a rule that *names the public body it belongs to*. No rule, no entry.
That single decision does four jobs: it keeps the queue readable, it caps the
spend, it makes "which body is this?" a stated answer rather than a guess, and
it gives the reader the body filter it needs — because a meeting cannot arrive
without a body attached.

The cost of default-deny is that a genuinely new committee is invisible until
somebody writes a rule. That would be a bad trade if the misses were silent, so
they are not: an unmatched title is returned as a **suggestion**, and the
steward console shows them as one-click "add a rule for this". The taxonomy is
learned from what the town actually posts, rather than guessed in advance.

Everything here is a pure function over a title and a config. No network, no
database, no clock — so the steward console can preview exactly what a rule
change would do before it changes anything.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# A poll that files more than this in one night is either a backfill or a bug,
# and both want a human in the loop before they cost anything.
DEFAULT_MAX_PER_POLL = 12

# Titles are short and human; these keep the matching forgiving without making
# it vague. Everything is matched case-insensitively against the title alone.
_WS = re.compile(r"\s+")


def normalise(title: str) -> str:
    """Lowercased, whitespace-collapsed, punctuation-loosened. Municipal titles
    are wildly inconsistent about dashes and dates — *Select Board Meeting -
    July 14, 2026* and *Select Board Meeting – 7/14/26* are the same body."""
    t = (title or "").lower().replace("—", "-").replace("–", "-")
    return _WS.sub(" ", t).strip()


def _rx(pattern: str):
    try:
        return re.compile(pattern, re.I)
    except re.error:
        # A steward typed a bad pattern. Treat it as a literal rather than
        # failing the whole poll — and say so upstream.
        return re.compile(re.escape(pattern), re.I)


def bad_patterns(source: dict) -> List[str]:
    """Every pattern in a source that will not compile. The console shows these
    at edit time; a poll must never be the thing that discovers them."""
    bad = []
    for rule in source.get("bodies") or []:
        try:
            re.compile(rule.get("match", ""), re.I)
        except re.error as exc:
            bad.append(f"{rule.get('body', '?')}: {rule.get('match')!r} ({exc})")
    for pat in source.get("exclude") or []:
        try:
            re.compile(pat, re.I)
        except re.error as exc:
            bad.append(f"exclude: {pat!r} ({exc})")
    return bad


def classify(title: str, source: dict) -> Dict[str, Optional[str]]:
    """Which body does this video belong to — and if none, why not.

    Returns `{"body", "rule", "verdict", "reason"}` where `verdict` is one of:

      `file`      — a body rule matched; this is a meeting of that body
      `excluded`  — an exclude pattern matched; deliberately not a meeting
      `unmatched` — nothing matched. NOT an error: it is a rule that does not
                    exist yet, and it comes back as a suggestion.

    Exclusions are checked first, so a specific "not a meeting" always beats a
    loose body rule — `dedication` should lose to nothing."""
    t = normalise(title)
    for pat in source.get("exclude") or []:
        if _rx(pat).search(t):
            return {"body": None, "rule": pat, "verdict": "excluded",
                    "reason": f"excluded by {pat!r}"}
    # Ordered, first match wins: put the specific bodies above the general one,
    # or "City Council" will swallow "Committee on Planning".
    for rule in source.get("bodies") or []:
        pat = rule.get("match") or ""
        if pat and _rx(pat).search(t):
            return {"body": rule.get("body") or "", "rule": pat,
                    "verdict": "file",
                    "reason": f"matched {rule.get('body')!r} on {pat!r}"}
    return {"body": None, "rule": None, "verdict": "unmatched",
            "reason": "no rule names a body for this title"}


def plan(items: List[dict], source: dict) -> Dict[str, object]:
    """What a poll *would* do, without doing any of it.

    This is the whole preview surface: the steward console runs it against a
    live feed and shows three lists before a single row is written. Returns
    `{"file", "excluded", "unmatched", "capped", "over_cap"}`.

    `unmatched` is the interesting one. It is what the town posts that the
    record has no name for yet, and it is how the rules get written."""
    since = (source.get("since") or "").strip()
    cap = int(source.get("max_per_poll") or DEFAULT_MAX_PER_POLL)

    filed, excluded, unmatched, too_old = [], [], [], []
    for it in items:
        published = (it.get("published") or "")[:10]
        if since and published and published < since:
            too_old.append({**it, "reason": f"published before {since}"})
            continue
        verdict = classify(it.get("title", ""), source)
        row = {**it, **verdict}
        if verdict["verdict"] == "file":
            filed.append(row)
        elif verdict["verdict"] == "excluded":
            excluded.append(row)
        else:
            unmatched.append(row)

    # The cap is a spend ceiling, not a filter: what it drops is reported, so a
    # backfill reads as "23 waiting" rather than silently losing eleven.
    over = filed[cap:]
    return {"file": filed[:cap], "excluded": excluded, "unmatched": unmatched,
            "too_old": too_old, "capped": len(over), "over_cap": over,
            "cap": cap}


def suggest_rules(unmatched: List[dict], min_count: int = 2) -> List[dict]:
    """Turn the titles nothing matched into rules worth offering.

    Municipal titles are formulaic — *Ways and Means on July 15, 2026*, *Age
    Friendly Cities Ep 61 - Charles Carey*, *Boston Licensing Board Voting
    Hearing 7/16/2026* — and the stable part is always the head: the run of
    words before the episode number, the date, or the guest's name. A head seen
    `min_count` times is a body the town has and the record does not.

    Splitting on a separator regex was the obvious approach and it does not
    work: `\b-\b` cannot match a spaced hyphen, and "Ep 61" is not a date, so
    two titles of one series produced two different heads and neither
    suggested anything. Reading tokens left to right until one stops looking
    like part of a name is duller and correct."""
    # Where a title stops naming a body and starts naming an instance of one.
    STOP = {"ep", "episode", "pt", "part", "on", "with", "featuring", "feat",
            "live", "special", "no", "number", "vol", "session"}
    MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
              "sept", "oct", "nov", "dec", "january", "february", "march",
              "april", "june", "july", "august", "september", "october",
              "november", "december"}

    heads: Dict[str, List[str]] = {}
    for it in unmatched:
        words, head = normalise(it.get("title", "")).split(), []
        for w in words:
            bare = w.strip("-–—:,.·()")
            if not bare:
                break                       # a separator: the head ended
            if any(ch.isdigit() for ch in bare):
                break                       # an episode number or a date
            if bare in STOP or bare in MONTHS:
                break
            head.append(bare)
        text = " ".join(head).strip()
        if len(text) >= 4 and len(head) >= 2:
            heads.setdefault(text, []).append(it.get("title", ""))

    out = []
    for text, titles in sorted(heads.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(titles) >= min_count:
            out.append({"body": text.title(), "match": re.escape(text),
                        "seen": len(titles), "examples": titles[:3]})
    return out


def bodies_of(source: dict) -> List[str]:
    """Every body this source can produce — the reader's filter options, taken
    from configuration rather than from whatever happens to be in the corpus,
    so a body with no meetings yet still reads as a thing that exists."""
    return [r.get("body", "") for r in (source.get("bodies") or [])
            if r.get("body")]


# --------------------------------------------------------------------------
# the two towns the record serves today
# --------------------------------------------------------------------------
#
# These are seeds, not law: a steward edits them in the console and the console
# writes them back to `towns.sources`. They are here so a fresh database has a
# working, honest starting point rather than an empty one — and so the rules
# that took a live poll to discover are written down instead of remembered.

BROOKLINE = {
    "slug": "Brookline", "name": "Brookline", "state": "MA",
    "sources": [{
        "kind": "youtube",
        "url": "UCtl_u3j2UDQMXK-G6QD5g_w",
        "label": "Brookline Interactive Group",
        "enabled": True,
        "max_per_poll": 12,
        # Ordered: specific first. BIG's civic titles are consistently
        # "<Body> Meeting - <Month> <D>, <YYYY>".
        "bodies": [
            {"body": "Select Board", "match": r"select board"},
            {"body": "School Committee", "match": r"school committee"},
            {"body": "Transportation Board", "match": r"transportation board"},
            {"body": "Planning Board", "match": r"planning board"},
            {"body": "Zoning Board of Appeals", "match": r"zoning board|\bzba\b"},
            {"body": "Advisory Committee", "match": r"advisory committee"},
            {"body": "Town Meeting", "match": r"town meeting"},
        ],
        # What a live poll actually turned up beside the meetings, 2026-07-19.
        "exclude": [r"\btv on tv\b", r"celebration", r"farewell",
                    r"\bpsa\b", r"public service announcement"],
    }],
}

BOSTON = {
    "slug": "Boston", "name": "Boston", "state": "MA",
    "sources": [
        {
            # Boston City TV carries the committees, the planning agency and —
            # the reason it is here at all — the School Committee. It also
            # carries dedications and PSAs, which is why default-deny matters
            # more on this source than on any other.
            "kind": "youtube",
            "url": "UCImopNmmU11qfuWBbiXdowQ",
            "label": "Boston City TV",
            "enabled": True,
            "max_per_poll": 12,
            "bodies": [
                {"body": "School Committee",
                 "match": r"school committee|boston school"},
                {"body": "BPDA",
                 "match": r"\bbpda\b|planning (and|&) development|"
                          r"development review|article 80"},
                {"body": "Zoning Board of Appeal",
                 "match": r"zoning board|\bzba\b|zoning commission"},
                {"body": "Licensing Board", "match": r"licensing board"},
                {"body": "Landmarks Commission", "match": r"landmarks"},
                {"body": "City Council Committee",
                 "match": r"committee on |ways and means|public hearing"},
            ],
            # Every one of these came from a live poll on 2026-07-19, not from
            # imagination. City TV posts roughly five items a day and most are
            # not meetings; the language-prefixed PSAs ("(Spanish) Recycling in
            # the Club") are a whole family, so they are matched as a shape.
            "exclude": [r"dedication", r"stay cool", r"roundtable", r"promo",
                        r"announces", r"press conference", r"ribbon cutting",
                        r"^\([^)]+\)",                 # (Spanish) …, (Vietnamese) …
                        r"never leave", r"recycling in the club",
                        r"live stream", r"\bceremony\b"],
        },
        {
            # The Council's own channel publishes the council meetings proper,
            # and — unusually — carries human-authored English captions beside
            # the auto track, so its transcripts are the better ones.
            "kind": "youtube",
            "url": "UCvM_2-HUTqwKkcQvLVRcMJw",
            "label": "Boston City Council",
            "enabled": True,
            "max_per_poll": 12,
            # The Council does NOT say "Committee on" — it titles committee
            # sessions "<Committee Name> on <Month> <D>, <YYYY>". A live poll
            # found six committees this rule set missed while looking for the
            # literal word: City Services, Human Services, Planning
            # Development and Transportation, Housing and Community
            # Development, and "Ways & Means" (ampersand, where the June
            # sessions spell it "and"). So the committee rule matches the
            # SHAPE — a name followed by "on <date>" — and the council meeting
            # proper is matched first so it does not fall into it.
            "bodies": [
                {"body": "City Council", "match": r"city council meeting"},
                {"body": "City Council Committee",
                 "match": r"\bon\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|"
                          r"nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}"},
            ],
            "exclude": [r"live stream", r"\btest\b"],
        },
    ],
}

SEEDS = {"Brookline": BROOKLINE, "Boston": BOSTON}
