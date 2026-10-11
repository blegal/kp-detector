import AppKit
import CoreLocation
import ServiceManagement
import SwiftUI
import UserNotifications

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, CLLocationManagerDelegate, NSPopoverDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let popover = NSPopover()
    private let locationManager = CLLocationManager()
    private let model = Model()
    private var timer: Timer?
    private var lastGeocoded: CLLocation?
    private lazy var alerts = AlertService(model: model)

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let i = CommandLine.arguments.firstIndex(of: "--screenshot"), i + 1 < CommandLine.arguments.count {
            renderScreenshots(to: CommandLine.arguments[i + 1])
            return
        }
        setTitle("Kp …", color: nil)
        statusItem.button?.target = self
        statusItem.button?.action = #selector(togglePopover)

        model.onRefresh = { [weak self] in self?.refresh() }
        model.onTestAlert = { [weak self] in self?.alerts.sendTest() }
        model.onToggleLogin = { [weak self] in self?.toggleLogin() }
        model.launchAtLogin = SMAppService.mainApp.status == .enabled

        popover.behavior = .transient
        popover.delegate = self

        alerts.requestAuthorization()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyReduced
        locationManager.distanceFilter = 20_000
        locationManager.requestWhenInUseAuthorization()
        locationManager.requestLocation()
        locationManager.startMonitoringSignificantLocationChanges()

        if CommandLine.arguments.contains("--test-alert") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in self?.alerts.sendTest() }
        }

        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 900, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
        timer?.tolerance = 120   // permet au système de regrouper les réveils
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
    }

    /// Documentation helper: renders the panel off-screen (real NOAA data, sample location, throw-away settings).
    private func renderScreenshots(to dir: String) {
        Task {
            let suite = "kpdetector.screenshot"
            let m = Model(defaults: UserDefaults(suiteName: suite)!)
            m.samples = (try? await NOAA.fetchKp()) ?? []
            m.coordinate = (48.85, 2.35)
            m.place = "Paris, France"
            m.auroraPercent = (try? await NOAA.fetchAurora(lat: 48.85, lon: 2.35)) ?? nil
            m.imessageOn = true; m.imessageTo = "alice@example.com, +1 555 0100"
            m.mailOn = true; m.mailTo = "bob@example.com"
            let lang = Locale.current.language.languageCode?.identifier ?? "en"
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            for (name, expanded) in [("panel", false), ("alerts", true)] {
                m.alertsExpanded = expanded
                let host = NSHostingView(rootView: PopoverView(model: m))
                let win = NSWindow(contentRect: .zero, styleMask: [.borderless], backing: .buffered, defer: false)
                win.appearance = NSAppearance(named: .aqua)
                win.backgroundColor = .windowBackgroundColor
                win.contentView = host
                win.setContentSize(host.fittingSize)
                win.setFrameOrigin(NSPoint(x: -20000, y: -20000))   // hors écran
                win.orderFrontRegardless()
                win.makeFirstResponder(nil)
                try? await Task.sleep(nanoseconds: 1_000_000_000)   // laisse Charts se mettre en page
                host.layoutSubtreeIfNeeded()
                if let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) {
                    host.cacheDisplay(in: host.bounds, to: rep)
                    try? rep.representation(using: .png, properties: [:])?
                        .write(to: URL(fileURLWithPath: "\(dir)/\(name)-\(lang).png"))
                }
                win.orderOut(nil)
            }
            UserDefaults.standard.removePersistentDomain(forName: suite)
            exit(0)
        }
    }

    @objc private func togglePopover() {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.contentViewController = NSHostingController(rootView: PopoverView(model: model))
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            refreshAuroraIfStale()
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    func popoverDidClose(_ notification: Notification) {
        popover.contentViewController = nil   // libère la hiérarchie SwiftUI/Charts
    }

    // MARK: Localisation

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        Task { @MainActor in
            let first = model.coordinate == nil
            let moved = lastGeocoded.map { loc.distance(from: $0) > 20_000 } ?? true
            model.coordinate = (loc.coordinate.latitude, loc.coordinate.longitude)
            model.error = nil
            if moved {
                lastGeocoded = loc
                if let m = try? await CLGeocoder().reverseGeocodeLocation(loc).first {
                    model.place = [m.locality, m.country].compactMap { $0 }.joined(separator: ", ")
                }
            }
            if first { refresh() }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in model.error = L("Position unavailable") }
    }

    // MARK: Données

    private func refresh() {
        Task {
            do {
                model.samples = try await NOAA.fetchKp()
                if let cur = model.current {
                    setTitle(String(format: "Kp %.1f", cur.kp), color: Model.nsColor(for: cur.kp))
                }
                if model.coordinate != nil { model.error = nil }
                alerts.checkForecast()
            } catch {
                if model.samples.isEmpty { setTitle("Kp ?", color: nil) }
                model.error = L("NOAA data unavailable")
            }
        }
    }

    /// OVATION (~900 Ko) n'est téléchargé que si le panneau est ouvert et la donnée a plus de 10 min.
    private var lastAurora = Date.distantPast
    private func refreshAuroraIfStale() {
        guard let c = model.coordinate, Date().timeIntervalSince(lastAurora) > 600 else { return }
        lastAurora = Date()
        Task { model.auroraPercent = (try? await NOAA.fetchAurora(lat: c.lat, lon: c.lon)) ?? nil }
    }

    private func setTitle(_ text: String, color: NSColor?) {
        var attrs: [NSAttributedString.Key: Any] = [.font: NSFont.menuBarFont(ofSize: 0)]
        if let color { attrs[.foregroundColor] = color }
        statusItem.button?.attributedTitle = NSAttributedString(string: text, attributes: attrs)
    }

    private func toggleLogin() {
        let svc = SMAppService.mainApp
        do {
            if svc.status == .enabled { try svc.unregister() } else { try svc.register() }
        } catch { model.error = L("Auto-start: %@", error.localizedDescription) }
        model.launchAtLogin = svc.status == .enabled
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = MainActor.assumeIsolated { AppDelegate() }
app.delegate = delegate
app.run()
