#!/bin/zsh
# Builds build/KPDetector.app.
#   ./build.sh                native architecture
#   ./build.sh --universal    arm64 + x86_64
# Env: VERSION (default 1.0), SIGN_IDENTITY (Developer ID; default: ad-hoc signature)
set -euo pipefail
cd "$(dirname "$0")"

ARCHS=()
[[ "${1:-}" == "--universal" ]] && ARCHS=(--arch arm64 --arch x86_64)
VERSION="${VERSION:-1.0}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"

swift build -c release "${ARCHS[@]}"
BIN="$(swift build -c release "${ARCHS[@]}" --show-bin-path)/KPDetector"

APP="build/KPDetector.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/"
strip -x "$APP/Contents/MacOS/KPDetector"
cp Resources/Info.plist "$APP/Contents/"
for lproj in Resources/*.lproj; do cp -R "$lproj" "$APP/Contents/Resources/"; done
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" -c "Set :CFBundleVersion $VERSION" "$APP/Contents/Info.plist"

if [[ "$SIGN_IDENTITY" == "-" ]]; then
    codesign --force --sign - "$APP"
else
    codesign --force --options runtime --timestamp --entitlements Resources/KPDetector.entitlements \
        --sign "$SIGN_IDENTITY" "$APP"
fi
echo "OK -> $APP ($(lipo -archs "$APP/Contents/MacOS/KPDetector"))"
