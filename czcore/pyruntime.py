"""Managed Python runtimes — the heavy optionals a signed app can't load.

The signed app runs under the hardened runtime with ZERO entitlements
(packaging/sign_suite.sh): library validation refuses every native library
not signed by our team, torch's included. So a heavy optional stack
(Stencil's torch + SAM 2) can never be imported INTO the app. It lives in
its own Python instead — installed into app support, verified, and driven
as a helper process the app talks to over pipes. From a source checkout the
same runtime works too.

Layout, under app support (…/control-z/runtimes/):

    python/            a relocatable CPython (python-build-standalone),
                       fetched once, sha256-checked against its release
    <name>/            one venv per runtime, made from that Python
    <name>.json        the last verification: {ok, detail, at, stamp}

The install is a queue job (pip's own lines as progress, cancel honored);
the "manual" road is the same three commands, printed for a terminal —
and "Check again" verifies whichever road the files arrived by.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import List, Optional

from .paths import support_dir

PBS_API = ("https://api.github.com/repos/astral-sh/"
           "python-build-standalone/releases/latest")
PY_MINOR = "3.12"          # torch + SAM 2's safest ground on macOS today


def root() -> Path:
    return support_dir("runtimes")


def venv_dir(name: str) -> Path:
    return root() / name


def venv_python(name: str) -> Path:
    return venv_dir(name) / "bin" / "python"


def managed_python() -> Path:
    return root() / "python" / "bin" / "python3"


def _stamp_file(name: str) -> Path:
    return root() / f"{name}.json"


# -- a Python to build the venv from -------------------------------------------

_SYS_PY: dict = {}


def find_system_python() -> Optional[str]:
    """A Python 3.10–3.13 already on this machine (Homebrew, python.org,
    pyenv) — named in the manual instructions so a terminal user can reuse
    what they have. The in-app install always uses its own managed copy.
    Probed once per app run (each candidate costs a subprocess)."""
    if "py" not in _SYS_PY:
        _SYS_PY["py"] = _probe_system_python()
    return _SYS_PY["py"]


def _probe_system_python() -> Optional[str]:
    cands = []
    for minor in ("3.12", "3.13", "3.11", "3.10"):
        cands += [f"/opt/homebrew/bin/python{minor}",
                  f"/usr/local/bin/python{minor}",
                  f"/Library/Frameworks/Python.framework/Versions/{minor}/bin/python3"]
    cands += [str(Path(p).expanduser()) for p in
              ("~/.pyenv/shims/python3", "/opt/homebrew/bin/python3",
               "/usr/local/bin/python3")]
    for c in cands:
        if Path(c).is_file() and os.access(c, os.X_OK):
            try:
                v = subprocess.run([c, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                continue
            if v in ("3.10", "3.11", "3.12", "3.13"):
                return c
    return None


def _arch() -> str:
    m = platform.machine().lower()
    return "aarch64" if m in ("arm64", "aarch64") else "x86_64"


def _fetch_json(url: str, timeout: float = 20.0) -> dict:
    from urllib.request import Request, urlopen
    with urlopen(Request(url, headers={"User-Agent": "control-z-suite",
                                       "Accept": "application/vnd.github+json"}),
                 timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: Path, job=None, label: str = "") -> Path:
    from urllib.request import Request, urlopen
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urlopen(Request(url, headers={"User-Agent": "control-z-suite"}),
                 timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while chunk := r.read(1 << 18):
            f.write(chunk)
            got += len(chunk)
            if job is not None:
                job.check_cancel()
                if total:
                    job.message = f"{label} {got * 100 // total}%"
    tmp.replace(dest)
    return dest


def ensure_managed_python(job=None) -> Path:
    """Fetch + unpack python-build-standalone once. Its release publishes
    SHA256SUMS; the tarball is refused if it doesn't match."""
    py = managed_python()
    if py.exists():
        return py
    if job is not None:
        job.message = "finding a Python for the runtime…"
    rel = _fetch_json(PBS_API)
    pat = re.compile(rf"^cpython-{re.escape(PY_MINOR)}\.\d+\+\d+-"
                     rf"{_arch()}-apple-darwin-install_only\.tar\.gz$")
    asset = next((a for a in rel.get("assets", []) if pat.match(a["name"])), None)
    if asset is None:
        raise RuntimeError(f"the python-build-standalone release has no "
                           f"Python {PY_MINOR} for {_arch()} macOS — use the "
                           "manual install with a Python you already have")
    sums = next((a for a in rel.get("assets", [])
                 if a["name"] == "SHA256SUMS"), None)
    root().mkdir(parents=True, exist_ok=True)
    tgz = root() / asset["name"]
    _download(asset["browser_download_url"], tgz, job,
              f"downloading Python {PY_MINOR} (~20 MB)…")
    # an interpreter we'll run is checked against its release's published
    # SHA256SUMS — and a release that doesn't say is refused, not trusted
    want = None
    if sums is not None:
        from urllib.request import Request, urlopen
        with urlopen(Request(sums["browser_download_url"],
                             headers={"User-Agent": "control-z-suite"}),
                     timeout=30) as r:
            table = r.read().decode("utf-8", "replace")
        want = next((ln.split()[0] for ln in table.splitlines()
                     if ln.strip().endswith(asset["name"])), None)
    got = hashlib.sha256(tgz.read_bytes()).hexdigest()
    if not want or want.lower() != got:
        tgz.unlink(missing_ok=True)
        raise RuntimeError("the Python download couldn't be checked against a "
                           "published sha256 — refused (the manual install "
                           "with a Python you already have still works)")
    if job is not None:
        job.message = "unpacking Python…"
    stage = root() / "python.unpack"
    shutil.rmtree(stage, ignore_errors=True)
    with tarfile.open(tgz) as tf:
        # the archive's own top level is python/ — nothing may land outside
        for m in tf.getmembers():
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                raise RuntimeError("the Python archive has an unsafe path")
        # "data" also refuses links that point outside and special files
        tf.extractall(stage, filter="data")
    shutil.rmtree(root() / "python", ignore_errors=True)
    (stage / "python").rename(root() / "python")
    shutil.rmtree(stage, ignore_errors=True)
    tgz.unlink(missing_ok=True)
    return py


