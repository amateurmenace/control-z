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
BRAND = REPO / "brand"
DMG_LATEST = "https://github.com/amateurmenace/control-z/releases/latest"
COMMUNITYAI = "https://communityai.studio"

# Where a reader goes to read the program that pressed what they are reading.
# The covenant page promises the source is published; a promise with a dead
# link behind it is worse than no promise, so these are constants and a test
# asserts the covenant page carries them.
SOURCE_REPO = "https://github.com/amateurmenace/control-z"
LICENSING_DOC = SOURCE_REPO + "/blob/main/LICENSING.md"
_CSP_BASE = ("default-src 'self'; base-uri 'self'; form-action 'self'; "
             "frame-src https://www.youtube-nocookie.com; "
             "img-src 'self' https://i.ytimg.com data:; "
             "font-src 'self'; "
             "style-src 'self' 'unsafe-inline'; script-src 'self'; "
             "connect-src 'self'{extra}; object-src 'none'")
CSP = _CSP_BASE.format(extra="")

# The record's own API, when this pressing has one. Empty for a desk edition,
# which is the case that must never change: press without --api and the bytes
# are identical to yesterday's.
#
# This is the one place the reader is allowed to reach past its own origin, and
# it is worth being exact about why that is not a hole in the covenant. The
# promise on the covenant page is that no THIRD PARTY can load a script, a font
# or a beacon — and that still holds, because default-src, script-src and
# img-src are untouched. What widens is connect-src, by exactly one first-party
# host: the record's own service, named in full, on the same project and the
# same bill. A reader who blocks it loses meaning-search and keeps everything
# else, which is the whole design.
#
# When the edition and the API eventually share an origin behind one load
# balancer, this exception disappears on its own and nothing else changes.
_API = {"base": ""}


def set_api(base: str = "") -> None:
    """Point this pressing at its Studio, or at nothing."""
    _API["base"] = (base or "").rstrip("/")


def api() -> str:
    """This pressing's Studio, or "" for a desk edition."""
    return _API["base"]


def csp() -> str:
    """The policy for this pressing. Identical to CSP when there is no API."""
    base = _API["base"]
    if not base:
        return CSP
    origin = "/".join(base.split("/")[:3])       # scheme://host, never a path
    return _CSP_BASE.format(extra=" " + origin)


def _api_meta() -> str:
    """The address the reader may call, next to the policy that permits it.

    A meta tag rather than a fetch of `manifest.json`, for two reasons. It is
    available when the parser reaches it, so the first keystroke in the search
    box does not race a round trip; and it sits in the same `<head>` as the
    `connect-src` that authorises it, so the permission and the address are one
    thing to read and one thing to change. The reader treats its absence as
    "this is a desk edition" — which is exactly what it means."""
    base = _API["base"]
    return f'\n<meta name="record-api" content="{esc(base)}">' if base else ""


# What this pressing serves, set once per bake by emit_stubs().
#
# Module state rather than a parameter because the scope bar lives in the
# shared chrome, and ten page functions call shell() — threading an eleventh
# argument through a page function so a folio can name a town would be
# ceremony that buys nothing. A bake is one process pressing one edition; this
# is written before the first stub renders and never again.
_EDITION = {"towns": [], "bodies": [], "untowned": 0, "meetings": 0}


def set_edition(towns_plane) -> None:
    """Tell the chrome which towns and bodies this edition actually holds."""
    _EDITION.update({"towns": [], "bodies": [], "untowned": 0, "meetings": 0})
    _EDITION.update(towns_plane or {})


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def xesc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def hms(t) -> str:
    t = max(0, float(t or 0))
    h, m, s = int(t // 3600), int((t % 3600) // 60), int(t % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _brand_mark() -> str:
    """The publicrecord keycap — the minutes on the record — read byte-equal
    from brand/logos and never redrawn (specs/20 §4, branding law). One read,
    used for both the masthead and the favicon, so the two can never drift."""
    return (BRAND / "logos" / "publicrecord-mark.svg").read_text(
        encoding="utf-8").strip()


# --------------------------------------------------------------------------
# shared chrome
# --------------------------------------------------------------------------

def _feed_link(feed) -> str:
    """A page's own RSS feed, advertised in the head for reader auto-discovery
    (specs/20 §7.9 C). An issue page carries its own long-view feed; it sits
    before the firehose so a reader who subscribes from an issue gets that
    issue, not the whole record."""
    if not feed:
        return ""
    return (f'<link rel="alternate" type="application/rss+xml" '
            f'title="{esc(feed["title"])}" href="{esc(feed["href"])}">')


def head(title, desc, canonical, og_image="", version="0", feed=None):
    og = (f'<meta property="og:image" content="{esc(og_image)}">'
          f'<meta name="twitter:card" content="summary_large_image">'
          if og_image else
          '<meta name="twitter:card" content="summary">')
    # preload only the two faces first paint needs (Inter body, mono headline);
    # the rest swap in. crossorigin is required on a font preload even for a
    # same-origin fetch, or the browser fetches the face twice.
    preload = "".join(
        f'<link rel="preload" href="/app/fonts/{f}.woff2" as="font" '
        f'type="font/woff2" crossorigin>' for f in _PRELOAD_FONTS)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp()}">{_api_meta()}
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">{og}
<meta name="theme-color" content="#f8fafc">
<link rel="icon" href="/app/favicon.svg">
<link rel="manifest" href="/app/manifest.webmanifest">
{_feed_link(feed)}<link rel="alternate" type="application/rss+xml" title="The record — new meetings and resurfacings" href="/app/feeds/firehose.xml">
{preload}<link rel="stylesheet" href="/app/app.css?v={esc(version)}">
</head><body>"""


def scope_bar():
    """The town picker, baked into every page (specs/17 §8).

    Three shapes, because the honest answer differs by how many towns the
    pressing actually holds:

      no town   — nothing to pick; the bar is not rendered at all
      one town  — the town is *named*, not offered. A picker with one option
                  is a question whose answer is already known, and asking it
                  would be the nag specs/17 warns against.
      many      — real anchors, one per town, plus the whole record.

    The anchors are `<a href>` and not buttons on purpose. A static edition
    cannot scope server-side, so with JavaScript off these still navigate
    somewhere true (the record, whole), and the line under them says plainly
    that the scoping itself is the browser's work. The alternative — controls
    that look live and silently do nothing — is the dishonesty the covenant
    is against."""
    towns = _EDITION.get("towns") or []
    if not towns:
        return ""
    if len(towns) == 1:
        t = towns[0]
        return (f'<div class="scope one" id="scope">'
                f'<span class="scopelabel">town</span>'
                f'<span class="scopenow" id="scopenow" data-town="{esc(t["town"])}">'
                f'{esc(t["town"])}</span>'
                f'<span class="scopehint">the only town on this edition</span>'
                f'</div>')
    links = "".join(
        f'<a class="scopetown" href="/app/?town={esc(t["town"])}" '
        f'data-town="{esc(t["town"])}">{esc(t["town"])}'
        f'<span class="scopen">{t["meetings"]}</span></a>'
        for t in towns)
    return (f'<div class="scope" id="scope">'
            f'<span class="scopelabel">town</span>'
            f'<span class="scopenow" id="scopenow">the whole record</span>'
            f'<div class="scopetowns">{links}'
            f'<a class="scopetown" href="/app/" data-town="">the whole record</a>'
            f'</div></div>')


# The record's own surfaces, as a newspaper's section line. The thirteen desk
# tools that used to share this rail are gone from it — they live on /app/press
# now (specs/20 §5). What is left is the paper's own sections, and nothing
# borrows a masthead it did not earn.
NAV = [("home", "The record", "/app/"),
       ("search", "Search", "/app/s"),
       ("officials", "The votes", "/app/officials"),
       ("analytics", "The record drawn", "/app/analytics"),
       ("graph", "The issue graph", "/app/graph"),
       ("watching", "Still watching", "/app/watching"),
       ("press", "The press", "/app/press")]


def section_nav(current):
    items = "".join(
        f'<a class="navlink{" active" if k == current else ""}" href="{href}">'
        f'{esc(label)}</a>'
        for k, label, href in NAV)
    return f'<nav class="sectionnav" aria-label="Sections">{items}</nav>'


def folio(manifest):
    """The line under the nameplate: the towns this edition holds, the dateline
    (the edition date reading finally as what it is), and the covenant's six
    words. It informs; unlike the old boxed banner, it does not interrupt."""
    ed = manifest.get("edition_date") or ""
    dateline = (f'<span class="dateline">pressed from the record of '
                f'<b>{esc(ed)}</b></span>') if ed else ""
    return (f'<div class="folio">{scope_bar()}{dateline}'
            f'<a class="cov6" href="/app/covenant">'
            f'no accounts · no tracking · yours</a></div>')


def masthead(current, manifest):
    """The nameplate — the publicrecord keycap (byte-equal from brand/logos)
    and the lowercase mono lockup — over the classic masthead rule pair, then
    the folio and the section line. 'Get the desktop app' is demoted off the
    masthead to /app/press and the footer (specs/20 §5)."""
    return f"""<header class="masthead">
  <div class="nameplate">
    <a class="brand" href="/app/" aria-label="publicrecord.studio — the record">
      <span class="brandmark">{_brand_mark()}</span>
      <span class="wm">publicrecord<span class="tld">.studio</span></span>
    </a>
  </div>
  {folio(manifest)}
  {section_nav(current)}
