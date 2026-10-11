"""Logique pure (sans GTK) : NOAA, géomagnétisme, alertes. Testable partout."""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
OVATION_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
USER_AGENT = "kp-detector (https://github.com/blegal/kp-detector)"

# Pôle géomagnétique dipolaire (approx. IGRF 2025)
POLE_LAT = math.radians(80.7)
POLE_LON = math.radians(-72.6)


@dataclass(frozen=True)
class Sample:
    date: dt.datetime  # aware, UTC
    kp: float
    predicted: bool


@dataclass
class Model:
    samples: list = field(default_factory=list)
    aurora: Optional[int] = None
    place: Optional[str] = None
    coord: Optional[tuple] = None  # (lat, lon)
    error: Optional[str] = None

    @property
    def current(self) -> Optional[Sample]:
        return current(self.samples)

    @property
    def geomag_lat(self) -> Optional[float]:
        return geomagnetic_latitude(*self.coord) if self.coord else None

    @property
    def kp_needed(self) -> Optional[float]:
        m = self.geomag_lat
        return kp_needed_for_aurora(m) if m is not None else None


# --- Réseau -----------------------------------------------------------------

def _get(url: str, timeout: float = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_kp(rows: list) -> list:
    out = []
    for r in rows:
        try:
            d = dt.datetime.strptime(r["time_tag"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
            out.append(Sample(d, float(r["kp"]), r["observed"] == "predicted"))
        except (KeyError, ValueError, TypeError):
            continue
    if not out:
        raise ValueError("no Kp data")
    return out


def fetch_kp() -> list:
    """Historique observé + prévisions (~7 j passés, ~3 j à venir), un point toutes les 3 h."""
    return parse_kp(json.loads(_get(KP_URL)))


def _round_half_away(x: float) -> int:
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)


def find_aurora(data: bytes, lat: float, lon: float) -> Optional[int]:
    """Probabilité d'aurore (%) au point de grille OVATION le plus proche.
    Recherche directe dans les octets : évite de décoder ~65 000 triplets."""
    la, lo = _round_half_away(lat), (_round_half_away(lon) + 360) % 360
    needle = f"[{lo}, {la}, ".encode()
    i = data.find(needle)
    if i < 0:
        return None
    m = re.match(rb"\d+", data[i + len(needle): i + len(needle) + 6])
    return int(m.group()) if m else None


def fetch_aurora(lat: float, lon: float) -> Optional[int]:
    return find_aurora(_get(OVATION_URL), lat, lon)


# --- Géomagnétisme ----------------------------------------------------------

def geomagnetic_latitude(lat: float, lon: float) -> float:
    phi, lam = math.radians(lat), math.radians(lon)
    s = math.sin(phi) * math.sin(POLE_LAT) + math.cos(phi) * math.cos(POLE_LAT) * math.cos(lam - POLE_LON)
    return math.degrees(math.asin(max(-1.0, min(1.0, s))))


def kp_needed_for_aurora(geomag_lat: float) -> float:
    """Kp minimal pour apercevoir une aurore sur l'horizon nord.
    Frontière de l'ovale ≈ 67° − 2°·Kp, relevée de ~2° (arcs hauts en altitude) ;
    calibré sur des observations en France (Kp ≈ 7 le 10/10/2026)."""
    return max(0.0, (65 - abs(geomag_lat)) / 2)


# --- Échantillons -----------------------------------------------------------

def current(samples: list) -> Optional[Sample]:
    obs = [s for s in samples if not s.predicted]
    return obs[-1] if obs else None


def peak_next_24h(samples: list, now: Optional[dt.datetime] = None) -> Optional[Sample]:
    now = now or dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(hours=24)
    p = [s for s in samples if s.predicted and s.date <= horizon]
    return max(p, key=lambda s: s.kp) if p else None


def daily_max(samples: list, today: Optional[dt.date] = None) -> list:
    """[(date locale, kp max, contient des prévisions)] pour aujourd'hui et la suite."""
    today = today or dt.datetime.now().astimezone().date()
    days: dict = {}
    for s in samples:
        d = s.date.astimezone().date()
        if d >= today:
            kp, pred = days.get(d, (0.0, False))
            days[d] = (max(kp, s.kp), pred or s.predicted)
    return [(d, kp, pred) for d, (kp, pred) in sorted(days.items())]


# --- Niveaux NOAA -----------------------------------------------------------

def level(kp: float) -> int:
    """0 calme, 1 = G1 (Kp 5), 2 = G2, 3 = G3 et plus."""
    if kp < 4.67:
        return 0
    if kp < 5.67:
        return 1
    if kp < 6.67:
        return 2
    return 3


LEVEL_RGB = [(0.20, 0.78, 0.35), (1.0, 0.80, 0.0), (1.0, 0.58, 0.0), (1.0, 0.23, 0.19)]
LEVEL_EMOJI = ["🟢", "🟡", "🟠", "🔴"]


def label_key(kp: float) -> str:
    if kp < 4.67:
        return "Calm"
    if kp < 5.67:
        return "G1 · minor"
    if kp < 6.67:
        return "G2 · moderate"
    if kp < 7.67:
        return "G3 · strong"
    if kp < 8.67:
        return "G4 · severe"
    return "G5 · extreme"


# --- Alertes ----------------------------------------------------------------

def slot_key(s: Sample) -> str:
    return str(int(s.date.timestamp()))


def hot_slots(samples: list, threshold: float, already: set, now: Optional[dt.datetime] = None) -> list:
    """Créneaux de 3 h dépassant le seuil, pas encore signalés et pas terminés."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return [s for s in samples
            if s.kp > threshold and s.date + dt.timedelta(hours=3) > now and slot_key(s) not in already]


def recipients(raw: str) -> list:
    """Destinataires séparés par virgule, point-virgule, espace ou retour à la ligne (sans doublons)."""
    seen, out = set(), []
    for r in re.split(r"[,;\s]+", raw or ""):
        r = r.strip()
        if r and r.lower() not in seen:
            seen.add(r.lower())
            out.append(r)
    return out
