#!/bin/bash
# control-z — rebuild PyAV from sdist against the LGPL FFmpeg from
# build_ffmpeg.sh. The PyPI wheel is what ships GPL x264/x265 (specs/09 §3);
# building from source against our prefix is the point, not an optimization.
set -euo pipefail
cd "$(dirname "$0")"

PREFIX="$(pwd)/vendor/ffmpeg"
REPO="$(cd .. && pwd)"
PIP="$REPO/.venv/bin/pip"
PY="$REPO/.venv/bin/python"
AV_VERSION="${AV_VERSION:-18.0.0}"

[ -x "$PREFIX/bin/ffmpeg" ] || { echo "FATAL: run build_ffmpeg.sh first"; exit 1; }

# PKG_CONFIG_LIBDIR replaces the DEFAULT search path — but PKG_CONFIG_PATH
# entries are searched FIRST and would still outrank it (adversarial review
# demonstrated exactly that with a decoy .pc), so it is explicitly unset. A
# Homebrew FFmpeg winning silently here reintroduces the GPL linkage this
# script exists to remove.
unset PKG_CONFIG_PATH
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"

echo "== build av $AV_VERSION from sdist =="
"$PIP" install "av==$AV_VERSION" --no-binary av --force-reinstall --no-cache-dir

echo "== gate: import, version, linkage =="
"$PY" - <<'PYEOF'
import av
print("av", av.__version__)
print("libavcodec", av.library_versions.get("libavcodec"))
# The license string is explicitly NOT trusted as evidence (specs/09 §3 trap 1)
# but a *GPL* answer here would still be an immediate red flag worth failing on.
lic = getattr(av, "license", None) or ""
assert "GPL " not in lic or "LGPL" in lic, f"avcodec reports GPL: {lic}"
PYEOF

SITE=$("$PY" -c "import av, pathlib; print(pathlib.Path(av.__file__).parent)")
FAIL=0
while IFS= read -r -d '' so; do
    LINKS=$(otool -L "$so")
    if echo "$LINKS" | grep -qE "x264|x265"; then
        echo "GPL LINKAGE: $so"; FAIL=1
    fi
    # every FFmpeg-family reference must resolve into our prefix, not a
    # wheel .dylibs dir or a Homebrew cellar — all seven libraries, not just
    # avcodec (an av built half-against-us, half-against-brew is exactly the
    # mixed-runtime crash the one-FFmpeg rule exists to prevent)
    if echo "$LINKS" | grep -E "libav(codec|format|util|filter|device)|libsw(scale|resample)" \
            | grep -qv "$PREFIX"; then
        echo "FOREIGN FFMPEG: $so"
        echo "$LINKS" | grep -E "libav|libsw"; FAIL=1
    fi
done < <(find "$SITE" -name "*.so" -print0)
if [ -d "$SITE/.dylibs" ]; then
    echo "FATAL: av/.dylibs exists — this is a wheel install, not our build"; FAIL=1
fi
[ "$FAIL" -eq 0 ] || exit 1
echo "PyAV linked against $PREFIX — no x264/x265 anywhere."
