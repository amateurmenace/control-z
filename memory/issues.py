"""The issue engine — the telescope's optics.

Highlighter reads one meeting; this makes *civic time* legible: it finds the
topics that recur across meetings and years, names them, and tracks every
appearance so a resident can follow a thread and catch up on an arc in one
sitting.

How it decides what an issue *is* — and why it is built this way. The suite's
embedding is lexical (hashed n-grams, no model — the covenant made literal), and
civic meetings share a large baseline vocabulary, so partitioning segments by a
cosine threshold collapses everything into one "a public meeting" blob (measured,
not guessed). So issues are **anchored in distinctive vocabulary** instead: the
multi-word phrases that recur across meetings — *vision zero*, *short term
rentals*, *the golf course lighting* — are the anchors, phrases that co-occur are
merged into one issue, and each issue carries a **keyword set** (its aliases plus
the words most enriched in its own passages). That set is the visible, auditable
surface: a segment belongs to an issue because it *says* one of the issue's
words, not because an opaque vector said so. Assignment is keyword-first (high
precision, high recall when the aliases are good); a conservative cosine
fallback catches a near-miss, and everything else waits in a candidate queue for
a steward — the spec's design, exactly.

Generative only on top: labeling and the resurfacing delta go through
`czcore.llm` **when the user has a key**, and every one has an extractive
fallback that stands alone. No stance is ever inferred about a person — a hard
non-goal. Memory supplements the official record; it never replaces it.
"""

from __future__ import annotations

import collections
import json
import math
import re
from typing import Dict, List, Optional, Tuple

from czcore import llm

from . import embed

# ---- tuning (calibrated against the real Brookline corpus) ----------------
PASSAGE_WORDS = 45         # a window of consecutive cues ≈ a paragraph of signal
MIN_PASSAGE_WORDS = 8      # below this a window is too thin to carry a topic
ANCHOR_MIN_DF = 3          # a phrase must recur to anchor an issue
ANCHOR_MIN_SOLO = 5        # …unless it is very frequent inside a single meeting
ANCHOR_MIN_PMI = 2.3       # …and be a *sticky* phrase, not two common words next
                           # to each other: 'vision zero' sticks, 'important work'
                           # doesn't. This is the filter that keeps the record
                           # about subjects, not sentence fragments.
MERGE_JACCARD = 0.35       # anchors sharing this many passages are one issue
ENRICH_MIN = 5.0           # a unigram this over-represented joins the keyword set…
ENRICH_MAX_DF = 0.18       # …but not if it is common across the whole record
ENRICH_CAP = 6
MIN_ISSUE_SEGMENTS = 4     # an auto issue thinner than this isn't worth a card
COS_ASSIGN = 0.82          # the cosine last-resort bar. Membership is really
                           # keyword-based (precise, auditable); the lexical space
                           # is too uniform for a loose cosine to mean much, so
                           # this sits high and an unmatched segment usually waits
                           # in the candidate queue instead — the spec's design.
ALIAS_CAP = 10

# Function words + the civic discourse filler that carries no topical signal.
# Phrases and enriched unigrams are drawn only from the words that survive this.
FILLER = set("""
a an the and or but of to in on for is are was were be been being it this that these those i you
he she we they so as at by with from up out if then than there here just have has had do does did
not no yes aye nay abstain okay um uh going know think right well kind sort like very much really
actually basically obviously mean also because would could should maybe about how what when where
who whom which while into onto over under again still even more most some any our your their my his
will shall can cannot may might must would could should ought going gonna wanna gotta
her its me us them thing things way ways time times people person go get got make made see look come
came said say says talk talking tell ask asked want need let put thank thanks please sorry happy
great good little bit lot number one two three four five first second third next last another other
others many few every each all both same such only own year years today tonight now here's there's
it's that's we're they're i'm you're don't didn't can't won't we've i've he's she's mr ms mrs dr
chair member members question questions answer point sense idea yeah welcome evening morning able
around back through take taking given give across without within upon whether being does doing done
""".split())

