"""Application : indicateur dans la barre GNOME (AppIndicator), panneau, rafraîchissement, alertes."""
from __future__ import annotations

import datetime as dt
import locale
import os
import sys
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify  # noqa: E402
except (ValueError, ImportError):
    Notify = None

AppIndicator = None
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as AppIndicator  # noqa: E402
    except (ValueError, ImportError):
        AppIndicator = None

from . import core, location  # noqa: E402
from .alerts import Alerter  # noqa: E402
from .config import Config  # noqa: E402
from .i18n import T  # noqa: E402
from .ui import PanelView, PanelWindow, SettingsDialog  # noqa: E402

APP_ID = "io.github.blegal.KPDetector"
REFRESH_SECONDS = 900
AUTOSTART = os.path.expanduser("~/.config/autostart/kp-detector.desktop")


def _icon_dirs() -> list:
    here = os.path.dirname(os.path.abspath(__file__))
    return [p for p in (os.path.join(here, "..", "data", "icons"),) if os.path.isdir(p)]


class KPApp(Gtk.Application):
    def __init__(self):
        flags = Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        if "--screenshot" in sys.argv:
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=APP_ID, flags=flags)
        self.add_main_option("background", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Start hidden (autostart)", None)
        self.add_main_option("test-alert", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Send a test alert", None)
        self.add_main_option("screenshot", 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "Render the panel to DIR/panel-<lang>.png and quit", "DIR")
        self.cfg = Config()
        self.model = core.Model()
        self.alerter = Alerter(self.cfg, self._notify, self._set_error)
        self.indicator = None
        self.window = None
        self._started = False
        self._last_aurora = 0.0
        self._refreshes = 0
        self._menu_items = {}

    # -- cycle de vie ---------------------------------------------------------
    def do_command_line(self, cmd):
        opts = cmd.get_options_dict().end().unpack()
        if "screenshot" in opts:
            self.hold()
            self._screenshot(opts["screenshot"])
            return 0
        if not self._started:
            self._started = True
            self._startup(background="background" in opts)
        elif "background" not in opts:
            self.show_panel()
        if "test-alert" in opts:
            self.alerter.send_test()
        return 0

    def _startup(self, background: bool):
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        if Notify:
            Notify.init("KP Detector")
        self.hold()
        self.window = PanelWindow(self.model, self.open_settings, self.refresh)
        self.window.set_application(self)
        self._build_indicator()
        self.refresh()
        self._resolve_location()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)
        if self.indicator is None or not background:
            self.show_panel()

    def _tick(self):
        self._refreshes += 1
        if self._refreshes % 4 == 0:
            self._resolve_location()
        self.refresh()
        return True

    # -- indicateur -----------------------------------------------------------
    def _build_indicator(self):
        if AppIndicator is None:
            return
        ind = AppIndicator.Indicator.new("kp-detector", "kp-detector-symbolic",
                                         AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        for d in _icon_dirs():
            ind.set_icon_theme_path(os.path.abspath(d))
        ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        ind.set_title("KP Detector")
        ind.set_label("Kp …", "Kp 9.9 🟢")
        menu = Gtk.Menu()

        def item(key, text, cb=None, sensitive=True):
            it = Gtk.MenuItem(label=text)
            it.set_sensitive(sensitive)
            if cb:
                it.connect("activate", lambda *_: cb())
            menu.append(it)
            self._menu_items[key] = it
            return it

        item("status", T("Loading…"), sensitive=False)
        item("peak", "", sensitive=False)
        item("place", "", sensitive=False)
        menu.append(Gtk.SeparatorMenuItem())
        item("open", T("Open panel"), self.show_panel)
        item("refresh", T("Refresh"), self.refresh)
        item("settings", T("Settings…"), self.open_settings)
        menu.append(Gtk.SeparatorMenuItem())
        item("quit", T("Quit"), self.quit)
        menu.show_all()
        for k in ("peak", "place"):
            self._menu_items[k].hide()
        ind.set_menu(menu)
        self.indicator = ind

    def _update_indicator(self):
        cur = self.model.current
        if not (self.indicator and cur):
            return
        lvl = core.level(cur.kp)
        self.indicator.set_label("%s Kp %.1f" % (core.LEVEL_EMOJI[lvl], cur.kp), "🟢 Kp 9.9")
        self._menu_items["status"].set_label("Kp %.1f · %s" % (cur.kp, T(core.label_key(cur.kp))))
        peak = core.peak_next_24h(self.model.samples)
        if peak:
            self._menu_items["peak"].set_label("%s : Kp %.1f" % (T("Peak forecast (24 h)"), peak.kp))
            self._menu_items["peak"].show()
        if self.model.coord:
            self._menu_items["place"].set_label("📍 " + (self.model.place or "%.2f°, %.2f°" % self.model.coord))
            self._menu_items["place"].show()

    # -- fenêtres -------------------------------------------------------------
    def show_panel(self):
        if not self.window:
            return
        self.window.update()
        self.window.present()
        self._refresh_aurora_if_stale()

    def open_settings(self):
        dlg = SettingsDialog(self.window, self.cfg, os.path.exists(AUTOSTART))
        dlg.test_button.connect("clicked", lambda *_: self._apply_settings(dlg) or self.alerter.send_test())
        if dlg.run() == Gtk.ResponseType.OK:
            self._apply_settings(dlg)
            self._resolve_location()
        dlg.destroy()

    def _apply_settings(self, dlg):
        self.cfg.update(**dlg.values())
        self.cfg.save()
        self._set_autostart(dlg.autostart.get_active())

    @staticmethod
    def _set_autostart(on: bool):
        if on:
            os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
            with open(AUTOSTART, "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\nType=Application\nName=KP Detector\n"
                        "Exec=kp-detector --background\nIcon=kp-detector\n"
                        "X-GNOME-Autostart-enabled=true\n")
        elif os.path.exists(AUTOSTART):
            os.remove(AUTOSTART)

    # -- données (threads → GLib.idle_add) -------------------------------------
    def refresh(self):
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            samples, err = core.fetch_kp(), None
        except Exception:  # noqa: BLE001
            samples, err = None, T("NOAA data unavailable")
        GLib.idle_add(self._apply_samples, samples, err)

    def _apply_samples(self, samples, err):
        if samples is not None:
            self.model.samples = samples
            if self.model.error == T("NOAA data unavailable"):
                self.model.error = None
            self._update_indicator()
            self.alerter.check(self.model)
        else:
            self.model.error = err
            if self.indicator and not self.model.samples:
                self.indicator.set_label("Kp ?", "Kp 9.9 🟢")
        self._refresh_window()
        return False

    def _resolve_location(self):
        def work():
            try:
                loc = location.resolve(self.cfg)
            except Exception:  # noqa: BLE001
                loc = None
            GLib.idle_add(self._apply_location, loc)
        threading.Thread(target=work, daemon=True).start()

    def _apply_location(self, loc):
        if loc is None:
            if self.model.coord is None:
                self.model.error = T("Position unavailable")
        else:
            self.model.coord = (loc.lat, loc.lon)
            self.model.place = loc.place
            if self.model.error == T("Position unavailable"):
                self.model.error = None
            self._last_aurora = 0.0
            self._update_indicator()
            self.alerter.check(self.model)
        self._refresh_window()
        return False

    def _refresh_aurora_if_stale(self):
        if not self.model.coord or time.monotonic() - self._last_aurora < 600:
            return
        self._last_aurora = time.monotonic()
        lat, lon = self.model.coord

        def work():
            try:
                pct = core.fetch_aurora(lat, lon)
            except Exception:  # noqa: BLE001
                pct = None
            GLib.idle_add(self._apply_aurora, pct)
        threading.Thread(target=work, daemon=True).start()

    def _apply_aurora(self, pct):
        self.model.aurora = pct
        self._refresh_window()
        return False

    def _refresh_window(self):
        if self.window:
            self.window.update()

    def _set_error(self, msg):
        self.model.error = msg
        self._refresh_window()
        return False

    # -- notifications --------------------------------------------------------
    def _notify(self, title, body):
        if Notify:
            try:
                n = Notify.Notification.new(title, body, "kp-detector")
                n.show()
                return
            except Exception:  # noqa: BLE001
                pass
        # repli : notifications GIO
        n = Gio.Notification.new(title)
        n.set_body(body)
        self.send_notification(None, n)

    # -- capture d'écran de documentation -------------------------------------
    def _screenshot(self, out_dir: str):
        """Rend le panneau hors écran avec des données NOAA réelles et une position d'exemple (Paris)."""
        def work():
            try:
                samples = core.fetch_kp()
                try:
                    pct = core.fetch_aurora(48.85, 2.35)
                except Exception:  # noqa: BLE001
                    pct = None
            except Exception as e:  # noqa: BLE001
                print("NOAA unreachable:", e, file=sys.stderr)
                GLib.idle_add(self.quit)
                return
            GLib.idle_add(self._render_screenshot, out_dir, samples, pct)
        threading.Thread(target=work, daemon=True).start()

    def _render_screenshot(self, out_dir, samples, pct):
        m = core.Model(samples=samples, aurora=pct, place="Paris, France", coord=(48.85, 2.35))
        view = PanelView(m)
        win = Gtk.OffscreenWindow()
        win.add(view)
        win.show_all()
        win.set_default_size(330, 10)

        def grab():
            pix = win.get_pixbuf()
            os.makedirs(out_dir, exist_ok=True)
            lang = (os.environ.get("LANGUAGE") or os.environ.get("LANG") or "en")[:2]
            path = os.path.join(out_dir, "panel-linux-%s.png" % lang)
            pix.savev(path, "png", [], [])
            print("wrote", path)
            self.quit()
            return False
        GLib.timeout_add(800, grab)
        return False
