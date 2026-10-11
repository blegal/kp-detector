import AppKit
import UserNotifications

/// Envoie les alertes de forte activité (> seuil) : centre de notification, iMessage, Mail.
/// iMessage et Mail ne sont utilisés que si l'utilisateur les a activés et a saisi un destinataire.
@MainActor
final class AlertService: NSObject, UNUserNotificationCenterDelegate {
    private let model: Model
    private let defaults = UserDefaults.standard
    private let sentKey = "alertedSamples"

    init(model: Model) {
        self.model = model
        super.init()
    }

    func requestAuthorization() {
        let c = UNUserNotificationCenter.current()
        c.delegate = self
        c.requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent n: UNNotification,
                                            withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) {
        done([.banner, .sound])
    }

    // MARK: Détection

    /// Une alerte par créneau de 3 h dépassant le seuil, jamais deux fois.
    func checkForecast() {
        let now = Date()
        let threshold = model.alertThreshold
        let already = Set(defaults.stringArray(forKey: sentKey) ?? [])
        let hot = model.samples.filter {
            $0.kp > threshold && $0.date.addingTimeInterval(3 * 3600) > now && !already.contains(Self.key($0))
        }
        guard let peak = hot.max(by: { $0.kp < $1.kp }) else { return }

        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("EEEEdMMMHHmm")
        let when = peak.predicted ? L("forecast %@", f.string(from: peak.date)) : L("ongoing")
        let level = Model.label(peak.kp)
        var body = String(format: "Kp %.1f %@ (%@).", peak.kp, when, level)
        if let need = model.kpNeeded, let place = model.place, !place.isEmpty {
            body += need <= peak.kp ? L(" Aurora possible in %@.", place) : L(" Probably not enough in %@.", place)
        }
        deliver(title: L("Geomagnetic storm: Kp %.1f", peak.kp), body: body)

        let all = Array(already.union(hot.map(Self.key)).suffix(200))
        defaults.set(all, forKey: sentKey)
    }

    func sendTest() {
        deliver(title: L("Test KP Detector"), body: L("This is a test alert."))
    }

    private static func key(_ s: KpSample) -> String { String(Int(s.date.timeIntervalSince1970)) }

    // MARK: Envoi

    private func deliver(title: String, body: String) {
        if model.notifyCenter {
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            UNUserNotificationCenter.current().add(
                UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
        }
        if model.imessageOn {
            for to in Self.recipients(model.imessageTo) {
                run(Self.messagesScript(to: to, text: "\(title) — \(body)"), channel: "iMessage \(to)")
            }
        }
        if model.mailOn {
            // Un message par destinataire : les adresses ne sont pas exposées entre elles.
            for to in Self.recipients(model.mailTo) {
                run(Self.mailScript(to: to, subject: title, body: body), channel: "Mail \(to)")
            }
        }
    }

    /// Destinataires séparés par virgule, point-virgule, espace ou retour à la ligne (doublons ignorés).
    private static func recipients(_ raw: String) -> [String] {
        var seen = Set<String>()
        return raw.components(separatedBy: CharacterSet(charactersIn: ",; \n\t"))
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && seen.insert($0.lowercased()).inserted }
    }

    private func run(_ source: String, channel: String) {
        var err: NSDictionary?
        NSAppleScript(source: source)?.executeAndReturnError(&err)
        if let err { model.error = L("%1$@: %2$@", channel, err[NSAppleScript.errorMessage] as? String ?? L("failed")) }
    }

    private static func esc(_ s: String) -> String {
        s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    }

    private static func messagesScript(to: String, text: String) -> String {
        """
        tell application "Messages"
            try
                set svc to 1st account whose service type = iMessage
                send "\(esc(text))" to participant "\(esc(to))" of svc
            on error
                set svc to 1st service whose service type = iMessage
                send "\(esc(text))" to buddy "\(esc(to))" of svc
            end try
        end tell
        """
    }

    private static func mailScript(to: String, subject: String, body: String) -> String {
        """
        tell application "Mail"
            set m to make new outgoing message with properties {subject:"\(esc(subject))", content:"\(esc(body))", visible:false}
            tell m to make new to recipient with properties {address:"\(esc(to))"}
            send m
        end tell
        """
    }
}