# meeting mechanics — real phrases, but not *issues*. Kept out of anchors so the
# record isn't full of "seeing none" and "will now move".
PROCEDURAL = {
    "anyone else", "seeing none", "will now", "now move", "will now move",
    "move forward", "favorable action", "recommend favorable action", "any other",
    "roll call", "all favor", "all opposed", "so moved", "second the motion",
    "call the question", "clears throat", "point of order", "any objection",
    "without objection", "take a vote", "the motion", "motion passes",
    "motion carries", "any questions", "next item", "next agenda", "agenda item",
    "public comment", "thank you", "good evening", "call to order", "blah blah",
    "weeks ago", "check ins", "omnibus fashion", "combined reports",
    "general orders", "track progress", "high priority", "make sure", "you know",
}

# Common first names — the cheap, honest heuristic that keeps *people* from
# becoming *issues*: a phrase that starts with one ("Rob Shown", "Andy Fischer")
# is almost always a name, and the record aggregates topics, never individuals
# (a hard non-goal). Imperfect and English-leaning by construction; stewards see
# the rest. Names still appear *inside* a meeting — this only stops name-shaped
# anchors from opening an issue.
FIRST_NAMES = set("""
james john robert michael william david richard joseph thomas charles chris christopher daniel
matthew anthony donald mark paul steven andrew ken kenneth george josh joshua kevin brian edward
ron ronald tim timothy jason jeff jeffrey ryan gary jacob nick nicholas eric jonathan stephen
larry lars justin scott brandon frank ben benjamin greg gregory sam samuel raymond patrick jack
dennis jerry tyler aaron rob jose adam henry nathan doug douglas peter zachary kyle walter ethan
jeremy harold carl keith roger gerald terry sean austin arthur noah lawrence jesse joe bryan billy
bruce mary patricia jennifer linda elizabeth barbara susan jessica sarah karen nancy lisa betty
margaret sandra ashley kimberly emily donna michelle carol amanda dorothy melissa deborah debbie
stephanie rebecca sharon laura cynthia kathleen amy angela shirley anna brenda pamela emma nicole
helen samantha katherine christine debra rachel carolyn janet catherine maria heather diane ruth
julie joyce virginia victoria kelly lauren christina joan evelyn judith megan andrea cheryl hannah
jacqueline martha gloria teresa ann sara madison frances kathryn janice jean abigail alice bernard
mike tom bob jim matt dan dave will ed tony pete rick steve nick andy joe jerry ron ken greg doug
jeff gary larry ben sam chris fred phil ray dick hank stan al ted jack dan danny johnny mikey
kate katie liz beth sue jen jenny cathy patty peggy becky terri debbie sandy angie chris pam
""".split())

_WORD = re.compile(r"[a-z0-9']+")


# ---- text helpers ---------------------------------------------------------

def content_words(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower())
            if w not in FILLER and len(w) > 2 and not w.isdigit()]


def phrases(text: str) -> List[str]:
    """Bi- and tri-grams whose every token carries signal (no filler edges, no
    all-stopword grams) — the raw anchor candidates."""
    ws = _WORD.findall((text or "").lower())
    out: List[str] = []
    for n in (2, 3):
        for i in range(len(ws) - n + 1):
            g = ws[i:i + n]
            if any(w in FILLER for w in g):
                continue
            if any(len(w) < 3 or w.isdigit() for w in g):
                continue
            p = " ".join(g)
            if p not in PROCEDURAL:
                out.append(p)
    return out


def _passages(segs: List[dict]) -> List[dict]:
    """Group a meeting's consecutive cues into ~paragraph windows. Each keeps the
    segment ids it spans (so an issue can point back at the exact seconds) and a
    vector over the whole window (short cues alone are too sparse to cluster)."""
    by_m: Dict[str, List[dict]] = collections.defaultdict(list)
    for s in segs:
        by_m[s["meeting_id"]].append(s)
    out: List[dict] = []
    for mid, ms in by_m.items():
        ms = sorted(ms, key=lambda s: s.get("idx", 0))
        i = 0
        while i < len(ms):
            buf, ids, wc = [], [], 0
            j = i
            while j < len(ms) and wc < PASSAGE_WORDS:
                buf.append(ms[j]["text"])
                ids.append(ms[j]["id"])
                wc += len(content_words(ms[j]["text"]))
                j += 1
            text = " ".join(buf)
            if len(content_words(text)) >= MIN_PASSAGE_WORDS:
                out.append({"mid": mid, "date": ms[i].get("date", ""),
                            "text": text, "seg_ids": ids,
                            "vec": embed.embed(text)})
            i = j
    return out


