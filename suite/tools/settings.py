"""Settings page — caches (sizes + clear), store paths, about. Everything on
this page is regenerable; nothing here can lose work.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .. import __version__

CACHES = {
    "frames": ("Preview frames", "suite scrub/filmstrip JPEGs",
               Path.home() / "Library" / "Caches" / "control-z" / "suite" / "frames"),
    "clear": ("Clear audio", "extracted audio, residuals, room tone",
              Path.home() / "Library" / "Caches" / "control-z" / "suite" / "clear"),
    "stencil": ("Stencil mattes", "analysis frames + propagated masks",
                Path.home() / "Library" / "Caches" / "control-z" / "suite" / "stencil"),
    "pivot-legacy": ("Pivot (legacy page)", "the old standalone page's scrub cache",
                     Path.home() / "Library" / "Caches" / "control-z" / "pivot"),
}

# Tools whose running jobs write into each cache — clearing it under them would
# throw away work in progress, so we refuse while one is active. None means any
# tool (every job decodes preview frames); () means no job of ours writes there
# (the legacy page is a separate process with its own cache).
CACHE_OWNERS = {
    "frames": None,
    "clear": ("clear",),
    "stencil": ("stencil",),
    "pivot-legacy": (),
}


def _size(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def usable_folder(root: str):
    """None when `root` is a folder new files can land in (creating it if
    needed) — else the sentence saying why not. Checked BEFORE a choice is
    saved: a bad saved folder would break every later download."""
    p = Path(root).expanduser()
    if not p.is_absolute():
        return f"“{root}” isn't a full folder path — use Change… to pick one"
    if p.exists() and not p.is_dir():
        return f"{p} is a file, not a folder"
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".cz-write-test"
        probe.write_text("")
        probe.unlink()
    except OSError as e:
        return (f"can't save files in {p} "
                f"({(e.strerror or 'not writable').lower()}) — pick another folder")
    return None


def register_settings(app, jobs, frames):
    from fastapi import Body
    from fastapi.responses import JSONResponse

    from czcore import models as reg
    from ..sessions import app_support

    @app.get("/api/settings/info")
    def api_info():
        return {
            "version": __version__,
            "python": sys.version.split()[0],
            "caches": [{"id": k, "label": v[0], "what": v[1],
                        "path": str(v[2]), "size": _size(v[2])}
                       for k, v in CACHES.items()],
            "model_store": {"path": str(reg.models_dir()),
                            "size": _size(reg.models_dir())},
            "app_support": str(app_support()),
            "jobs_db_size": _size(app_support() / "jobs.db") or (
                (app_support() / "jobs.db").stat().st_size
                if (app_support() / "jobs.db").exists() else 0),
        }

    @app.post("/api/settings/clear-cache")
    def api_clear(body: dict = Body(...)):
        which = body.get("which")
        if which not in CACHES:
            return JSONResponse({"error": f"unknown cache {which!r}"},
                                status_code=422)
        owners = CACHE_OWNERS[which]
        busy = jobs.active() if owners is None else [
            j for t in owners for j in jobs.active(tool=t)]
        if busy:
            what = busy[0].label or busy[0].kind
            return JSONResponse(
                {"error": f"{CACHES[which][0]} is being written to right now by "
                          f"{what} — clearing it would throw that work away. "
                          "Let it finish (or cancel it in the queue) and try again."},
                status_code=409)
        p = CACHES[which][2]
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "note": f"{CACHES[which][0]} cleared — it rebuilds "
                                    "as you work"}

    @app.post("/api/jobs/clear-history")
    def api_clear_history():
        n = jobs.clear_finished()
        return {"ok": True, "removed": n}

    # -- fetch network: the Webshare residential proxy — a switch, OFF by
    #    default; the built-in account or your own (czcore/proxy.py) --------

    @app.get("/api/settings/proxy")
    def api_proxy_get():
        from czcore import proxy
        return proxy.status()

    @app.post("/api/settings/proxy")
    def api_proxy_set(body: dict = Body(...)):
        from czcore import proxy
        if "username" not in body:
            st = None
            if "relay" in body:
                st = proxy.set_relay(bool(body["relay"]))
            if "enabled" in body:
                if body["enabled"] and not proxy.get_config()["username"]:
                    return JSONResponse(
                        {"error": "no proxy account yet — add your own "
                                  "Webshare username and password below"},
                        status_code=409)
                st = proxy.set_enabled(bool(body["enabled"]))
            return st or proxy.status()
        st = proxy.get_config()
        if st["source"] == "env" and body.get("username"):
            return JSONResponse(
                {"error": "the proxy is set by environment variables — "
                          "change WEBSHARE_PROXY_USERNAME/PASSWORD there"},
                status_code=409)
        return proxy.set_config(str(body.get("username", "")),
                                str(body.get("password", "")),
                                str(body.get("host", "")))

    @app.post("/api/settings/proxy/test")
    def api_proxy_test():
        """One real request through the account — works with the switch
        off, so you can check your credentials before relying on them."""
        from czcore import proxy
        return proxy.test()

    # -- downloads: where fetched videos land (czcore.paths) ------------------

    @app.get("/api/settings/downloads")
    def api_downloads_get():
        from czcore.paths import DOWNLOADS_FOLDER, downloads_chosen, downloads_root
        return {"path": str(downloads_root()), "confirmed": downloads_chosen(),
                "default": str(Path.home() / "Downloads" / DOWNLOADS_FOLDER)}

    @app.post("/api/settings/downloads")
    def api_downloads_set(body: dict = Body(...)):
        from czcore.paths import downloads_chosen, downloads_dir, set_downloads_root
        root = str(body.get("path", "")).strip()
        if root:
            err = usable_folder(root)
            if err:
                return JSONResponse({"error": err}, status_code=422)
        set_downloads_root(root)          # saved only once it's known good
        return {"path": str(downloads_dir()), "confirmed": downloads_chosen()}

    # -- outputs: where finished files land ---------------------------------

    @app.get("/api/settings/outputs")
    def api_outputs_get():
        from czcore.paths import media_root
        return {"root": str(media_root())}

    @app.post("/api/settings/outputs")
    def api_outputs_set(body: dict = Body(...)):
        from czcore.paths import set_media_root
        root = str(body.get("root", "")).strip()
        if root and not Path(root).expanduser().parent.exists():
            return JSONResponse({"error": f"the folder above {root} doesn't "
                                          "exist — pick a real place"},
                                status_code=422)
        return {"root": str(set_media_root(root))}

    # -- runtimes: the optional heavies, installable from inside the app ----
    #
    # All three install from the SIGNED app now. The old gate ("this signed
    # build can't install runtimes yet") blocked even the two that were
    # never a problem: DeepFilterNet and Deno are standalone binaries we run
    # as subprocesses, exactly like yt-dlp. Stencil's torch can't load
    # inside a signed app, so it installs as a helper runtime in its own
    # Python (suite/tools/stencil.py, czcore/pyruntime.py). Each row also
    # carries the manual road — the exact terminal lines and the exact
    # place the app looks — and "Check again" verifies either road.

    def _dfn_check() -> dict:
        import platform
        import subprocess as sp
        from clear import isolate as dfn
        p = dfn.binary_path()
        if not p.exists():
            return {"ok": False, "detail": "not installed"}
        if not os.access(p, os.X_OK):
            return {"ok": False, "detail": f"{p.name} isn't executable — run "
                                           f"chmod +x on it"}
        try:
            out = sp.run([str(p), "--version"], capture_output=True, text=True,
                         timeout=15)
            if out.returncode == 0:
                return {"ok": True, "detail": (out.stdout.strip() or
                                               "deep-filter ready")[:80]}
            why = (out.stderr.strip().splitlines() or ["it didn't run"])[-1]
        except OSError as e:
            why = e.strerror or str(e)
        except sp.TimeoutExpired:
            why = "it didn't answer"
        if platform.machine() not in ("arm64", "aarch64"):
            why += " — this binary is for Apple silicon Macs"
        return {"ok": False, "detail": f"present but won't run ({why[:120]})"}

    def _runtime_rows():
        import platform

        from czcore import pyruntime, ytdlp
        from clear import isolate as dfn

        from . import stencil as stencil_tool
        q = lambda s: f'"{s}"'  # noqa: E731

        st = stencil_tool.runtime_status()
        if st["available"] and st.get("mode") == "helper":
            v = pyruntime.verify(stencil_tool.RUNTIME, stencil_tool.VERIFY)
            st_detail = f"its own runtime — {v['detail']}"
        elif st["available"]:
            st_detail = "running inside this checkout's Python"
        else:
            v = pyruntime.verify(stencil_tool.RUNTIME, stencil_tool.VERIFY)
            st_detail = ("" if v["detail"] == "not installed" else
                         f"found at the location below, but the check "
                         f"failed: {v['detail']}")
        sys_py = pyruntime.find_system_python()
        stencil_row = {
            "id": "stencil-sam2", "label": "Stencil click-to-matte",
            "what": "PyTorch + Meta's SAM 2 — click a subject, get a matte",
            "size": "~1 GB", "installed": bool(st["available"]),
            "detail": st_detail, "installable": True,
            "location": str(pyruntime.venv_dir(stencil_tool.RUNTIME)),
            "removable": pyruntime.venv_python(stencil_tool.RUNTIME).exists(),
            "manual": {
                "intro": ("In Terminal, with a Python 3.10–3.13 "
                          + (f"(found: {sys_py})" if sys_py else
                             "from python.org or Homebrew (brew install "
                             "python@3.12)")
                          + " — about 1 GB; it takes a few minutes:"),
                "lines": pyruntime.manual_commands(
                    stencil_tool.RUNTIME, stencil_tool.STEPS,
                    stencil_tool.STEP_ENV),
                "outro": "Then press Check again — the app looks for "
                         "that folder's bin/python and test-imports "
                         "torch + SAM 2 from it."},
        }
        dfn_ok = _dfn_check()
        arm = platform.machine() in ("arm64", "aarch64")
        bp = dfn.binary_path()
        dfn_row = {
            "id": "clear-dfn", "label": "Clear voice isolation",
            "what": "the official DeepFilterNet3 binary (MIT/Apache) — "
                    "everything else in Clear works without it",
            "size": "~40 MB", "installed": dfn_ok["ok"],
            "detail": "" if dfn_ok["detail"] == "not installed"
                      else dfn_ok["detail"],
            "installable": arm,
            "why_not": None if arm else "DeepFilterNet ships this binary "
                                        "for Apple silicon only",
            "location": str(bp), "removable": bp.exists(),
            "manual": {
                "intro": "In Terminal (one download, checked against its "
                         "published fingerprint):",
                "lines": [f"mkdir -p {q(bp.parent)}",
                          f"curl -L {dfn.BIN_URL} -o {q(bp)}",
                          f"shasum -a 256 {q(bp)}   # must print "
                          f"{dfn.BIN_SHA256}",
                          f"chmod +x {q(bp)}"],
                "outro": "Downloaded it with a browser instead? Move it to "
                         "that exact path, then also run: xattr -d "
                         f"com.apple.quarantine {q(bp)}"},
        }
        rt = ytdlp.js_runtime()
        managed = ytdlp.deno_path()
        js_row = {
            "id": "yt-deno", "label": "YouTube helper (Deno)",
            "what": "lets yt-dlp answer YouTube's JavaScript challenges, so "
                    "every quality is on offer and fewer downloads fail",
            "size": "~45 MB", "installed": rt is not None,
            "detail": (f"using {rt[0]} at {rt[1]}" if rt else ""),
            "installable": True,
            "location": str(managed), "removable": managed.exists(),
            "manual": {
                "intro": "Any of these works — the app looks in the usual "
                         "places (Homebrew, ~/.deno, ~/.bun) and in its own "
                         "folder:",
                "lines": ["brew install deno",
                          "curl -fsSL https://deno.land/install.sh | sh",
                          "brew install node   # Node works too"],
                "outro": "Then press Check again."},
        }
        return [stencil_row, dfn_row, js_row]

    @app.get("/api/settings/runtimes")
    def api_runtimes():
        return {"runtimes": _runtime_rows(), "frozen": getattr(sys, "frozen",
                                                               False)}

    @app.post("/api/settings/runtimes/check")
    def api_runtimes_check(body: dict = Body(default={})):
        """Verify again — after a manual install, or to see why one fails."""
        from czcore import pyruntime

        from . import stencil as stencil_tool
        which = str(body.get("id", ""))
        if which == "stencil-sam2":
            pyruntime.verify(stencil_tool.RUNTIME, stencil_tool.VERIFY,
                             force=True)
        rows = _runtime_rows()
        row = next((r for r in rows if r["id"] == which), None)
        return {"runtimes": rows, "row": row}

    @app.post("/api/settings/runtimes/remove")
    def api_runtimes_remove(body: dict = Body(...)):
        from czcore import pyruntime, ytdlp
        from clear import isolate as dfn

        from . import stencil as stencil_tool
        which = str(body.get("id", ""))
        if which == "stencil-sam2":
            if jobs.active(tool="stencil"):
                return JSONResponse({"error": "Stencil is working right now — "
                                              "let it finish first"},
                                    status_code=409)
            if stencil_tool._helper:
                stencil_tool._helper.stop()
            pyruntime.remove(stencil_tool.RUNTIME)
        elif which == "clear-dfn":
            dfn.binary_path().unlink(missing_ok=True)
        elif which == "yt-deno":
            ytdlp.deno_path().unlink(missing_ok=True)
        else:
            return JSONResponse({"error": f"unknown runtime {which!r}"},
                                status_code=422)
        return {"runtimes": _runtime_rows()}

    @app.post("/api/settings/runtimes/install")
    def api_runtimes_install(body: dict = Body(...)):
        which = str(body.get("id", ""))
        if which == "stencil-sam2":
            from . import stencil as stencil_tool
            return stencil_tool.install_job(jobs).to_dict()
        if which not in ("clear-dfn", "yt-deno"):
            return JSONResponse({"error": f"unknown runtime {which!r}"},
                                status_code=422)

        def fetch(job, url, dest, what):
            import urllib.request
            job.message = f"downloading {what}…"
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            req = urllib.request.Request(url, headers={
                "User-Agent": "control-z-suite"})
            with urllib.request.urlopen(req, timeout=120) as r, \
                    open(tmp, "wb") as f:
                got, total = 0, int(r.headers.get("Content-Length") or 0)
                while chunk := r.read(1 << 18):
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        job.progress = got / total
                        job.message = f"downloading {what}… {got * 100 // total}%"
                    if job.cancel_requested:
                        f.close()
                        tmp.unlink(missing_ok=True)
                        job.check_cancel()
            return tmp

        def work(job):
            import hashlib
            if which == "clear-dfn":
                from clear import isolate as dfn
                dest = dfn.binary_path()
                tmp = fetch(job, dfn.BIN_URL, dest, "DeepFilterNet3")
                sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
                if sha != dfn.BIN_SHA256:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("the download didn't match its "
                                       "published sha256 — refused")
                tmp.chmod(0o755)
                tmp.replace(dest)
                ok = _dfn_check()
                if not ok["ok"]:
                    raise RuntimeError(f"installed, but {ok['detail']}")
                job.message = "voice isolation ready — Clear's Isolate is live"
            else:
                import platform
                import urllib.request
                import zipfile

                from czcore import ytdlp
                arch = ("aarch64" if platform.machine() in ("arm64", "aarch64")
                        else "x86_64")
                name = f"deno-{arch}-apple-darwin.zip"
                base = "https://github.com/denoland/deno/releases/latest/download/"
                tmp = fetch(job, base + name, ytdlp.deno_path().with_suffix(".zip"),
                            "Deno")
                try:   # the release publishes a checksum beside each zip
                    want = urllib.request.urlopen(urllib.request.Request(
                        base + name + ".sha256sum",
                        headers={"User-Agent": "control-z-suite"}),
                        timeout=30).read().decode().split()[0].lower()
                except Exception:
                    want = None
                if want and hashlib.sha256(tmp.read_bytes()).hexdigest() != want:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("the Deno download didn't match its "
                                       "published sha256 — refused")
                with zipfile.ZipFile(tmp) as z:
                    data = z.read("deno")
                dest = ytdlp.deno_path()
                part = dest.with_name("deno.part")
                part.write_bytes(data)
                part.chmod(0o755)
                part.replace(dest)
                tmp.unlink(missing_ok=True)
                job.message = "Deno ready — yt-dlp uses it from the next fetch"
            return {"ok": True, "id": which}

        return jobs.start("install", work, tool="suite",
                          label=f"install runtime — {which}").to_dict()

    # -- AI: the user's own Anthropic key, optional, never the default -------

    @app.get("/api/settings/llm")
    def api_llm_get():
        from czcore import llm
        return llm.status()

    @app.post("/api/settings/llm")
    def api_llm_set(body: dict = Body(...)):
        from czcore import llm
        if llm.get_config()["source"] == "env" and body.get("api_key"):
            return JSONResponse(
                {"error": "the key is set by ANTHROPIC_API_KEY in the "
                          "environment — change it there"}, status_code=409)
        return llm.set_config(str(body.get("api_key", "")).strip(),
                              str(body.get("model", "")).strip())

    @app.get("/api/settings/llm/usage")
    def api_llm_usage():
        """The session's AI audit: every API call since this serve started,
        counted and attributed to its tool. Token counts come from the
        providers' own responses; the page turns them into rough dollars."""
        from czcore import llm
        return {**llm.usage_summary(),
                "model": llm.status().get("model"),
                "window": llm.context_window(llm.status().get("model") or "")}