</header>"""


def footer(manifest):
    ed = manifest.get("edition_date") or ""
    # The second way back to the picker. specs/17 §8 asks for re-choosable "at
    # any time", and a reader who has scrolled to the bottom of a four-hour
    # transcript should not have to scroll back up to leave a town. The anchor
    # works with JavaScript off, because it is only an anchor.
    again = ('<a class="scopelink" href="#scope">town — change</a>'
             if len(_EDITION.get("towns") or []) > 1 else "")
    return f"""<footer class="foot">
  <span class="foot-mark">{_brand_mark()}</span>
  <a class="cov" href="/app/covenant">the covenant</a>
  <a class="cov" href="/app/press">the press · get the desktop app</a>
  {again}
  <a class="cov" href="{COMMUNITYAI}">a Community AI Project tool</a>
  <span class="ed">edition {esc(ed)} · v{esc(manifest.get('version',''))}</span>
</footer>"""


def shell(title, desc, canonical, body, current, manifest,
          og_image="", version="0", feed=None):
    # The banner slot rides in the markup rather than being minted by script so
    # it lands in one known place on every page — top of the main column, above
    # whatever the reader came for, which is the only position that can honestly
    # claim to have warned them before they read.
    slot = '<div class="scopebanner" id="scopebanner" hidden></div>'
    return (head(title, desc, canonical, og_image, version, feed)
            + masthead(current, manifest)
            + f'<main class="main paper" id="app">{slot}{body}</main>'
            + footer(manifest)
            + f'<script src="/app/app.js?v={esc(version)}"></script></body></html>')


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def body_strip():
    """The public bodies this edition holds, as a filter — and, underneath it,
    as a plain sentence.

    Two renderings of one fact, and both ship. The chips are minted by app.js
    into the empty rail (they are stateful, so markup cannot honestly bake
    them); the sentence is real HTML and is what a reader with JavaScript off
    gets — not a dead control, but the same information in the form that still
    works. The counts come from the pressed meetings, so every body named here
    has at least one meeting behind it."""
    bodies = _EDITION.get("bodies") or []
    if not bodies:
        return ""
    named = " · ".join(
        f'{esc(b["body"] or "no body recorded")} <b>{b["meetings"]}</b>'
        for b in bodies)
    return f"""
  <section class="card bodycard">
    <span class="tag">the bodies on the record — filter what you see</span>
    <div class="bodyfilter" id="bodyfilter" role="group"
         aria-label="Filter by public body" hidden></div>
    <p class="bodylist" id="bodylist">{named}</p>
    <p class="hint">Filtering runs in your browser and touches nothing else.
      With JavaScript off this page lists the whole record — every meeting
      below stays readable either way.</p>
  </section>"""


def _brief_card(m):
    """A brief — a recent meeting as a small still + a one-line deck, in the
    briefs column. Same .mcard the scope filter already knows how to hide."""
    thumb = m.get("thumb") or ""
    return (f'<a class="mcard" href="/app/m/{m["pid"]}" '
            f'data-town="{esc(m.get("town", ""))}" data-body="{esc(m["body"])}">'
            + (f'<img loading="lazy" src="{esc(thumb)}" alt="" width="96" height="54">'
               if thumb else "")
            + f'<div class="mc-body"><span class="chip">{esc(m["body"] or "meeting")}</span>'
              f'<b>{esc(m["title"])}</b>'
              f'<span class="mc-meta">{esc(m["date"] or "undated")} · '
              f'{int(round((m.get("duration") or 0)/60))} min</span></div></a>')


def page_home(meetings, issues, stats, manifest, base):
    c = stats["counts"]
    ms = sorted(meetings, key=lambda m: (m.get("date") or ""), reverse=True)
    lead = ms[0] if ms else None

    # -- the lead story: the latest meeting, given the front page --
    if lead:
        # the two strongest moments, but never two from the same second — a vote
        # and the question beside it share a timestamp, and the paper wants two
        # different beats
        top, secs = [], set()
        for mo in sorted(lead.get("moments") or [], key=lambda mo: -mo["score"]):
            if int(mo["t"]) in secs:
                continue
            secs.add(int(mo["t"]))
            top.append(mo)
            if len(top) == 2:
                break
        pulls = "".join(
            f'<a class="pull" href="/app/m/{lead["pid"]}#t{int(mo["t"])}">'
            f'<span class="ts">{hms(mo["t"])}</span>'
            f'<span class="mk">{esc(mo["kind"])}</span> '
            f'{esc(mo["quote"][:130])}</a>' for mo in top)
        lthumb = lead.get("thumb") or ""
        deck = (f'<p class="deck">{esc(lead["summary"][:260])}</p>'
                if lead.get("summary") else "")
        lead_html = (
            f'<article class="lead" data-town="{esc(lead["town"])}" '
            f'data-body="{esc(lead["body"])}">'
            f'<span class="kicker">the latest meeting on the record</span>'
            + (f'<a class="lead-media" href="/app/m/{lead["pid"]}">'
               f'<img src="{esc(lthumb)}" alt="" width="960" height="540"></a>'
               if lthumb else "")
            + f'<a class="lead-hl" href="/app/m/{lead["pid"]}"><h2>{esc(lead["title"])}</h2></a>'
              f'<p class="lead-meta"><span class="chip">{esc(lead["body"] or "meeting")}</span> '
              f'{esc(lead["town"] or "")} · {esc(lead["date"] or "undated")} · '
              f'{int(round((lead["duration"] or 0)/60))} min</p>'
            + deck
            + (f'<div class="pulls"><span class="kicker">from the tape</span>{pulls}</div>'
               if pulls else "")
            + '</article>')
    else:
        lead_html = '<p class="hint">The record is empty — no meetings pressed yet.</p>'

    # -- briefs: the next few meetings --
    briefs = "".join(_brief_card(m) for m in ms[1:6]) or \
        '<p class="hint">just the one meeting, so far</p>'

    # -- by the numbers: every figure a link --
    def stat(n, label, href):
        return (f'<a class="statcell" href="{href}"><b>{n}</b>'
                f'<span>{esc(label)}</span></a>')
    band = "".join([
        stat(c["meetings"], "meetings", "/app/s"),
        stat(c["hours"], "hours", "/app/analytics"),
        stat(c["bodies"], "bodies", "/app/analytics"),
        stat(c["issues"], "issues", "/app/graph"),
        stat(c["votes"], "roll calls", "/app/officials"),
        stat(f'{c["segments"]:,}', "segments", "/app/s"),
        stat(c["languages"], "languages", "/app/press#interpreter"),
        stat(c["described"], "described", "/app/press#narrator"),
    ])

    # -- standing stories: the long view --
    loud = "".join(
        f'<a class="lrow" href="/app/i/{i["slug"]}">'
        f'<b>{esc(i["name"])}</b>'
        f'<span class="lmeta">{i["n_meetings"]} meetings · {i["n_segments"]} moments · '
        f'{esc((i["first_seen"] or "")[:4])}–{esc((i["last_seen"] or "")[:4])}</span></a>'
        for i in stats["loud"])

    # -- updates: what resurfaced, quoting its bead --
    resurf = "".join(
        f'<a class="rsrow" href="/app/i/{r["slug"]}"><b>{esc(r["name"])}</b>'
        f'<span class="rsdelta">{esc(r["delta"][:220])}</span></a>'
        for r in stats["resurfacings"]) \
        or ('<p class="hint">No threads have resurfaced yet — follow an issue '
            'and the record will keep watch.</p>')

    # -- the access ledger: captioned / translated / described, honest zeros --
    langs = stats["languages"]
    translated = (", ".join(f'{esc(l["name"])} {l["pct"]}%' for l in langs)
                  if langs else
                  "0 — no meeting is translated yet; the drain fills this in")
    access = (
        f'<div class="acc"><span class="acc-l">captioned</span>'
        f'<b class="acc-n">{stats["access"]["captioned_pct"]}%</b>'
        f'<span class="acc-w">every live meeting ships its words</span></div>'
        f'<div class="acc"><span class="acc-l">translated</span>'
        f'<span class="acc-w">{translated}</span></div>'
        f'<div class="acc"><span class="acc-l">described</span>'
        f'<b class="acc-n">{stats["access"]["described_pct"]}%</b>'
        f'<span class="acc-w">audio description arrives with the drain</span></div>')

    # -- the votes teaser: latest roll calls --
    allvotes = []
    for m in meetings:
        for v in (m.get("votes") or []):
            allvotes.append({"pid": m["pid"], "date": m.get("date", ""),
                             "title": m.get("title", ""), **v})
    allvotes.sort(key=lambda v: (v.get("date", ""), v.get("t", 0)), reverse=True)
    votes_teaser = "".join(
        f'<a class="vteaser" href="/app/m/{v["pid"]}#t{int(v.get("t") or 0)}">'
        f'<span class="vt-motion">{esc((v.get("motion") or "")[:90])}</span>'
        f'<span class="vt-meta"><span class="outcome">{esc(v.get("outcome",""))}</span> '
        f'<span class="tally">{esc(v.get("tally",""))}</span> · {esc(v.get("date",""))}</span></a>'
        for v in allvotes[:4]) \
        or '<p class="hint">no roll calls read yet</p>'

    # -- coverage strip --
    mx = max([m["total"] for m in stats["coverage"]] or [1])
    bars = "".join(
        f'<div class="covbar" data-month="{esc(m["month"])}" '
        f'title="{esc(m["month"])}: {m["total"]} meeting(s)">'
        f'<span style="height:{max(6, round(56*m["total"]/mx))}px"></span>'
        # an undated meeting's month is the literal "undated" — slicing [5:] off
        # that spells "ed"; show a dash for the no-date bucket instead
        f'<label>{esc("—" if m["month"] == "undated" else (m["month"] or "?")[5:] or "?")}</label></div>'
        for m in stats["coverage"])

    body = f"""
  <form class="askform frontsearch" action="/app/s" method="get">
    <input name="q" placeholder="ask the record — a phrase, a topic, a street name…" aria-label="Search the record">
    <button class="btn primary" type="submit">Search</button>
    <a class="addline" href="/app/add">＋ Add a meeting</a>
  </form>
  <p class="scopeline" id="scopeline" hidden></p>
  {body_strip()}
  <div class="leadrow">
    <div class="leadcol">{lead_html}</div>
    <div class="briefscol">
      <div class="sectionhead"><span class="kicker">also on the record</span></div>
      <div class="mcards briefs">{briefs}</div>
    </div>
  </div>
  <section class="numbers">
    <div class="sectionhead"><span class="kicker">by the numbers</span></div>
    <div class="statband">{band}</div>
    <div class="covwrap"><span class="kicker">meetings by month</span>
      <div class="covstrip">{bars}</div></div>
  </section>
  <div class="storyrow">
    <section class="story"><div class="sectionhead"><span class="kicker">the long view — issues by reach</span></div>
      <div class="lrows">{loud or '<p class="hint">the long view needs two read meetings</p>'}</div></section>
    <section class="story"><div class="sectionhead"><span class="kicker">what changed, last time</span></div>
      <div class="rsrows">{resurf}</div></section>
  </div>
  <div class="storyrow">
    <section class="story"><div class="sectionhead"><span class="kicker">the access ledger</span></div>
      <div class="accled">{access}</div></section>
    <section class="story"><div class="sectionhead"><span class="kicker">the latest roll calls</span>
      <a class="seeall" href="/app/officials">the votes →</a></div>
      <div class="vteasers">{votes_teaser}</div></section>
  </div>
