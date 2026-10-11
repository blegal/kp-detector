"""Panneau GTK3 (jauges, courbe historique + prévisions, détails) et fenêtre de réglages."""
from __future__ import annotations

import datetime as dt
import math

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import core  # noqa: E402
from .i18n import T  # noqa: E402

PURPLE = (0.78, 0.2, 0.9)
BLUE = (0.25, 0.55, 1.0)
WIDTH = 330


def _fg(widget):
    c = widget.get_style_context().get_color(Gtk.StateFlags.NORMAL)
    return (c.red, c.green, c.blue)


def _text(cr, s, x, y, size, rgba, bold=False, anchor="start"):
    cr.select_font_face("Sans", 0, 1 if bold else 0)
    cr.set_font_size(size)
    e = cr.text_extents(s)
    if anchor == "middle":
        x -= e.width / 2 + e.x_bearing
    elif anchor == "end":
        x -= e.width + e.x_bearing
    cr.move_to(x, y)
    cr.set_source_rgba(*rgba)
    cr.show_text(s)


def _ring(cr, cx, cy, r, width, progress, color, fg, big, caption):
    cr.set_line_width(width)
    cr.set_source_rgba(*fg, 0.15)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.stroke()
    if progress > 0:
        cr.set_source_rgba(*color, 1)
        cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * min(1.0, progress))
        cr.stroke()
    _text(cr, big, cx, cy + r * 0.12, r * 0.55, (*fg, 1), True, "middle")
    _text(cr, caption, cx, cy + r * 0.48, r * 0.24, (*fg, 0.6), False, "middle")


