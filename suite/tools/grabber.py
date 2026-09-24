"""Video Grabber inside the suite — the search desk for civic media.

One query runs two rooms at once: YouTube (yt-dlp's own search, newest
first — a town's name should mean its latest meetings) and the CivicClerk
portal (events with their video and Zoom links). Fetch and conform are
queue jobs; a paste-in URL downloads directly at any rung of the quality
ladder, always mp4 with audio (audio-only lands m4a). Schedules fetch on
a weekly clock while the app is open and catch up on launch. The
broadcast re-namer takes a download to a playout-safe name — sidecars
travel with it.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from czcore import ytdlp
from czcore.paths import downloads_dir, downloads_root, media_dir, support_dir

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v", ".mpg", ".m4a")


def bin_dirs() -> list:
    """Where the bin lists from: the Downloads folder fetches land in now,
    plus the old ~/Movies/control-z/grabber so nothing fetched before the
    move goes missing."""
    out = []
    try:
        out.append(downloads_dir())
    except OSError:
        pass            # a chosen folder on an unplugged drive: list the rest
    legacy = media_dir("grabber")
    if all(legacy.resolve() != d.resolve() for d in out):
        out.append(legacy)
    return out


def bin_videos() -> list:
    """Every fetched recording, newest first — [Path]. Section clips and
    conform outputs are the same bin's citizens; half-downloads aren't."""
    seen, rows = set(), []
    for d in bin_dirs():
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.suffix.lower() not in VIDEO_EXTS or not p.is_file():
                continue
            if ".temp." in p.name or re.search(r"\.f\d+\.\w+$", p.name):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            rows.append(p)
    rows.sort(key=lambda p: -p.stat().st_mtime)
    return rows

_SCHED_LOCK = threading.Lock()


def _sched_file() -> Path:
    return support_dir() / "grabber-schedules.json"


def _load_schedules() -> list:
    try:
        return list(json.loads(_sched_file().read_text()))
    except (OSError, ValueError):
        return []


def _save_schedules(rows: list):
    _sched_file().write_text(json.dumps(rows, indent=1))


def _clean_title(stem: str) -> str:
    """A download's stem without the machinery: [id] and [span] tags out,
    separators to spaces, tidy."""
    s = re.sub(r"\s*\[[\w-]{6,}\]\s*", " ", stem)
    s = re.sub(r"\s*\[\d+-\d+\]\s*", " ", s)
    s = re.sub(r"[._]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _file_date(p: Path) -> str:
    """YYYYMMDD for the re-namer: the video's own upload date when its
    info.json is beside it, the file's mtime otherwise."""
    for cand in (p.with_suffix(".info.json"),
                 p.parent / (p.stem + ".info.json")):
        try:
            d = json.loads(cand.read_text()).get("upload_date", "")
            if re.fullmatch(r"\d{8}", str(d)):
                return str(d)
        except (OSError, ValueError):
            continue
    return time.strftime("%Y%m%d", time.localtime(p.stat().st_mtime))


def sched_due(s: dict, now: datetime) -> bool:
    """True when the most recent (weekday, hour) tick at or before `now`
    postdates the schedule's last run (or its creation — a schedule made
    on Friday for Thursdays waits for next Thursday, it doesn't fire
    backwards)."""
    if not s.get("enabled", True):
        return False
    wd = int(s.get("weekday", 3))        # Thursday, the agenda-cycle classic
    hr = int(s.get("hour", 9))
    days_back = (now.weekday() - wd) % 7
    tick = now.replace(hour=hr, minute=0, second=0, microsecond=0) \
        - timedelta(days=days_back)
    if tick > now:
        tick -= timedelta(days=7)
    anchor = s.get("last_run") or s.get("created") or ""
    try:
        seen = datetime.fromisoformat(anchor)
    except ValueError:
        return False
    return tick > seen


def broadcast_name(p: Path, pattern: str = "{title}_{date}") -> str:
    """Playout servers want predictable names: no spaces, no brackets, one
    underscore language. Tokens: {title} {date}."""
    title = _clean_title(p.stem)
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s-]+", "_", title).strip("_")
    out = (pattern or "{title}_{date}").replace("{title}", title or "program")
    out = out.replace("{date}", _file_date(p))
    out = re.sub(r"[^\w.-]", "_", out)
    out = re.sub(r"_+", "_", out).strip("_.") or "program"
    return out + p.suffix.lower()