"""
    return shell("The record — publicrecord.studio",
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
        # anchor id and data-t must floor to the SAME whole second, or a
        # deep-link's #t<sec> won't match its row. data-t carries the exact
        # start (for precise seek + Math.floor()==int(t)); NEVER the rounded
        # form — round(t,1) can cross an integer and break ~5% of deep-links.
        rows.append(
            f'<p class="seg" id="t{int(t)}" data-t="{t}" data-i="{i}">'
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
    # the roll calls — who voted how, read from the record (officials only)
    votes_html = ""
    if m.get("votes"):
        vrows = []
        for v in m["votes"]:
            roll = "".join(
                f'<span class="rollent"><a href="#t{int(r.get("t", v["t"]))}">'
                f'{esc(r.get("name",""))}</a> {_rollcell(r.get("vote",""))}</span>'
                for r in (v.get("roll") or []))
            vrows.append(
                f'<div class="vrow"><a class="vhead" href="#t{int(v["t"])}">'
                f'<span class="ts">{hms(v["t"])}</span> {esc((v["motion"] or "")[:110])} '
                f'<span class="tally">{esc(v.get("tally",""))}</span> '
                f'<span class="outcome">{esc(v.get("outcome",""))}</span></a>'
                f'<div class="roll">{roll}</div></div>')
        votes_html = (
            '<section class="card ledger"><span class="tag">the vote ledger — '
            'roll calls read from this meeting</span>'
            f'<div class="vledger">{"".join(vrows)}</div>'
            '<p class="hint">Read from the transcript; a name may be misheard — '
            'verify against the official minutes.</p></section>')
    # the analyzer's read — framing lenses (with drift), questions, tension
    an = m.get("analysis") or {}
    framing = (an.get("framing") or {})
    framing_html = ""
    if framing.get("lenses"):
        mx = max((l["count"] for l in framing["lenses"]), default=1) or 1
        DRIFT = {"rising": "↑ rising", "fading": "↓ fading", "steady": "· steady"}
        # no per-lens hue: publicrecord takes deep green only, so the bars are
        # the accent and the labels are ink — the lens is named, not colour-coded
        # (specs/20 §5). The counts and drift carry the difference.
        rows = "".join(
            f'<div class="lensrow"><span class="lenslabel">{esc(l["lens"])}</span>'
            f'<span class="lensbar"><i style="width:{round(100*l["count"]/mx)}%"></i></span>'
            f'<span class="lensn">{l["count"]}</span>'
            f'<span class="lensdrift">{DRIFT.get(l["drift"],"")}</span></div>'
            for l in framing["lenses"])
        framing_html = ('<section class="card"><span class="tag">how the meeting '
                        'framed it — eight civic lenses, counted from its own '
                        'words</span>'
                        f'<div class="lenses">{rows}</div>'
                        '<p class="hint">Counted, not modeled — each lens is a '
                        'word list; drift compares the first half to the '
                        'second.</p></section>')
    questions_html = ""
    if an.get("questions"):
        byt = {}
        for q in an["questions"]:
            byt.setdefault(q.get("type", "information"), []).append(q)
        blocks = "".join(
            f'<div class="qgroup"><span class="qtype">{esc(t)}</span>'
            + "".join(f'<a class="qrow" href="#t{int(q["t"])}">'
                      f'<span class="ts">{hms(q["t"])}</span> {esc(q["text"])}</a>'
                      for q in qs[:8]) + '</div>'
            for t, qs in sorted(byt.items()))
        questions_html = ('<section class="card"><span class="tag">the questions '
                          'asked — typed by what they ask about</span>'
                          f'<div class="qgroups">{blocks}</div></section>')
    # the town's paper for this meeting
    docs_html = ""
    if m.get("documents"):
        drows = "".join(
            (f'<a class="docrow" href="{esc(d["url"])}" target="_blank" rel="noopener">'
             if d.get("url") else '<div class="docrow">')
            + f'📄 <b>{esc(d.get("kind","document"))}</b> {esc((d.get("title") or "")[:70])}'
            + f' <span class="lmeta">{d.get("pages",0)} pp</span>'
            + ("</a>" if d.get("url") else "</div>")
            for d in m["documents"])
        docs_html = ('<section class="card"><span class="tag">the town’s paper — '
                     'agendas, minutes, and packets for this meeting</span>'
                     f'<div class="docrows">{drows}</div></section>')
    # the Moments panel (specs/20 §6) — the analyzer's scored moments as cards,
    # each a deep link into the tape. Baked into the stub so it reads with
    # JavaScript off; app.js turns a click into a seek. The kinds differ by
    # their mono kicker, never by colour (the record takes deep green only).
    moments_html = ""
    if m.get("moments"):
        cards = ""
        for mo in m["moments"]:
            score = max(0.0, min(1.0, float(mo.get("score") or 0)))
            reason = mo.get("reason") or ""
            # the anchor carries the whole moment (end, kind, quote) so the reel
            # composer (specs/20 §6, P1) can build a clip from a tick without a
            # second fetch — and the card stays a plain deep link with JS off.
            cards += (
                '<div class="mo-card">'
                f'<a class="moment" href="#t{int(mo["t"])}" data-t="{mo["t"]}" '
                f'data-start="{mo.get("start", mo["t"])}" '
                f'data-end="{mo.get("end") or mo["t"]}" data-kind="{esc(mo["kind"])}" '
                f'data-quote="{esc(mo["quote"])}">'
                f'<div class="mo-head"><span class="ts">{hms(mo["t"])}</span>'
                f'<span class="mo-kind">{esc(mo["kind"])}</span></div>'
                f'<p class="mo-quote">{esc(mo["quote"])}</p>'
                + (f'<div class="mo-foot"><span class="mo-reason">{esc(reason)}</span>'
                   f'<span class="mo-score" title="salience {round(score*100)}%">'
                   f'<i style="width:{round(score*100)}%"></i></span></div>'
                   if reason or score else "")
                + '</a></div>')
        # a meeting with a tape has a publish kit (web/kit.py's gate); link it
        # from the moments it was cut from, so a producer can find it.
        kitlink = (
            f'<p class="hint"><a class="liveshere" href="/app/k/{esc(m["pid"])}">'
            '→ the publish kit for this meeting</a> — the clips worth cutting and '
            'draft copy, for a producer.</p>'
            if m.get("video_id") else "")
        moments_html = (
            '<section class="card moments"><span class="tag">the moments — the '
            'analyzer’s scored read of this meeting; click one to jump the '
            'tape</span>'
            f'<div class="mo-grid">{cards}</div>'
            '<p class="hint">Scored, not chosen for you — the salience bar is a '
            'measurement, and every moment is a receipt into the transcript '
            'below. With JavaScript on, tick moments to compose a reel — and tick '
            'moments on other meetings too; a reel can span the record.</p>'
            f'{kitlink}'
            '</section>')
    meta = " · ".join([x for x in (m["body"], m["town"], m["date"] or "undated",
                                   f'{m["n_speakers"]} speakers' if m["n_speakers"] else "")
                       if x])
    # english is served from the transcript itself; per-language tracks below.
    # esc() the code into the href too — a local sidecar filename is
    # operator-controlled and the track-code regex ([^.]+) permits quotes/angle
    # brackets, so match the escaping the <option value> already does.
    tdl = "".join(f'<a class="dl" href="/app/tracks/{m["pid"]}/{esc(t["code"])}.vtt" download>{esc(t["name"])} .vtt</a>'
                  for t in m["tracks"])
    addl = (f'<a class="dl" href="/app/ad/{m["pid"]}.vtt" download>described .vtt</a>' if m["ad"] else "")
    body = f"""
  <article class="meeting" data-pid="{esc(m["pid"])}" data-town="{esc(m["town"])}" data-body="{esc(m["body"])}">
    <div class="mhead">
      <a class="back" href="/app/">← the record</a>
      <h1>{esc(m["title"])}</h1>
      <div class="mmeta">{esc(meta)}</div>
      <div class="chips">{langs}
        <button class="btn cite-all" type="button" data-cite="all">⧉ Cite this meeting</button></div>
    </div>
    {player}
    {summ}
    {moments_html}
    {votes_html}
    {docs_html}
    {framing_html}
    {questions_html}
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