class PanelView(Gtk.Box):
    """Contenu du panneau. `on_settings` / `on_refresh` : callbacks des boutons de l'en-tête."""

    def __init__(self, model, on_settings=None, on_refresh=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.model = model
        for side in ("start", "end", "top", "bottom"):
            getattr(self, f"set_margin_{side}")(14)
        self.set_size_request(WIDTH, -1)

        head = Gtk.Box(spacing=6)
        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        refresh.set_relief(Gtk.ReliefStyle.NONE)
        refresh.set_tooltip_text(T("Refresh"))
        gear = Gtk.Button.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON)
        gear.set_relief(Gtk.ReliefStyle.NONE)
        gear.set_tooltip_text(T("Settings…"))
        if on_refresh:
            refresh.connect("clicked", lambda *_: on_refresh())
        if on_settings:
            gear.connect("clicked", lambda *_: on_settings())
        title = Gtk.Label(label="<b>Kp</b>", use_markup=True)
        head.pack_start(refresh, False, False, 0)
        head.set_center_widget(title)
        head.pack_end(gear, False, False, 0)
        self.pack_start(head, False, False, 0)

        self.gauges = Gtk.DrawingArea()
        self.gauges.set_size_request(WIDTH - 28, 120)
        self.gauges.connect("draw", self._draw_gauges)
        self.pack_start(self.gauges, False, False, 0)

        self.pack_start(self._section(T("History and forecast")), False, False, 0)
        self.chart = Gtk.DrawingArea()
        self.chart.set_size_request(WIDTH - 28, 140)
        self.chart.connect("draw", self._draw_chart)
        self.pack_start(self.chart, False, False, 0)

        self.pack_start(self._section(T("Details")), False, False, 0)
        self.details = Gtk.Grid(column_spacing=12, row_spacing=4)
        self.pack_start(self.details, False, False, 0)

        self.pack_start(self._section(T("Coming days")), False, False, 0)
        self.days = Gtk.Grid(column_spacing=12, row_spacing=4)
        self.pack_start(self.days, False, False, 0)

        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.get_style_context().add_class("dim-label")
        self.pack_start(self.status, False, False, 0)
        self.update()

    @staticmethod
    def _section(s):
        lab = Gtk.Label(label=s, margin_top=6)
        lab.get_style_context().add_class("dim-label")
        return lab

    # -- contenu --------------------------------------------------------------
    @staticmethod
    def _clear(grid):
        for c in grid.get_children():
            grid.remove(c)

    @staticmethod
    def _cell(grid, row, left, right, markup=None):
        l = Gtk.Label(label=left, xalign=0, hexpand=True)
        l.get_style_context().add_class("dim-label")
        r = Gtk.Label(xalign=1)
        r.set_markup(markup if markup is not None else "<b>%s</b>" % GLib.markup_escape_text(right))
        r.set_ellipsize(3)
        grid.attach(l, 0, row, 1, 1)
        grid.attach(r, 1, row, 1, 1)

    @staticmethod
    def _hex(color):
        return "#%02x%02x%02x" % tuple(int(c * 255) for c in color)

    def update(self):
        m = self.model
        cur = m.current
        self._clear(self.details)
        row = 0
        if cur:
            col = self._hex(core.LEVEL_RGB[core.level(cur.kp)])
            self._cell(self.details, row, T("Status"), "",
                       '<b><span foreground="%s">%s</span></b>' % (col, T(core.label_key(cur.kp))))
            row += 1
            peak = core.peak_next_24h(m.samples)
            if peak:
                col = self._hex(core.LEVEL_RGB[core.level(peak.kp)])
                self._cell(self.details, row, T("Peak forecast (24 h)"), "",
                           '<b><span foreground="%s">Kp %.1f</span></b>' % (col, peak.kp))
                row += 1
        if m.coord:
            place = m.place or "%.2f°, %.2f°" % m.coord
            self._cell(self.details, row, T("Location"), place)
            self._cell(self.details, row + 1, T("Geomagnetic latitude"), "%.1f°" % m.geomag_lat)
            need = m.kp_needed
            self._cell(self.details, row + 2, T("Kp needed here (northern horizon)"), "",
                       '<b><span foreground="%s">%s</span></b>' % (
                           self._hex(PURPLE), "0" if need == 0 else "≈ %.1f" % need))
        self.details.show_all()

        self._clear(self.days)
        today = dt.datetime.now().astimezone().date()
        for i, (d, kp, pred) in enumerate(core.daily_max(m.samples)):
            if d == today:
                name = T("Today")
            elif d == today + dt.timedelta(days=1):
                name = T("Tomorrow")
            else:
                name = d.strftime("%A %d %b").capitalize()
            col = self._hex(core.LEVEL_RGB[core.level(kp)])
            tag = ' <small><span alpha="60%%">%s</span></small>' % T("fcst.") if pred else ""
            l = Gtk.Label(xalign=0, hexpand=True)
            l.set_markup('<span foreground="%s">●</span>  %s%s' % (col, GLib.markup_escape_text(name), tag))
            r = Gtk.Label(xalign=1)
            r.set_markup("<b>Kp %.1f</b>" % kp)
            self.days.attach(l, 0, i, 1, 1)
            self.days.attach(r, 1, i, 1, 1)
        self.days.show_all()

        self.status.set_text(m.error or "")
        self.status.set_visible(bool(m.error))
        self.gauges.queue_draw()
        self.chart.queue_draw()

    # -- dessin ---------------------------------------------------------------
    def _draw_gauges(self, w, cr):
        fg = _fg(w)
        cur = self.model.current
        width = w.get_allocated_width()
        if cur:
            _ring(cr, width * 0.33, 60, 46, 10, cur.kp / 9, core.LEVEL_RGB[core.level(cur.kp)], fg,
                  "%.1f" % cur.kp, "Kp")
        else:
            _ring(cr, width * 0.33, 60, 46, 10, 0, (0.5, 0.5, 0.5), fg, "–", "Kp")
        a = self.model.aurora
        _ring(cr, width * 0.73, 60, 34, 8, (a or 0) / 100, PURPLE, fg,
              "–" if a is None else "%d%%" % a, T("Aurora"))
        return False

    def _draw_chart(self, w, cr):
        fg = _fg(w)
        s = self.model.samples
        if not s:
            return False
        W, H = w.get_allocated_width(), w.get_allocated_height()
        left, right, top, bottom = 2, 22, 6, 18
        pw, ph = W - left - right, H - top - bottom
        t0 = s[0].date.timestamp()
        t1 = s[-1].date.timestamp() + 3 * 3600
        X = lambda t: left + (t - t0) / (t1 - t0) * pw
        Y = lambda kp: top + ph - kp / 9 * ph

        cr.set_line_width(1)
        for g in (3, 5, 7, 9):
            cr.set_source_rgba(*fg, 0.2)
            cr.move_to(left, Y(g) + 0.5)
            cr.line_to(left + pw, Y(g) + 0.5)
            cr.stroke()
            _text(cr, str(g), W - 2, Y(g) + 4, 9, (*fg, 0.6), anchor="end")
        for smp in s:
            x0, x1 = X(smp.date.timestamp()), X(smp.date.timestamp() + 3 * 3600)
            cr.set_source_rgba(*core.LEVEL_RGB[core.level(smp.kp)], 0.4 if smp.predicted else 0.95)
            cr.rectangle(x0, Y(smp.kp), max(1.0, x1 - x0 - 0.5), top + ph - Y(smp.kp))
            cr.fill()

        # jours (étiquette à midi)
        d = dt.datetime.fromtimestamp(t0).replace(hour=12, minute=0, second=0, microsecond=0)
        while d.timestamp() < t1:
            if d.timestamp() > t0:
                _text(cr, d.strftime("%a"), X(d.timestamp()), H - 4, 9, (*fg, 0.6), anchor="middle")
            d += dt.timedelta(days=1)

        cr.set_dash([3, 3])
        now = dt.datetime.now().timestamp()
        if t0 < now < t1:
            cr.set_source_rgba(*BLUE, 0.9)
            cr.move_to(X(now), top)
            cr.line_to(X(now), top + ph)
            cr.stroke()
        need = self.model.kp_needed
        if need and 0 < need <= 9:
            cr.set_dash([4, 3])
            cr.set_source_rgba(*PURPLE, 1)
            cr.move_to(left, Y(need))
            cr.line_to(left + pw, Y(need))
            cr.stroke()
            _text(cr, T("aurora here"), left + 2, Y(need) - 3, 9, (*PURPLE, 1))
        cr.set_dash([])
        return False


