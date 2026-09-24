"""yt-dlp, managed: the nightly binary Highlighter and Grabber share.

The suite doesn't vendor yt-dlp — sites change weekly and a pinned copy rots,
so the fetch tools run the official **nightly** build and check for a newer
one every time their page opens (a cheap GitHub API call, rate-limited to
once a minute here). The binary lives in app support, its version and last
check are recorded beside it, and being offline is reported as a sentence —
the tool keeps working with whatever build it already has.

This is the suite's one deliberate network surface besides model downloads:
user-initiated fetches of public video. Nothing here phones home about you.
"""

from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .paths import support_dir

NIGHTLY_API = ("https://api.github.com/repos/yt-dlp/"
               "yt-dlp-nightly-builds/releases/latest")

# quality presets the UIs offer — every one merges to mp4 for edit-friendliness
# h264+m4a preferred at every rung — the codecs that decode EVERYWHERE
# (QuickTime, playout servers, and the suite's own PyAV frame service,
# which has no AV1 decoder). ext=mp4 alone is not enough: YouTube ships
# AV1 in mp4 too. Fall through to any mp4, then anything; the remux flag
# in download() keeps the container promise on the fallbacks, losslessly.
def _rung(h: str = "") -> str:
    # <=? — a format whose height yt-dlp doesn't know (a bare .mp4 link)
    # passes the cap instead of failing every rung with "Requested format
    # is not available"
    lim = f"[height<=?{h}]" if h else ""
    return (f"bv*{lim}[vcodec^=avc1]+ba[ext=m4a]/"
            f"bv*{lim}[ext=mp4]+ba[ext=m4a]/"
            f"bv*{lim}+ba/b{lim}")


FORMATS = {
    "best": _rung(),
    "2160": _rung("2160"),
    "1440": _rung("1440"),
    "1080": _rung("1080"),
    "720": _rung("720"),
    "480": _rung("480"),
    "audio": "ba[ext=m4a]/ba/b",
}

_lock = threading.Lock()
_state = {"phase": "idle", "detail": "", "checked_at": 0.0}
_CHECK_COOLDOWN = 60.0  # rapid page flips shouldn't hammer GitHub


def asset_name(platform: str = sys.platform, machine: str = "") -> str:
    """Which nightly release asset runs on this box."""
    if platform == "darwin":
        return "yt-dlp_macos"
    if platform.startswith("win"):
        return "yt-dlp.exe"
    if machine in ("aarch64", "arm64"):
        return "yt-dlp_linux_aarch64"
    return "yt-dlp_linux"


def binary_path() -> Path:
    return support_dir("bin") / asset_name()


def _meta_path() -> Path:
    return support_dir("bin") / "yt-dlp.meta.json"


def installed_version() -> Optional[str]:
    try:
        return json.loads(_meta_path().read_text()).get("version") or None
    except (OSError, ValueError):
        return None


def newer(latest: str, installed: Optional[str]) -> bool:
    """Nightly tags are dotted datestamps (2026.07.15.232840) — numeric
    field-by-field compare, so 2026.7.9 vs 2026.07.15 orders correctly."""
    if not installed:
        return True

    def parts(v: str):
        return [int(x) for x in re.findall(r"\d+", v)]

    return parts(latest) > parts(installed)


def status() -> dict:
    """What the tool pages show: version, freshness, any check in flight,
    whether fetches ride a proxy, and which JavaScript runtime (if any)
    yt-dlp can use for YouTube's player challenges."""
    from . import proxy as _proxy

    with _lock:
        s = dict(_state)
    s["installed"] = installed_version()
    s["present"] = binary_path().exists()
    s["proxy"] = _proxy.status()
    rt = js_runtime()
    s["js_runtime"] = ({"name": rt[0], "path": rt[1]} if rt else None)
    try:
        s["checked_at"] = json.loads(_meta_path().read_text()).get("checked_at", 0)
    except (OSError, ValueError):
        pass
    return s