def _milestone_html(pid, mm):
    """One milestone row — a roll-call vote (with its tally) or a decision."""
    if mm.get("kind") == "vote":
        tally = f' <span class="tally">{esc(mm.get("tally",""))}</span>' if mm.get("tally") else ""
        out = (f' <span class="outcome">{esc(mm["outcome"])}</span>'
               if mm.get("outcome") else "")
        return (f'<a class="milestone vote" href="/app/m/{pid}#t{int(mm["t"])}">'
                f'⬡ <span class="ts">{hms(mm["t"])}</span> {esc(mm["text"][:70])}'
                f'{tally}{out}</a>')
    return (f'<a class="milestone" href="/app/m/{pid}#t{int(mm["t"])}">'
            f'◆ <span class="ts">{hms(mm["t"])}</span> {esc(mm["text"][:70])}'
            + (f' <span class="outcome">{esc(mm["outcome"])}</span>' if mm.get("outcome") else "")
            + '</a>')


def _docs_html(pid, docs):
    """The document lane on a timeline node — the town's paper for this meeting,
    each cite page-numbered and linking to the portal PDF."""
    if not docs:
        return ""
    rows = []
    for d in docs:
        cites = "".join(
            f'<span class="cite">p.{c.get("page",0)} · {esc(c.get("text","")[:80])}</span>'
            for c in (d.get("cites") or [])[:2])
        link = (f'<a class="docn" href="{esc(d["url"])}" target="_blank" rel="noopener">'
                if d.get("url") else '<span class="docn">')
        end = "</a>" if d.get("url") else "</span>"
        rows.append(f'{link}📄 {esc(d.get("kind","document"))} — '
                    f'{esc((d.get("title") or "")[:60])}{end}{cites}')
    return f'<div class="docs">{"".join(rows)}</div>'


def _rollcell(v):
    cls = {"yes": "y", "no": "n", "abstain": "a"}.get(v, "")
    label = {"yes": "aye", "no": "no", "abstain": "abs"}.get(v, esc(v))
    return f'<span class="rc {cls}">{label}</span>'


def _ledger_html(ledger):
    """The roll-call ledger for an issue — who voted how, each a receipt into
    the tape. Officials only (a roll call is the board voting)."""
    if not ledger:
        return ""
    rows = []
    for v in ledger:
        roll = "".join(
            f'<span class="rollent"><a href="/app/m/{v["pid"]}#t{int(r.get("t",v["t"]))}">'
            f'{esc(r.get("name",""))}</a> {_rollcell(r.get("vote",""))}</span>'
            for r in v.get("roll", []))
        rows.append(
            f'<div class="vrow"><a class="vhead" href="/app/m/{v["pid"]}#t{int(v["t"])}">'
            f'<span class="ts">{esc(v["date"] or "")}</span> {esc((v["motion"] or "")[:100])} '
            f'<span class="tally">{esc(v.get("tally",""))}</span> '
            f'<span class="outcome">{esc(v.get("outcome",""))}</span></a>'
            f'<div class="roll">{roll}</div></div>')
    return (f'<section class="card ledger"><span class="tag">the vote ledger — '
            f'roll calls on this issue, read from the record</span>'
            f'<div class="vledger">{"".join(rows)}</div>'
            f'<p class="hint">Roll calls are read from the transcript and may '
            f'mishear a name — verify against the official minutes.</p></section>')


def page_issue(i, manifest, base):
    nodes = []
    for n in i["timeline"]:
        beads = "".join(
            f'<a class="bead" href="/app/m/{n["pid"]}#t{int(b["t"])}">'
            f'<span class="ts">{hms(b["t"])}</span> {esc(b["text"][:90])}</a>'
            for b in n["beads"][:6])
        miles = "".join(_milestone_html(n["pid"], mm)
                        for mm in n.get("milestones", []))
        docs = _docs_html(n["pid"], n.get("documents", []))
        nodes.append(
            f'<div class="tnode"><div class="tdot"></div>'
            f'<div class="thead"><span class="tdate">{esc(n["date"] or "undated")}</span>'
            f'<a class="ttitle" href="/app/m/{n["pid"]}">{esc(n["body"] or n["title"])}</a>'
            f'<span class="tn">{n["n"]} moment(s)</span></div>'
            f'<div class="beads">{beads}{miles}</div>{docs}</div>')
    origin = ("Named by a model" if (i["name_origin"] or "").startswith("ai:")
              else "Named from the record's own words")
    aliases = "".join(f'<span class="alias">{esc(a)}</span>' for a in i["aliases"])
    related = "".join(f'<span class="rel">{esc(r)}</span>' for r in i["related"])
    ledger = _ledger_html(i.get("ledger", []))
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
    {ledger}
  </article>
"""
    desc = (f'“{i["name"]}” — {i["n_meetings"]} meetings, {i["n_segments"]} moments '
            f'on the record, {(i["first_seen"] or "")[:4]}–{(i["last_seen"] or "")[:4]}')
    return shell(f'{i["name"]} — the long view', desc,
                 f"{base}/app/i/{i['slug']}", body, "memory", manifest,
                 version=manifest["version"],
                 feed={"href": f"/app/feeds/{i['slug']}.xml",
                       "title": f'“{i["name"]}” — the long view (RSS)'})


def page_tombstone(slug, name, date, manifest, base):
    """A citation to an issue a steward curated away resolves to an explanation,
    never a bare 404 (specs/20 §6). The date is stored audit state, pressed
    idempotently — never a wall clock. This pays the debt specs/19 R1.7 named:
    control-z.org/app still carries a page publicrecord correctly dropped."""
    when = f" on {esc(date)}" if date else ""
    body = f"""
  <section class="tombstone">
    <a class="back" href="/app/">← the record</a>
    <h1>{esc(name) or "This issue"}</h1>
    <p class="presslede">This issue was <b>removed from the record by a
      steward{when}</b>. The record is curated in public: a steward may fold one
      issue into another or, rarely, forget one entirely. The meetings it
      gathered are all still on the record — only this grouping of them was
      withdrawn.</p>
    <p class="hint"><a href="/app/">Browse the record</a> ·
      <a href="/app/s">search it</a> · <a href="/app/covenant">the covenant</a>.</p>
  </section>
"""
    return shell(f"{name or 'Removed'} — removed from the record",
                 f"This issue was removed from the record by a steward{when}.",
                 f"{base}/app/i/{slug}", body, "", manifest,
                 version=manifest["version"])


def page_reel(manifest, base):
    """The reel viewer — /app/r (specs/20 §6/§7, P1). A shared reel lives
    entirely in its link (?v=1&m=<pid>&c=<start>-<end>,…); this page is the
    same static stub for every reel, and app.js decodes the link, fetches the
    meeting's own plane, and plays the sequence through the youtube-nocookie
    facade, clip to clip. No server, no reader state — the reel is in the URL
    and nowhere else.

    JS-off, a reel is just its citations, and a static page cannot read the
    query string to list them — so the honest fallback says exactly that, and
    sends the reader to the record where every moment reads in place. app.js
    replaces this with the decoded cite list (and the player) when it runs."""
    body = f"""
  <section class="reel" id="reel">
    <a class="back" href="/app/">← the record</a>
    <h1>A reel from the record</h1>
    <p class="presslede">A <b>reel</b> is a short sequence of moments — roll
      calls, decisions, questions, the turns of an argument — pulled from the
      record, from one meeting or several, and strung together in order. The
      whole reel rides in the link that brought you here: which meetings, which
      moments, in what order. Nothing was uploaded, and nothing about you was
      kept.</p>
    <div class="reelstage" id="reelstage"></div>
    <div class="reelcites" id="reelcites">
      <p class="hint">Playing the reel — seeking the tape from clip to clip —
        needs JavaScript, and so does listing its clips (they live in the link,
        not on any page). With JavaScript off, open <a href="/app/">the
        record</a> or <a href="/app/s">search it</a> to read the moments in
        place.</p>
    </div>
    <p class="disclose">The tape is embedded from YouTube, never rehosted. The
      reel lives in this link and your browser — there is no account and no
      server holding it. Rendering it as a video needs the desk.</p>
  </section>