# ---- discovery: passages → anchors → issues -------------------------------

def _anchors(passages: List[dict]) -> Tuple[List[str], dict, dict]:
    """Distinctive recurring *collocations*, ranked by idf-weighted frequency,
    with the passage set and meeting set each covers. A phrase must recur (df),
    span meetings or be locally frequent, and — the load-bearing test — be a
    sticky phrase by PMI, so the record fills with 'vision zero' and 'short term
    rentals', not 'important work' and 'pretty clear'."""
    df: collections.Counter = collections.Counter()
    uni: collections.Counter = collections.Counter()   # passage-frequency of words
    pset: Dict[str, set] = collections.defaultdict(set)
    mset: Dict[str, set] = collections.defaultdict(set)
    for pi, p in enumerate(passages):
        seen = set()
        for ph in phrases(p["text"]):
            if ph not in seen:
                df[ph] += 1
                seen.add(ph)
            pset[ph].add(pi)
            mset[ph].add(p["mid"])
        for w in set(content_words(p["text"])):
            uni[w] += 1
    n = max(1, len(passages))

    def sticky(ph: str) -> bool:
        toks = ph.split()
        denom = 1.0
        for w in toks:
            denom *= (uni.get(w, 1) or 1) / n
        if denom <= 0:
            return True
        pmi = math.log((df[ph] / n) / denom)     # >0: co-occur more than chance
        return (pmi / max(1, len(toks) - 1)) >= ANCHOR_MIN_PMI

    def name_shaped(ph: str) -> bool:
        toks = ph.split()
        return toks[0] in FIRST_NAMES or (len(toks) >= 2 and toks[1] in FIRST_NAMES)

    anchors = [ph for ph in df
               if df[ph] >= ANCHOR_MIN_DF
               and (len(mset[ph]) >= 2 or df[ph] >= ANCHOR_MIN_SOLO)
               and sticky(ph)
               and not name_shaped(ph)]
    anchors.sort(key=lambda ph: -(df[ph] * math.log(n / (1 + df[ph]))))
    return anchors, pset, mset


def _group_anchors(anchors: List[str], pset: dict) -> List[List[str]]:
    """Union-find: two anchors are one issue if they blanket the same passages
    (Jaccard) or one names the other ('design review' ⊂ 'design review
    committee'). Token overlap alone never merges — 'climate action' and
    'favorable action' share a word but not a subject."""
    parent = {a: a for a in anchors}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for i, a in enumerate(anchors):
        for b in anchors[i + 1:]:
            if a in b or b in a:
                union(a, b)
                continue
            inter = len(pset[a] & pset[b])
            if not inter:
                continue
            uni = len(pset[a] | pset[b])
            if uni and inter / uni >= MERGE_JACCARD:
                union(a, b)
    groups: Dict[str, List[str]] = collections.defaultdict(list)
    for a in anchors:
        groups[find(a)].append(a)
    # widest-covering issues first
    return sorted(groups.values(),
                  key=lambda g: -len(set().union(*[pset[x] for x in g])))


def _enriched_unigrams(member_pi: set, passages: List[dict],
                       corpus_df: collections.Counter) -> List[str]:
    """Single words over-represented in an issue's own passages versus the whole
    record — the vocabulary that widens recall past the exact anchor phrase
    ('fatalities', 'crosswalk' for Vision Zero). Auditable, not opaque."""
    n = max(1, len(passages))
    grp: collections.Counter = collections.Counter()
    for pi in member_pi:
        for w in set(content_words(passages[pi]["text"])):
            grp[w] += 1
    scored = []
    for w, gc in grp.items():
        if gc < 2 or len(w) < 4:
            continue
        if corpus_df[w] / n > ENRICH_MAX_DF:      # a record-wide common word adds
            continue                              # noise, not recall — skip it
        enrich = (gc / len(member_pi)) / ((corpus_df[w] + 1) / n)
        if enrich >= ENRICH_MIN:
            scored.append((w, enrich))
    scored.sort(key=lambda x: -x[1])
    return [w for w, _ in scored[:ENRICH_CAP]]


