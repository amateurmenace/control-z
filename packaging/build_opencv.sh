#!/bin/bash
# control-z — rebuild opencv-python from sdist WITHOUT FFmpeg (specs/09 §3).
#
# The PyPI wheel bundles a second, GPL-linked FFmpeg (libavcodec 61 + x264/x265)
# that (a) nothing here uses — no VideoCapture/VideoWriter call site exists in
# the repo; every decode goes through PyAV — and (b) collides with PyAV's
# FFmpeg at the ObjC runtime in a frozen app (duplicate AVFFrameReceiver, an
# observed launch-log warning and a latent nondeterministic crash).
# Building with WITH_FFMPEG=OFF removes both problems at the root.
set -euo pipefail
cd "$(dirname "$0")"

REPO="$(cd .. && pwd)"
PIP="$REPO/.venv/bin/pip"
PY="$REPO/.venv/bin/python"
CV_VERSION="${CV_VERSION:-5.0.0.93}"

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"
# Only FFmpeg goes. Everything else stays at the wheel's defaults so runtime
# behaviour (dnn, objdetect/FaceDetectorYN, imgproc) does not drift.
export CMAKE_ARGS="-DWITH_FFMPEG=OFF"

echo "== build opencv-python $CV_VERSION from sdist (long — tens of minutes) =="
"$PIP" install "opencv-python==$CV_VERSION" --no-binary opencv-python \
    --force-reinstall --no-cache-dir

echo "== gate: import, modules, linkage =="
"$PY" - <<'PYEOF'
import cv2
print("cv2", cv2.__version__)
# the two OpenCV surfaces the suite actually uses must survive the rebuild
assert hasattr(cv2, "FaceDetectorYN"), "objdetect/FaceDetectorYN missing"
assert hasattr(cv2, "dnn"), "dnn missing"
info = cv2.getBuildInformation()
for line in info.splitlines():
    if "FFMPEG" in line:
        print(line.strip())
        assert "YES" not in line.split(":")[-1], "FFmpeg still enabled"
PYEOF

SITE=$("$PY" -c "import cv2, pathlib; print(pathlib.Path(cv2.__file__).parent)")
if find "$SITE" \( -name "*avcodec*" -o -name "*x264*" -o -name "*x265*" \) | grep -q .; then
    echo "FATAL: FFmpeg/x264/x265 dylibs still present under cv2/"; exit 1
fi
while IFS= read -r -d '' so; do
    if otool -L "$so" | grep -qE "x264|x265|avcodec"; then
        echo "FATAL: GPL/FFmpeg linkage in $so"; exit 1
    fi
done < <(find "$SITE" \( -name "*.so" -o -name "*.dylib" \) -type f -print0)
echo "cv2 rebuilt with no FFmpeg — one FFmpeg in the app, ours."