# -- the JavaScript runtime YouTube's player now requires ---------------------
#
# yt-dlp solves YouTube's signature/n challenges by running the player's own
# JavaScript (yt-dlp's EJS). It enables only Deno by default and looks for it
# on PATH — but an app launched from Finder gets PATH=/usr/bin:/bin, so even
# an installed Node or Deno is invisible. Without one, YouTube hands out a
# thinner format list ("some formats may be missing", measured). We look in
# the usual install spots and name the runtime explicitly.

_JS_CANDIDATES = (
    ("deno", "bin/deno"),                        # managed copy (app support)
    ("deno", "~/.deno/bin/deno"),
    ("deno", "/opt/homebrew/bin/deno"),
    ("deno", "/usr/local/bin/deno"),
    ("node", "/opt/homebrew/bin/node"),
    ("node", "/usr/local/bin/node"),
    ("bun", "~/.bun/bin/bun"),
    ("bun", "/opt/homebrew/bin/bun"),
)


def deno_path() -> Path:
    """Where the Settings → optional runtimes installer puts Deno."""
    return support_dir("bin") / "deno"


def js_runtime() -> Optional[tuple]:
    """(name, path) of the first usable JS runtime, or None."""
    import os
    import shutil

    for name, cand in _JS_CANDIDATES:
        p = deno_path() if cand == "bin/deno" else Path(cand).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return name, str(p)
    for name in ("deno", "node", "bun"):
        hit = shutil.which(name)
        if hit:
            return name, hit
    return None


def _js_args() -> list:
    rt = js_runtime()
    return ["--js-runtimes", f"{rt[0]}:{rt[1]}"] if rt else []


# -- "YouTube is refusing this computer" ---------------------------------------

_BLOCKED = re.compile(
    r"429|too many requests|not a bot|confirm you.re not|sign in to confirm|"
    r"rate.?limit|http error 403|unusual traffic|flagged this address",
    re.I)


def looks_blocked(text: str) -> bool:
    """True when a failure reads like YouTube refusing THIS address — the
    one case where turning on the proxy is the fix."""
    return bool(_BLOCKED.search(text or ""))


def _explain(why: str) -> str:
    """yt-dlp's last ERROR line, plus the fix when the fix is the proxy."""
    why = why.strip()[:300]
    if looks_blocked(why):
        why += (" — YouTube is limiting this computer. Turn on the proxy "
                "(the switch on this page) and try again.")
    return why


