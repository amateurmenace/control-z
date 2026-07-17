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
FORMATS = {
    "best": "bv*+ba/b",
    "1080": "bv*[height<=1080]+ba/b[height<=1080]",
    "720": "bv*[height<=720]+ba/b[height<=720]",
    "audio": "ba/b",
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
    and whether fetches ride the user's Webshare proxy."""
    from . import proxy as _proxy

    with _lock:
        s = dict(_state)
    s["installed"] = installed_version()
    s["present"] = binary_path().exists()
    s["proxy"] = _proxy.status()
    try:
        s["checked_at"] = json.loads(_meta_path().read_text()).get("checked_at", 0)
    except (OSError, ValueError):
        pass
    return s


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
    out = subprocess.run([str(exe)] + args, capture_output=True, text=True,
                         timeout=timeout)
    if out.returncode != 0:
        why = next((ln for ln in reversed(out.stderr.splitlines())
                    if "ERROR" in ln), out.stderr.strip()[-300:])
        raise RuntimeError(f"yt-dlp couldn't read that — {why[:300]}")
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
            "extractor": d.get("extractor_key")}


def fetch_captions(url: str, outdir: Path) -> dict:
    """Captions + info json only — the transcript arrives before any video.
    Returns {"vtt": path|None, "info": path|None, "id": video id}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    exe = binary_path()
    if not exe.exists():
        raise RuntimeError("yt-dlp isn't installed yet — the nightly check "
                           "installs it on page open; get online once.")
    out = subprocess.run(
        [str(exe), url, "--skip-download", "--no-playlist", *_proxy_args(),
         "--write-info-json", "--write-subs", "--write-auto-subs",
         "--sub-langs", "en,en-orig", "--sub-format", "vtt/srt",
         "-o", str(outdir / "meeting.%(ext)s"),
         "--print", "id"],
        capture_output=True, text=True, timeout=120)
    vid = next((ln.strip() for ln in out.stdout.splitlines() if ln.strip()), "")
    vtt = next((p for p in sorted(outdir.iterdir())
                if p.suffix in (".vtt", ".srt")), None)
    info = outdir / "meeting.info.json"
    if out.returncode != 0 and not vtt:
        why = next((ln for ln in reversed(out.stderr.splitlines())
                    if "ERROR" in ln), "")
        raise RuntimeError(f"couldn't fetch captions — {why[:250] or 'no captions'}")
    return {"vtt": str(vtt) if vtt else None,
            "info": str(info) if info.exists() else None, "id": vid}


def search(query: str, n: int = 12) -> list:
    """YouTube search through yt-dlp itself — no API key, flat and fast."""
    rows = _run_json(["-J", "--flat-playlist", *_proxy_args(),
                     f"ytsearch{max(1, min(30, n))}:{query}"], timeout=45)
    entries = (rows[0].get("entries") or []) if rows else []
    return [{"id": e.get("id"), "title": e.get("title"),
             "duration": e.get("duration"),
             "uploader": e.get("uploader") or e.get("channel"),
             "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
             "views": e.get("view_count")} for e in entries if e.get("id")]


_PROG = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


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
    # subtitles: just en + en-orig — asking for en.* pulls every translated
    # variant and trips YouTube's 429 rate limit, killing the whole fetch
    cmd = [str(exe), url, *_proxy_args(),
           "-f", FORMATS.get(quality, quality),
           "--newline", "--no-playlist",
           "--merge-output-format", "mp4",
           "--write-info-json",
           "--write-subs", "--write-auto-subs",
           "--sub-langs", "en,en-orig", "--sub-format", "vtt/srt",
           "--no-simulate", "--print", "after_move:filepath"]
    for a, b in (sections or []):
        cmd += ["--download-sections", f"*{float(a):.1f}-{float(b):.1f}"]
    if sections:
        # each span is its own clip; keyframe cuts so the files start clean
        template = ("%(title).100B [%(id)s]"
                    " [%(section_start)d-%(section_end)d].%(ext)s")
        cmd += ["--force-keyframes-at-cuts", "--no-write-subs",
                "--no-write-auto-subs"]
    cmd += ["-o", str(outdir / template)]
    cmd += list(extra_args or [])
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    finals, tail = [], []
    for line in proc.stdout:
        line = line.rstrip("\n")
        if cancelled and cancelled():
            proc.terminate()
            proc.wait(timeout=10)
            raise RuntimeError("cancelled")
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
    # the video landing is what success means — a failed subtitle fetch after
    # it (rate limits love caption endpoints) must not throw the video away
    finals = [f for f in finals if Path(f).exists()]
    if not finals:
        why = next((t for t in reversed(tail) if "ERROR" in t), tail[-1] if tail else "")
        raise RuntimeError(f"yt-dlp couldn't fetch this — {why[:300] or f'exit {code}'}")
    p = Path(finals[-1])
    # startswith, not glob: yt-dlp names carry "[id]", which glob reads as a
    # character class and never matches
    stem0 = Path(finals[0]).stem.split(" [")[0]
    sidecars = [str(s) for s in p.parent.iterdir()
                if str(s) not in finals and s.name.startswith(stem0)
                and s.suffix in (".json", ".vtt", ".srt")]
    return {"path": str(p), "paths": finals, "sidecars": sidecars}
