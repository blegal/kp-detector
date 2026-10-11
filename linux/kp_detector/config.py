"""Réglages persistés dans ~/.config/kp-detector/config.json (permissions 0600)."""
import json
import os
import tempfile

DEFAULTS = {
    "alert_threshold": 6,
    "notify": True,
    "email_on": False,
    "email_to": "",
    "email_from": "",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_security": "starttls",  # starttls | ssl | none
    "location_mode": "auto",      # auto | manual
    "lat": 0.0,
    "lon": 0.0,
    "ip_fallback": True,
}


def config_dir() -> str:
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "kp-detector")


def state_dir() -> str:
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "kp-detector")


class Config:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(config_dir(), "config.json")
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data[k]

    def update(self, **kw):
        self.data.update({k: v for k, v in kw.items() if k in DEFAULTS})

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.chmod(tmp, 0o600)  # contient le mot de passe SMTP
        os.replace(tmp, self.path)