"""
    return shell("A reel — publicrecord.studio",
                 "A sequence of moments from one meeting on the record, played "
                 "clip to clip — the reel lives entirely in its link.",
                 f"{base}/app/r", body, "", manifest,
                 version=manifest["version"])


def _kit_card(k):
    """A kit in the index — a meeting's still + deck, linking to its kit."""
    meta = k.get("meta") or {}
    thumb = meta.get("thumb") or ""
    n = len(k.get("clips") or [])
    return (f'<a class="mcard" href="/app/k/{esc(k.get("slug", ""))}" '
            f'data-town="{esc(meta.get("town", ""))}" '
            f'data-body="{esc(meta.get("body", ""))}">'
            + (f'<img loading="lazy" src="{esc(thumb)}" alt="" width="96" height="54">'
               if thumb else "")
            + f'<div class="mc-body"><span class="chip">{esc(meta.get("body") or "meeting")}</span>'
              f'<b>{esc(meta.get("title") or "Community program")}</b>'
              f'<span class="mc-meta">{esc(meta.get("date") or "undated")} · '
              f'{n} clip{"" if n == 1 else "s"}</span></div></a>')


def page_kits_index(kits, manifest, base):
    """The kits index — /app/k (specs/20 §6, §7.9 P2). Publisher's reading half:
    one entry per meeting that has a video and moments to publish. When an
    edition has none (nothing with a tape to cut), the page says so plainly
    rather than standing empty — the same honesty the /app/press door keeps."""
    if kits:
        cards = "".join(_kit_card(k) for k in kits)
        listing = f'<div class="kitgrid">{cards}</div>'
    else:
        listing = ('<p class="hint">No publish kits in this edition yet — a kit '
                   'is pressed for each meeting that has a tape to cut from. '
                   '<a href="/app/">Browse the record</a> in the meantime.</p>')
    body = f"""
  <section class="press">
    <a class="back" href="/app/">← the record</a>
    <div class="eyebrow"><span class="kicker">from Community Publisher</span></div>
    <h1>Publish kits</h1>
    <p class="presslede">A <b>publish kit</b> is what a producer needs to take a
      meeting out to the world: the clips worth cutting, and draft copy to ship
      them with — titles, a description, chapters — all assembled from the
      transcript, no model. Every kit here reads in the browser; <b>cutting the
      video and burning captions happen in Publisher at the desk</b>, and each
      kit downloads as a file that opens there.</p>
    {listing}
    <p class="hint">Kits are drafts, not decisions — the analyzer scored the
      moments and the copy is lifted from the record itself. A producer edits
      the kit in <a href="/app/press#publisher">Community Publisher</a> before
      anything is published.</p>
  </section>
"""
    return shell("Publish kits — publicrecord.studio",
                 "A publish kit for every meeting: the clips worth cutting and "
                 "draft copy, assembled from the transcript.",
                 f"{base}/app/k", body, "", manifest,
                 version=manifest["version"])


def page_kit(kit, manifest, base):
    """One meeting's publish kit, read-only (specs/20 §6, §7.9 P2).

    Publisher's reading half: the clips (the moments plane, as cut candidates)
    and the draft copy, assembled from the transcript and labeled so. Rendering
    the clips — the one step that touches local media — stays at the desk, and
    the page says so. JS-off everything reads: the clips are server-rendered
    cards deep-linking the tape, the copy is real text, kit.json is a plain
    download, and 'play as a reel' is a link into the /app/r viewer (P1)."""
    meta = kit.get("meta") or {}
    slug = kit.get("slug") or ""
    pid = esc(meta.get("pid") or "")
    title = esc(meta.get("title") or "Community program")
    where = " · ".join(x for x in [meta.get("body"), meta.get("town"),
                                   meta.get("date")] if x)
    clips = kit.get("clips") or []
    copy = kit.get("copy") or {}

    cards = ""
    for c in clips:
        t = float(c.get("t", c.get("start", 0)) or 0)
        quote = esc(c.get("text") or c.get("label") or "")
        span = f'{hms(c.get("start", 0))}–{hms(c.get("end", 0))}'
        cards += (
            '<div class="mo-card">'
            f'<a class="moment" href="/app/m/{pid}#t{int(t)}" '
            f'data-t="{c.get("t", c.get("start", 0))}">'
            f'<div class="mo-head"><span class="ts">{hms(t)}</span>'
            f'<span class="mo-kind">{esc(c.get("kind") or "moment")}</span></div>'
            f'<p class="mo-quote">{quote}</p>'
            f'<div class="mo-foot"><span class="mo-reason">clip {esc(span)}</span></div>'
            '</a></div>')

    # 'play as a reel' hands the whole kit to /app/r (P1), which plays clip to
    # clip through the facade — the same clip encoding the composer writes.
    # `%g` matches app.js's r1() stringification (0.1-quantized, no trailing
    # ".0"), so a kit-page reel link is byte-identical to a composer share link.
    def _b(v):
        return "%g" % round(float(v or 0), 1)
    reel_clips = ",".join(f"{_b(c.get('start'))}-{_b(c.get('end'))}" for c in clips)
    reel_href = esc(f"/app/r?v=1&m={meta.get('pid', '')}&c={reel_clips}")
    kit_href = esc(f"/app/kits/{slug}.json")

    titles = copy.get("titles") or []
    title_opts = "".join(f'<li>{esc(t)}</li>' for t in titles)
    desc = esc(copy.get("description") or "").replace("\n", "<br>")
    origin = esc(copy.get("origin") or "")

    body = f"""
  <section class="press kit">
    <a class="back" href="/app/k">← all the kits</a>
    <div class="eyebrow"><span class="kicker">a publish kit — Community Publisher</span></div>
    <h1>{title}</h1>
    <p class="hint">{esc(where)}</p>
    <p class="presslede">The <b>publish kit</b> for this meeting: the clips worth
      cutting and draft copy to ship them with, assembled from the transcript.
      It reads here; <b>cutting the video, burning captions and choosing aspect
      ratios happen in Publisher at the desk</b>, against the program file on
      your own machine. Download the kit and open it there to carry on from this
      draft.</p>

    <div class="sectionhead"><span class="kicker">the clips — {len(clips)}</span></div>
    <div class="mo-grid">{cards}</div>
    <div class="presscta">
      <a class="btn primary" href="{reel_href}">▶ Play these clips as a reel</a>
      <a class="btn" href="{kit_href}" download>⬇ kit.json — open at the desk</a>
      <a class="btn" href="/app/m/{pid}">Read the whole meeting →</a>
    </div>

    <div class="sectionhead"><span class="kicker">draft headlines</span></div>
    <ul class="kittitles">{title_opts}</ul>
    <div class="sectionhead"><span class="kicker">draft description</span></div>
    <p class="kitdesc">{desc}</p>
    <p class="hint">{origin}. Every line is a working draft — a producer edits it
      in Publisher before anything goes out.</p>

    <p class="disclose">The tape is embedded from YouTube, never rehosted.
      Rendering the clips as video needs the desk — this page composes, it does
      not cut. Community Publisher is
      <a href="{COMMUNITYAI}">a Community AI Project</a> tool.</p>
  </section>
"""
    return shell(f"{meta.get('title') or 'Publish kit'} — the kits · publicrecord.studio",
                 f"The publish kit for {meta.get('title') or 'this meeting'}: "
                 "clips and draft copy, assembled from the transcript.",
                 f"{base}/app/k/{slug}", body, "", manifest,
                 version=manifest["version"])


def _search_note() -> str:
    """What the search field promises, which differs by pressing.

    A desk edition genuinely has no server, and saying "vector search stays at
    the desk" is true there. On a Studio pressing it was a lie the page told
    for a month, so the sentence is now derived from the same fact the CSP is:
    whether this edition was pressed with an API behind it. app.js replaces it
    again at runtime if the API turns out to be unreachable — a promise made at
    press time cannot know that, and the reader deserves the live answer."""
    if _API["base"]:
        return ("Search reads the record two ways at once — the words you typed, "
                "and what they mean. Nothing about you is sent with the query.")
    return ("Search runs in your browser over a prebuilt lexical index — no "
            "query leaves this page. (Meaning-search needs the Studio.)")


