import SwiftUI

@MainActor
final class Model: ObservableObject {
    @Published var samples: [KpSample] = []
    @Published var auroraPercent: Int?
    @Published var place: String?
    @Published var coordinate: (lat: Double, lon: Double)?
    @Published var error: String?
    @Published var launchAtLogin = false

    // Réglages d'alerte (persistés)
    private let defaults: UserDefaults
    @Published var alertsExpanded = false
    @Published var alertThreshold: Double { didSet { defaults.set(alertThreshold, forKey: "alertThreshold") } }
    @Published var notifyCenter: Bool { didSet { defaults.set(notifyCenter, forKey: "notifyCenter") } }
    @Published var imessageOn: Bool { didSet { defaults.set(imessageOn, forKey: "imessageOn") } }
    @Published var imessageTo: String { didSet { defaults.set(imessageTo, forKey: "imessageTo") } }
    @Published var mailOn: Bool { didSet { defaults.set(mailOn, forKey: "mailOn") } }
    @Published var mailTo: String { didSet { defaults.set(mailTo, forKey: "mailTo") } }

    init(defaults d: UserDefaults = .standard) {
        defaults = d
        alertThreshold = d.object(forKey: "alertThreshold") as? Double ?? 6
        notifyCenter = d.object(forKey: "notifyCenter") as? Bool ?? true
        imessageOn = d.bool(forKey: "imessageOn")
        imessageTo = d.string(forKey: "imessageTo") ?? ""
        mailOn = d.bool(forKey: "mailOn")
        mailTo = d.string(forKey: "mailTo") ?? ""
    }

    var onTestAlert: () -> Void = {}
    var onRefresh: () -> Void = {}
    var onToggleLogin: () -> Void = {}

    var current: KpSample? { samples.last { !$0.predicted } }

    var peakNext24h: KpSample? {
        let horizon = Date().addingTimeInterval(24 * 3600)
        return samples.filter { $0.predicted && $0.date <= horizon }.max { $0.kp < $1.kp }
    }

    var geomagLat: Double? {
        coordinate.map { Geo.geomagneticLatitude(lat: $0.lat, lon: $0.lon) }
    }
    var kpNeeded: Double? { geomagLat.map(Geo.kpNeededForAurora) }

    /// Maximum de Kp par jour (jours courant et à venir).
    var dailyMax: [(day: Date, kp: Double, predicted: Bool)] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let groups = Dictionary(grouping: samples.filter { cal.startOfDay(for: $0.date) >= today }) {
            cal.startOfDay(for: $0.date)
        }
        return groups.keys.sorted().map { d in
            let g = groups[d]!
            return (d, g.map(\.kp).max() ?? 0, g.contains { $0.predicted })
        }
    }

    static func color(for kp: Double) -> Color {
        switch kp {
        case ..<4.67: return .green
        case ..<5.67: return .yellow
        case ..<6.67: return .orange
        default: return .red
        }
    }

    static func nsColor(for kp: Double) -> NSColor? {
        switch kp {
        case ..<4.67: return nil
        case ..<5.67: return .systemYellow
        case ..<6.67: return .systemOrange
        default: return .systemRed
        }
    }

    static func label(_ kp: Double) -> String {
        switch kp {
        case ..<4.67: return L("Calm")
        case ..<5.67: return L("G1 · minor")
        case ..<6.67: return L("G2 · moderate")
        case ..<7.67: return L("G3 · strong")
        case ..<8.67: return L("G4 · severe")
        default: return L("G5 · extreme")
        }
    }
}
