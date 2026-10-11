# KP Detector

**English** · [Français](README.fr.md)

A tiny macOS menu-bar app that shows the current **geomagnetic Kp index** and tells you what it means **where you are**: aurora chances at your location, a 7-day history and a 3-day forecast.

- Menu-bar title `Kp 3.3`, colored by NOAA storm scale (G1 – G5)
- Popover with gauges, history + forecast chart, daily maximums and local details
- **Local relevance**: geomagnetic latitude, Kp needed to see an aurora on your northern horizon, live aurora probability (NOAA OVATION model)
- **Alerts** when the forecast Kp exceeds a threshold (default: > 6): Notification Center, and optionally iMessage and/or Mail to several recipients
- Lightweight: ~50 MB, 0 % CPU at idle, no cache, no background polling beyond one request every 15 minutes
- English and French UI (follows your system language)

## Install

1. Download the latest `KPDetector-x.y.z.dmg` from the [Releases](../../releases) page.
2. Open it and drag **KP Detector** to **Applications**.
3. First launch: the app is not notarized by Apple, so macOS will block it. Right-click the app → **Open**, or go to *System Settings → Privacy & Security → Open Anyway*. (Or run `xattr -dr com.apple.quarantine /Applications/KPDetector.app`.)
4. Allow location access when asked. Enable *Launch at login* from the ⚙ menu.

Requires macOS 13 or later (universal binary: Apple silicon and Intel).

## Alerts

Open the panel → **Alerts**. Choose a threshold, then enable any channel:

| Channel | Notes |
|---|---|
| Notification Center | Enabled by default |
| iMessage | Comma-separated phone numbers / Apple IDs. macOS asks once for permission to control Messages |
| Mail | Comma-separated addresses; one message per recipient. Requires a configured account in Mail.app |

Messages are sent from your Mac with your accounts. Use **Send a test alert** to check your setup. Each 3-hour slot above the threshold triggers at most one alert.

## Data and accuracy

- Kp (observed + forecast): [NOAA SWPC](https://www.swpc.noaa.gov/) planetary K-index. Kp is planetary: the same everywhere.
- Aurora probability: NOAA OVATION nowcast at your grid point.
- "Kp needed here" is an **approximation**: auroral oval boundary ≈ 65° − 2°·Kp in geomagnetic latitude, calibrated on observations in France. Clouds, light pollution and your horizon matter more than any formula.

Location is used only on your Mac to compute the above. Nothing is sent anywhere except anonymous requests for public NOAA files.

## Build from source

```bash
git clone https://github.com/<you>/kp-detector && cd kp-detector
./build.sh                  # native build → build/KPDetector.app
./scripts/package.sh        # universal build → dist/KPDetector-<version>.dmg + .zip
```

Needs the Swift toolchain (Xcode or Command Line Tools). For a notarized release, set `SIGN_IDENTITY="Developer ID Application: …"` and `NOTARY_PROFILE=<notarytool keychain profile>`.

### Releasing

Push a tag; GitHub Actions builds the DMG/ZIP and attaches them to a release:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

### Translating

Strings live in `Resources/<lang>.lproj/Localizable.strings` (the key is the English text). Copy `fr.lproj`, translate, and add the language to `CFBundleLocalizations` in `Resources/Info.plist`.

## License

[MIT](LICENSE)