# civic acronyms that should read as themselves, not Title Case
ACRONYMS = set("""mbta adu zba dpw mwra mapc epa hud ada dph dcr peg hoa tif rfp rfq
cpc cpa zba dcamm masshousing evse ev pilot tnd tdm mbta's dei ari recck""".split())


def _title(phrase: str) -> str:
    """A readable canonical name from an anchor phrase — title-case, but keep the
    civic acronyms upper (MBTA, ZBA, ADU) rather than 'Mbta'."""
    words = []
    for w in phrase.split():
        if w in ACRONYMS or (len(w) <= 4 and w.isalpha()
                             and not any(v in w for v in "aeiou")):
            words.append(w.upper())
        else:
            words.append(w[:1].upper() + w[1:])
    return " ".join(words)


def _rank_aliases(group: List[str], mset: dict, df: collections.Counter) -> List[str]:
    return sorted(group, key=lambda ph: -(len(mset[ph]) * 1000 + df[ph]))


_LABEL_SYS = (
    "You name a civic issue that recurs across public meetings. Given a few "
    "recurring phrases and short transcript excerpts, return the single "
    "canonical name a resident would use (2 to 6 words) and a short list of "
    "aliases (other names or phrases for the SAME topic). Name the topic only. "
    "Never characterize anyone's position or stance — that is forbidden. "
    'Reply as JSON: {"name": "...", "aliases": ["...", "..."]}.'
)


def _llm_label(anchors: List[str], samples: List[str]) -> Optional[Tuple[str, list]]:
    if not llm.enabled():
        return None
    body = ("Recurring phrases: " + ", ".join(anchors[:10]) + "\n\n"
            "Excerpts:\n" + "\n".join("- " + s[:240] for s in samples[:3]) +
            "\n\nName this issue.")
    try:
        raw = llm.complete(body, system=_LABEL_SYS, max_tokens=200)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)
        name = str(data.get("name", "")).strip()
        aliases = [str(a).strip() for a in (data.get("aliases") or []) if str(a).strip()]
        if name:
            return name, aliases
    except Exception:
        return None
    return None


def label_group(group: List[str], member_pi: set, passages: List[dict],
                mset: dict, df: collections.Counter,
                corpus_df: collections.Counter) -> dict:
    """Name an issue and build its keyword set. Generative name when a key is set
    (origin ai:<model>), extractive otherwise — the fallback stands alone, and
    the recall vocabulary (anchors + enriched words) is kept either way."""
    ranked = _rank_aliases(group, mset, df)
    enriched = _enriched_unigrams(member_pi, passages, corpus_df)
    samples = sorted((passages[pi]["text"] for pi in member_pi),
                     key=len, reverse=True)[:3]
    llm_out = _llm_label(ranked, samples)
    if llm_out:
        name, ai_aliases = llm_out
        origin = "ai:" + llm.status().get("model", "a model")
        aliases = _dedupe([*ai_aliases, *ranked])[:ALIAS_CAP]
    else:
        name = _title(ranked[0])
        origin = "extractive"
        aliases = _dedupe(ranked)[:ALIAS_CAP]
    # what a segment must *say* to belong: the canonical name and its aliases,
    # which are all multi-word collocations — precise and auditable. The enriched
    # single words are the issue's vocabulary for display and "why this issue",
    # never a match key (one common word like 'vote' would swallow the corpus).
    keywords = _dedupe([name.lower()] + [a.lower() for a in aliases])
    return {"name": name, "name_origin": origin, "aliases": aliases,
            "keywords": keywords, "related": enriched}


def _dedupe(items) -> list:
    seen, out = set(), []
    for x in items:
        k = str(x).strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _slug(town: str, name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:48]
    t = re.sub(r"[^a-z0-9]+", "-", (town or "").lower()).strip("-")
    return f"issue:{t}:{s}" if t else f"issue:{s}"


# ---- assignment: a segment belongs to an issue that it *says* -------------

def _matchers(keywords: List[str]):
    return [re.compile(r"\b" + re.escape(k) + r"\b") for k in keywords if k]


