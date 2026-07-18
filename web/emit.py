"""HTML stubs + static assets for the edition.

Every stub is a complete, readable document with JavaScript OFF — the meeting's
transcript is real HTML, the issue's timeline is a real list of links, and the
head carries OG/Twitter tags so a link unfurls in a group chat with the
meeting's name, date, and thumbnail (specs/16 §P0.2). app.js then hydrates the
same DOM (adds the player facade, cite, search, the language menu) without
tearing the transcript down — progressive enhancement, so JS-off passes the
acceptance click-paths natively.

CSP is machine-enforced via a <meta http-equiv> tag on every page: default-src
'self', frames only to youtube-nocookie, images 'self' + i.ytimg.com. No
third-party script, font, or beacon rides in.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from web import tools

REPO = Path(__file__).resolve().parents[1]
DMG_LATEST = "https://github.com/amateurmenace/control-z/releases/latest"
CSP = ("default-src 'self'; base-uri 'self'; form-action 'self'; "
       "frame-src https://www.youtube-nocookie.com; "
       "img-src 'self' https://i.ytimg.com data:; "
       "style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; object-src 'none'")


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def xesc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def hms(t) -> str:
    t = max(0, float(t or 0))
    h, m, s = int(t // 3600), int((t % 3600) // 60), int(t % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _glyph(accent, square, ready=True):
    fill = f'fill="{accent}" fill-opacity=".28"' if ready else 'fill="none"'
    if square:
        shape = f'<rect x="4" y="4" width="12" height="12" rx="3" {fill} stroke="{accent}" stroke-width="1.4"/>'
    else:
        shape = f'<rect x="5.5" y="5.5" width="9" height="9" rx="1.5" transform="rotate(45 10 10)" {fill} stroke="{accent}" stroke-width="1.4"/>'
    return f'<svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true">{shape}</svg>'


# --------------------------------------------------------------------------
# shared chrome
# --------------------------------------------------------------------------

def head(title, desc, canonical, og_image="", version="0"):
    og = (f'<meta property="og:image" content="{esc(og_image)}">'
          f'<meta name="twitter:card" content="summary_large_image">'
          if og_image else
          '<meta name="twitter:card" content="summary">')
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">{og}
<link rel="icon" href="/app/favicon.svg">
<link rel="stylesheet" href="/app/app.css?v={esc(version)}">
</head><body>"""


def mark():
    return f"""<header class="mark">
  <a class="brand" href="/app/"><b>community</b> <i>ai</i> <b>project</b></a>
  <span class="webchip">WEB</span>
  <details class="mark-panel"><summary class="btn">Get the desktop app</summary>
    <div class="mark-body">
      <p>The desktop app adds what a browser can't:</p>
      <ul><li>work on your own footage</li>
          <li>render, transcribe and cut with local AI</li>
          <li>nothing ever uploads</li></ul>
      <p class="hint">macOS 12+ · Apple silicon · signed &amp; notarized</p>
      <a class="btn primary" href="{DMG_LATEST}">Download for macOS</a>
    </div>
  </details>
</header>"""


def rail(current=""):
    def item(href, label, glyph, cls=""):
        act = " active" if cls == current else ""
        return (f'<a class="rail-item{act}" href="{href}">'
                f'<span class="glyph">{glyph}</span>'
                f'<span class="rlabel">{esc(label)}</span></a>')
    civic = "".join(
        item("/app/" if t["id"] == "memory" else f"/app/t/{t['id']}",
             t.get("long", t["name"]).replace("Community ", ""),
             _glyph(t["accent"], True), t["id"])
        for t in tools.community())
    bench = "".join(
        item(f"/app/t/{t['id']}", t["name"], _glyph(t["accent"], False), t["id"])
        for t in tools.workbench())
    return f"""<nav class="rail">
  <a class="rail-item{' active' if current=='home' else ''}" href="/app/">
    <span class="glyph">⌂</span><span class="rlabel">Home</span></a>
  <a class="rail-item{' active' if current=='search' else ''}" href="/app/s">
    <span class="glyph">⌕</span><span class="rlabel">Search</span></a>
  <div class="rail-sect">civic media suite</div>{civic}
  <div class="rail-sect">control-z</div>{bench}
</nav>"""


