"""Install OpenFX page (specs/08 §5) — Hush and Speak into free Resolve.

Detection is all local reads. The release check is one GET to the public
GitHub API when the user asks (spec: "release-check (GitHub API, no
telemetry)") — nothing phones home on its own. Install downloads the
release .pkg to ~/Downloads and opens the system installer, which handles
privileges properly; /Library/OFX/Plugins is root-owned on most machines
and we say so instead of pretending.
"""

from __future__ import annotations

import json
import plistlib
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

PLUGINS_DIR = Path("/Library/OFX/Plugins")
CACHE_FILE = (Path.home() / "Library" / "Application Support" /
              "Blackmagic Design" / "DaVinci Resolve" / "OFXPluginCacheV2.xml")

PLUGINS = {
    "hush": {
        "name": "Hush",
        "bundle": "OpenNR.ofx.bundle",
        "repo": "amateurmenace/Hush-OpenNR",
        "one": "open noise reduction — denoise on the Color page",
        "site": "https://control-z.org/#t-hush",
    },
    "speak": {
        "name": "Speak",
        "bundle": "Speak.ofx.bundle",
        "repo": "amateurmenace/Speak",
        "one": "film character — the last node before delivery",
        "site": "https://control-z.org/#t-speak",
    },
}


def _installed_version(bundle: str):
    plist = PLUGINS_DIR / bundle / "Contents" / "Info.plist"
    if not plist.exists():
        return None
    try:
        d = plistlib.loads(plist.read_bytes())
        return str(d.get("CFBundleShortVersionString") or
                   d.get("CFBundleVersion") or "unknown")
    except Exception:
        return "unknown"


def _resolve_present() -> bool:
    return any(Path(p).exists() for p in (
        "/Applications/DaVinci Resolve/DaVinci Resolve.app",
        "/Applications/DaVinci Resolve.app",
        "/Applications/DaVinci Resolve"))


def _gh_json(url: str):
    req = urllib.request.Request(
        url, headers={"User-Agent": "control-z-suite",
                      "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _latest_release(repo: str) -> dict:
    try:
        d = _gh_json(f"https://api.github.com/repos/{repo}/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        # /latest excludes prereleases — a beta-only repo 404s here (Speak)
        rows = _gh_json(f"https://api.github.com/repos/{repo}/releases?per_page=1")
        if not rows:
            raise RuntimeError(f"{repo} has no releases yet") from None
        d = rows[0]
    assets = [{"name": a["name"], "url": a["browser_download_url"],
               "size": a.get("size", 0)} for a in d.get("assets", [])]
    pkg = next((a for a in assets if a["name"].endswith(".pkg")), None)
    return {"tag": d.get("tag_name"), "published": d.get("published_at"),
            "notes_url": d.get("html_url"), "pkg": pkg, "assets": assets,
            "prerelease": bool(d.get("prerelease"))}


def register_ofx(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    @app.get("/api/ofx/status")
    def api_status():
        out = {
            "resolve_present": _resolve_present(),
            "plugins_dir": str(PLUGINS_DIR),
            "plugins_dir_exists": PLUGINS_DIR.exists(),
            "plugins_dir_writable": PLUGINS_DIR.exists() and
                __import__("os").access(PLUGINS_DIR, __import__("os").W_OK),
            "cache_file_present": CACHE_FILE.exists(),
            "plugins": {},
        }
        for key, p in PLUGINS.items():
            out["plugins"][key] = {
                "name": p["name"], "bundle": p["bundle"], "repo": p["repo"],
                "one": p["one"], "site": p["site"],
                "installed": _installed_version(p["bundle"]),
            }
        return out

    @app.post("/api/ofx/check-updates")
    def api_check(body: dict = Body(default={})):
        """One explicit GET per plugin to the public GitHub API — no telemetry,
        runs only when this button is pressed."""
        out = {}
        for key, p in PLUGINS.items():
            try:
                out[key] = _latest_release(p["repo"])
            except Exception as e:
                out[key] = {"error": f"couldn't reach GitHub: "
                                     f"{e.__class__.__name__} — offline is fine, "
                                     "the plugins still work"}
        return out

    @app.post("/api/ofx/install")
    def api_install(body: dict = Body(...)):
        key = body.get("plugin")
        if key not in PLUGINS:
            return JSONResponse({"error": f"unknown plugin {key!r}"}, status_code=422)
        p = PLUGINS[key]

        def work(job):
            job.message = "asking GitHub for the latest release…"
            rel = _latest_release(p["repo"])
            if not rel.get("pkg"):
                raise RuntimeError(
                    f"the latest {p['name']} release ({rel.get('tag')}) has no "
                    ".pkg installer — grab the zip from "
                    f"{rel.get('notes_url')} and follow its install steps")
            pkg = rel["pkg"]
            dest = Path.home() / "Downloads" / pkg["name"]
            job.message = f"downloading {pkg['name']} ({pkg['size'] // (1 << 20)} MB)…"
            req = urllib.request.Request(pkg["url"],
                                         headers={"User-Agent": "control-z-suite"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                total = pkg["size"] or 1
                got = 0
                while True:
                    chunk = r.read(1 << 18)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    job.progress = min(0.95, got / total)
                    job.check_cancel()
            job.message = "opening the installer — finish in the system dialog"
            subprocess.run(["open", str(dest)], check=True)
            return {"pkg": str(dest), "tag": rel["tag"],
                    "note": "the macOS installer handles permissions; when it "
                            "finishes, clear the OFX cache below and restart "
                            "Resolve so it rescans"}

        return jobs.start("ofx-install", work, tool="suite",
                          label=f"{p['name']} — download installer").to_dict()

    @app.post("/api/ofx/clear-cache")
    def api_clear_cache():
        if not CACHE_FILE.exists():
            return {"ok": True, "note": "no cache file — Resolve will scan fresh"}
        try:
            CACHE_FILE.unlink()
            return {"ok": True,
                    "note": "cache cleared — Resolve rescans plugins on next launch"}
        except OSError as e:
            return JSONResponse({"error": f"couldn't remove it: {e}"},
                                status_code=500)

    @app.post("/api/ofx/uninstall-hint")
    def api_uninstall(body: dict = Body(...)):
        key = body.get("plugin")
        if key not in PLUGINS:
            return JSONResponse({"error": f"unknown plugin {key!r}"}, status_code=422)
        bundle = PLUGINS_DIR / PLUGINS[key]["bundle"]
        if not bundle.exists():
            return {"note": "not installed — nothing to remove"}
        import os
        import shutil
        if os.access(PLUGINS_DIR, os.W_OK):
            shutil.rmtree(bundle)
            return {"note": f"removed {bundle}"}
        return {"needs_admin": True,
                "command": f'sudo rm -rf "{bundle}"',
                "note": "the plugins folder is admin-owned — run this in "
                        "Terminal, then clear the OFX cache"}
