#!/bin/bash
# control-z — build the LGPL FFmpeg the covenant mandates (specs/00, specs/09 §3).
#
# Why this exists: the PyAV wheel on PyPI links GPL libx264/libx265, and cv2
# bundles a second FFmpeg doing the same. otool -L is the authority for that
# claim — avcodec_license() says "LGPL" and PyPI metadata says "BSD-3-Clause",
# and both are wrong (specs/09 §3). A frozen .app must carry an FFmpeg we built:
#
#   - LGPL-2.1 only: no --enable-gpl, no --enable-version3, no --enable-nonfree.
#     version3 stays off deliberately: it buys only opencore-amr (nothing here
#     reads AMR) and would widen the license to LGPL-3.0.
#   - no external codec libraries at all — x264/x265 are not merely disabled,
#     they are never reachable from this tree.
#   - VideoToolbox + AudioToolbox on (hardware H.264/HEVC/ProRes per specs/00).
#   - shared libs: LGPL's relink story wants shared linking, and PyAV's setup
#     refuses static FFmpeg anyway.
#
# The same build supplies the bundled ffmpeg/ffprobe binaries specs/00 has
# always promised. Everything lands in packaging/vendor/ (gitignored).
set -euo pipefail
cd "$(dirname "$0")"

FFMPEG_VERSION="${FFMPEG_VERSION:-8.1.2}"
# sha256 of ffmpeg-8.1.2.tar.xz as fetched from https://ffmpeg.org/releases on
# 2026-07-16. First fetch was trusted on TLS to ffmpeg.org; pinned thereafter.
# An empty pin means "first fetch": the script records the hash it saw and
# refuses subsequent runs until the recorded hash is pasted here.
FFMPEG_SHA256="${FFMPEG_SHA256:-464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c}"

VENDOR="$(pwd)/vendor"
SRC_DIR="$VENDOR/src"
PREFIX="$VENDOR/ffmpeg"
TARBALL="$SRC_DIR/ffmpeg-$FFMPEG_VERSION.tar.xz"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"

mkdir -p "$SRC_DIR"

echo "== fetch ffmpeg-$FFMPEG_VERSION =="
OBSERVED="$SRC_DIR/ffmpeg-$FFMPEG_VERSION.sha256.observed"
# TOFU that actually closes: the FIRST run records what it fetched; every
# later unpinned run is refused until the recorded hash is pasted into
# FFMPEG_SHA256 above. (Adversarial review: the earlier draft printed the
# note and carried on forever, which is not a pin, it's a diary.)
if [ -z "$FFMPEG_SHA256" ] && [ -f "$OBSERVED" ]; then
    echo "FATAL: no FFMPEG_SHA256 pinned, but a previous fetch recorded:"
    sed 's/^/    /' "$OBSERVED"
    echo "  Pin that value in this script (or delete $OBSERVED to re-fetch)."
    exit 1
fi
if [ ! -f "$TARBALL" ]; then
    # download to a .part and rename only on success, so an interrupted
    # transfer can never be cached as the authoritative tarball
    curl -fL --retry 3 -o "$TARBALL.part" \
        "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz"
    mv "$TARBALL.part" "$TARBALL"
fi
GOT_SHA=$(shasum -a 256 "$TARBALL" | awk '{print $1}')
if [ -n "$FFMPEG_SHA256" ]; then
    if [ "$GOT_SHA" != "$FFMPEG_SHA256" ]; then
        echo "FATAL: ffmpeg tarball sha256 mismatch"
        echo "  expected: $FFMPEG_SHA256"
        echo "  got:      $GOT_SHA"
        exit 1
    fi
else
    echo "NOTE: first fetch (trusted on TLS to ffmpeg.org). It hashed to:"
    echo "  $GOT_SHA"
    echo "Pin it in FFMPEG_SHA256; unpinned re-runs will refuse."
    echo "$GOT_SHA" > "$OBSERVED"
fi

echo "== unpack =="
rm -rf "$SRC_DIR/ffmpeg-$FFMPEG_VERSION"
tar -xJf "$TARBALL" -C "$SRC_DIR"

echo "== configure (LGPL-2.1, shared, no external codec libs) =="
cd "$SRC_DIR/ffmpeg-$FFMPEG_VERSION"
./configure \
    --prefix="$PREFIX" \
    --enable-shared --disable-static \
    --enable-videotoolbox --enable-audiotoolbox \
    --disable-ffplay --disable-doc --disable-sdl2 \
    --disable-xlib --disable-libxcb

# The configure output is not the gate (otool below is), but a GPL flag here
# means the invocation above was edited badly — fail before wasting a build.
if grep -qE "^CONFIG_(GPL|VERSION3|NONFREE)=yes" ffbuild/config.mak; then
    echo "FATAL: GPL/version3/nonfree leaked into the configuration"; exit 1
fi

echo "== build =="
make -j"$(sysctl -n hw.ncpu)" >/dev/null
rm -rf "$PREFIX"
make install >/dev/null

echo "== linkage gate (in the build itself; tests/test_packaging.py re-checks the app tree) =="
FAIL=0
CHECKED=0
for f in "$PREFIX"/lib/*.dylib "$PREFIX"/bin/ffmpeg "$PREFIX"/bin/ffprobe; do
    [ -f "$f" ] && [ ! -L "$f" ] || continue
    CHECKED=$((CHECKED + 1))
    if otool -L "$f" | grep -qE "x264|x265|libpostproc"; then
        echo "GPL LINKAGE: $f"; otool -L "$f" | grep -E "x264|x265|libpostproc"; FAIL=1
    fi
done
# a gate that inspected nothing has not gated anything
if [ "$CHECKED" -lt 8 ]; then
    echo "FATAL: only $CHECKED binaries found under $PREFIX — install went wrong"; FAIL=1
fi
# libpostproc only builds under --enable-gpl; its absence is a second witness.
if ls "$PREFIX"/lib/libpostproc* >/dev/null 2>&1; then
    echo "FATAL: libpostproc built — this build thinks it is GPL"; FAIL=1
fi
[ "$FAIL" -eq 0 ] || exit 1

echo "== capability gate: the encoders the presets resolve to must exist =="
ENC=$("$PREFIX/bin/ffmpeg" -hide_banner -encoders 2>/dev/null)
for e in h264_videotoolbox hevc_videotoolbox prores_videotoolbox prores_ks dnxhd aac pcm_s16le; do
    echo "$ENC" | grep -q " $e " || { echo "FATAL: encoder missing: $e"; exit 1; }
done
if echo "$ENC" | grep -qE "libx264|libx265"; then
    echo "FATAL: a GPL encoder is registered"; exit 1
fi
"$PREFIX/bin/ffmpeg" -hide_banner -version | head -2
echo
echo "LGPL FFmpeg ready at: $PREFIX"
