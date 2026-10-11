"""Position : GeoClue2 (D-Bus) → repli par IP (optionnel) ; ou coordonnées manuelles."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

from .core import _get


@dataclass
class Location:
    lat: float
    lon: float
    place: Optional[str] = None


def geoclue(timeout: float = 10.0) -> Optional[Location]:
    try:
        from gi.repository import Gio, GLib
    except Exception:
        return None
    A, IFACE = "org.freedesktop.GeoClue2", "org.freedesktop.GeoClue2.Client"
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        def proxy(path, iface):
            return Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None, A, path, iface, None)

        def call(p, method, params=None):
            return p.call_sync(method, params, Gio.DBusCallFlags.NONE, 5000, None)

        client_path = call(proxy("/org/freedesktop/GeoClue2/Manager", A + ".Manager"), "GetClient").unpack()[0]
        props = proxy(client_path, "org.freedesktop.DBus.Properties")
        client = proxy(client_path, IFACE)
        call(props, "Set", GLib.Variant("(ssv)", (IFACE, "DesktopId", GLib.Variant("s", "kp-detector"))))
        call(props, "Set", GLib.Variant("(ssv)", (IFACE, "RequestedAccuracyLevel", GLib.Variant("u", 4))))  # city
        call(client, "Start")
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                path = call(props, "Get", GLib.Variant("(ss)", (IFACE, "Location"))).unpack()[0]
                if path and path != "/":
                    lp = proxy(path, "org.freedesktop.DBus.Properties")
                    li = A + ".Location"
                    lat = call(lp, "Get", GLib.Variant("(ss)", (li, "Latitude"))).unpack()[0]
                    lon = call(lp, "Get", GLib.Variant("(ss)", (li, "Longitude"))).unpack()[0]
                    return Location(float(lat), float(lon))
                time.sleep(0.5)
        finally:
            try:
                call(client, "Stop")
            except Exception:
                pass
    except Exception:
        return None
    return None


def ip_lookup() -> Optional[Location]:
    try:
        d = json.loads(_get("https://ipwho.is/", timeout=10))
        if d.get("success"):
            place = ", ".join(x for x in (d.get("city"), d.get("country")) if x)
            return Location(float(d["latitude"]), float(d["longitude"]), place or None)
    except Exception:
        pass
    return None


def resolve(cfg) -> Optional[Location]:
    """Bloquant : à appeler hors du thread GTK."""
    if cfg["location_mode"] == "manual":
        return Location(float(cfg["lat"]), float(cfg["lon"]))
    loc = geoclue()
    if loc is None and cfg["ip_fallback"]:
        loc = ip_lookup()
    return loc
