"""Bundled-binary resolution: where ffmpeg/ffprobe actually live.

A Finder-launched frozen app inherits launchd's PATH — /opt/homebrew/bin is
not on it — so shutil.which() finds nothing even on a machine where Homebrew
ffmpeg exists. This looked fine forever in dev (terminal launches leak the
shell's PATH) and would break for every downloader (specs/09 §5). The
packaged app ships its own LGPL binaries anyway (packaging/build_ffmpeg.sh).

One resolver, three honest stops:
  1. frozen: the binaries bundled beside the app's code (czbin/)
  2. source checkout: PATH, via shutil.which
  3. neither: an exception whose sentence names the real problem
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


class ToolNotFound(RuntimeError):
    """A required external binary is absent; str() is the user-facing sentence."""


def _bundled_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    # PyInstaller onedir: _MEIPASS is the bundle's data root (Contents/
    # Frameworks in a 6.x .app). packaging/suite.spec places the binaries in
    # czbin/ under it — the two must move together.
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return base / "czbin"


def tool_path(name: str) -> str:
    bundled = _bundled_dir()
    if bundled is not None:
        cand = bundled / name
        if cand.is_file():
            return str(cand)
        # Frozen but absent is a packaging bug. Deliberately no PATH
        # fallback here: silently borrowing a user's Homebrew build would
        # mask the broken bundle (and change which FFmpeg users actually run).
        raise ToolNotFound(
            f"packaging bug: {name} is missing from this app bundle "
            f"(expected at {cand}). Please report this — the app should "
            f"never have shipped without it.")
    exe = shutil.which(name)
    if exe:
        return exe
    raise ToolNotFound(
        f"{name} not found. Running from source needs ffmpeg on PATH "
        f"(brew install ffmpeg); packaged control-z builds bundle it.")


def ffmpeg_path() -> str:
    return tool_path("ffmpeg")


def ffprobe_path() -> str:
    return tool_path("ffprobe")
