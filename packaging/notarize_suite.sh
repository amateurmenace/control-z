#!/bin/bash
# control-z Suite — notarize, staple, and build the DMG (specs/09 §4).
#
# Order of operations is load-bearing: the .app is stapled FIRST and the DMG
# is built FROM the stapled copy, then the DMG gets its own submission and
# ticket. Built the other way, the DMG's ticket covers the download while the
# dragged-out app carries none — it then works online and fails offline,
# the worst possible bug shape. (The sibling repos shipped exactly that zip
# for two releases.)
#
# Two submissions is correct, not wasteful.
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/control-z Suite.app"
NOTARY_PROFILE="${NOTARY_PROFILE:-opennr-notary}"
[ -d "$APP" ] || { echo "FATAL: $APP missing"; exit 1; }

# The app must be Developer-ID signed already; notarizing an ad-hoc app is a
# guaranteed rejection with a misleading error. TeamIdentifier is the check:
# `codesign -dv` prints it always, whereas Authority= lines only appear at
# -dvv (that mismatch false-failed this guard once). One retry, and the
# guard shows codesign's actual words: a transient codesign failure (e.g.
# the app still shutting down from a smoke run) is not "unsigned", and a
# guard that swallows its evidence into grep -q misleads exactly when it
# matters.
SIGINFO=$(codesign -dv "$APP" 2>&1) || true
if ! echo "$SIGINFO" | grep -q "TeamIdentifier=6M536MV7GT"; then
    sleep 3
    SIGINFO=$(codesign -dv "$APP" 2>&1) || true
    if ! echo "$SIGINFO" | grep -q "TeamIdentifier=6M536MV7GT"; then
        echo "FATAL: app is not signed by team 6M536MV7GT — run sign_suite.sh"
        echo "codesign said:"; echo "$SIGINFO" | sed 's/^/    /'
        exit 1
    fi
fi

if ! xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" >/dev/null 2>&1; then
    echo "FATAL: no notarytool profile '$NOTARY_PROFILE'."
    echo "  Stephen stores it himself (never paste the app-specific password"
    echo "  into a terminal an agent drives):"
    echo "    xcrun notarytool store-credentials $NOTARY_PROFILE --apple-id <id> --team-id 6M536MV7GT"
    exit 1
fi

VERSION=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Contents/Info.plist")
DMG="dist/control-z-suite-$VERSION-macos-arm64.dmg"

submit() {  # submit <artifact> — waits; on anything but Accepted, prints the log
    local artifact="$1"
    local out id status
    echo "  submitting $(basename "$artifact") ($(du -h "$artifact" | cut -f1 | tr -d ' '))..."
    out=$(xcrun notarytool submit "$artifact" --keychain-profile "$NOTARY_PROFILE" \
          --wait --timeout 30m 2>&1) || true
    echo "$out" | sed 's/^/    /'
    if echo "$out" | grep -qE "HTTP status code: 403|required agreement"; then
        echo "STOP: Apple returned 403 'required agreement'. This is NOT a bad"
        echo "  password — the Developer Program License Agreement needs"
        echo "  re-accepting at developer.apple.com, and only Stephen can click it."
        exit 78
    fi
    id=$(echo "$out" | awk '/^  id: /{print $2; exit}')
    status=$(echo "$out" | awk '/status: /{s=$2} END{print s}')
    if [ "$status" != "Accepted" ]; then
        echo "REJECTED (status: ${status:-unknown}). The notary log is the only"
        echo "thing that says what Apple actually objected to:"
        [ -n "$id" ] && xcrun notarytool log "$id" --keychain-profile "$NOTARY_PROFILE" | sed 's/^/    /'
        exit 1
    fi
}

echo "== notarize the .app =="
rm -f dist/_submit.zip
ditto -c -k --keepParent "$APP" dist/_submit.zip
submit dist/_submit.zip
rm -f dist/_submit.zip
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"

echo "== DMG, built from the STAPLED app =="
STAGE="dist/dmgroot"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
# the volume wears the logo. The custom-icon bit does NOT survive a direct
# -srcfolder create (measured) — build RW, set the bit on the mounted root,
# convert to the compressed read-only image.
cp icon.icns "$STAGE/.VolumeIcon.icns"
# The LGPL travels WITH the download, not just with the repo. We bundle an
# LGPL-2.1 FFmpeg, so the licence text and the written offer for source have
# to reach whoever receives the DMG — a user who never sees this repository.
# They sit BESIDE the .app, never inside it: the app is already signed and
# stapled by this point, and staging a sibling file needs no re-sign.
cp ../NOTICE "$STAGE/NOTICE.txt"
cp vendor/src/ffmpeg-8.1.2/COPYING.LGPLv2.1 "$STAGE/LICENSE-FFmpeg-LGPL-2.1.txt"
rm -f "$DMG" dist/_rw.dmg
hdiutil create -volname "control-z Suite" -srcfolder "$STAGE" -ov -format UDRW -quiet dist/_rw.dmg
hdiutil attach -quiet dist/_rw.dmg
if command -v SetFile >/dev/null 2>&1 || xcrun -f SetFile >/dev/null 2>&1; then
    (SetFile -a C "/Volumes/control-z Suite" 2>/dev/null || \
     xcrun SetFile -a C "/Volumes/control-z Suite")
else
    echo "  note: SetFile unavailable — volume icon bit not set (cosmetic)"
fi
hdiutil detach -quiet "/Volumes/control-z Suite"
hdiutil convert -quiet dist/_rw.dmg -format UDZO -o "$DMG"
rm -f dist/_rw.dmg
rm -rf "$STAGE"

DEV_ID=$(security find-identity -v -p codesigning 2>/dev/null \
    | grep -o '"Developer ID Application: [^"]*"' | head -1 | tr -d '"')
codesign --timestamp --sign "$DEV_ID" "$DMG"

echo "== notarize the DMG (its own artifact, its own ticket) =="
submit "$DMG"
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"

echo
echo "== the verdicts that matter (not 'the script ran') =="
spctl -a -vvv "$APP" 2>&1 | sed 's/^/  app: /'
spctl -a -t open --context context:primary-signature -v "$DMG" 2>&1 | sed 's/^/  dmg: /'
echo
shasum -a 256 "$DMG"
echo "Remaining gate that CANNOT run here: spctl on a machine that has never"
echo "seen a dev cert or Homebrew (specs/09 §7). That is Stephen's Mac-mini/"
echo "loaner test, before the release tag."