def _assign(corpus, segs: List[dict], issues: List[dict]) -> Dict[str, int]:
    """Attach each segment to every issue whose vocabulary it uses (word-boundary
    match), plus its single nearest issue by cosine when that clears COS_ASSIGN.
    Returns {issue_id: n_segments_linked}. Resurfacing detection lives in the
    caller, run *after* these links land so a delta can see the new beads."""
    if not issues:
        return {}
    pats = {iss["id"]: _matchers(iss.get("keywords") or []) for iss in issues}
    have_cos = embed.np is not None and any(iss.get("centroid") is not None
                                            for iss in issues)
    cen_ids, cen_mat = [], None
    if have_cos:
        for iss in issues:
            if iss.get("centroid") is not None:
                cen_ids.append(iss["id"])
        cen_mat = embed.np.vstack([
            iss["centroid"] for iss in issues if iss.get("centroid") is not None])

    links: Dict[str, List[tuple]] = collections.defaultdict(list)
    counts: Dict[str, int] = collections.Counter()

    for s in segs:
        text = (s.get("text") or "").lower()
        mid = s["meeting_id"]
        hit_here = set()
        for iss in issues:
            for pat in pats[iss["id"]]:
                if pat.search(text):
                    links[iss["id"]].append((s["id"], mid, 1.0, "alias"))
                    hit_here.add(iss["id"])
                    counts[iss["id"]] += 1
                    break
        # cosine fallback: the nearest issue, only if the segment matched none of
        # them by word and the similarity is genuinely high
        if not hit_here and cen_mat is not None:
            v = embed.from_bytes(s.get("emb"))
            if v is not None:
                sims = cen_mat @ v
                b = int(sims.argmax())
                if float(sims[b]) >= COS_ASSIGN:
                    iid = cen_ids[b]
                    links[iid].append((s["id"], mid, float(sims[b]), "related"))
                    counts[iid] += 1

    for iid, ls in links.items():
        corpus.link_segments(iid, ls)
    return dict(counts)


# ---- the public engine ----------------------------------------------------

def discover(corpus, town: str = "", job=None) -> dict:
    """Rebuild a town's issues from scratch (the backfill job). Machine-made,
    unfollowed issues are recomputed; minted, steward-edited, and followed issues
    are kept and re-assigned. Returns a JSON-safe summary."""
    def say(msg, prog=None):
        if job is not None:
            job.message = msg
            if prog is not None:
                job.progress = prog

    say("gathering the record…", -1)
    segs = corpus.live_segments(town)
    if not segs:
        return {"town": town, "issues": 0, "note": "no live meetings yet"}
    passages = _passages(segs)
    say(f"reading {len(passages)} passages for recurring topics…", 0.2)
    anchors, pset, mset = _anchors(passages)
    df = collections.Counter({a: len(pset[a]) for a in anchors})
    corpus_df: collections.Counter = collections.Counter()
    for p in passages:
        for w in set(content_words(p["text"])):
            corpus_df[w] += 1
    groups = _group_anchors(anchors, pset)

    if job is not None:
        job.check_cancel()
    corpus.clear_auto_issues(town)          # keep followed/minted; drop the rest
    say(f"naming {len(groups)} candidate issues…", 0.4)

    created = []
    for g in groups:
        member_pi = set().union(*[pset[x] for x in g])
        lab = label_group(g, member_pi, passages, mset, df, corpus_df)
        iid = _slug(town, lab["name"])
        cen = _passage_centroid(member_pi, passages)
        corpus.upsert_issue({"id": iid, "town": town, "status": "active",
                             "origin": "auto", "centroid": cen, **lab})
        created.append(iid)
        if job is not None:
            job.check_cancel()

    # re-assign the whole town against every active/candidate issue (auto +
    # preserved), from a clean slate, then let thin auto issues fall away.
    issues = corpus.issue_keywords(active_only=True)
    for iss in issues:
        corpus.clear_issue_links(iss["id"])
    say("assigning segments to issues…", 0.7)
    counts = _assign(corpus, segs, issues)
    kept = 0
    for iss in issues:
        n = counts.get(iss["id"], 0)
        full = corpus.get_issue(iss["id"])
        followed = full and full.get("following")
        if iss["origin"] == "auto" and not followed and n < MIN_ISSUE_SEGMENTS:
            corpus.delete_issue(iss["id"])
            continue
        corpus.recompute_centroid(iss["id"])
        kept += 1

    say(f"the long view holds {kept} issues", 1.0)
    return {"town": town or "all", "passages": len(passages),
            "issues": kept, "assigned": sum(counts.values())}


