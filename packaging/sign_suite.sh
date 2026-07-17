#!/bin/bash
# control-z Suite — sign the frozen app (specs/09 §4).
#
# Inside-out, leaf-first, batched. Mach-O by INSPECTION, never by extension:
# the first extension-matched pass in the research build missed
# Python.framework/Versions/3.14/Python (no extension) and the app died at
# launch with "different Team IDs" — the exact failure that tempts people
# into disable-library-validation. The bug is an unsigned nested Mach-O; the
# entitlement would only mask it.
#
# ZERO entitlements, verified sufficient: onnxruntime+CoreML runs real
# inference under a full Developer ID hardened-runtime signature with no
# entitlements file at all (specs/09 §4, measured). Every entitlement must be
# justified in writing here or it doesn't ship — and none is.
#
# --deep is used on VERIFY only. codesign --deep on a 500-Mach-O bundle signs
# in the wrong order and rewrites nested seals; it does not transfer from the
# single-binary plugin scripts.
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/control-z Suite.app"
[ -d "$APP" ] || { echo "FATAL: $APP missing — run build_suite.sh first"; exit 1; }

# Identity: grep the literal Developer ID Application string. The FIRST
# identity in this keychain belongs to a different team (597T4G6JU5), so a
# bare `security find-identity | head -1` signs with the wrong team.
DEV_ID=$(security find-identity -v -p codesigning 2>/dev/null \
    | grep -o '"Developer ID Application: [^"]*"' | head -1 | tr -d '"') || true
if [ -z "${DEV_ID:-}" ]; then
    echo "FATAL: no Developer ID Application identity in the keychain."
    echo "  (Refusing to ad-hoc sign a release candidate: an ad-hoc app"
    echo "   cannot be notarized, and shipping one is how the siblings"
    echo "   shipped Gatekeeper-rejected. For local dev the unsigned build"
    echo "   from build_suite.sh already runs.)"
    exit 1
fi
echo "signing with: $DEV_ID"

MAIN="$APP/Contents/MacOS/control-z Suite"

echo "== leaf pass: every nested Mach-O, by file(1) inspection =="
# -type f skips symlinks (codesign errors on them — sherpa_onnx ships one);
# the main executable is excluded here and signed after all its dependents.
COUNT=0
while IFS= read -r -d '' f; do
    file -b "$f" | grep -q "Mach-O" || continue
    [ "$f" = "$MAIN" ] && continue
    printf '%s\0' "$f"
    COUNT=$((COUNT + 1))
done < <(find "$APP/Contents" -type f -print0) \
    | xargs -0 codesign --force --timestamp --options runtime --sign "$DEV_ID"
echo "  signed nested Mach-O files (see verify below)"

echo "== framework seal =="
# The inner Versions/3.14/Python binary was signed by the leaf pass; the
# framework bundle carries its own seal on top.
FRAMEWORK=$(find "$APP/Contents" -maxdepth 3 -name "Python.framework" -type d | head -1)
if [ -n "$FRAMEWORK" ]; then
    codesign --force --timestamp --options runtime --sign "$DEV_ID" "$FRAMEWORK"
fi

echo "== main executable =="
codesign --force --timestamp --options runtime --sign "$DEV_ID" "$MAIN"

echo "== the .app (outer seal, NO entitlements — see header) =="
codesign --force --timestamp --options runtime --sign "$DEV_ID" "$APP"

echo "== verify (--deep belongs HERE, not on signing) =="
codesign --verify --strict --deep --verbose=1 "$APP"
codesign -dv "$APP" 2>&1 | grep -E "Authority=Developer ID Application|flags=" | head -3

echo
echo "Signed. Next: packaging/notarize_suite.sh (submits, staples, builds the DMG)."