def register_grabber(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore.media import presets_report
    from grabber.civicclerk import DEFAULT_TENANT, search_events
    from grabber.convert import CONFORM_PRESETS

    @app.get("/api/grabber/status")
    def api_status():
        from czcore.paths import downloads_chosen
        presets = [p for p in presets_report() if p["id"] in CONFORM_PRESETS]
        return {"ytdlp": ytdlp.status(), "library": str(downloads_root()),
                "downloads": {"path": str(downloads_root()),
                              "confirmed": downloads_chosen()},
                "default_tenant": DEFAULT_TENANT, "presets": presets,
                "schedules": _load_schedules()}

    @app.post("/api/grabber/ytdlp-check")
    def api_ytdlp_check(body: dict = Body(default={})):
        return {"ytdlp": ytdlp.check_async(force=bool(body.get("force")))}

    # -- the search desk -----------------------------------------------------

    @app.post("/api/grabber/find")
    def api_find(body: dict = Body(...)):
        """One query, two rooms, in parallel. Either room may fail without
        killing the other — the answer names what broke."""
        q = str(body.get("q", "")).strip()
        if len(q) < 2:
            return JSONResponse({"error": "give the search a couple of words"},
                                status_code=422)
        want_yt = bool(body.get("youtube", True))
        want_portal = bool(body.get("portal", True))
        tenant = str(body.get("tenant") or DEFAULT_TENANT).strip()
        days = max(1, min(365, int(body.get("days") or 60)))
        n = max(1, min(24, int(body.get("n") or 12)))
        out = {"q": q, "youtube": [], "portal": [], "errors": {}}

        def yt():
            return ytdlp.search(q, n=n, newest=True)

        def portal():
            to = date.today()
            frm = to - timedelta(days=days)
            events = search_events(tenant, frm.isoformat(), to.isoformat())
            toks = [t for t in re.findall(r"\w+", q.lower()) if len(t) > 2]
            # the portal is date-ranged, not worded — filter here; a town
            # name matches everything its portal lists, which is the point
            drop = {tenant.lower().replace("ma", ""), "meeting", "the"}
            toks = [t for t in toks if t not in drop] or []
            rows = []
            for ev in events:
                low = f"{ev.get('name', '')} {ev.get('category', '')}".lower()
                score = sum(1 for t in toks if t in low)
                if not toks or score:
                    rows.append({**ev, "score": score})
            rows.sort(key=lambda r: (-r["score"], r.get("when", "")))
            return rows[:24]

        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {}
            if want_yt:
                futs["youtube"] = ex.submit(yt)
            if want_portal:
                futs["portal"] = ex.submit(portal)
            for key, fut in futs.items():
                try:
                    out[key] = fut.result(timeout=60)
                except Exception as e:
                    out["errors"][key] = str(e)[:300]
        return out

    # -- fetch (search results and pasted links share this) ------------------

    def _start_fetch(url: str, name: str, quality: str):
        def work(job):
            def prog(p, m):
                if p >= 0:
                    job.progress = p
                job.message = m or job.message

            from grabber import zoomshare
            dest = downloads_dir()   # read now: the folder may have changed
            if zoomshare.is_zoom_share(url):
                got = zoomshare.download(url, dest, progress=prog,
                                         cancelled=lambda: job.cancel_requested,
                                         name=name)
            else:
                got = ytdlp.download(url, dest, quality=quality, progress=prog,
                                     cancelled=lambda: job.cancel_requested)
            note = f"fetched {Path(got['path']).name}" + (
                f" (+{got['clips'] - 1} more clips)" if got.get("clips", 1) > 1 else "")
            if not zoomshare.is_zoom_share(url) and quality != "audio":
                # the video is safe on disk; the words are a best effort
                # that can never cost it (ytdlp.sidecar_captions says why)
                job.message = note + " · fetching captions…"
                job.progress = -1
                cap = ytdlp.sidecar_captions(url, Path(got["path"]))
                got["captions"] = cap
                note += {"fetched": " · captions ✓",
                         "none": " · no captions on YouTube (Scribe can "
                                 "transcribe it)",
                         }.get(cap["captions"],
                               " · captions didn't come (" + cap["note"][:90]
                               + ")")
            job.message = note
            return got

        label = f"fetch — {name or url[:70]}"
        return jobs.start("fetch", work, tool="grabber", label=label)

    @app.post("/api/grabber/probe")
    def api_probe(body: dict = Body(...)):
        """What a link offers before a byte moves — the quality chooser's
        list, each rung resolved to the file the fetch would really take."""
        url = str(body.get("url", "")).strip()
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "that link isn't a URL"},
                                status_code=422)
        from grabber import zoomshare
        if zoomshare.is_zoom_share(url):
            # a Zoom share page serves the recording as recorded — one version
            return {"kind": "zoom", "url": url, "options": []}
        try:
            return {"kind": "video", **ytdlp.probe_url(url)}
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    @app.post("/api/grabber/fetch")
    def api_fetch(body: dict = Body(...)):
        url = str(body.get("url", "")).strip()
        name = str(body.get("name", "")).strip()
        quality = str(body.get("quality", "best")) or "best"
        if not url.lower().startswith(("http://", "https://")):
            return JSONResponse({"error": "that link isn't a URL"},
                                status_code=422)
        return _start_fetch(url, name, quality).to_dict()

    @app.get("/api/grabber/library")
    def api_library():
        rows = []
        for p in bin_videos():
            info = {}
            try:
                raw = json.loads(p.with_suffix(".info.json").read_text())
                info = {"title": raw.get("title"), "url": raw.get("webpage_url"),
                        "duration": raw.get("duration"),
                        "uploader": raw.get("uploader") or raw.get("channel")}
            except (OSError, ValueError):
                pass
            words = p.with_suffix(".scribe.json").exists()
            # the names yt-dlp and sidecar_captions write — probed directly;
            # a listing per row would crawl a Downloads folder n² times
            caps = words or any(
                p.with_name(p.stem + tail).exists()
                for tail in (".en.vtt", ".en-orig.vtt", ".en.srt", ".vtt",
                             ".srt"))
            rows.append({"path": str(p), "name": p.name,
                         "size": p.stat().st_size, "mtime": p.stat().st_mtime,
                         "folder": str(p.parent), **info,
                         "captions": caps, "transcript": words,
                         "highlights": p.with_suffix(".highlights.json").exists(),
                         "section": bool(re.search(r"\[\d+-\d+\]$", p.stem))})
        return rows

    @app.post("/api/grabber/captions")
    def api_captions(body: dict = Body(...)):
        """Fetch (or re-fetch) the captions for a video already in the bin —
        the words a fetch couldn't bring (a 429, the proxy off) come later,
        without re-downloading a byte of video."""
        p = Path(str(body.get("path", ""))).expanduser()
        if not p.is_file():
            return JSONResponse({"error": f"no such file: {p}"}, status_code=404)
        url = str(body.get("url") or "")
        if not url:
            try:
                url = json.loads(p.with_suffix(".info.json").read_text()) \
                    .get("webpage_url") or ""
            except (OSError, ValueError):
                url = ""
        if not url:
            return JSONResponse({"error": "this file doesn't say where it came "
                                          "from — transcribe it with Scribe "
                                          "instead"}, status_code=422)

        def work(job):
            job.message = "fetching captions…"
            cap = ytdlp.sidecar_captions(url, p)
            job.message = {"fetched": "captions ✓ — beside the video",
                           "none": "YouTube has no captions for this one"}.get(
                cap["captions"], f"captions didn't come — {cap['note'][:160]}")
            if cap["captions"] == "failed":
                raise RuntimeError(job.message)
            return cap

        return jobs.start("captions", work, tool="grabber",
                          label=f"captions — {p.name[:60]}").to_dict()

    @app.post("/api/grabber/convert")
    def api_convert(body: dict = Body(...)):
        from grabber.convert import convert

        path = str(Path(body["path"]).expanduser())
        preset = str(body.get("preset", "prores-422"))
        height = body.get("height")
        fps = body.get("fps")
        if not Path(path).is_file():
            return JSONResponse({"error": f"no such file: {path}"},
                                status_code=404)

        def work(job):
            def prog(frac, m):
                job.progress = frac
                if m:
                    job.message = m

            job.message = "conforming…"
            rep = convert(path, str(Path(path).parent), preset=preset,
                          fps=float(fps) if fps else None,
                          height=int(height) if height else None,
                          progress=prog,
                          cancelled=lambda: job.cancel_requested)
            job.message = (f"{rep['label']} · "
                           f"{'hardware' if rep['hardware'] else 'software'}")
            return rep

        label = f"{Path(path).name} — conform ({preset})"
        return jobs.start("convert", work, tool="grabber", label=label).to_dict()

    # -- the broadcast re-namer ----------------------------------------------

    @app.post("/api/grabber/rename")
    def api_rename(body: dict = Body(...)):
        """Playout-safe rename; every sidecar sharing the stem travels
        along. preview:true answers what WOULD happen, renames nothing."""
        p = Path(str(body.get("path", ""))).expanduser()
        pattern = str(body.get("pattern") or "{title}_{date}")
        if not p.is_file():
            return JSONResponse({"error": f"no such file: {p}"},
                                status_code=404)
        new = broadcast_name(p, pattern)
        target = p.with_name(new)
        k = 2
        while target.exists() and target != p:
            target = p.with_name(f"{Path(new).stem}_{k}{Path(new).suffix}")
            k += 1
        if body.get("preview"):
            return {"from": p.name, "to": target.name}
        moved = []
        stem = p.stem
        for s in list(p.parent.iterdir()):
            if s == p or not s.name.startswith(stem + "."):
                continue
            tail = s.name[len(stem):]
            s.rename(s.with_name(target.stem + tail))
            moved.append(s.name)
        p.rename(target)
        return {"from": p.name, "to": target.name, "sidecars": len(moved)}

    # -- schedules: the weekly clock -----------------------------------------

    def _run_schedule(s: dict) -> str:
        to = date.today()
        frm = to - timedelta(days=max(1, int(s.get("days") or 7)))
        events = search_events(str(s.get("tenant") or DEFAULT_TENANT),
                               frm.isoformat(), to.isoformat())
        queued = 0
        for ev in events:
            for link in ev.get("links", []):
                if link.get("videoish"):
                    _start_fetch(link["url"], ev.get("name", ""),
                                 str(s.get("quality") or "best"))
                    queued += 1
        return (f"{queued} fetch{'es' if queued != 1 else ''} queued from "
                f"{len(events)} events")

    def _clock():
        """Runs while the app runs; a missed Thursday fires on next launch.
        That's the honest shape of a desktop scheduler, and the UI says so."""
        while True:
            try:
                now = datetime.now()
                with _SCHED_LOCK:
                    rows = _load_schedules()
                    dirty = False
                    for s in rows:
                        if sched_due(s, now):
                            try:
                                s["last_note"] = _run_schedule(s)
                            except Exception as e:
                                s["last_note"] = f"failed — {str(e)[:160]}"
                            s["last_run"] = now.isoformat(timespec="seconds")
                            dirty = True
                    if dirty:
                        _save_schedules(rows)
            except Exception:
                pass                     # the clock must never die
            time.sleep(600)

    threading.Thread(target=_clock, daemon=True).start()

    @app.get("/api/grabber/schedules")
    def api_schedules():
        return {"schedules": _load_schedules()}

    @app.post("/api/grabber/schedules")
    def api_schedules_edit(body: dict = Body(...)):
        with _SCHED_LOCK:
            rows = _load_schedules()
            if body.get("add"):
                a = dict(body["add"])
                rows.append({
                    "id": uuid.uuid4().hex[:8],
                    "tenant": str(a.get("tenant") or DEFAULT_TENANT),
                    "weekday": max(0, min(6, int(a.get("weekday", 3)))),
                    "hour": max(0, min(23, int(a.get("hour", 9)))),
                    "days": max(1, min(90, int(a.get("days", 7)))),
                    "quality": str(a.get("quality") or "best"),
                    "enabled": True,
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "last_run": None, "last_note": "",
                })
            if body.get("update"):
                u = body["update"]
                for s in rows:
                    if s["id"] == u.get("id"):
                        for k in ("tenant", "weekday", "hour", "days",
                                  "quality", "enabled"):
                            if k in (u.get("patch") or {}):
                                s[k] = u["patch"][k]
            if body.get("remove"):
                rows = [s for s in rows if s["id"] != body["remove"]]
            _save_schedules(rows)
        if body.get("run"):
            with _SCHED_LOCK:
                rows = _load_schedules()
                for s in rows:
                    if s["id"] == body["run"]:
                        try:
                            s["last_note"] = _run_schedule(s)
                        except Exception as e:
                            s["last_note"] = f"failed — {str(e)[:160]}"
                        s["last_run"] = datetime.now().isoformat(
                            timespec="seconds")
                _save_schedules(rows)
        return {"schedules": _load_schedules()}