def _passage_centroid(member_pi: set, passages: List[dict]):
    if embed.np is None or not member_pi:
        return None
    mat = embed.np.vstack([passages[pi]["vec"] for pi in member_pi])
    c = embed.np.mean(mat, axis=0)
    n = float(embed.np.linalg.norm(c))
    return (c / n) if n else c


def assign_meeting(corpus, meeting_id: str, emit_events: bool = True) -> dict:
    """Incremental assignment for one freshly-live meeting: match its segments to
    the issues that already exist, note a resurfacing for any followed issue that
    just reappeared, and queue what matched nothing for a steward. Cheap — it is
    a pipeline stage, run on every ingest."""
    m = corpus.get_meeting(meeting_id)
    if not m:
        return {"meeting_id": meeting_id, "assigned": 0}
    town = m.get("town", "")
    segs = corpus.segments_of(meeting_id)
    if not segs:
        return {"meeting_id": meeting_id, "assigned": 0}
    corpus.clear_meeting_links(meeting_id)
    issues = [i for i in corpus.issue_keywords(active_only=True)
              if not i["town"] or not town or i["town"] == town]

    counts = _assign(corpus, segs, issues)
    for iid in counts:
        corpus.recompute_centroid(iid)

    # resurfacings — computed *after* the links land, so each delta can quote the
    # new meeting's own beads. A followed issue this meeting reopened, newer than
    # the follower has seen, wakes a thread with a "what changed" paragraph.
    resurfaced: List[dict] = []
    mdate = m.get("date", "") or ""
    if emit_events:
        for iid in counts:
            full = corpus.get_issue(iid)
            if not full or not full.get("following"):
                continue
            th = corpus.get_thread(iid)
            seen = (th or {}).get("last_seen_date", "") or ""
            if mdate and seen and mdate <= seen:
                continue                 # nothing newer than the follower has seen
            d = delta(corpus, full, meeting_id)
            corpus.add_event("resurfacing", issue_id=iid, meeting_id=meeting_id,
                             thread_id=(th or {}).get("id", ""),
                             payload={"delta": d, "title": m.get("title", ""),
                                      "date": mdate, "body": m.get("body", "")})
            if mdate:
                corpus.advance_thread(iid, mdate)
            resurfaced.append({"issue_id": iid, "name": full["name"], "delta": d})

    # candidate queue: substantive segments this meeting that matched no issue,
    # grouped by any phrase they repeat — the steward's "is this a new issue?" list
    _queue_candidates(corpus, meeting_id, town, segs, counts)

    return {"meeting_id": meeting_id, "assigned": sum(counts.values()),
            "issues_touched": len(counts), "resurfaced": resurfaced}


def reassign_issue(corpus, issue_id: str) -> int:
    """Re-match one issue against the whole record — run after a steward changes
    its aliases (rename/merge/promote) so its membership tracks its new words."""
    iss = corpus.get_issue(issue_id)
    if not iss:
        return 0
    corpus.clear_issue_links(issue_id)
    segs = corpus.live_segments(iss.get("town", ""))
    counts = _assign(corpus, segs,
                     [{"id": issue_id, "keywords": iss.get("keywords") or [],
                       "centroid": None}])
    corpus.recompute_centroid(issue_id)
    return counts.get(issue_id, 0)


def split_off_meeting(corpus, issue_id: str, meeting_id: str,
                      name: str = "") -> Optional[dict]:
    """Steward split: lift one meeting's segments out of an issue into a new
    issue of their own (the clusterer wrongly merged them). The original keeps
    the rest; the record shows the correction rather than hiding it."""
    src = corpus.get_issue(issue_id)
    if not src:
        return None
    beads = _issue_beads(corpus, issue_id, meeting_id)
    if not beads:
        return None
    m = corpus.get_meeting(meeting_id) or {}
    name = name or (src["name"] + " — " + (m.get("date") or meeting_id))
    new_id = _slug(src.get("town", ""), name) + ":split"
    corpus.upsert_issue({
        "id": new_id, "town": src.get("town", ""), "status": "active",
        "origin": "steward", "name": name, "name_origin": "steward",
        "aliases": src.get("aliases") or [], "keywords": src.get("keywords") or [],
        "note": f"split from {src['name']}"})
    corpus.link_segments(new_id, [(b["seg_id"], meeting_id, b.get("score", 0.5),
                                   b.get("why", "steward")) for b in beads])
    with corpus._con() as con:
        con.execute("DELETE FROM issue_segments WHERE issue_id=? AND meeting_id=?",
                    (issue_id, meeting_id))
        con.commit()
    corpus.recompute_centroid(new_id)
    corpus.recompute_centroid(issue_id)
    return corpus.get_issue(new_id)