def footer(manifest):
    ed = manifest.get("edition_date") or ""
    return f"""<footer class="foot">
  <a class="cov" href="/app/covenant">no accounts · no tracking · yours</a>
  <span class="ed">edition {esc(ed)} · v{esc(manifest.get('version',''))}</span>
</footer>"""


def shell(title, desc, canonical, body, current, manifest,
          og_image="", version="0"):
    return (head(title, desc, canonical, og_image, version)
            + mark() + '<div class="layout">' + rail(current)
            + f'<main class="main" id="app">{body}</main></div>'
            + footer(manifest)
            + f'<script src="/app/app.js?v={esc(version)}"></script></body></html>')


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def page_home(meetings, issues, stats, manifest, base):
    c = stats["counts"]
    def stat(n, label, href):
        return (f'<a class="statcell" href="{href}"><b>{n}</b>'
                f'<span>{esc(label)}</span></a>')
    band = "".join([
        stat(c["meetings"], "meetings", "/app/s"),
        stat(c["hours"], "hours", "/app/s"),
        stat(c["bodies"], "bodies", "/app/s"),
        stat(c["issues"], "issues", "/app/i/"),
        stat(f'{c["segments"]:,}', "segments", "/app/s"),
        stat(c["languages"], "languages", "/app/"),
        stat(c["described"], "described", "/app/"),
    ])
    new = "".join(
        f'<a class="mcard" href="/app/m/{m["pid"]}">'
        + (f'<img loading="lazy" src="{esc(m["thumb"])}" alt="">' if m["thumb"] else "")
        + f'<div class="mc-body"><span class="chip">{esc(m["body"] or "meeting")}</span>'
          f'<b>{esc(m["title"])}</b>'
          f'<span class="mc-meta">{esc(m["date"] or "undated")} · {m["minutes"]} min</span>'
          f'</div></a>'
        for m in stats["new"])
    loud = "".join(
        f'<a class="lrow" href="/app/i/{i["slug"]}">'
        f'<b>{esc(i["name"])}</b>'
        f'<span class="lmeta">{i["n_meetings"]} meetings · {i["n_segments"]} moments · '
        f'{esc((i["first_seen"] or "")[:4])}–{esc((i["last_seen"] or "")[:4])}</span></a>'
        for i in stats["loud"])
    # coverage strip (hand-drawn bars) + access meters
    mx = max([m["total"] for m in stats["coverage"]] or [1])
    bars = "".join(
        f'<div class="covbar" title="{esc(m["month"])}: {m["total"]} meeting(s)">'
        f'<span style="height:{max(6, round(56*m["total"]/mx))}px"></span>'
        f'<label>{esc((m["month"] or "?")[5:] or "?")}</label></div>'
        for m in stats["coverage"])
    meters = "".join(
        f'<div class="meter"><span>{esc(name)}</span>'
        f'<div class="mtrack"><i style="width:{pct}%"></i></div>'
        f'<b>{pct}%</b></div>'
        for name, pct in [("captioned", stats["access"]["captioned_pct"]),
                          ("described", stats["access"]["described_pct"])]
        + [(l["name"], l["pct"]) for l in stats["languages"]])
    resurf = "".join(
        f'<a class="rsrow" href="/app/i/{r["slug"]}"><b>{esc(r["name"])}</b> — '
        f'{esc(r["delta"][:200])}</a>' for r in stats["resurfacings"]) \
        or '<p class="hint">No threads have resurfaced yet — follow an issue and the record will keep watch.</p>'
    body = f"""
  <section class="hero">
    <h1>The record, open.</h1>
    <p class="why">Search everything the town has said across every read meeting,
      and land in the tape at the second it was said. Local, labeled, and
      supplementing the official record — never replacing it.</p>
    <form class="askform" action="/app/s" method="get">
      <input name="q" placeholder="ask the record — a phrase, a topic, a street name…" aria-label="Search the record">
      <button class="btn primary" type="submit">Search</button>
    </form>
    <p class="addline"><a href="/app/add">＋ Add a meeting</a></p>
  </section>
  <section class="statband">{band}</section>
  <section class="card"><span class="tag">coverage — meetings on the record, by month</span>
    <div class="covstrip">{bars}</div></section>
  <div class="grid2">
    <section class="card"><span class="tag">new on the record</span>
      <div class="mcards">{new or '<p class="hint">nothing yet</p>'}</div></section>
    <section class="card"><span class="tag">the long view — issues by reach</span>
      <div class="lrows">{loud or '<p class="hint">the long view needs two read meetings</p>'}</div></section>
  </div>
  <section class="card"><span class="tag">what changed, last time</span>
    <div class="rsrows">{resurf}</div></section>
  <section class="card"><span class="tag">the mission, measured</span>
    <div class="meters">{meters}</div></section>
"""
    return shell("The record — Community AI Project",
                 f"{c['meetings']} meetings, {c['hours']} hours, {c['issues']} issues "
                 "tracked across the record — open in any browser.",
                 f"{base}/app/", body, "home", manifest, version=manifest["version"])


