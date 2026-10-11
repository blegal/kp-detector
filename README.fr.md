# KP Detector

[English](README.md) · **Français**

Une petite application macOS de barre de menu qui affiche l'**indice géomagnétique Kp** et ce qu'il signifie **là où vous êtes** : chances d'aurore à votre position, historique sur 7 jours et prévisions sur 3 jours.

- Titre de barre de menu `Kp 3.3`, coloré selon l'échelle NOAA (G1 – G5)
- Panneau avec jauges, courbe historique + prévisions, maxima par jour et détails locaux
- **Pertinence locale** : latitude géomagnétique, Kp requis pour voir une aurore sur l'horizon nord, probabilité d'aurore en direct (modèle OVATION de NOAA)
- **Alertes** quand le Kp prévu dépasse un seuil (par défaut : > 6) : Centre de notification, et en option iMessage et/ou Mail vers plusieurs destinataires
- Léger : ~50 Mo, 0 % de CPU au repos, pas de cache, une requête toutes les 15 minutes
- Interface en anglais et en français (selon la langue du système)

## Installation

1. Téléchargez le dernier `KPDetector-x.y.z.dmg` depuis la page [Releases](../../releases).
2. Ouvrez-le et glissez **KP Detector** dans **Applications**.
3. Premier lancement : l'app n'est pas notarisée par Apple, macOS la bloque. Clic droit sur l'app → **Ouvrir**, ou *Réglages Système → Confidentialité et sécurité → Ouvrir quand même*. (Ou : `xattr -dr com.apple.quarantine /Applications/KPDetector.app`.)
4. Autorisez la localisation quand c'est demandé. Activez *Lancer à l'ouverture de session* dans le menu ⚙.

Nécessite macOS 13 ou plus récent (binaire universel : Apple silicon et Intel).

## Alertes

Ouvrez le panneau → **Alertes**. Choisissez un seuil, puis activez les canaux souhaités :

| Canal | Remarques |
|---|---|
| Centre de notification | Activé par défaut |
| iMessage | Numéros / Apple ID séparés par des virgules. macOS demande une fois l'autorisation de contrôler Messages |
| Mail | Adresses séparées par des virgules ; un message par destinataire. Nécessite un compte configuré dans Mail.app |

Les messages partent de votre Mac avec vos comptes. Utilisez **Envoyer une alerte de test** pour vérifier. Chaque créneau de 3 h au-dessus du seuil déclenche au plus une alerte.

## Données et précision

- Kp (observé + prévu) : indice K planétaire de [NOAA SWPC](https://www.swpc.noaa.gov/). Le Kp est planétaire : identique partout.
- Probabilité d'aurore : modèle OVATION de NOAA au point de grille le plus proche.
- « Kp requis ici » est une **approximation** : frontière de l'ovale auroral ≈ 65° − 2°·Kp en latitude géomagnétique, calibrée sur des observations en France. Nuages, pollution lumineuse et horizon comptent plus que toute formule.

La position reste sur votre Mac. Seules des requêtes vers des fichiers publics NOAA sont envoyées.

## Compiler

```bash
./build.sh                  # build natif → build/KPDetector.app
./scripts/package.sh        # build universel → dist/KPDetector-<version>.dmg + .zip
```

Nécessite la chaîne Swift (Xcode ou Command Line Tools). Pour une version notarisée : `SIGN_IDENTITY="Developer ID Application: …"` et `NOTARY_PROFILE=<profil notarytool>`.

### Publier une version

Poussez un tag ; GitHub Actions construit le DMG/ZIP et les joint à une release :

```bash
git tag v1.0.0 && git push origin v1.0.0
```

## Licence

[MIT](LICENSE)
