#!/bin/zsh
# Builds a universal app and packages it as dist/KPDetector-<version>.dmg and .zip.
# Env: VERSION (default 1.0)
#      SIGN_IDENTITY   "Developer ID Application: Name (TEAMID)" -> signed with hardened runtime
#      NOTARY_PROFILE  notarytool keychain profile -> notarizes and staples the DMG (needs SIGN_IDENTITY)
set -euo pipefail
cd "$(dirname "$0")/.."

export VERSION="${VERSION:-1.0}"
./build.sh --universal

DIST=dist
DMG="$DIST/KPDetector-$VERSION.dmg"
ZIP="$DIST/KPDetector-$VERSION.zip"
rm -rf "$DIST" && mkdir -p "$DIST"

# Zip (ditto keeps signatures and attributes)
ditto -c -k --keepParent build/KPDetector.app "$ZIP"

# DMG with an Applications shortcut for drag-and-drop install
STAGE="$(mktemp -d)"
cp -R build/KPDetector.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "KP Detector" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

if [[ -n "${SIGN_IDENTITY:-}" && "$SIGN_IDENTITY" != "-" ]]; then
    codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG"
    if [[ -n "${NOTARY_PROFILE:-}" ]]; then
        xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
        xcrun stapler staple "$DMG"
    fi
fi

shasum -a 256 "$DMG" "$ZIP" | tee "$DIST/SHA256SUMS.txt"
echo "OK -> $DMG"