def page_meeting(m, manifest, base):
    # the transcript as a real document (JS-off complete)
    rows = []
    last_spk = None
    for i, s in enumerate(m["segments"]):
        t = float(s.get("start") or 0)
        spk = s.get("speaker") or ""
        head_spk = (f'<span class="spk">{esc(spk)}</span>'
                    if spk and spk != last_spk else "")
        last_spk = spk or last_spk
        rows.append(
            f'<p class="seg" id="t{int(t)}" data-t="{t:.1f}" data-i="{i}">'
            f'<a class="ts" href="#t{int(t)}">{hms(t)}</a> '
            f'{head_spk}<span class="sx">{esc(s.get("text"))}</span></p>')
    transcript = "\n".join(rows)
    thumb = m["thumb"]
    player = ""
    if m["source_kind"] == "youtube" and m["video_id"]:
        player = (f'<div class="player facade" data-video="{esc(m["video_id"])}">'
                  + (f'<img src="{esc(thumb)}" alt="" class="pfacade-img">' if thumb else "")
                  + '<button class="playbtn" type="button" aria-label="Play (loads YouTube)">▶</button>'
                  '<span class="phint">tap to load the tape · nothing plays until you do</span></div>')
    else:
        player = ('<div class="player local"><p class="phint">the tape lives at '
                  'the station — this page is the meeting as a document.</p></div>')
    langs = ""
    if m["tracks"]:
        opts = "".join(f'<option value="{esc(t["code"])}">{esc(t["name"])}</option>'
                       for t in m["tracks"])
        langs = ('<label class="langmenu">captions '
                 f'<select id="langsel"><option value="en">English</option>{opts}'
                 + ('<option value="ad">Described (AD)</option>' if m["ad"] else "")
                 + '</select></label>')
    summ = ""
    if m["summary"]:
        origin = ("AI summary" if (m["summary_origin"] or "").startswith("ai:")
                  else "summary")
        summ = (f'<section class="card summary"><span class="tag">{origin} — '
                'supplements the official record</span>'
                f'<p>{esc(m["summary"])}</p></section>')
    meta = " · ".join([x for x in (m["body"], m["town"], m["date"] or "undated",
                                   f'{m["n_speakers"]} speakers' if m["n_speakers"] else "")
                       if x])
    dl = (f'<a class="dl" href="/app/tracks/{m["pid"]}/en.vtt" download>captions .vtt</a>'
          if False else "")  # english served from transcript; per-lang below
    tdl = "".join(f'<a class="dl" href="/app/tracks/{m["pid"]}/{t["code"]}.vtt" download>{esc(t["name"])} .vtt</a>'
                  for t in m["tracks"])
    addl = (f'<a class="dl" href="/app/ad/{m["pid"]}.vtt" download>described .vtt</a>' if m["ad"] else "")
    body = f"""
  <article class="meeting" data-pid="{esc(m["pid"])}">
    <div class="mhead">
      <a class="back" href="/app/">← the record</a>
      <h1>{esc(m["title"])}</h1>
      <div class="mmeta">{esc(meta)}</div>
      <div class="chips">{langs}
        <button class="btn cite-all" type="button" data-cite="all">⧉ Cite this meeting</button></div>
    </div>
    {player}
    {summ}
    <div class="tbar">
      <span class="tag">transcript — select any line to Cite it, click a time to jump</span>
      <span class="dls">{tdl}{addl}
        <a class="dl" href="/app/m/{m["pid"]}/transcript.txt" download>transcript .txt</a></span>
    </div>
    <div class="transcript" id="transcript">{transcript}</div>
    <p class="disclose">AI-touched surfaces are labeled; verify against the official record.
      The tape is embedded from YouTube, never rehosted.</p>
  </article>
"""
    desc = (f'{m["body"]} · {m["date"] or "undated"} · '
            f'{int(round((m["duration"] or 0)/60))} min · read on the record')
    return shell(m["title"], desc, f"{base}/app/m/{m['pid']}", body,
                 "memory", manifest, og_image=thumb, version=manifest["version"])