def _fetch_json(url: str, timeout: float = 8.0) -> dict:
    from urllib.request import Request, urlopen

    req = Request(url, headers={"User-Agent": "control-z-suite",
                                "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: Path, on_note: Callable[[str], None]):
    from urllib.request import Request, urlopen

    tmp = dest.with_suffix(".part")
    req = Request(url, headers={"User-Agent": "control-z-suite"})
    with urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                on_note(f"downloading yt-dlp nightly… {got * 100 // total}%")
    tmp.chmod(tmp.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)  # atomic: a running download never sees half a binary


def _check_and_update():
    def note(detail, phase=None):
        with _lock:
            _state["detail"] = detail
            if phase:
                _state["phase"] = phase

    try:
        note("checking for tonight's build…", "checking")
        rel = _fetch_json(NIGHTLY_API)
        latest = str(rel.get("tag_name", "")).strip()
        want = asset_name(machine=__import__("platform").machine().lower())
        asset = next((a for a in rel.get("assets", [])
                      if a.get("name") == want), None)
        if not latest or asset is None:
            note(f"nightly feed had no build for this platform ({want})", "error")
            return
        if newer(latest, installed_version()) or not binary_path().exists():
            note(f"updating to nightly {latest}…", "updating")
            _download(asset["browser_download_url"], binary_path(), note)
            note(f"yt-dlp nightly {latest} ready", "ok")
        else:
            note(f"yt-dlp nightly {latest} — already current", "ok")
        _meta_path().write_text(json.dumps(
            {"version": latest, "checked_at": time.time()}))
    except Exception as e:
        # offline is a state, not a failure — say so and keep the old binary
        have = installed_version()
        kept = f" — keeping {have}" if have else ""
        note(f"couldn't reach the nightly feed ({e.__class__.__name__}){kept}",
             "error")


def check_async(force: bool = False) -> dict:
    """Kick a nightly check unless one just ran; returns current status.

    Called every time a fetch tool's page opens — that's the deal the UI
    states out loud. The check runs on its own thread so a queued render
    never waits behind a version ping.
    """
    with _lock:
        busy = _state["phase"] in ("checking", "updating")
        recent = (time.time() - _state["checked_at"]) < _CHECK_COOLDOWN
        if not busy and (force or not recent):
            _state["phase"] = "checking"
            _state["detail"] = "checking for tonight's build…"
            _state["checked_at"] = time.time()
            threading.Thread(target=_check_and_update, daemon=True).start()
    return status()


def _proxy_args() -> list:
    """--proxy for every YouTube-facing call when the user configured one.
    The nightly self-update never uses it — that's GitHub, not YouTube."""
    from . import proxy as _proxy

    url = _proxy.proxy_url()
    return ["--proxy", url] if url else []


def _run_json(args: list, timeout: float = 60.0):
    """yt-dlp -J … -> parsed JSON (one object per line for playlists)."""
    exe = binary_path()
    if not exe.exists():
        raise RuntimeError(
            "yt-dlp isn't installed yet — open the page once with the network "
            "up (the nightly check installs it), then retry.")
    try:
        out = subprocess.run([str(exe), *_js_args()] + args,
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp didn't answer within {int(timeout)}s — "
                           "YouTube may be slow or limiting this computer; "
                           "try again") from None
    if out.returncode != 0:
        why = next((ln for ln in reversed(out.stderr.splitlines())
                    if "ERROR" in ln), out.stderr.strip()[-300:])
        raise RuntimeError(f"yt-dlp couldn't read that — {_explain(why)}")
    return [json.loads(ln) for ln in out.stdout.splitlines() if ln.strip()]


def probe_url(url: str) -> dict:
    """Metadata without downloading a byte of video: title, duration,
    uploader, and whether captions exist to seed a transcript from."""
    rows = _run_json(["-J", "--skip-download", "--no-playlist", *_proxy_args(), url])
    if not rows:
        raise RuntimeError("that URL answered with no metadata")
    d = rows[0]
    subs = set(d.get("subtitles") or {}) | set(d.get("automatic_captions") or {})
    return {"id": d.get("id"), "title": d.get("title"),
            "duration": d.get("duration"),
            "uploader": d.get("uploader") or d.get("channel"),
            "upload_date": d.get("upload_date"),
            "url": d.get("webpage_url") or url,
            "captions": any(l == "en" or str(l).startswith("en") for l in subs),
            "extractor": d.get("extractor_key"),
            "live": bool(d.get("is_live")),
            "options": quality_options(d),
            # the tallest it exists in ANY codec — the chooser says so when
            # that's above the h264 ladder (VP9/AV1-only 4K, say)
            "max_height": max((f.get("height") or 0 for f in d.get("formats") or []
                               if _has_video(f)), default=0)}


# -- what a video really offers: the ladder, resolved --------------------------

_LADDER = ("480", "720", "1080", "1440", "2160")


def _has_video(f: dict) -> bool:
    return f.get("vcodec") != "none"     # None = unknown = maybe, as yt-dlp reads it


def _has_audio(f: dict) -> bool:
    return f.get("acodec") != "none"


def _size(f: dict, duration) -> Optional[int]:
    n = f.get("filesize") or f.get("filesize_approx")
    if n:
        return int(n)
    if f.get("tbr") and duration:
        return int(f["tbr"] * 1000 / 8 * duration)     # tbr is kbit/s
    return None


def _vbest(c: list) -> dict:
    # yt-dlp's own order for these fields: resolution, frame rate, then a
    # KNOWN size beats an unknown one — which is why YouTube's plain https
    # 1080p (sized) wins over its HLS twin (unsized, higher bitrate)
    return max(c, key=lambda f: (f.get("height") or 0, f.get("fps") or 0,
                                 f.get("filesize") or f.get("filesize_approx") or -1,
                                 f.get("tbr") or 0))


def _abest(c: list) -> dict:
    # the original-language track first (a dubbed video lists one per language)
    return max(c, key=lambda f: (f.get("language_preference") or 0,
                                 f.get("abr") or f.get("tbr") or 0))


def _pick(fmts: list, cap: Optional[int]):
    """_rung(cap)'s selector, replayed on a probed format list → the
    (video, audio) formats yt-dlp would take; audio is None when the video
    carries its own. Close to yt-dlp's sort, not identical — this is for
    labels and sizes, never for choosing the download."""
    vids = [f for f in fmts if _has_video(f)
            and (cap is None or f.get("height") is None or f["height"] <= cap)]
    auds = [f for f in fmts if _has_audio(f) and not _has_video(f)]
    m4a = [f for f in auds if f.get("ext") == "m4a"]
    for want, pool in ((lambda f: str(f.get("vcodec") or "").startswith("avc1"), m4a),
                       (lambda f: f.get("ext") == "mp4", m4a),
                       (lambda f: True, auds)):
        c = [f for f in vids if want(f)]
        if c and pool:
            return _vbest(c), _abest(pool)
    both = [f for f in vids if _has_audio(f)]     # b[height<=?cap]
    return (_vbest(both), None) if both else (None, None)


def quality_options(info: dict) -> list:
    """The rungs this video really offers, resolved the way download() will
    take them: [{quality, label, height, bytes}], best first, then audio
    only. Rungs that land on the same file collapse to one — the ladder
    prefers h264 (it plays everywhere) and YouTube serves h264 to 1080p at
    most, so "4K" usually IS 1080p here; the chooser says so instead of
    promising it. bytes is an estimate, or None when the site won't say."""
    fmts = [f for f in (info.get("formats") or [])
            if _has_video(f) or _has_audio(f)]          # drops storyboards
    dur = info.get("duration")
    seen, out = set(), []
    for q in (*_LADDER, "best"):
        v, a = _pick(fmts, int(q) if q != "best" else None)
        if not v:
            continue
        sig = (v.get("format_id"), (a or {}).get("format_id"))
        if sig in seen:
            continue
        seen.add(sig)
        h, fps = v.get("height"), v.get("fps") or 0
        parts = [_size(v, dur)] + ([_size(a, dur)] if a else [])
        out.append({"quality": q if h else "best",
                    "label": (f"{h}p" + (str(round(fps)) if fps > 30 else ""))
                             if h else "as published",
                    "height": h or 0,
                    "bytes": None if None in parts else sum(parts)})
    out.reverse()
    auds = [f for f in fmts if _has_audio(f) and not _has_video(f)]
    if auds:                                      # ba[ext=m4a]/ba
        a = _abest([f for f in auds if f.get("ext") == "m4a"] or auds)
        out.append({"quality": "audio", "label": "audio only", "height": 0,
                    "bytes": _size(a, dur)})
    return out


def fetch_captions(url: str, outdir: Path) -> dict:
    """Captions + info json only — the transcript arrives before any video.
    Returns {"vtt": path|None, "info": path|None, "id": video id}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    exe = binary_path()
    if not exe.exists():
        raise RuntimeError("yt-dlp isn't installed yet — the nightly check "
                           "installs it on page open; get online once.")
    try:
        out = subprocess.run(
            [str(exe), url, *_js_args(), "--skip-download", "--no-playlist",
             *_proxy_args(), "--ignore-errors",
             "--write-info-json", "--write-subs", "--write-auto-subs",
             # ONE track: "en,en-orig" fetched the same auto-captions twice
             # and doubled the requests YouTube's 429 limiter counts
             "--sub-langs", "en", "--sub-format", "vtt/srt",
             "-o", str(outdir / "meeting.%(ext)s"),
             "--print", "id"],
            capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError("couldn't fetch captions — yt-dlp didn't finish "
                           "within 2 minutes") from None
    vid = next((ln.strip() for ln in out.stdout.splitlines() if ln.strip()), "")
    vtt = next((p for p in sorted(outdir.iterdir())
                if p.suffix in (".vtt", ".srt")), None)
    info = outdir / "meeting.info.json"
    if not vtt:
        why = next((ln for ln in reversed(out.stderr.splitlines())
                    if "ERROR" in ln or "WARNING: Unable to download" in ln),
                   "")
        raise RuntimeError("couldn't fetch captions — "
                           f"{_explain(why) if why else 'none came'}")
    return {"vtt": str(vtt) if vtt else None,
            "info": str(info) if info.exists() else None, "id": vid}


def sidecar_captions(url: str, video: Path) -> dict:
    """Captions for a video that already landed, written beside it as
    `<stem>.en.vtt` — the words Highlighter reads first.

    Deliberately a SECOND pass: yt-dlp fetches subtitles before the video
    and aborts the whole download when a subtitle request 429s (YouTube
    rate-limits its caption endpoint far harder than its video CDN) — the
    grabber's "Unable to download video subtitles … 429" was a lost VIDEO,
    not lost captions. Now the video is safe first, and captions are a
    best effort that never fails the fetch.

    Returns {"captions": "fetched" | "none" | "failed", "note": sentence,
             "blocked": bool, "path": str | None}.
    """
    from . import captions as ct
    from . import proxy as _proxy

    video = Path(video)
    dest = video.with_name(video.stem + ".en.vtt")
    if dest.exists():
        return {"captions": "fetched", "note": "captions already beside it",
                "blocked": False, "path": str(dest)}
    if ct.video_id(url):
        try:
            got = ct.fetch_vtt(url, proxy=_proxy.proxy_url())
            dest.write_text(got["vtt"])
            return {"captions": "fetched", "path": str(dest), "blocked": False,
                    "note": f"captions via YouTube's {got.get('route')}"}
        except ct.CaptionError as e:
            if e.kind == "no_captions":
                return {"captions": "none", "note": str(e), "blocked": False,
                        "path": None}
            first = e
        except Exception as e:           # never let captions fail a fetch
            first = ct.CaptionError(str(e))
    else:
        first = None
    # other sites (Vimeo, Zoom portals…) — yt-dlp knows their captions
    try:
        with __import__("tempfile").TemporaryDirectory(prefix="cz-subs-") as td:
            got = fetch_captions(url, Path(td))
            if got.get("vtt"):
                src = Path(got["vtt"])
                dest = video.with_name(video.stem + ".en" + src.suffix)
                dest.write_text(src.read_text(errors="replace"))
                return {"captions": "fetched", "path": str(dest),
                        "blocked": False, "note": "captions via yt-dlp"}
    except Exception as e:
        why = str(first or e)
        return {"captions": "failed", "path": None,
                "blocked": bool(getattr(first, "blocked", False))
                or looks_blocked(str(e)),
                "note": why[:300]}
    return {"captions": "none", "path": None, "blocked": False,
            "note": str(first) if first else "no captions offered"}


def search(query: str, n: int = 12, newest: bool = False) -> list:
    """YouTube search through yt-dlp itself — no API key, flat and fast.

    newest=True asks YouTube's own date-sorted results page (sp=CAI=) —
    the civic finder's default, where "brookline" should mean the town's
    LATEST meetings, not a smattering of its year. (The ytsearchdate
    prefix died in the 2026.07 nightlies; the results URL is the door
    that stays open. YouTube's date sort is bucketed, not strict — the
    newest leads, neighbors may swap.)"""
    n = max(1, min(30, n))
    if newest:
        from urllib.parse import quote_plus
        target = ("https://www.youtube.com/results?search_query="
                  + quote_plus(query) + "&sp=CAI%3D")
        args = ["-J", "--flat-playlist", "--playlist-end", str(n),
                "--extractor-args", "youtubetab:approximate_date",
                *_proxy_args(), target]
    else:
        args = ["-J", "--flat-playlist", *_proxy_args(),
                f"ytsearch{n}:{query}"]
    rows = _run_json(args, timeout=45)
    entries = (rows[0].get("entries") or []) if rows else []
    return [{"id": e.get("id"), "title": e.get("title"),
             "duration": e.get("duration"),
             "uploader": e.get("uploader") or e.get("channel"),
             "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
             "views": e.get("view_count"),
             "date": e.get("upload_date")} for e in entries if is_video(e)]


def is_video(e: dict) -> bool:
    """A search row that is one video. YouTube's results page mixes in
    CHANNELS and playlists (a town's name surfaces its station's channel
    first — measured: "brookline select board" led with the BIG channel),
    and a channel row handed to Load crawls the whole channel for 2
    minutes and reads nothing."""
    vid = str(e.get("id") or "")
    url = str(e.get("url") or "")
    if e.get("ie_key") in ("YoutubeTab", "YoutubePlaylist"):
        return False
    if "/channel/" in url or "/playlist" in url or "/@" in url:
        return False
    return bool(re.fullmatch(r"[\w-]{11}", vid))


_PROG = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


def _cancel_watch(proc, cancelled) -> threading.Event:
    """Poll the job's cancel flag on its own thread and stop the whole
    process group the moment it flips — yt-dlp can go quiet for minutes
    (an ffmpeg merge prints nothing), and a cancel checked only between
    output lines waited for the next one. Returns an Event: set = the run
    was cancelled (or has finished and the watcher should retire)."""
    import os
    import signal

    ev = threading.Event()
    if cancelled is None:
        return ev

    def watch():
        while proc.poll() is None and not ev.is_set():
            if cancelled():
                ev.set()
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        pass
                return
            time.sleep(0.4)

    threading.Thread(target=watch, daemon=True).start()
    return ev


def _sweep_partials(outdir: Path, since: float, vid: str = ""):
    """A cancelled fetch leaves nothing behind: yt-dlp's .part/.ytdl
    fragments and half-merged temp files from THIS run are removed.

    Scoped to THIS video: every name yt-dlp writes carries its "[id]"
    (the output template says so), and only files with that tag and a
    timestamp inside the run are touched — the Downloads folder can be a
    shared place (a browser's .part files live there too). No id known
    (cancelled before extraction finished) → nothing was written → nothing
    to sweep."""
    if not vid:
        return
    tag = f"[{vid}]"
    files = [f for f in Path(outdir).iterdir() if tag in f.name]
    for f in files:
        name = f.name
        # .fNNN.ext = one format stream waiting for the merge
        partial = (f.suffix in (".part", ".ytdl") or ".part-Frag" in name
                   or ".temp." in name or re.search(r"\.f\d+\.\w+$", name))
        try:
            if partial and f.is_file() and f.stat().st_mtime >= since - 1:
                f.unlink()
        except OSError:
            pass
    # the info.json this run wrote for a video that never landed
    for f in files:
        if not f.name.endswith(".info.json"):
            continue
        stem = f.name[:-len(".info.json")]
        try:
            landed = any(g.name.startswith(stem + ".") and g.suffix.lower()
                         in (".mp4", ".m4a", ".mkv", ".webm", ".mov")
                         and g.exists() for g in files)
            if not landed and f.stat().st_mtime >= since - 1:
                f.unlink()
        except OSError:
            pass


def download(url: str, outdir: Path, quality: str = "best",
             progress: Optional[Callable[[float, str], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None,
             extra_args: Optional[list] = None,
             sections: Optional[list] = None) -> dict:
    """Fetch one video (YouTube, Zoom, direct file — yt-dlp's thousand sites).

    sections: [(start_s, end_s), …] downloads ONLY those spans — each lands
    as its own file (named with the span) instead of the whole meeting.
    Returns {"path": final file, "paths": all files, "sidecars": […]}.
    """
    exe = binary_path()
    if not exe.exists():
        raise RuntimeError(
            "yt-dlp isn't installed yet — open the page once with the network "
            "up (the nightly check installs it), then retry.")
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    template = "%(title).120B [%(id)s].%(ext)s"
    # NO subtitles here. yt-dlp writes subtitles BEFORE the video and a
    # caption 429 aborts the whole fetch ("Unable to download video
    # subtitles for 'en': HTTP Error 429" = no video at all). Captions are
    # sidecar_captions()'s job, after the video is safely on disk.
    cmd = [str(exe), url, *_js_args(), *_proxy_args(),
           "-f", FORMATS.get(quality, quality),
           # --print (below) silently implies --quiet, which swallowed every
           # progress line: fetches sat at "running" with no percentage.
           # --progress brings the bar back under --quiet.
           "--newline", "--progress", "--no-playlist",
           "--merge-output-format", "mp4",
           # a single-file download never merges, so the merge flag alone
           # can't keep the container promise — remux catches it, lossless
           "--remux-video", "m4a" if quality == "audio" else "mp4",
           "--write-info-json",
           "--no-write-subs", "--no-write-auto-subs",
           # the id, announced before a byte lands — a cancel sweeps only
           # files tagged with it (see _sweep_partials)
           "--no-simulate", "--print", "video:__CZID__%(id)s",
           "--print", "after_move:filepath"]
    for a, b in (sections or []):
        cmd += ["--download-sections", f"*{float(a):.1f}-{float(b):.1f}"]
    if sections:
        # each span is its own clip; keyframe cuts so the files start clean
        template = ("%(title).100B [%(id)s]"
                    " [%(section_start)d-%(section_end)d].%(ext)s")
        cmd += ["--force-keyframes-at-cuts"]
    cmd += ["-o", str(outdir / template)]
    cmd += list(extra_args or [])
    t0 = time.time()
    # its own process group: yt-dlp runs ffmpeg as a CHILD for the merge,
    # and a cancel has to stop both — terminating yt-dlp alone orphaned a
    # merge that kept writing after the queue said "cancelled"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                            start_new_session=True)
    stop = _cancel_watch(proc, cancelled)
    finals, tail, vid = [], [], ""
    for line in proc.stdout:
        line = line.rstrip("\n")
        if stop.is_set():
            break
        if line.startswith("__CZID__"):
            vid = line[len("__CZID__"):].strip()
            continue
        m = _PROG.search(line)
        if m and progress:
            progress(float(m.group(1)) / 100.0, line.split("]", 1)[-1].strip())
        elif line.startswith("/") or re.match(r"^[A-Za-z]:\\", line):
            finals.append(line.strip())  # --print after_move:filepath, per file
        elif line:
            tail.append(line)
            if progress and line.startswith("["):
                progress(-1, line[:140])
    code = proc.wait()
    if stop.is_set():
        _sweep_partials(outdir, t0, vid)
        from .appshell.jobs import JobCancelled
        raise JobCancelled()
    stop.set()                           # the watcher thread can retire
    finals = [f for f in finals if Path(f).exists()]
    if not finals:
        why = next((t for t in reversed(tail) if "ERROR" in t), tail[-1] if tail else "")
        raise RuntimeError("yt-dlp couldn't fetch this — "
                           f"{_explain(why) if why else f'exit {code}'}")
    p = Path(finals[-1])
    # startswith, not glob: yt-dlp names carry "[id]", which glob reads as a
    # character class and never matches
    stem0 = Path(finals[0]).stem.split(" [")[0]
    sidecars = [str(s) for s in p.parent.iterdir()
                if str(s) not in finals and s.name.startswith(stem0)
                and s.suffix in (".json", ".vtt", ".srt")]
    return {"path": str(p), "paths": finals, "sidecars": sidecars}
