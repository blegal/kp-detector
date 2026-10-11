import Foundation

struct KpSample: Identifiable {
    let date: Date
    let kp: Double
    let predicted: Bool
    var id: Date { date }
}

enum Geo {
    // Pôle géomagnétique dipolaire (approx. IGRF 2025)
    static let poleLat = 80.7 * .pi / 180
    static let poleLon = -72.6 * .pi / 180

    static func geomagneticLatitude(lat: Double, lon: Double) -> Double {
        let φ = lat * .pi / 180, λ = lon * .pi / 180
        let s = sin(φ) * sin(poleLat) + cos(φ) * cos(poleLat) * cos(λ - poleLon)
        return asin(max(-1, min(1, s))) * 180 / .pi
    }

    /// Kp minimal pour apercevoir une aurore sur l'horizon nord à cette latitude géomagnétique.
    /// Frontière de l'ovale ≈ 67° − 2°·Kp, relevée de ~2° car l'aurore est visible de loin
    /// (arcs hauts en altitude). Calibré sur les observations en France (Kp ≈ 7 le 10/10/2026).
    static func kpNeededForAurora(geomagLat: Double) -> Double {
        max(0, (65 - abs(geomagLat)) / 2)
    }
}

enum NOAA {
    /// Session sans cache disque/mémoire : les réponses ne sont jamais conservées.
    static let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.urlCache = nil
        c.requestCachePolicy = .reloadIgnoringLocalCacheData
        c.timeoutIntervalForRequest = 20
        c.waitsForConnectivity = false
        return URLSession(configuration: c)
    }()

    static let kpURL = URL(string: "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json")!
    static let ovationURL = URL(string: "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json")!

    /// Historique observé + prévisions (≈ 7 jours passés, 3 jours à venir), un point toutes les 3 h.
    static func fetchKp() async throws -> [KpSample] {
        let (data, _) = try await session.data(from: kpURL)
        guard let rows = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw URLError(.cannotParseResponse)
        }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let samples: [KpSample] = rows.compactMap {
            guard let t = $0["time_tag"] as? String, let d = f.date(from: t),
                  let kp = ($0["kp"] as? NSNumber)?.doubleValue ?? Double($0["kp"] as? String ?? ""),
                  let status = $0["observed"] as? String else { return nil }
            return KpSample(date: d, kp: kp, predicted: status == "predicted")
        }
        guard !samples.isEmpty else { throw URLError(.cannotParseResponse) }
        return samples
    }

    /// Probabilité d'aurore (%) au point de grille OVATION le plus proche.
    /// Recherche directe dans les octets du JSON : évite de décoder ~65 000 tableaux.
    static func fetchAurora(lat: Double, lon: Double) async throws -> Int? {
        let (data, _) = try await session.data(from: ovationURL)
        let la = Int(lat.rounded()), lo = (Int(lon.rounded()) + 360) % 360
        let needle = Array("[\(lo), \(la), ".utf8)
        return data.withUnsafeBytes { (buf: UnsafeRawBufferPointer) -> Int? in
            let b = buf.bindMemory(to: UInt8.self)
            guard b.count > needle.count else { return nil }
            var i = 0
            let last = b.count - needle.count
            while i <= last {
                if b[i] == needle[0] {
                    var j = 1
                    while j < needle.count && b[i + j] == needle[j] { j += 1 }
                    if j == needle.count {
                        var k = i + needle.count, v = 0
                        while k < b.count, b[k] >= 48, b[k] <= 57 { v = v * 10 + Int(b[k] - 48); k += 1 }
                        return v
                    }
                }
                i += 1
            }
            return nil
        }
    }
}