def page_meeting_txt(m):
    lines = [m["title"], m.get("date", ""), ""]
    for s in m["segments"]:
        spk = (s.get("speaker") + ": ") if s.get("speaker") else ""
        lines.append(f"[{hms(s.get('start') or 0)}] {spk}{s.get('text','')}")
    return "\n".join(lines)


def page_issue(i, manifest, base):
    nodes = []
    for n in i["timeline"]:
        beads = "".join(
            f'<a class="bead" href="/app/m/{n["pid"]}#t{int(b["t"])}">'
            f'<span class="ts">{hms(b["t"])}</span> {esc(b["text"][:90])}</a>'
            for b in n["beads"][:6])
        miles = "".join(
            f'<a class="milestone" href="/app/m/{n["pid"]}#t{int(mm["t"])}">'
            f'◆ <span class="ts">{hms(mm["t"])}</span> {esc(mm["text"][:70])}'
            + (f' <span class="outcome">{esc(mm["outcome"])}</span>' if mm.get("outcome") else "")
            + '</a>' for mm in n.get("milestones", []))
        nodes.append(
            f'<div class="tnode"><div class="tdot"></div>'
            f'<div class="thead"><span class="tdate">{esc(n["date"] or "undated")}</span>'
            f'<a class="ttitle" href="/app/m/{n["pid"]}">{esc(n["body"] or n["title"])}</a>'
            f'<span class="tn">{n["n"]} moment(s)</span></div>'
            f'<div class="beads">{beads}{miles}</div></div>')
    origin = ("Named by a model" if (i["name_origin"] or "").startswith("ai:")
              else "Named from the record's own words")
    aliases = "".join(f'<span class="alias">{esc(a)}</span>' for a in i["aliases"])
    related = "".join(f'<span class="rel">{esc(r)}</span>' for r in i["related"])
    body = f"""
  <article class="issue">
    <a class="back" href="/app/">← the record</a>
    <h1>{esc(i["name"])}</h1>
    <div class="idisclose">{origin} · tracked across {i["n_meetings"]} meetings ·
      officials-only aggregation · supplements the official record</div>
    <div class="ichips">{aliases}{related}</div>
    <p class="feedlink"><a href="/app/feeds/{i["slug"]}.xml">☉ follow by RSS</a></p>
    <section class="card"><span class="tag">the long view — every meeting this issue touched</span>
      <div class="timeline">{nodes and "".join(nodes) or '<p class="hint">no appearances</p>'}</div>
    </section>
  </article>
"""
    desc = (f'“{i["name"]}” — {i["n_meetings"]} meetings, {i["n_segments"]} moments '
            f'on the record, {(i["first_seen"] or "")[:4]}–{(i["last_seen"] or "")[:4]}')
    return shell(f'{i["name"]} — the long view', desc,
                 f"{base}/app/i/{i['slug']}", body, "memory", manifest,
                 version=manifest["version"])


def page_search(manifest, base):
    body = """
  <section class="searchpage">
    <h1>Search the record</h1>
    <form class="askform" id="searchform" action="/app/s" method="get">
      <input name="q" id="q" placeholder="a phrase, a topic, a street name…" aria-label="Search">
      <button class="btn primary" type="submit">Search</button>
    </form>
    <p class="hint" id="search-note">Search runs in your browser over a prebuilt
      lexical index — no query leaves this page. (Vector search stays at the desk.)</p>
    <div id="results"><noscript><p class="hint">Search needs JavaScript.
      <a href="/app/">Browse the record</a> instead — every meeting is a readable
      document with JavaScript off.</p></noscript></div>
  </section>
"""
    return shell("Search — the record", "Search everything the town has said.",
                 f"{base}/app/s", body, "search", manifest,
                 version=manifest["version"])


