"""Alertes : notification du bureau + e-mail SMTP (un message par destinataire)."""
from __future__ import annotations

import datetime as dt
import json
import os
import smtplib
import ssl
import threading
from email.message import EmailMessage

from . import core
from .config import state_dir
from .i18n import T


class Alerter:
    def __init__(self, cfg, notify, on_error):
        """notify(title, body) est appelé dans le thread principal ; on_error(msg) aussi."""
        self.cfg, self.notify, self.on_error = cfg, notify, on_error
        self._path = os.path.join(state_dir(), "alerted.json")

    # -- état -----------------------------------------------------------------
    def _load(self) -> set:
        try:
            with open(self._path, encoding="utf-8") as f:
                return set(json.load(f))
        except (OSError, ValueError):
            return set()

    def _save(self, keys: set):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(sorted(keys)[-200:], f)

    # -- détection ------------------------------------------------------------
    def check(self, model) -> None:
        already = self._load()
        hot = core.hot_slots(model.samples, self.cfg["alert_threshold"], already)
        if not hot:
            return
        peak = max(hot, key=lambda s: s.kp)
        when = (T("forecast %s", peak.date.astimezone().strftime("%a %d %b %H:%M"))
                if peak.predicted else T("ongoing"))
        body = "Kp %.1f %s (%s)." % (peak.kp, when, T(core.label_key(peak.kp)))
        need = model.kp_needed
        if need is not None and model.place:
            body += T(" Aurora possible in %s.", model.place) if need <= peak.kp \
                else T(" Probably not enough in %s.", model.place)
        self.deliver(T("Geomagnetic storm: Kp %.1f", peak.kp), body)
        self._save(already | {core.slot_key(s) for s in hot})

    def send_test(self):
        self.deliver(T("Test KP Detector"), T("This is a test alert."))

    # -- envoi ----------------------------------------------------------------
    def deliver(self, title: str, body: str):
        if self.cfg["notify"]:
            self.notify(title, body)
        if self.cfg["email_on"]:
            to = core.recipients(self.cfg["email_to"])
            if to:
                threading.Thread(target=self._send_emails, args=(to, title, body), daemon=True).start()

    def _send_emails(self, to: list, title: str, body: str):
        from gi.repository import GLib
        c = self.cfg
        for addr in to:
            try:
                msg = EmailMessage()
                msg["From"] = c["email_from"] or c["smtp_user"]
                msg["To"] = addr
                msg["Subject"] = title
                msg.set_content(body)
                if c["smtp_security"] == "ssl":
                    smtp = smtplib.SMTP_SSL(c["smtp_host"], int(c["smtp_port"]), timeout=20,
                                            context=ssl.create_default_context())
                else:
                    smtp = smtplib.SMTP(c["smtp_host"], int(c["smtp_port"]), timeout=20)
                with smtp:
                    if c["smtp_security"] == "starttls":
                        smtp.starttls(context=ssl.create_default_context())
                    if c["smtp_user"]:
                        smtp.login(c["smtp_user"], c["smtp_password"])
                    smtp.send_message(msg)
            except Exception as e:  # noqa: BLE001 — on affiche l'erreur à l'utilisateur
                GLib.idle_add(self.on_error, T("Email to %s failed: %s", addr, e))