def _queue_candidates(corpus, meeting_id: str, town: str, segs: List[dict],
                      counts: dict) -> None:
    assigned_segs = set()
    with corpus._con() as con:
        for r in con.execute(
                "SELECT seg_id FROM issue_segments WHERE meeting_id=?",
                (meeting_id,)):
            assigned_segs.add(r["seg_id"])
    left = [s for s in segs if s["id"] not in assigned_segs]
    if len(left) < 6:
        return
    passages = _passages(left)
    if not passages:
        return
    anchors, pset, mset = _anchors(passages)
    for g in _group_anchors(anchors, pset)[:6]:
        member_pi = set().union(*[pset[x] for x in g])
        if len(member_pi) < 2:
            continue
        seg_ids = set()
        for pi in member_pi:
            seg_ids.update(passages[pi]["seg_ids"])
        name = _title(_rank_aliases(g, mset, collections.Counter(
            {a: len(pset[a]) for a in g}))[0])
        iid = _slug(town, name) + ":cand"
        corpus.upsert_issue({
            "id": iid, "town": town, "status": "candidate", "origin": "auto",
            "name": name, "name_origin": "extractive",
            "aliases": list(g)[:ALIAS_CAP],
            "keywords": _dedupe([a.lower() for a in g] + [name.lower()]),
            "note": "candidate — a steward can promote, rename, or discard"})
        corpus.link_segments(iid, [(sid, meeting_id, 0.5, "candidate")
                                   for sid in seg_ids])
        corpus.recompute_centroid(iid)


# ---- resurfacing delta: "what changed since last time" --------------------

_DELTA_SYS = (
    "You write one short paragraph for a resident following a civic issue, "
    "summarizing what a new meeting added to it versus its earlier appearances. "
    "Be concrete and neutral; use the [MM:SS] timestamps so a reader can check "
    "you. Never invent a vote or a position, and never characterize anyone's "
    "stance. This supplements the official record; it does not replace it."
)


def delta(corpus, issue: dict, meeting_id: str) -> str:
    """A one-paragraph 'what changed since last time' for a resurfacing.
    Generative with a key, extractive otherwise — the fallback names the meeting,
    the arc so far, and quotes the new segments verbatim."""
    m = corpus.get_meeting(meeting_id) or {}
    beads = _issue_beads(corpus, issue["id"], meeting_id)
    prior = [n for n in corpus.issue_appearances(issue["id"])
             if n["meeting_id"] != meeting_id]
    where = " · ".join(x for x in (m.get("body"), m.get("date")) if x)
    if llm.enabled():
        try:
            lines = [f"[{_ms(b['t'])}] {(b.get('speaker') + ': ') if b.get('speaker') else ''}"
                     f"{b['text']}" for b in beads[:30]]
            body = (f"Issue: {issue['name']}\n"
                    f"Earlier appearances: {len(prior)} "
                    f"meeting(s) since {issue.get('first_seen') or 'the start'}.\n"
                    f"New meeting: {m.get('title','')} ({where}).\n\n"
                    "New passages:\n" + "\n".join(lines) +
                    "\n\nWrite the 'what changed' paragraph.")
            txt = llm.complete(body, system=_DELTA_SYS, max_tokens=300)
            if txt.strip():
                return txt.strip()
        except Exception:
            pass
    # extractive fallback
    head = (f"“{issue['name']}” returned"
            + (f" at {m.get('title','')}" if m.get("title") else "")
            + (f" ({where})" if where else "") + ". ")
    arc = (f"That is {len(prior) + 1} appearance"
           f"{'s' if len(prior) else ''} on the record"
           + (f" since {issue.get('first_seen')}" if issue.get("first_seen") else "")
           + ". ")
    quotes = " ".join(f"[{_ms(b['t'])}] {b['text']}" for b in beads[:3])
    return (head + arc + ("This time: " + quotes if quotes else "")).strip()


