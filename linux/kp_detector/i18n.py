"""Traductions EN (clé = texte anglais) / FR."""
import os

FR = {
    "Calm": "Calme", "G1 · minor": "G1 · mineur", "G2 · moderate": "G2 · modéré",
    "G3 · strong": "G3 · fort", "G4 · severe": "G4 · sévère", "G5 · extreme": "G5 · extrême",
    "Refresh": "Actualiser", "Settings…": "Réglages…", "Open panel": "Ouvrir le panneau", "Quit": "Quitter",
    "Aurora": "Aurore", "History and forecast": "Historique et prévisions", "Details": "Détails",
    "Coming days": "Prochains jours", "aurora here": "aurore ici", "Status": "État",
    "Peak forecast (24 h)": "Pic prévu (24 h)", "Location": "Lieu",
    "Geomagnetic latitude": "Latitude géomagnétique",
    "Kp needed here (northern horizon)": "Kp requis ici (horizon nord)",
    "Today": "Aujourd'hui", "Tomorrow": "Demain", "fcst.": "prév.",
    "Position unavailable": "Position indisponible", "NOAA data unavailable": "Données NOAA indisponibles",
    "Loading…": "Chargement…",
    "Settings": "Réglages", "Alert if forecast Kp >": "Alerter si Kp prévu >",
    "Desktop notifications": "Notifications du bureau", "Email alerts": "Alertes par e-mail",
    "Recipients (comma-separated)": "Destinataires (séparés par une virgule)",
    "SMTP server": "Serveur SMTP", "Port": "Port", "User": "Utilisateur", "Password": "Mot de passe",
    "Security": "Sécurité", "Sender address": "Adresse d'expéditeur",
    "Location mode": "Mode de localisation", "Automatic": "Automatique", "Manual": "Manuel",
    "Latitude": "Latitude", "Longitude": "Longitude",
    "IP-based fallback (sends your IP to ipwho.is)": "Repli par adresse IP (envoie votre IP à ipwho.is)",
    "Launch at login": "Lancer à l'ouverture de session", "Send a test alert": "Envoyer une alerte de test",
    "Cancel": "Annuler", "Save": "Enregistrer",
    "Geomagnetic storm: Kp %.1f": "Orage géomagnétique : Kp %.1f", "forecast %s": "prévu %s",
    "ongoing": "en cours", " Aurora possible in %s.": " Aurore possible à %s.",
    " Probably not enough in %s.": " Probablement insuffisant à %s.",
    "Test KP Detector": "Test KP Detector", "This is a test alert.": "Ceci est une alerte de test.",
    "Email to %s failed: %s": "E-mail à %s impossible : %s",
}


def _lang() -> str:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return v.split(":")[0][:2].lower()
    return "en"


def T(key: str, *args) -> str:
    s = FR.get(key, key) if _lang() == "fr" else key
    return s % args if args else s