def page_search(manifest, base):
    # The two filters are baked as real <select name=…> inside the form, so a
    # scoped search is a URL: /app/s?q=override&town=Brookline&body=Select+Board.
    # That is what makes a filtered result shareable, and it is why they are
    # form controls rather than script-minted chips — the search page is the
    # one surface where JavaScript is already load-bearing (the index is read
    # in the browser), so a control that submits a query string is honest here
    # in a way it would not be on the home page.
    towns = _EDITION.get("towns") or []
    bodies = _EDITION.get("bodies") or []
    tsel = ""
    if len(towns) > 1:
        opts = "".join(f'<option value="{esc(t["town"])}">{esc(t["town"])}</option>'
                       for t in towns)
        tsel = ('<label class="filt">town <select name="town" id="townsel">'
                f'<option value="">every town</option>{opts}</select></label>')
    bsel = ""
    if len(bodies) > 1:
        opts = "".join(
            f'<option value="{esc(b["body"])}">'
            f'{esc(b["body"] or "no body recorded")} ({b["meetings"]})</option>'
            for b in bodies)
        bsel = ('<label class="filt">body <select name="body" id="bodysel">'
                f'<option value="">every body</option>{opts}</select></label>')
    filters = (f'<div class="searchfilters">{tsel}{bsel}</div>'
               if (tsel or bsel) else "")
    body = f"""
  <section class="searchpage">
    <h1>Search the record</h1>
    <form class="askform" id="searchform" action="/app/s" method="get">
      <input name="q" id="q" placeholder="a phrase, a topic, a street name…" aria-label="Search">
      <button class="btn primary" type="submit">Search</button>
    </form>
    {filters}
    <p class="hint" id="search-note">{_search_note()}</p>
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
      <li><b>Follows and your chosen town live in your browser</b>
        (localStorage, never a cookie — a cookie would ride every request and
        become the server's business); notifications are RSS.</li>
      <li><b>Embeds are click-to-load</b> (youtube-nocookie) — nothing plays,
        and no third party sees you, until you tap.</li>
      <li><b>No video rehosting.</b> Tapes are embedded or transcript-first; a
        meeting whose tape is a local file ships as a document.</li>
      <li><b>No person pages.</b> Officials-only aggregation is applied at press
        time; nothing about a private citizen is aggregated into an edition.</li>
      <li><b>Corrections annotate, never rewrite.</b> A takedown path reaches the steward.</li>
      <li><b>Anti-lock-in.</b> Every meeting downloads as transcript and every
        timeline as data — the record is yours to keep.</li>
      <li><b>Licensed to stay free.</b> AGPL-3.0 for the code, CC BY-SA 4.0 for
        the record — and below, in plain words, what that buys you.</li>
    </ul>
    <h2>What the licence means for you</h2>
    <p class="covwhy">Three different things are licensed here, and the
      difference matters more than the names do.</p>
    <ul class="covlist">
      <li><b>The meetings belong to the town.</b> They were public when they
        happened and they are public now. This site supplements the official
        record; it does not replace it, and it cannot become the only place the
        town's business can be found.</li>
      <li><b>The record on this site is CC BY-SA 4.0.</b> Anyone may copy it,
        quote it, republish it, or build something else on top of it — so long
        as they credit it and pass the same freedom on to whoever comes next.</li>
      <li><b>The software is AGPL-3.0</b> — a licence whose whole purpose is
        that a public thing stays public. The program that pressed this edition
        is published in full. Anyone can run their own copy: the town, the
        library, a neighbor with a laptop. And anyone who changes it and runs it
        as a service for other people owes those people the changed program too.
        So this record cannot be taken away, fenced off, or sold back to the
        town, and there is no version of it that quietly becomes somebody's
        product.</li>
    </ul>
    <p class="hint">The source is at
      <a href="{SOURCE_REPO}">github.com/amateurmenace/control-z</a>; which
      licence covers which part, in full, is in
      <a href="{LICENSING_DOC}">LICENSING.md</a>.</p>
    <p class="hint">A strict Content-Security-Policy on every page enforces all
      of this in the browser: no third-party script, font, or beacon can load.</p>
    <p class="hint">This edition was pressed {esc(manifest.get('edition_date',''))}
      from a corpus fingerprinted {esc(manifest.get('corpus_hash',''))}.</p>
  </section>
"""
    return shell("The covenant — publicrecord.studio",
                 "Static files, no accounts, no tracking. The covenant in one screen.",
                 f"{base}/app/covenant", body, "", manifest,
                 version=manifest["version"])


def page_officials(officials, manifest, base):
    """The accountability page — every official's roll-call record, each cell a
    receipt into the tape. Officials only, by construction (specs/14 §8)."""
    cards = []
    for o in officials:
        # the 24 MOST-RECENT roll calls, newest first (member_records appends
        # oldest-first, so slice the tail and reverse — not the head)
        recent = "".join(
            f'<a class="vcell" href="/app/m/{v["pid"]}#t{int(v.get("t") or 0)}" '
            f'title="{esc((v.get("motion") or "")[:80])}">'
            f'{_rollcell(v.get("vote",""))}<span class="vc-date">{esc((v.get("date") or "")[5:])}</span></a>'
            for v in reversed(o.get("votes", [])[-24:]))
        cards.append(
            f'<div class="offcard" data-town="{esc(o.get("town", ""))}">'
            f'<div class="offhead"><b>{esc(o["name"])}</b>'
            f'<span class="lmeta">{esc(o.get("town",""))}</span></div>'
            f'<div class="offtally"><span class="rc y">{o["yes"]} aye</span>'
            f'<span class="rc n">{o["no"]} no</span>'
            f'<span class="rc a">{o["abstain"]} abs</span>'
            f'<span class="offtot">{o["total"]} recorded votes</span></div>'
            f'<div class="vcells">{recent}</div></div>')
    body = f"""
  <section class="officials">
    <a class="back" href="/app/">← the record</a>
    <h1>The people's votes</h1>
    <p class="why">Every roll call the record has read, by member. These are the
      votes officials cast in public session — officials only, by construction:
      a roll call is the board voting. Each cell links to the moment on the tape.
      Read from the transcript; verify against the official minutes.</p>
    <div class="offgrid">{"".join(cards) or '<p class="hint">no roll calls on the record yet</p>'}</div>
  </section>
"""
    return shell("The people's votes — the record",
                 "Every official's roll-call record, each cell a receipt into the tape.",
                 f"{base}/app/officials", body, "officials", manifest,
                 version=manifest["version"])


def page_analytics(analytics, manifest, base):
    """The record, drawn — the desk's Library made static: the eight civic
    framing lenses per meeting, the topics that recur, the names that keep
    appearing. Every mark links to its meeting. JS-off complete."""
    order = analytics.get("lens_order", [])
    color = analytics.get("lens_color", {})
    fm = analytics.get("framing", [])
    # framing heatmap: meetings × lenses, cell shade = share of that meeting
    head = "".join(f'<th>{esc(n)}</th>' for n in order)
    body_rows = []
    for r in fm:
        tot = r.get("total", 0) or 1
        # the green tint scale (specs/20 §5): a darker deep-green is a bigger
        # share; the lens hues never come near this domain. Ink flips to white
        # once the cell is dark enough to need it (AA on the count).
        cells = ""
        for n in order:
            cnt = r["lenses"].get(n, 0)
            a = round(0.05 + 0.9 * min(1, cnt / tot * 4), 2)
            ink = "#ffffff" if a > 0.45 else "#0f172a"
            cells += (f'<td style="background:rgba(5,46,22,{a});color:{ink}" '
                      f'title="{esc(n)}: {cnt}">{cnt or ""}</td>')
        body_rows.append(
            f'<tr><th class="fmlbl"><a href="/app/m/{r["pid"]}">'
            f'{esc((r["date"] or "?")[:10])} · {esc((r["body"] or r["title"])[:26])}</a></th>{cells}</tr>')
    heat = (f'<table class="heat"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>') if fm else \
        '<p class="hint">the framing map needs a read meeting</p>'
    # topics that recur across meetings
    topics = "".join(
        f'<a class="trow" href="/app/m/{t["meetings"][0]["pid"]}#t{int(t["meetings"][0].get("t") or 0)}">'
        f'<b>{esc(t["topic"])}</b>'
        f'<span class="lmeta">{len(t["meetings"])} meetings · {t["count"]} mentions</span></a>'
        for t in analytics.get("topics", [])[:24])
    # recurring names
    names = "".join(
        f'<a class="nrow" href="/app/m/{n["meetings"][0]["pid"]}#t{int(n["meetings"][0].get("t") or 0)}">'
        f'<span class="nkind nk-{esc(n["kind"][:3])}"></span><b>{esc(n["name"])}</b>'
        f'<span class="lmeta">{len(n["meetings"])} meetings · {n["count"]}×</span></a>'
        for n in analytics.get("names", [])[:30])
    body = f"""
  <section class="analytics">
    <a class="back" href="/app/">← the record</a>
    <h1>The record, drawn</h1>
    <p class="why">Every read meeting as one picture — how the town framed what
      it discussed, the topics that keep returning, and the names that recur.
      Counted from the record's own words; every mark opens its meeting.</p>
    <section class="card"><span class="tag">civic framing — meetings down, lenses across</span>
      <div class="heatwrap">{heat}</div>
      <p class="hint">A darker cell is a bigger share of that meeting's framing —
        the green scale is measurement, and these are measurements.</p></section>
    <div class="grid2">
      <section class="card"><span class="tag">topics that recur across the record</span>
        <div class="trows">{topics or '<p class="hint">nothing recurs yet</p>'}</div></section>
      <section class="card"><span class="tag">names across two or more meetings</span>
        <div class="nrows">{names or '<p class="hint">no name recurs yet</p>'}</div></section>
    </div>
  </section>
"""
    return shell("The record, drawn — publicrecord.studio",
                 "The town's meetings as one picture — framing, topics, and names "
                 "counted across the record.",
                 f"{base}/app/analytics", body, "analytics", manifest,
                 version=manifest["version"])