def _issue_beads(corpus, issue_id: str, meeting_id: str) -> List[dict]:
    for node in corpus.issue_appearances(issue_id):
        if node["meeting_id"] == meeting_id:
            return node["beads"]
    return []


def _ms(t: float) -> str:
    t = max(0, int(t or 0))
    return f"{t // 60:02d}:{t % 60:02d}"


# ---- the "still watching" digest (local covenant for the spec's email) ----

def digest(corpus) -> dict:
    """A plain, exportable roundup of every followed thread — the local stand-in
    for the spec's resurfacing email (no accounts, no network, nothing sent). New
    activity first, then the quiet threads so a follower knows they're still held."""
    threads = corpus.list_threads()
    all_events = corpus.list_events(limit=200)   # newest first — fetch once
    active, quiet = [], []
    for t in threads:
        latest = next((e for e in all_events
                       if e["issue_id"] == t["issue_id"]), None)
        row = {"issue_id": t["issue_id"], "name": t["name"],
               "n_meetings": t["n_meetings"], "unseen": t["unseen"],
               "last_seen": t["last_seen"],
               "delta": (latest["payload"].get("delta") if latest else "")}
        (active if t["unseen"] else quiet).append(row)
    lines = ["# Still watching — Community Memory", ""]
    if active:
        lines.append("## New since you last looked")
        for r in active:
            lines.append(f"\n### {r['name']}  ({r['unseen']} new)")
            if r["delta"]:
                lines.append(r["delta"])
    if quiet:
        lines.append("\n## Quiet for now")
        for r in quiet:
            lines.append(f"- **{r['name']}** — {r['n_meetings']} appearance(s), "
                         f"last on {r['last_seen'] or 'an undated meeting'}. "
                         "Still watching.")
    if not threads:
        lines.append("_No threads followed yet. Follow an issue to start a "
                     "thread._")
    return {"markdown": "\n".join(lines), "threads": len(threads),
            "active": len(active), "quiet": len(quiet)}


# ---- mint a thread from a search result -----------------------------------

def mint_from_query(corpus, query: str, town: str = "") -> Optional[dict]:
    """A user starts following straight from a search: attach to the nearest
    existing issue if the query clearly lands on one, else create a minted issue
    seeded from the query's own words and the moments it already finds."""
    query = (query or "").strip()
    if not query:
        return None
    qvec = embed.embed(query)
    best, best_sim = None, 0.0
    if qvec is not None:
        for iss in corpus.issue_keywords(active_only=True):
            if iss.get("centroid") is None:
                continue
            if town and iss["town"] and iss["town"] != town:
                continue
            sim = float(iss["centroid"] @ qvec)
            # a query that already uses the issue's words is a strong match
            if any(re.search(r"\b" + re.escape(k) + r"\b", query.lower())
                   for k in iss["keywords"]):
                sim += 0.3
            if sim > best_sim:
                best, best_sim = iss, sim
    if best and best_sim >= 0.6:
        corpus.follow(best["id"])
        return {"issue_id": best["id"], "name": best["name"], "attached": True}

    # else mint a fresh issue from the query
    name = query[:60]
    iid = _slug(town, name) + ":minted"
    kws = _dedupe([query.lower()] + content_words(query))
    corpus.upsert_issue({"id": iid, "town": town, "status": "active",
                         "origin": "minted", "name": name,
                         "name_origin": "extractive", "aliases": [query],
                         "keywords": kws, "centroid": qvec,
                         "note": "minted from a search"})
    # seed it with the moments the query already finds
    hits = corpus.search(query, limit=60)
    links = [(h["seg_id"], h["meeting_id"], h.get("score", 0.5), "minted")
             for h in hits if h.get("seg_id")]
    if links:
        corpus.link_segments(iid, links)
        corpus.recompute_centroid(iid)
    corpus.follow(iid)
    return {"issue_id": iid, "name": name, "attached": False,
            "seeded": len(links)}