def page_add(manifest, base):
    body = """
  <section class="addpage">
    <a class="back" href="/app/">← the record</a>
    <h1>Add a meeting</h1>
    <p class="why">Paste a meeting's link. If it's already on the record, this
      walks you to it. If not, it composes a submission for the steward — a
      steward reviews; the record updates on the next pressing.</p>
    <form class="askform" id="addform">
      <input id="addurl" placeholder="https://youtube.com/watch?v=…  —or—  a meeting URL" aria-label="Meeting URL">
      <button class="btn primary" type="submit">Check the record</button>
    </form>
    <div id="addresult"></div>
    <details class="addcompose" id="addcompose" hidden>
      <summary>Compose a submission</summary>
      <div class="composebody">
        <label>Town <input id="ctown" placeholder="Brookline"></label>
        <label>Body <input id="cbody" placeholder="Select Board"></label>
        <label>Date <input id="cdate" placeholder="2026-06-18"></label>
        <label>Note <textarea id="cnote" placeholder="anything the steward should know"></textarea></label>
        <div class="composeacts">
          <a class="btn primary" id="c-github" target="_blank" rel="noopener">Open a GitHub submission</a>
          <button class="btn" id="c-copy" type="button">Copy submission JSON</button>
          <a class="btn" id="c-mail">Email the steward</a>
        </div>
      </div>
    </details>
  </section>
"""
    return shell("Add a meeting — the record",
                 "Paste a link; add a meeting to the town's record.",
                 f"{base}/app/add", body, "home", manifest,
                 version=manifest["version"])


def page_covenant(manifest, base):
    body = f"""
  <section class="covpage">
    <a class="back" href="/app/">← the record</a>
    <h1>The covenant, in public</h1>
    <ul class="covlist">
      <li><b>Static files only.</b> No backend, no compute, no accounts.</li>
      <li><b>No cookies, no analytics, no telemetry.</b> We will not know our
        reader count, and we ship anyway.</li>
      <li><b>Follows live in your browser</b> (localStorage); notifications are RSS.</li>
      <li><b>Embeds are click-to-load</b> (youtube-nocookie) — nothing plays,
        and no third party sees you, until you tap.</li>
      <li><b>No video rehosting.</b> Tapes are embedded or transcript-first; a
        meeting whose tape is a local file ships as a document.</li>
      <li><b>No person pages.</b> Officials-only aggregation is applied at press
        time; nothing about a private citizen is aggregated into an edition.</li>
      <li><b>Corrections annotate, never rewrite.</b> A takedown path reaches the steward.</li>
      <li><b>Anti-lock-in.</b> Every meeting downloads as transcript and every
        timeline as data — the record is yours to keep.</li>
      <li><b>Licensed to stay free.</b> AGPL-3.0 for the code, CC BY-SA 4.0 for the record.</li>
    </ul>
    <p class="hint">A strict Content-Security-Policy on every page enforces all
      of this in the browser: no third-party script, font, or beacon can load.</p>
    <p class="hint">This edition was pressed {esc(manifest.get('edition_date',''))}
      from a corpus fingerprinted {esc(manifest.get('corpus_hash',''))}.</p>
  </section>
"""
    return shell("The covenant — Community AI Project",
                 "Static files, no accounts, no tracking. The covenant in one screen.",
                 f"{base}/app/covenant", body, "", manifest,
                 version=manifest["version"])