def page_graph(graph, manifest, base):
    """The issue graph — issues that share meetings, drawn as the network they
    are. A hand-laid ring of nodes with weighted chords; SVG, no libraries, so
    the strict CSP holds. JS-off it's a readable ring; app.js adds hover."""
    import math
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    W = 760
    R = 300
    cx = cy = W / 2
    n = len(nodes)
    pos = []
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * i / max(1, n)
        pos.append((round(cx + R * math.cos(a), 1), round(cy + R * math.sin(a), 1)))
    idx = {node["slug"]: i for i, node in enumerate(nodes)}
    mxw = max((e["weight"] for e in edges), default=1) or 1
    lines = "".join(
        f'<line x1="{pos[idx[e["a"]]][0]}" y1="{pos[idx[e["a"]]][1]}" '
        f'x2="{pos[idx[e["b"]]][0]}" y2="{pos[idx[e["b"]]][1]}" '
        f'stroke="#052e16" stroke-opacity="{0.12 + 0.5*e["weight"]/mxw:.2f}" '
        f'stroke-width="{0.5 + 2.5*e["weight"]/mxw:.1f}"/>'
        for e in edges if e["a"] in idx and e["b"] in idx)
    mxm = max((node["n_meetings"] for node in nodes), default=1) or 1
    dots = ""
    labels = ""
    for i, node in enumerate(nodes):
        x, y = pos[i]
        r = 3 + 7 * node["n_meetings"] / mxm
        dots += (f'<a href="/app/i/{esc(node["slug"])}">'
                 f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#052e16" '
                 f'fill-opacity=".82"><title>{esc(node["name"])} · '
                 f'{node["n_meetings"]} meetings</title></circle></a>')
        # label just outside the ring, anchored by side
        lx = round(cx + (R + 14) * math.cos(-math.pi/2 + 2*math.pi*i/max(1, n)), 1)
        ly = round(cy + (R + 14) * math.sin(-math.pi/2 + 2*math.pi*i/max(1, n)), 1)
        anchor = "start" if lx >= cx else "end"
        labels += (f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" '
                   f'font-size="10" fill="#475569" dominant-baseline="middle">'
                   f'{esc(node["name"][:22])}</text>')
    svg = (f'<svg viewBox="0 0 {W} {W}" class="graphsvg" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="issue co-occurrence network">{lines}{dots}{labels}</svg>'
           if nodes else '<p class="hint">the graph needs issues that share meetings</p>')
    # a JS-off table twin (WCAG: every chart has a table twin)
    twin = "".join(
        f'<tr><td><a href="/app/i/{esc(e["a"])}">{esc(_gname(nodes, e["a"]))}</a></td>'
        f'<td><a href="/app/i/{esc(e["b"])}">{esc(_gname(nodes, e["b"]))}</a></td>'
        f'<td>{e["weight"]} shared</td></tr>' for e in edges[:60])
    body = f"""
  <section class="graphpage">
    <a class="back" href="/app/">← the record</a>
    <h1>The issue graph</h1>
    <p class="why">The town's concerns as the network they are: two issues are
      tied when they share meetings, and the tie thickens with every meeting
      they share. A bigger dot appears on more of the record. Tap a node to walk
      its long view.</p>
    <section class="card graphcard">{svg}</section>
    <details class="graphtwin"><summary>the same, as a table</summary>
      <table class="twin"><thead><tr><th>issue</th><th>issue</th><th>tie</th></tr></thead>
      <tbody>{twin or '<tr><td colspan="3">no ties yet</td></tr>'}</tbody></table>
    </details>
  </section>
"""
    return shell("The issue graph — publicrecord.studio",
                 "The town's issues drawn as the network they are — tied when "
                 "they share meetings.",
                 f"{base}/app/graph", body, "graph", manifest,
                 version=manifest["version"])


def _gname(nodes, slug):
    for n in nodes:
        if n["slug"] == slug:
            return n["name"]
    return slug


def page_still(manifest, base):
    """Still watching — the follows view. Follows live only in localStorage, so
    the body is a JS-rendered list with an honest noscript story."""
    body = """
  <section class="stillpage">
    <a class="back" href="/app/">← the record</a>
    <h1>Still watching</h1>
    <p class="why">The issues you follow, and what has changed on each since you
      last looked. Follows live in your browser — no account, nothing uploaded.</p>
    <div class="stilltools">
      <button class="btn" id="follow-export" type="button">Export follows (JSON)</button>
      <label class="btn" for="follow-import">Import follows<input id="follow-import" type="file" accept="application/json" hidden></label>
    </div>
    <div id="stilllist"><noscript><p class="hint">The still-watching view needs
      JavaScript to read your follows. <a href="/app/">Browse the record</a> —
      every issue timeline is a readable document, and each offers RSS.</p></noscript></div>
  </section>
"""
    return shell("Still watching — the record",
                 "The issues you follow, and what changed since you last looked.",
                 f"{base}/app/watching", body, "watching", manifest,
                 version=manifest["version"])


CREDIT = ("designed + developed by Stephen Walter with Brookline Interactive "
          "Group &amp; Neighborhood AI · CC BY-SA 4.0")


def _tool_row(t, lives_here=None):
    """A tool's one-line entry. `lives_here` defaults to the registry's static
    link, but a caller can pass one the registry can't know at import time — the
    Publisher row's cross-link into /app/k, say, which is honest only in an
    edition that actually pressed kits (specs/20 §7.9: the door stays honest
    until then)."""
    lh = lives_here if lives_here is not None else t.get("lives_here")
    lives = ""
    if lh:
        lives = (f' <a class="liveshere" href="{esc(lh["href"])}">'
                 f'its work already lives here → {esc(lh["label"])}</a>')
    return (f'<div class="toolrow" id="{esc(t["id"])}">'
            f'<div class="toolname">{esc(t.get("long", t["name"]))}'
            f'<span class="tverb">{esc(t["verb"])}</span></div>'
            f'<div class="toolwhy">{esc(t["why_desk"] or t["one"])}{lives}</div>'
            f'</div>')


def page_press(manifest, base, has_kits=False):
    """The press behind the paper — one quiet page where the thirteen doors
    used to shout (specs/20 §5). The civicmedia story in three sentences, the
    tool list as one-line entries (name, verb, the true reason each needs the
    desk), the DMG, and the cross-link to communityai.studio done once.

    `has_kits` flips Publisher's line from "nothing yet" to a cross-link into
    /app/k, but only when this edition actually pressed kits — the door stays
    honest until then (specs/20 §6, §7.9)."""
    def row(t):
        if t["id"] == "publisher" and has_kits:
            return _tool_row(t, {"label": "a publish kit for every meeting",
                                 "href": "/app/k"})
        return _tool_row(t)
    suite = "".join(row(t) for t in tools.community()
                    if t["surface"] != "web")
    bench = "".join(_tool_row(t) for t in tools.workbench())
    body = f"""
  <section class="press">
    <a class="back" href="/app/">← the record</a>
    <h1>The press behind the paper</h1>
    <p class="presslede">The Public Record is the newspaper; <b>Civic Media
      Studio</b> is the press that makes it. The Studio is a desktop suite that
      fetches, transcribes, translates, describes and cuts civic video on your
      own machine — your files, your GPU, nothing uploaded. Everything those
      tools produce that can be <em>read</em> already lives here on the record;
      the tools themselves stay at the desk, because they touch local media and
      local compute — and below, for each one, is why.</p>
    <div class="sectionhead"><span class="kicker">the civic media suite</span></div>
    <div class="toollist">{suite}</div>
    <div class="sectionhead"><span class="kicker">control-z — the finishing tools</span></div>
    <div class="toollist">{bench}</div>
    <div class="presscta">
      <a class="btn primary" href="{DMG_LATEST}">Get the desktop app — macOS</a>
      <span class="hint">macOS 12+ · Apple silicon · signed &amp; notarized</span>
    </div>
    <p class="hint">Civic Media Studio and The Public Record are
      <a href="{COMMUNITYAI}">a Community AI Project</a> — {CREDIT}.</p>
  </section>
"""
    return shell("The press — publicrecord.studio",
                 "Civic Media Studio, the desktop press that makes the record: "
                 "what each tool does, and why it lives at the desk.",
                 f"{base}/app/press", body, "press", manifest,
                 version=manifest["version"])


def page_door_stub(t, manifest, base):
    """A citation must never die (specs/20 §5). Every /app/t/<tool>/ URL the
    old doors answered survives as a slim redirect into /app/press#<tool> — a
    meta-refresh (CSP-safe, no inline script) with a real link underneath for
    the reader whose browser honours neither. No slide, no site/ asset, nothing
    to break."""
    dest = f"/app/press#{esc(t['id'])}"
    name = esc(t.get("long", t["name"]))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp()}">
<meta http-equiv="refresh" content="0; url={dest}">
<title>{name} — the press · publicrecord.studio</title>
<meta name="description" content="{name} is a desk tool; its page is on the press.">
<link rel="canonical" href="{esc(base)}/app/press#{esc(t['id'])}">
<link rel="stylesheet" href="/app/app.css?v={esc(manifest['version'])}">
</head><body>
<main class="main paper"><section class="press">
  <h1>{name}</h1>
  <p class="presslede">{name} is a desk tool. Its page is now part of
    <a href="{dest}">the press</a> — you are being redirected there.</p>
</section></main>
</body></html>"""


# --------------------------------------------------------------------------
# assets + orchestration
# --------------------------------------------------------------------------

_VAR_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

# The two critical first-paint faces (body + headline) preloaded in <head>; the
# rest swap in. font-display:swap means the system stack is the visible
# fallback, never a blank. CSP stays font-src 'self' — every byte is ours.
_FONTS = [("Inter", 400, "inter-400"), ("Inter", 500, "inter-500"),
          ("Inter", 700, "inter-700"),
          ("JetBrains Mono", 400, "jetbrains-mono-400"),
          ("JetBrains Mono", 700, "jetbrains-mono-700"),
          ("JetBrains Mono", 800, "jetbrains-mono-800")]
_PRELOAD_FONTS = ["inter-400", "jetbrains-mono-700"]
_FONT_FACES = "".join(
    f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{w};"
    f"font-display:swap;src:url('/app/fonts/{file}.woff2') format('woff2');}}"
    for fam, w, file in _FONTS)


def _brand_vars(name) -> dict:
    """Parse a brand token file into {var: value}, resolving one level of
    var() references within the same file. brand/ is the single source for the
    record's face (specs/20 §8) — values are read, never re-typed."""
    text = _COMMENT_RE.sub("", (BRAND / "tokens" / name).read_text(encoding="utf-8"))
    raw = {m.group(1): m.group(2).strip() for m in _VAR_RE.finditer(text)}
    def deref(v):
        m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", v)
        return raw.get(m.group(1), v) if m else v
    return {k: deref(v) for k, v in raw.items()}


