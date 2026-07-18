#!/bin/bash
# Double-click this in Finder to run Civic Media Studio.
#
# First run: builds a private .venv next to this file and installs what the
# tools need (a few minutes, a few hundred MB). Every run after: opens in
# seconds. Nothing is installed system-wide; deleting this folder removes it
# all. Local only — no accounts, no telemetry.

cd "$(dirname "$0")" || exit 1
VENV=".venv"
STAMP="$VENV/.control-z-deps-installed"

say_line() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# --- python ---------------------------------------------------------------
PY=""
for cand in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; print("%d%02d" % sys.version_info[:2])' 2>/dev/null)
    if [ -n "$ver" ] && [ "$ver" -ge 310 ] 2>/dev/null; then PY="$cand"; break; fi
  fi
done
if [ -z "$PY" ]; then
  say_line "control-z needs Python 3.10 or newer."
  echo "Install it from https://www.python.org/downloads/ (or: brew install python)"
  echo "then double-click this file again."
  echo; read -r -p "Press return to close."
  exit 1
fi

# --- ffmpeg (media IO) ----------------------------------------------------
if ! command -v ffprobe >/dev/null 2>&1; then
  say_line "control-z needs ffmpeg for media probing."
  echo "Install it with:  brew install ffmpeg"
  echo "(A future packaged build will bundle it — this dev checkout doesn't.)"
  echo; read -r -p "Press return to close."
  exit 1
fi

# --- venv + deps ----------------------------------------------------------
if [ ! -d "$VENV" ]; then
  say_line "First run — building a private Python environment (a few minutes)…"
  "$PY" -m venv "$VENV" || { echo "venv failed"; read -r -p "Press return to close."; exit 1; }
fi

if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
  say_line "Installing what the tools need (this takes a few minutes)…"
  "$VENV/bin/pip" install --quiet --upgrade pip
  if "$VENV/bin/pip" install -r requirements.txt; then
    date > "$STAMP"
  else
    say_line "Install failed — the error is above."
    echo "Nothing was changed outside this folder. Fix the error, or ask for help at"
    echo "https://github.com/amateurmenace/control-z/issues"
    echo; read -r -p "Press return to close."
    exit 1
  fi
fi

# --- go -------------------------------------------------------------------
say_line "Starting Civic Media Studio…"
echo "Close this window (or press Ctrl-C) to quit the app."
exec "$VENV/bin/python" -m suite "$@"
