"""Press an edition — read everything Memory knows, write a static site.

    python -m web.bake --corpus <corpus.db> --out site/docs/app

Pure stdlib + the suite's own corpus reader. Idempotent: the same corpus
presses a byte-identical edition (no wall-clock stamps — every date is derived
from the corpus itself), and manifest.corpus_hash proves it. JSON is written
plain; GitHub Pages/Fastly gzips text on the wire, so the reader is a plain
fetch and the budget report measures the gzipped size that actually ships.

specs/16 §P0.1 is the contract; §8 the budgets.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from web import SCHEMA_VERSION, canon, emit, tools

# the seven panel languages (czcore/mt.py) — code -> display name
LANG_NAMES = {
    "es": "Español", "simple": "Simple English", "zh": "中文",
    "pt": "Português", "ht": "Kreyòl Ayisyen", "vi": "Tiếng Việt",
    "ru": "Русский",
}
_TOKEN = re.compile(r"[a-z0-9]+")
_WORD = re.compile(r"\w+")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def pid(mid: str) -> str:
    """A filename/URL-safe id ('file:ab…' and 'url:…' carry ':')."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", mid)[:80]


def islug(iid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", iid)[:96]


def _thumb(m: dict) -> str:
    v = m.get("video_id") or ""
    return f"https://i.ytimg.com/vi/{v}/hqdefault.jpg" if v else ""


def _minutes(sec) -> int:
    return int(round((sec or 0) / 60))


def _month(date: str) -> str:
    return (date or "")[:7]     # YYYY-MM, '' when undated


def _write(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text if isinstance(text, str) else json.dumps(text)
    path.write_text(data, encoding="utf-8")
    return len(data.encode("utf-8"))


def _dumps(obj) -> str:
    # sort_keys + compact separators + non-ASCII: the exact bytes an edition
    # ships (deterministic for idempotence; the budget report measures these,
    # not json's spaced ensure_ascii=True default).
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _json(path: Path, obj) -> int:
    return _write(path, _dumps(obj))


def _gz_size(text: str) -> int:
    return len(gzip.compress(text.encode("utf-8"), mtime=0))


def _gz_of(obj) -> int:
    return _gz_size(_dumps(obj))


# --------------------------------------------------------------------------
# sidecar discovery — translation + AD tracks written beside a meeting
# --------------------------------------------------------------------------

def _sidecar_dirs(m: dict, media) -> list:
    """Where Interpreter/Narrator would have written tracks for this meeting:
    the Highlighter session dir (by video id, then by corpus id) and, for a
    local-file meeting, beside the media file."""
    out = []
    for tool in ("highlighter", "memory"):
        base = media(tool) / ".meetings"
        for key in (m.get("video_id"), m["id"], pid(m["id"])):
            if key:
                d = base / re.sub(r"[^\w.-]", "_", str(key))[:64]
                if d.is_dir():
                    out.append(("meeting", d))
    mp = m.get("media_path") or ""
    if mp and Path(mp).exists():
        out.append((Path(mp).stem, Path(mp).parent))
    return out


def _find_tracks(m: dict, media) -> dict:
    """{lang_code: vtt_path} for translation tracks, plus 'ad' -> described.vtt
    path when present. First dir that has them wins."""
    found = {}
    ad = None
    for stem, d in _sidecar_dirs(m, media):
        # glob broadly then filter with the re.escape(stem) regex — a local
        # media stem carries yt-dlp/Grabber "[id]" names, and Path.glob would
        # read the brackets as a character class and never match (the same
        # "[id] poison to glob" hazard highlighter._captions_for documents).
        for f in sorted(d.glob("*.translated.*.vtt")):
            mm = re.match(rf"{re.escape(stem)}\.translated\.([^.]+)\.vtt$", f.name)
            if mm and mm.group(1) not in found:
                found[mm.group(1)] = f
        adf = d / f"{stem}.described.vtt"
        if ad is None and adf.exists():
            ad = adf
    return {"tracks": found, "ad": ad}


# --------------------------------------------------------------------------
# per-meeting milestones (votes) — replicate memory.py _timeline()
# --------------------------------------------------------------------------

def _decisions(m: dict) -> list:
    an = m.get("analysis") or {}
    out = []
    for d in (an.get("decisions") or []):
        try:
            out.append({"t": float(d.get("t") or 0),
                        "text": str(d.get("text") or "")[:200],
                        "outcome": str(d.get("outcome") or "")})
        except (TypeError, ValueError):
            continue
    return out


def _milestones_for(beads: list, decisions: list) -> list:
    """A decision within ±90s of any bead is a milestone on that node."""
    out = []
    for d in decisions:
        if any(abs(d["t"] - b["t"]) <= 90 for b in beads):
            out.append(d)
        if len(out) >= 8:
            break
    return out


# --------------------------------------------------------------------------
# the bake
# --------------------------------------------------------------------------

class Bake:
    def __init__(self, corpus, out: Path, version: str, media):
        self.c = corpus
        self.out = out
        self.version = version
        self.media = media
        self.budgets = []          # (label, gz_bytes)
        self.warnings = []

    def note(self, label, gz):
        self.budgets.append((label, gz))

    # -- meetings ---------------------------------------------------------
    def bake_meetings(self):
        mrows = [m for m in self.c.list_meetings(limit=2000)
                 if m.get("status") == "live"]
        meetings = []
        for row in mrows:
            m = self.c.get_meeting(row["id"])
            p = pid(m["id"])
            segs = self.c.transcript(m["id"])
            tr = _find_tracks(m, self.media)
            langs = [{"code": c, "name": LANG_NAMES.get(c, c)}
                     for c in sorted(tr["tracks"])]
            an = m.get("analysis") or {}
            doc = {
                "id": m["id"], "pid": p, "title": m.get("title") or m["id"],
                "body": m.get("body", ""), "town": m.get("town", ""),
                "date": m.get("date", ""), "duration": m.get("duration") or 0,
                "video_id": m.get("video_id", ""), "url": m.get("url", ""),
                "source_kind": m.get("source_kind", ""),
                "origin": m.get("origin", ""),
                "n_segments": m.get("n_segments") or len(segs),
                "n_speakers": m.get("n_speakers") or 0,
                "uploader": m.get("uploader", ""),
                "summary": m.get("summary", ""),
                "summary_origin": m.get("summary_origin", ""),
                "thumb": _thumb(m),
                "tracks": langs, "ad": bool(tr["ad"]),
                "analysis": {
                    "decisions": (an.get("decisions") or [])[:20],
                    "topics": (an.get("topics") or [])[:16],
                    "entities": {k: (an.get("entities") or {}).get(k, [])[:8]
                                 for k in ("people", "places",
                                           "organizations", "money")},
                    "participation": (an.get("participation") or [])[:12],
                },
            }
            n = _json(self.out / "meetings" / f"{p}.json",
                      {k: v for k, v in doc.items()})
            self.note(f"meetings/{p}.json", _gz_of(doc))
            # copy caption + AD tracks
            for code, f in tr["tracks"].items():
                self._copy(f, self.out / "tracks" / p / f"{code}.vtt")
            if tr["ad"]:
                self._copy(tr["ad"], self.out / "ad" / f"{p}.vtt")
            meetings.append({**doc, "segments": segs})   # segments only for stubs
        return meetings

    def _copy(self, src: Path, dst: Path):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # -- issues (the long view) ------------------------------------------
    def bake_issues(self, meetings_by_id):
        issues = self.c.list_issues(status="active", limit=500)
        full = []
        for it in issues:
            issue = self.c.get_issue(it["id"])
            nodes = self.c.issue_appearances(it["id"])
            timeline = []
            for n in nodes:
                m = meetings_by_id.get(n["meeting_id"])
                decisions = _decisions(m) if m else []
                beads = [{"t": float(b["t"]), "text": str(b["text"])[:220],
                          "speaker": b.get("speaker") or "",
                          "why": b.get("why") or ""}
                         for b in (n.get("beads") or [])]
                timeline.append({
                    "meeting_id": n["meeting_id"],
                    "pid": pid(n["meeting_id"]),
                    "title": n.get("title") or n["meeting_id"],
                    "date": n.get("date", ""), "body": n.get("body", ""),
                    "town": n.get("town", ""),
                    "video_id": n.get("video_id", ""),
                    "source_kind": n.get("source_kind", ""),
                    "n": len(beads), "beads": beads,
                    "milestones": _milestones_for(beads, decisions),
                })
            doc = {
                "id": issue["id"], "slug": islug(issue["id"]),
                "name": issue["name"], "name_origin": issue.get("name_origin", ""),
                "status": issue.get("status", ""),
                "aliases": issue.get("aliases", [])[:10],
                "related": issue.get("related", [])[:8],
                "keywords": issue.get("keywords", []),
                "n_meetings": issue.get("n_meetings", 0),
                "n_segments": issue.get("n_segments", 0),
                "first_seen": issue.get("first_seen", ""),
                "last_seen": issue.get("last_seen", ""),
                "timeline": timeline,
            }
            _json(self.out / "issues" / f"{islug(issue['id'])}.json", doc)
            self.note(f"issues/{islug(issue['id'])}.json", _gz_of(doc))
            full.append(doc)
        full.sort(key=lambda d: (-d["n_meetings"], -d["n_segments"], d["name"]))
        return full

    # -- stats / dashboard (Home reads this) ------------------------------
    def bake_stats(self, meetings, issues):
        s = self.c.stats()
        n_live = len(meetings)
        # per-language coverage
        lang_meetings = {}
        described = 0
        for m in meetings:
            if m["ad"]:
                described += 1
            for t in m["tracks"]:
                lang_meetings[t["code"]] = lang_meetings.get(t["code"], 0) + 1
        languages = [{"code": c, "name": LANG_NAMES.get(c, c),
                      "meetings": n, "pct": round(100 * n / max(1, n_live))}
                     for c, n in sorted(lang_meetings.items(),
                                        key=lambda kv: -kv[1])]
        # coverage strip: meetings per month, stacked per body
        cov = {}
        for m in meetings:
            mo = _month(m["date"]) or "undated"
            body = m["body"] or "—"
            cov.setdefault(mo, {"month": mo, "total": 0, "bodies": {}})
            cov[mo]["total"] += 1
            cov[mo]["bodies"][body] = cov[mo]["bodies"].get(body, 0) + 1
        coverage = [cov[k] for k in sorted(cov)]
        # dashboard rails
        new = [{"pid": m["pid"], "title": m["title"], "body": m["body"],
                "date": m["date"], "minutes": _minutes(m["duration"]),
                "video_id": m["video_id"], "thumb": m["thumb"]}
               for m in sorted(meetings, key=lambda x: (x["date"] or ""),
                               reverse=True)][:8]
        loud = [{"slug": i["slug"], "name": i["name"],
                 "n_meetings": i["n_meetings"], "n_segments": i["n_segments"],
                 "first_seen": i["first_seen"], "last_seen": i["last_seen"]}
                for i in issues[:8]]
        # resurfacings (what changed, last time)
        resurf = []
        for e in self.c.list_events(limit=40):
            if e.get("kind") == "resurfacing":
                pl = e.get("payload") or {}
                resurf.append({
                    "slug": islug(e.get("issue_id") or ""),
                    "name": e.get("issue_name", ""),
                    "delta": pl.get("delta", ""),
                    "date": pl.get("date", ""), "title": pl.get("title", ""),
                    "pid": pid(e.get("meeting_id") or "")})
        # counts derive from the LIVE meetings the edition actually ships —
        # corpus.stats() sums every status (error/no_transcript included), so
        # its seconds/segments/towns/bodies would disagree with the meeting
        # count and the coverage strip. issues/threads are corpus-wide by design.
        stats = {
            "counts": {
                "meetings": n_live,
                "hours": round(sum(m["duration"] or 0 for m in meetings) / 3600, 1),
                "segments": sum(m["n_segments"] or 0 for m in meetings),
                "issues": s["issues"], "threads": s["threads"],
                "towns": len({m["town"] for m in meetings if m["town"]}),
                "bodies": len({m["body"] for m in meetings if m["body"]}),
                "languages": len(languages), "described": described,
            },
            "access": {
                "captioned_pct": 100 if n_live else 0,   # every live meeting has words
                "translated": {l["code"]: l["pct"] for l in languages},
                "described_pct": round(100 * described / max(1, n_live)),
            },
            "languages": languages, "coverage": coverage,
            "new": new, "loud": loud, "resurfacings": resurf,
        }
        _json(self.out / "stats.json", stats)
        self.note("stats.json", _gz_of(stats))
        return stats

    # -- urls.json (Add-a-meeting dedup) ---------------------------------
    def bake_urls(self, meetings):
        urls = {}
        for m in meetings:
            keys = set()
            if m.get("url"):
                keys.add(canon.canon(m["url"]))
            if m.get("video_id"):
                keys.add(f"youtube:{m['video_id']}")
            # the corpus's own url_canon is the ground truth
            uc = self.c.get_meeting(m["id"]).get("url_canon") or ""
            if uc:
                keys.add(uc)
            for k in keys:
                if k:
                    urls[k] = m["pid"]
        _json(self.out / "urls.json", urls)
        self.note("urls.json", _gz_of(urls))
        return urls

    # -- search index (prefix-sharded inverted index) --------------------
    def bake_search(self, meetings):
        meta = [{"pid": m["pid"], "title": m["title"], "body": m["body"],
                 "date": m["date"], "video_id": m["video_id"],
                 "source_kind": m["source_kind"]} for m in meetings]
        segs = []                       # [mi, t, speaker, text] — segId = index
        index = {}                      # term -> [segId,...]
        for mi, m in enumerate(meetings):
            for seg in m["segments"]:
                text = str(seg.get("text") or "")
                if not text.strip():
                    continue
                sid = len(segs)
                # store the TRUNCATED whole second, matching the transcript
                # anchor id (t{int(start)}) the search deep-link jumps to —
                # round(,1) would cross an integer and miss the anchor
                segs.append([mi, int(float(seg.get("start") or 0)),
                             seg.get("speaker") or "", text])
                for term in set(_TOKEN.findall(text.lower())):
                    index.setdefault(term, []).append(sid)
        # shard the index by first char
        shards = {}
        for term, ids in index.items():
            c = term[0]
            key = c if (c.isascii() and c.isalnum()) else "_"
            shards.setdefault(key, {})[term] = ids
        _json(self.out / "search" / "meta.json", meta)
        segs_txt = json.dumps(segs, ensure_ascii=False, separators=(",", ":"))
        _write(self.out / "search" / "segs.json", segs_txt)
        self.note("search/segs.json", _gz_size(segs_txt))
        keys = sorted(shards)
        for key in keys:
            _json(self.out / "search" / f"t-{key}.json", shards[key])
        _json(self.out / "search" / "shards.json",
              {"shards": keys, "segments": len(segs), "terms": len(index)})
        # honest ceiling (specs/16 §8): the design envelope is ~300 mtg / 600h
        gz = _gz_size(segs_txt)
        if gz > 2_000_000:
            self.warnings.append(
                f"search/segs.json is {gz//1024} KB gz — past the design "
                "envelope; the Bureau conversation (specs/13 §P2) has earned "
                "itself. The search page states the ceiling.")
        return {"segments": len(segs), "terms": len(index)}

    # -- feeds (RSS) ------------------------------------------------------
    def bake_feeds(self, meetings, issues, stats, site_base):
        def rss(title, desc, link, items):
            it = "".join(
                f"<item><title>{emit.xesc(i['title'])}</title>"
                f"<link>{emit.xesc(i['link'])}</link>"
                f"<guid isPermaLink=\"true\">{emit.xesc(i['link'])}</guid>"
                f"<description>{emit.xesc(i['desc'])}</description></item>"
                for i in items)
            return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<rss version="2.0"><channel>'
                    f"<title>{emit.xesc(title)}</title>"
                    f"<link>{emit.xesc(link)}</link>"
                    f"<description>{emit.xesc(desc)}</description>"
                    f"{it}</channel></rss>")
        # firehose: newest meetings + resurfacings
        items = [{"title": f"{m['title']} — {m['date'] or 'undated'}",
                  "link": f"{site_base}/app/m/{m['pid']}",
                  "desc": f"{m['body']} · {_minutes(m['duration'])} min"}
                 for m in sorted(meetings, key=lambda x: x["date"] or "",
                                 reverse=True)[:30]]
        _write(self.out / "feeds" / "firehose.xml",
               rss("Community AI Project — the record",
                   "New on the record, and issues that resurfaced.",
                   f"{site_base}/app/", items))
        for i in issues:
            items = [{"title": f"{n['title']} — {n['date'] or 'undated'}",
                      "link": f"{site_base}/app/m/{n['pid']}",
                      "desc": f"{n['n']} appearance(s) of “{i['name']}”"}
                     for n in i["timeline"]]
            _write(self.out / "feeds" / f"{i['slug']}.xml",
                   rss(f"“{i['name']}” — the long view",
                       "Every meeting this issue has touched.",
                       f"{site_base}/app/i/{i['slug']}", items))

    # -- manifest (idempotence proof) ------------------------------------
    def bake_manifest(self, meetings, issues, stats):
        # edition date derived from the corpus, never wall-clock
        stamps = [m.get("date", "") for m in meetings]
        edition_date = max([d for d in stamps if d] or [""])
        # a stable hash over the meaningful content
        h = hashlib.sha256()
        for m in sorted(meetings, key=lambda x: x["id"]):
            h.update(f"{m['id']}|{m['n_segments']}|{m['date']}|"
                     f"{m.get('summary','')[:40]}".encode())
        for i in sorted(issues, key=lambda x: x["id"]):
            h.update(f"{i['id']}|{i['n_meetings']}|{i['n_segments']}".encode())
        manifest = {
            "schema": SCHEMA_VERSION, "version": self.version,
            "corpus_hash": h.hexdigest()[:16], "edition_date": edition_date,
            "counts": stats["counts"],
        }
        _json(self.out / "manifest.json", manifest)
        return manifest

    # -- report -----------------------------------------------------------
    def report(self):
        total = sum(gz for _, gz in self.budgets)
        biggest = max(self.budgets, key=lambda kv: kv[1]) if self.budgets else ("", 0)
        print(f"  edition size (gz est.): {total/1024:.0f} KB across "
              f"{len(self.budgets)} data files")
        print(f"  biggest single file: {biggest[0]} ({biggest[1]/1024:.0f} KB gz)")
        # budgets (specs/16 §8): meeting page ≤ 400 KB gz; edition ≤ 3 MB gz
        busts = [(l, gz) for l, gz in self.budgets
                 if l.startswith("meetings/") and gz > 400_000]
        if busts:
            for l, gz in busts:
                print(f"  ⚠ BUDGET BUST: {l} is {gz/1024:.0f} KB gz (> 400 KB)")
        if total > 3_000_000:
            print(f"  ⚠ BUDGET BUST: edition {total/1024/1024:.1f} MB gz (> 3 MB)")
        for w in self.warnings:
            print(f"  ⚠ {w}")
        return {"total_gz": total, "busts": len(busts) + (total > 3_000_000)}


def bake(corpus_db: str, out_dir: str, version: str, site_base: str) -> dict:
    from czcore.paths import media_dir
    from memory.store import Corpus

    out = Path(out_dir).resolve()
    if out.exists():
        # a clean press: wipe only what the bake owns (keep sibling site files)
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    corpus = Corpus(corpus_db) if corpus_db else Corpus()
    b = Bake(corpus, out, version, media_dir)

    print("pressing the edition…")
    meetings = b.bake_meetings()
    by_id = {m["id"]: m for m in meetings}
    issues = b.bake_issues(by_id)
    stats = b.bake_stats(meetings, issues)
    b.bake_urls(meetings)
    idx = b.bake_search(meetings)
    b.bake_feeds(meetings, issues, stats, site_base)
    manifest = b.bake_manifest(meetings, issues, stats)

    # the reader (static assets) + the HTML stubs
    emit.emit_assets(out, version, manifest)
    emit.emit_stubs(out, meetings, issues, stats, manifest, site_base)

    print(f"  {len(meetings)} meetings · {len(issues)} issues · "
          f"{idx['segments']} segments indexed ({idx['terms']} terms)")
    rep = b.report()
    print(f"edition pressed → {out}  (corpus {manifest['corpus_hash']})")
    return {"meetings": len(meetings), "issues": len(issues),
            "manifest": manifest, **rep}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="web.bake",
                                 description="Press a static edition of the record.")
    ap.add_argument("--corpus", default="",
                    help="path to corpus.db (default: media_dir('memory')/corpus.db)")
    ap.add_argument("--out", default="site/docs/app",
                    help="output dir (default: site/docs/app)")
    ap.add_argument("--base", default="https://control-z.org",
                    help="site base URL for feed links + OG tags")
    args = ap.parse_args(argv)
    try:
        from suite import __version__ as version
    except Exception:
        version = "0"
    r = bake(args.corpus, args.out, version, args.base)
    return 1 if r.get("busts") else 0


if __name__ == "__main__":
    sys.exit(main())