def _brand_inner(name) -> str:
    """The declarations inside a brand :root block, comments stripped — used
    verbatim for the type and spacing scales (no colour lives there)."""
    text = _COMMENT_RE.sub("", (BRAND / "tokens" / name).read_text(encoding="utf-8"))
    return " ".join(f"--{m.group(1)}:{m.group(2).strip()};"
                    for m in _VAR_RE.finditer(text))


def _brand_tokens() -> str:
    """The publicrecord :root — the quiet set, drawn byte-faithfully from
    brand/. This supersedes the desk-token concatenation (specs/20 §8):
    brand/ is the single source for the record's face, and the desk keeps its
    own. Only the neutrals + deep green cross this line. The pop accents
    (fuchsia, purple) and the whole warm desk palette never enter this file —
    publicrecord is the quietest property, and its stylesheet has to prove it:
    no forbidden hex ever appears, not even as an unused variable."""
    c = _brand_vars("colors.css")
    colours = (
        f"--surface-page:{c['offwhite']};--surface-card:{c['white']};"
        f"--surface-inverse:{c['ink']};"
        f"--text-primary:{c['ink']};--text-secondary:{c['slate']};"
        f"--text-muted:{c['slate-soft']};--text-inverse:{c['offwhite']};"
        f"--border-hairline:{c['border-hairline']};--border-strong:{c['slate-soft']};"
        # the accent, and the whole accent (deep green); emerald is state only
        f"--accent:{c['green-deep']};--state:{c['green-emerald']};"
        # measurement tints (green scale) — backgrounds in graphics only. The
        # two lightest (green-50/100) are named in specs/20 §4; the two brighter
        # come straight from brand (green-soft, green-bright).
        f"--tint-1:#f0fdf4;--tint-2:#dcfce7;"
        f"--tint-3:{c['green-soft']};--tint-4:{c['green-bright']};")
    return (":root{" + colours + _brand_inner("typography.css") + " "
            + _brand_inner("spacing.css") + "}")


def emit_assets(out: Path, version, manifest):
    (out / "assets").mkdir(parents=True, exist_ok=True)
    # app.css = publicrecord's own tokens (from brand/) + the self-hosted
    # @font-face block + the web rules. No desk tokens, no third-party fonts.
    web_css = (Path(__file__).resolve().parent / "static" / "app.web.css").read_text(encoding="utf-8")
    (out / "app.css").write_text(
        _brand_tokens() + "\n" + _FONT_FACES + "\n\n" + web_css, encoding="utf-8")
    # app.js (the reader)
    shutil.copyfile(Path(__file__).resolve().parent / "static" / "app.js",
                    out / "app.js")
    # the self-hosted faces (subset latin woff2, vendored with their OFL texts)
    fonts_src = Path(__file__).resolve().parent / "static" / "fonts"
    if fonts_src.is_dir():
        shutil.copytree(fonts_src, out / "fonts", dirs_exist_ok=True)
    # favicon — the publicrecord keycap, byte-equal from brand/logos (never
    # redrawn); the mark must survive as a favicon and this is where it does.
    (out / "favicon.svg").write_text(_brand_mark(), encoding="utf-8")
    # PWA: the web-app manifest (a DIFFERENT file from the edition manifest.json)
    # + a service worker. Both deterministic — the SW's cache name rides the
    # corpus fingerprint so a new pressing supersedes the old cache cleanly.
    _write_pwa(out, manifest)


def _write_pwa(out: Path, manifest):
    import json as _json
    webmanifest = {
        "name": "The Public Record — publicrecord.studio",
        "short_name": "the record",
        "description": "A town's whole spoken life, cross-linked and searchable "
                       "— open in any browser.",
        "start_url": "/app/", "scope": "/app/", "display": "standalone",
        "background_color": "#f8fafc", "theme_color": "#f8fafc",
        "icons": [{"src": "/app/favicon.svg", "sizes": "any",
                   "type": "image/svg+xml"}],
    }
    (out / "manifest.webmanifest").write_text(
        _json.dumps(webmanifest, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")), encoding="utf-8")
    # the service worker: precache the shell, cache-first for the edition, and
    # tell the page when a fresher pressing has been fetched. Cache name = the
    # corpus fingerprint, so a new edition's SW owns a new cache and sweeps the
    # old one on activate. No wall-clock anywhere (idempotence).
    # cache name keys on BOTH the version and the corpus fingerprint: a new
    # pressing (corpus change) OR a new release (statics/pages change, which
    # always bumps the version) supersedes the old cache, so a returning reader
    # never sees a stale shell after an edition ships.
    cache = f"cz-record-{manifest.get('version','0')}-{manifest.get('corpus_hash','0')}"
    v = esc(manifest.get("version", "0"))
    shell_urls = _json.dumps([
        "/app/", f"/app/app.css?v={manifest.get('version','0')}",
        f"/app/app.js?v={manifest.get('version','0')}", "/app/favicon.svg",
        "/app/manifest.json", "/app/stats.json", "/app/s", "/app/watching",
        "/app/officials"], separators=(",", ":"))
    sw = f"""'use strict';
// the record's service worker — precache the shell, keep last-read meetings,
// and let the page announce a fresher pressing. Cache name is the corpus
// fingerprint (deterministic; a new edition = a new cache).
const CACHE = {cache!r};
const SHELL = {shell_urls};
self.addEventListener('install', e => {{
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
}});
self.addEventListener('activate', e => {{
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== CACHE && k.indexOf('cz-record-') === 0).map(k => caches.delete(k))
  )).then(() => self.clients.claim()));
}});
self.addEventListener('fetch', e => {{
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || url.pathname.indexOf('/app/') !== 0) return;
  // cache-first: the edition is immutable within a pressing; the shell and any
  // meeting you've read stay available offline.
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {{
    if (res && res.ok && res.type === 'basic') {{
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy));
    }}
    return res;
  }}).catch(() => hit)));
}});
"""
    (out / "sw.js").write_text(sw, encoding="utf-8")


def emit_stubs(out, meetings, issues, stats, manifest, base, officials=None,
               analytics=None, graph=None, towns=None, tombstones=None,
               kits=None):
    v = manifest["version"]
    # before a single stub renders: the chrome needs to know what it may offer
    set_edition(towns)
    (out / "index.html").write_text(page_home(meetings, issues, stats, manifest, base), encoding="utf-8")
    (out / "s" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "s" / "index.html").write_text(page_search(manifest, base), encoding="utf-8")
    (out / "add" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "add" / "index.html").write_text(page_add(manifest, base), encoding="utf-8")
    (out / "covenant" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "covenant" / "index.html").write_text(page_covenant(manifest, base), encoding="utf-8")
    (out / "watching" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "watching" / "index.html").write_text(page_still(manifest, base), encoding="utf-8")
    (out / "officials" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "officials" / "index.html").write_text(
        page_officials(officials or [], manifest, base), encoding="utf-8")
    (out / "analytics" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "analytics" / "index.html").write_text(
        page_analytics(analytics or {}, manifest, base), encoding="utf-8")
    (out / "graph" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "graph" / "index.html").write_text(
        page_graph(graph or {}, manifest, base), encoding="utf-8")
    # the press page — the one place the thirteen doors now lead. Publisher's
    # line points at the kits only when this edition pressed some.
    kits = kits or []
    (out / "press" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "press" / "index.html").write_text(
        page_press(manifest, base, has_kits=bool(kits)), encoding="utf-8")
    # the reel viewer — one static stub; the reel itself lives in the link
    (out / "r" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "r" / "index.html").write_text(
        page_reel(manifest, base), encoding="utf-8")
    # the kits — Publisher's reading half (specs/20 §6, §7.9 P2). An index, and
    # a read-only page per meeting whose kit the bake pressed. The downloadable
    # kit.json is the plane the bake already wrote at /app/kits/<slug>.json.
    (out / "k" / "index.html").parent.mkdir(parents=True, exist_ok=True)
    (out / "k" / "index.html").write_text(
        page_kits_index(kits, manifest, base), encoding="utf-8")
    for kit in kits:
        d = out / "k" / kit["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_kit(kit, manifest, base), encoding="utf-8")
    for m in meetings:
        d = out / "m" / m["pid"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_meeting(m, manifest, base), encoding="utf-8")
        (d / "transcript.txt").write_text(page_meeting_txt(m), encoding="utf-8")
    for i in issues:
        d = out / "i" / i["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_issue(i, manifest, base), encoding="utf-8")
    # tombstones — a forgotten issue's URL explains itself, never 404s. Written
    # after the live issues so a live issue always wins a shared slug.
    for t in (tombstones or []):
        d = out / "i" / t["slug"]
        if (d / "index.html").exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page_tombstone(t["slug"], t["name"], t["date"], manifest, base),
            encoding="utf-8")
    # the thirteen door URLs survive as slim redirect stubs into /app/press
    for t in tools.TOOLS:
        if t["surface"] != "web":
            d = out / "t" / t["id"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(
                page_door_stub(t, manifest, base), encoding="utf-8")