class PanelWindow(Gtk.Window):
    def __init__(self, app_model, on_settings, on_refresh):
        super().__init__(title="KP Detector")
        self.set_icon_name("kp-detector")
        self.set_resizable(False)
        self.view = PanelView(app_model, on_settings, on_refresh)
        self.add(self.view)
        self.connect("delete-event", lambda w, e: w.hide_on_delete())

    def update(self):
        self.view.update()


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, cfg, autostart: bool):
        super().__init__(title=T("Settings"), transient_for=parent, modal=True)
        self.add_button(T("Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(T("Save"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        g = Gtk.Grid(column_spacing=12, row_spacing=8, margin=14)
        self.get_content_area().add(g)
        self._row = 0

        def add(label, widget):
            lab = Gtk.Label(label=label, xalign=0)
            g.attach(lab, 0, self._row, 1, 1)
            widget.set_hexpand(True)
            g.attach(widget, 1, self._row, 1, 1)
            self._row += 1
            return widget

        def head(text):
            l = Gtk.Label(label="<b>%s</b>" % GLib.markup_escape_text(text), use_markup=True, xalign=0, margin_top=8)
            g.attach(l, 0, self._row, 2, 1)
            self._row += 1

        def entry(value, **kw):
            e = Gtk.Entry(text=str(value), **kw)
            e.set_activates_default(True)
            return e

        self.threshold = add(T("Alert if forecast Kp >"), Gtk.SpinButton.new_with_range(3, 9, 1))
        self.threshold.set_value(cfg["alert_threshold"])
        self.notify = add(T("Desktop notifications"), Gtk.Switch(halign=Gtk.Align.START, active=cfg["notify"]))

        head(T("Email alerts"))
        self.email_on = add(T("Email alerts"), Gtk.Switch(halign=Gtk.Align.START, active=cfg["email_on"]))
        self.email_to = add(T("Recipients (comma-separated)"), entry(cfg["email_to"]))
        self.email_from = add(T("Sender address"), entry(cfg["email_from"]))
        self.smtp_host = add(T("SMTP server"), entry(cfg["smtp_host"]))
        self.smtp_port = add(T("Port"), Gtk.SpinButton.new_with_range(1, 65535, 1))
        self.smtp_port.set_value(cfg["smtp_port"])
        self.smtp_user = add(T("User"), entry(cfg["smtp_user"]))
        self.smtp_password = add(T("Password"), entry(cfg["smtp_password"], visibility=False))
        self.smtp_security = add(T("Security"), Gtk.ComboBoxText())
        for i, k in enumerate(("starttls", "ssl", "none")):
            self.smtp_security.append(k, {"starttls": "STARTTLS", "ssl": "SSL/TLS", "none": "—"}[k])
        self.smtp_security.set_active_id(cfg["smtp_security"])

        head(T("Location"))
        self.loc_mode = add(T("Location mode"), Gtk.ComboBoxText())
        self.loc_mode.append("auto", T("Automatic"))
        self.loc_mode.append("manual", T("Manual"))
        self.loc_mode.set_active_id(cfg["location_mode"])
        self.lat = add(T("Latitude"), entry(cfg["lat"]))
        self.lon = add(T("Longitude"), entry(cfg["lon"]))
        self.ip_fallback = add(T("IP-based fallback (sends your IP to ipwho.is)"),
                               Gtk.Switch(halign=Gtk.Align.START, active=cfg["ip_fallback"]))

        head(T("Launch at login"))
        self.autostart = add(T("Launch at login"), Gtk.Switch(halign=Gtk.Align.START, active=autostart))
        self.test_button = Gtk.Button(label=T("Send a test alert"), margin_top=8)
        g.attach(self.test_button, 0, self._row, 2, 1)
        self.show_all()

    @staticmethod
    def _float(entry, default=0.0):
        try:
            return float(entry.get_text().replace(",", "."))
        except ValueError:
            return default

    def values(self) -> dict:
        return {
            "alert_threshold": int(self.threshold.get_value()),
            "notify": self.notify.get_active(),
            "email_on": self.email_on.get_active(),
            "email_to": self.email_to.get_text(),
            "email_from": self.email_from.get_text(),
            "smtp_host": self.smtp_host.get_text().strip(),
            "smtp_port": int(self.smtp_port.get_value()),
            "smtp_user": self.smtp_user.get_text(),
            "smtp_password": self.smtp_password.get_text(),
            "smtp_security": self.smtp_security.get_active_id() or "starttls",
            "location_mode": self.loc_mode.get_active_id() or "auto",
            "lat": self._float(self.lat),
            "lon": self._float(self.lon),
            "ip_fallback": self.ip_fallback.get_active(),
        }
