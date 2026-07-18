#!/bin/bash
# control-z Suite — freeze the app (specs/09 §5). Produces
# packaging/dist/control-z Suite.app, UNSIGNED — packaging/sign_suite.sh is
# the next step. Every gate here fails loudly: a guard around a release step
# fails loudly or it doesn't exist (specs/09 §2's lesson, paid for twice).
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(cd .. && pwd)"
VENV="$REPO/.venv"
APP="dist/control-z Suite.app"

echo "== preflight =="
[ -x "$VENV/bin/python" ] || { echo "FATAL: $VENV missing"; exit 1; }
[ -x "vendor/ffmpeg/bin/ffmpeg" ] || { echo "FATAL: run build_ffmpeg.sh first"; exit 1; }
# av must be OUR sdist build, not the GPL wheel — the wheel ships a .dylibs
# dir, ours doesn't. (tests/test_packaging.py checks the same thing.)
SITE=$("$VENV/bin/python" -c "import av,pathlib;print(pathlib.Path(av.__file__).parent)")
if [ -d "$SITE/.dylibs" ]; then
    echo "FATAL: av is the PyPI wheel (GPL x264/x265). Run build_pyav.sh."; exit 1
fi
"$VENV/bin/python" -c "import PyInstaller" 2>/dev/null || {
    echo "FATAL: PyInstaller not in the repo venv: .venv/bin/pip install -e '.[packaging]'"; exit 1; }

echo "== freeze (onedir) =="
# Two attempts: Finder drops .DS_Store into a browsed dist/ mid-delete and
# rm reports "Directory not empty" — a race, not a permission problem.
rm -rf build dist 2>/dev/null || true
rm -rf build dist
"$VENV/bin/python" -m PyInstaller suite.spec --noconfirm --distpath dist --workpath build

echo "== gate: the venv reaches for no Homebrew library =="
# This must run against the VENV, not the frozen tree: PyInstaller rewrites
# collected /opt/homebrew paths to @loader_path, so an app-tree grep for the
# string is a gate that cannot fire. Pre-collection load commands are where
# the truth lives. (The Homebrew AVIF stack once rode in via cv2 exactly this
# way and set the app's macOS floor to 26.)
FAIL=0
while IFS= read -r -d '' so; do
    if otool -L "$so" 2>/dev/null | tail -n +2 | grep -q "/opt/homebrew"; then
        echo "HOMEBREW LINKAGE: $so"
        otool -L "$so" | grep "/opt/homebrew" | head -3
        FAIL=1
    fi
done < <(find "$SITE/.." -maxdepth 4 \( -name "*.so" -o -name "*.dylib" \) -type f -print0)
[ "$FAIL" -eq 0 ] || exit 1

echo "== gate: the app tree carries no GPL library =="
while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q "Mach-O"; then
        if otool -L "$f" 2>/dev/null | tail -n +2 | grep -qE "x264|x265|libpostproc|libvidstab"; then
            echo "GPL LINKAGE: $f"; FAIL=1
        fi
    fi
done < <(find "$APP" -type f -print0)
[ "$FAIL" -eq 0 ] || exit 1

echo "== gate: exactly one FFmpeg (the cv2 second-copy hazard) =="
MAJORS=$(find "$APP" -name "libavcodec*.dylib" -type f | sed -E 's/.*libavcodec\.([0-9]+).*/\1/' | sort -u)
COUNT=$(echo "$MAJORS" | grep -c . || true)
if [ "$COUNT" -gt 1 ]; then
    echo "FATAL: multiple libavcodec majors in the bundle: $MAJORS"; exit 1
fi

echo "== gate: the assets that die silently when missing =="
FW="$APP/Contents/Frameworks"
RS="$APP/Contents/Resources"
# faster-whisper's VAD model: absent = Scribe dies on FIRST transcribe.
find "$FW" "$RS" -ipath "*faster_whisper*silero*" 2>/dev/null | grep -q . || {
    echo "FATAL: faster_whisper silero VAD asset missing (Scribe would die on first transcribe)"; exit 1; }
# the bundled binaries czcore/tools.py resolves
for b in ffmpeg ffprobe; do
    B=$(find "$FW" "$RS" -path "*czbin/$b" 2>/dev/null | head -1)
    [ -n "$B" ] && [ -x "$B" ] || { echo "FATAL: bundled $b missing/not executable"; exit 1; }
done
# UI + Fusion templates at their load-bearing destinations. The bundled
# template count must match the SOURCE tree (the pack's size belongs to
# specs/10 and has already grown once); the freeze contract is "all of them
# made it in", not a number.
find "$FW" "$RS" -path "*suite/static/app.css" | grep -q . || { echo "FATAL: suite/static missing"; exit 1; }
# Interpreter's seed glossary: absent = the Brookline names/terms never load
# and every town opens empty (glossary.py resolves interpreter/glossaries/
# by package path, which pyproject package-data covers for a wheel but the
# freeze must carry as datas — suite.spec does).
find "$FW" "$RS" -path "*interpreter/glossaries/*.json" | grep -q . || {
    echo "FATAL: interpreter glossary seeds missing (every town would open empty)"; exit 1; }
N_SRC=$(find "$REPO/depth/templates" -name "*.setting" | wc -l | tr -d ' ')
N_SETTINGS=$(find "$FW" "$RS" -path "*depth/templates/*.setting" | wc -l | tr -d ' ')
[ "$N_SETTINGS" -eq "$N_SRC" ] && [ "$N_SRC" -ge 5 ] || {
    echo "FATAL: depth templates: $N_SRC in source, $N_SETTINGS in bundle"; exit 1; }

echo "== measure the real macOS floor and write it into the plist =="
# The floor is a MEASUREMENT (max minos over every Mach-O we ship), never a
# declaration. Today the Homebrew-built Python sets it; swapping interpreters
# changes it automatically here, with no stale string left behind.
MINOS=$(find "$APP" -type f -print0 | while IFS= read -r -d '' f; do
    file -b "$f" | grep -q "Mach-O" || continue
    otool -l "$f" 2>/dev/null | awk '/LC_BUILD_VERSION/{v=1} v&&/minos/{print $2; exit}'
done | sort -V | tail -1)
[ -n "$MINOS" ] || { echo "FATAL: could not measure a minos floor"; exit 1; }
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string $MINOS" \
    "$APP/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion $MINOS" "$APP/Contents/Info.plist"
echo "  LSMinimumSystemVersion = $MINOS (measured — this is a download-page sentence)"

echo
du -sh "$APP" | sed 's/^/  bundle size: /'
echo "Unsigned app ready: packaging/$APP"
echo "Next: packaging/sign_suite.sh"