# -- the venv + pip ------------------------------------------------------------

def _run_streaming(cmd: List[str], job=None, env: Optional[dict] = None,
                   what: str = "pip"):
    """Run a command, its lines as the job's message; cancel kills it."""
    import signal
    import threading

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                            env={**os.environ, **(env or {})},
                            start_new_session=True)
    stopped = threading.Event()

    def watch():
        # pip goes silent for minutes while a 700 MB wheel downloads — a
        # cancel checked only between its lines would wait that out
        while proc.poll() is None:
            if job is not None and job.cancel_requested:
                stopped.set()
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    pass
                return
            time.sleep(0.4)

    threading.Thread(target=watch, daemon=True).start()
    tail = []
    for line in proc.stdout:
        s = line.strip()
        if s:
            tail = (tail + [s])[-12:]
            if job is not None:
                job.message = s[:120]
    proc.wait()
    if stopped.is_set() and job is not None:
        job.check_cancel()
    if proc.returncode != 0:
        why = next((t for t in reversed(tail) if "error" in t.lower()),
                   tail[-1] if tail else f"exit {proc.returncode}")
        raise RuntimeError(f"{what} couldn't finish — {why[:220]}")


def install(name: str, steps: List[List[str]], verify_code: str,
            job=None, env: Optional[dict] = None,
            base_python: Optional[str] = None) -> dict:
    """Make the venv (from the managed Python unless base_python is given),
    run each pip step (a list of pip arguments), verify. Idempotent: an
    existing venv is reused, so a cancelled or failed install resumes."""
    py = base_python or str(ensure_managed_python(job))
    vd = venv_dir(name)
    if not venv_python(name).exists():
        if job is not None:
            job.message = "making the runtime's own environment…"
        _run_streaming([py, "-m", "venv", str(vd)], job, what="venv")
    for i, args in enumerate(steps, 1):
        if job is not None:
            job.message = f"step {i}/{len(steps)} — pip {' '.join(args[:3])}…"
            job.progress = (i - 1) / (len(steps) + 1)
        _run_streaming([str(venv_python(name)), "-m", "pip", *args], job,
                       env=env)
    if job is not None:
        job.progress = len(steps) / (len(steps) + 1)
        job.message = "verifying the runtime…"
    return verify(name, verify_code, force=True)