def page_door(t, manifest, base):
    beats = "".join(f'<div class="beat"><span>{i+1}</span>{esc(b)}</div>'
                    for i, b in enumerate(t["beats"]))
    demo = ""
    if t["slide"]:
        demo = (f'<div class="demo"><img src="/app/assets/slide-{esc(t["slide"])}.jpg" '
                f'alt="{esc(t["name"])} at work" loading="lazy"></div>')
    lives = ""
    if t["lives_here"]:
        lives = (f'<a class="liveshere" href="{esc(t["lives_here"]["href"])}">'
                 f'but its work lives here → {esc(t["lives_here"]["label"])}</a>')
    body = f"""
  <section class="door" style="--acc:{esc(t["accent"])}">
    <div class="doorhead">
      <span class="dglyph">{_glyph(t["accent"], t["group"]=="community")}</span>
      <div><h1>{esc(t.get("long", t["name"]))}</h1>
        <p class="dverb">{esc(t["verb"])} — {esc(t["one"])}</p></div>
      <span class="desktag">desk</span>
    </div>
    {demo}
    <div class="beats">{beats}</div>
    <p class="whydesk">{esc(t["why_desk"])}</p>
    {lives}
    <div class="doorcta">
      <details class="mark-panel open"><summary class="btn primary">Get the desktop app</summary>
        <div class="mark-body">
          <p>Everything {esc(t["name"])} does happens on your own machine, with
             your files. The desktop app is where that work lives.</p>
          <p class="hint">macOS 12+ · Apple silicon · signed &amp; notarized</p>
          <a class="btn primary" href="{DMG_LATEST}">Download for macOS</a>
        </div></details>
    </div>
  </section>
"""
    return shell(f'{t.get("long", t["name"])} — Community AI Project',
                 f'{t["verb"]} — {t["one"]}. A desk tool; its work lives on the record.',
                 f"{base}/app/t/{t['id']}", body, t["id"], manifest,
                 version=manifest["version"])


# --------------------------------------------------------------------------
# assets + orchestration
# --------------------------------------------------------------------------

_ROOT_RE = re.compile(r":root\s*\{(.*?)\}", re.S)


def _desk_tokens() -> str:
    """Lift the :root token block from the desk's single-source stylesheet so
    the edition carries the SAME values (specs/16 §9 — import, never fork)."""
    css = (REPO / "suite" / "static" / "app.css").read_text(encoding="utf-8")
    m = _ROOT_RE.search(css)
    return f":root {{{m.group(1)}}}" if m else ":root{}"


def emit_assets(out: Path, version, manifest):
    (out / "assets").mkdir(parents=True, exist_ok=True)
    # app.css = the desk's tokens (single source) + the web-only rules
    web_css = (Path(__file__).resolve().parent / "static" / "app.web.css").read_text(encoding="utf-8")
    (out / "app.css").write_text(_desk_tokens() + "\n\n" + web_css, encoding="utf-8")
    # app.js (the reader)
    shutil.copyfile(Path(__file__).resolve().parent / "static" / "app.js",
                    out / "app.js")
    # favicon — the node motif, oxblood (the record)
    (out / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
        '<rect x="4" y="4" width="12" height="12" rx="3" fill="#8E4A55"/></svg>',
        encoding="utf-8")
    # demo slides the doors reference
    src = REPO / "site" / "content" / "assets"
    for t in tools.TOOLS:
        if t["slide"]:
            f = src / f"slide-{t['slide']}.jpg"
            if f.exists():
                shutil.copyfile(f, out / "assets" / f"slide-{t['slide']}.jpg")


def emit_stubs(out, meetings, issues, stats, manifest, base):
    v = manifest["version"]
    (out / "index.html").write_text(page_home(meetings, issues, stats, manifest, base), encoding="utf-8")
    (out / "s" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "s" / "index.html").write_text(page_search(manifest, base), encoding="utf-8")
    (out / "add" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "add" / "index.html").write_text(page_add(manifest, base), encoding="utf-8")
    (out / "covenant" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "covenant" / "index.html").write_text(page_covenant(manifest, base), encoding="utf-8")
    for m in meetings:
        d = out / "m" / m["pid"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_meeting(m, manifest, base), encoding="utf-8")
        (d / "transcript.txt").write_text(page_meeting_txt(m), encoding="utf-8")
    for i in issues:
        d = out / "i" / i["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_issue(i, manifest, base), encoding="utf-8")
    for t in tools.TOOLS:
        if t["surface"] != "web":
            d = out / "t" / t["id"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(page_door(t, manifest, base), encoding="utf-8")
