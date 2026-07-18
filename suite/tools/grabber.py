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
from czcore.paths import media_dir, support_dir

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".m4v", ".mpg", ".m4a")

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

    lib = media_dir("grabber")

    @app.get("/api/grabber/status")
    def api_status():
        presets = [p for p in presets_report() if p["id"] in CONFORM_PRESETS]
        return {"ytdlp": ytdlp.status(), "library": str(lib),
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
            if zoomshare.is_zoom_share(url):
                got = zoomshare.download(url, lib, progress=prog,
                                         cancelled=lambda: job.cancel_requested,
                                         name=name)
            else:
                got = ytdlp.download(url, lib, quality=quality, progress=prog,
                                     cancelled=lambda: job.cancel_requested)
            job.message = f"fetched {Path(got['path']).name}" + (
                f" (+{got['clips'] - 1} more clips)" if got.get("clips", 1) > 1 else "")
            return got

        label = f"fetch — {name or url[:70]}"
        return jobs.start("fetch", work, tool="grabber", label=label)

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
        rows = [{"path": str(p), "name": p.name, "size": p.stat().st_size,
                 "mtime": p.stat().st_mtime}
                for p in sorted(lib.iterdir())
                if p.suffix.lower() in VIDEO_EXTS]
        rows.sort(key=lambda r: -r["mtime"])
        return rows

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
