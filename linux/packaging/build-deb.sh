#!/bin/sh
# Builds dist/kp-detector_<version>_all.deb (run from anywhere). Needs dpkg-deb (Debian/Ubuntu).
#   VERSION=1.0.2 linux/packaging/build-deb.sh
set -eu
cd "$(dirname "$0")/.."
VERSION="${VERSION:-$(python3 -c 'import kp_detector; print(kp_detector.__version__)')}"
PKG="kp-detector_${VERSION}_all"
OUT="../dist"
STAGE="$(mktemp -d)/$PKG"

install -d "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/kp-detector" \
    "$STAGE/usr/share/applications" "$STAGE/usr/share/icons" "$STAGE/usr/share/doc/kp-detector"
cp -R kp_detector "$STAGE/usr/lib/kp-detector/"
find "$STAGE" -name '__pycache__' -prune -exec rm -rf {} +
install -m 755 packaging/kp-detector.sh "$STAGE/usr/bin/kp-detector"
install -m 644 data/kp-detector.desktop "$STAGE/usr/share/applications/kp-detector.desktop"
cp -R data/icons/hicolor "$STAGE/usr/share/icons/"
install -m 644 ../LICENSE "$STAGE/usr/share/doc/kp-detector/copyright"
find "$STAGE/usr" -type d -exec chmod 755 {} +
find "$STAGE/usr/lib" "$STAGE/usr/share" -type f -exec chmod 644 {} +

SIZE=$(du -sk "$STAGE/usr" | cut -f1)
cat > "$STAGE/DEBIAN/control" <<CTRL
Package: kp-detector
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.9), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-notify-0.7, gir1.2-ayatanaappindicator3-0.1
Recommends: gnome-shell-extension-appindicator, geoclue-2.0
Maintainer: Bertrand LE GAL <bertrand.legal@gmail.com>
Homepage: https://github.com/blegal/kp-detector
Description: Geomagnetic Kp index and aurora chances in the top bar
 Shows the current planetary Kp index in the GNOME top bar, with a 7-day
 history, a 3-day forecast, the Kp needed to see an aurora at your location
 and desktop/email alerts when a geomagnetic storm is forecast.
 Data: NOAA Space Weather Prediction Center.
CTRL
cat > "$STAGE/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
exit 0
POST
chmod 755 "$STAGE/DEBIAN/postinst"

mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT/$PKG.deb"
echo "OK -> $OUT/$PKG.deb"