def verify(name: str, code: str, force: bool = False,
           timeout: float = 120.0) -> dict:
    """Run `code` in the runtime's Python. Cached against the venv's own
    timestamp — importing torch costs seconds, the Settings page asks often."""
    py = venv_python(name)
    if not py.exists():
        return {"ok": False, "detail": "not installed", "python": None}
    try:
        cfg = (venv_dir(name) / "pyvenv.cfg").stat().st_mtime_ns
    except OSError:
        return {"ok": False, "python": str(py),
                "detail": "the runtime folder is incomplete (no pyvenv.cfg) — "
                          "remove it and install again"}
    # the check itself is part of the key: a release that changes what
    # "ready" means re-verifies instead of trusting an old "ok"
    stamp = (f"{cfg}:{_site_mtime(name)}:"
             f"{hashlib.sha256(code.encode()).hexdigest()[:12]}")
    sf = _stamp_file(name)
    if not force:
        try:
            d = json.loads(sf.read_text())
            if d.get("stamp") == stamp:
                return {"ok": d["ok"], "detail": d["detail"], "python": str(py)}
        except (OSError, ValueError, KeyError):
            pass
    try:
        out = subprocess.run([str(py), "-c", code], capture_output=True,
                             text=True, timeout=timeout)
        ok = out.returncode == 0
        detail = (out.stdout.strip().splitlines() or ["ok"])[-1] if ok else \
            ((out.stderr.strip().splitlines() or ["failed"])[-1])
    except subprocess.TimeoutExpired:
        ok, detail = False, f"the check didn't finish in {int(timeout)}s"
    except OSError as e:
        ok, detail = False, f"couldn't run the runtime's Python ({e.strerror})"
    sf.write_text(json.dumps({"ok": ok, "detail": detail[:300], "at": time.time(),
                              "stamp": stamp}))
    return {"ok": ok, "detail": detail[:300], "python": str(py)}


def _site_mtime(name: str) -> int:
    """The venv's site-packages mtime — changes when pip adds or removes a
    package, so a manual install invalidates the cached verification."""
    try:
        sp = next((venv_dir(name) / "lib").glob("python3*/site-packages"))
        return sp.stat().st_mtime_ns
    except (StopIteration, OSError):
        return 0


def remove(name: str):
    shutil.rmtree(venv_dir(name), ignore_errors=True)
    _stamp_file(name).unlink(missing_ok=True)


def manual_commands(name: str, steps: List[List[str]],
                    env: Optional[dict] = None) -> List[str]:
    """The same install, as terminal lines — for the person who'd rather.
    The venv path is the exact place the app looks."""
    vd = venv_dir(name)
    base = find_system_python() or "python3.12"
    q = lambda s: f'"{s}"' if " " in s else s  # noqa: E731
    lines = [f"{base} -m venv {q(str(vd))}"]
    prefix = " ".join(f"{k}={v}" for k, v in (env or {}).items())
    for args in steps:
        arg = " ".join(f"'{a}'" if ("@" in a or " " in a) else a for a in args)
        lines.append(f"{prefix + ' ' if prefix else ''}"
                     f"{q(str(vd / 'bin' / 'python'))} -m pip {arg}")
    return lines


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
