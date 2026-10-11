import SwiftUI
import Charts

struct PopoverView: View {
    @ObservedObject var model: Model

    var body: some View {
        VStack(spacing: 10) {
            header
            gauges
            section(L("History and forecast"))
            chart
            section(L("Details"))
            details
            section(L("Coming days"))
            days
            alertSettings
        }
        .padding(14)
        .frame(width: 320)
    }

    // MARK: En-tête

    private var header: some View {
        ZStack {
            Text("Kp").font(.headline)
            HStack {
                Spacer()
                Menu {
                    Button(L("Refresh"), action: model.onRefresh)
                    Toggle(L("Launch at login"),
                           isOn: Binding(get: { model.launchAtLogin }, set: { _ in model.onToggleLogin() }))
                    Divider()
                    Button(L("Quit")) { NSApp.terminate(nil) }
                } label: {
                    Image(systemName: "gearshape.fill").foregroundStyle(.secondary)
                }
                .menuStyle(.borderlessButton)
                .menuIndicator(.hidden)
                .fixedSize()
            }
        }
    }

    // MARK: Jauges

    private var gauges: some View {
        HStack(spacing: 28) {
            if let c = model.current {
                Ring(progress: c.kp / 9, color: Model.color(for: c.kp),
                     big: String(format: "%.1f", c.kp), caption: "Kp", size: 96)
            } else {
                Ring(progress: 0, color: .gray, big: "–", caption: "Kp", size: 96)
            }
            Ring(progress: Double(model.auroraPercent ?? 0) / 100, color: .purple,
                 big: model.auroraPercent.map { "\($0)%" } ?? "–", caption: L("Aurora"), size: 70)
        }
        .padding(.top, 4)
    }

    // MARK: Courbe

    private var chart: some View {
        let now = Date()
        return Chart {
            ForEach(model.samples) { s in
                RectangleMark(xStart: .value("Début", s.date),
                              xEnd: .value("Fin", s.date.addingTimeInterval(3 * 3600)),
                              yStart: .value("Base", 0),
                              yEnd: .value("Kp", s.kp))
                    .foregroundStyle(Model.color(for: s.kp).opacity(s.predicted ? 0.4 : 0.9))
            }
            RuleMark(x: .value("Maintenant", now))
                .foregroundStyle(.primary.opacity(0.6))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
            if let need = model.kpNeeded, need > 0, need <= 9 {
                RuleMark(y: .value("Seuil", need))
                    .foregroundStyle(.purple)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    .annotation(position: .top, alignment: .leading, spacing: 1) {
                        Text(L("aurora here")).font(.system(size: 9)).foregroundStyle(.purple)
                    }
            }
        }
        .chartYScale(domain: 0...9)
        .chartYAxis {
            AxisMarks(values: [0, 3, 5, 7, 9]) { _ in
                AxisGridLine(); AxisValueLabel().font(.system(size: 9))
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day)) { _ in
                AxisTick()
                AxisValueLabel(format: .dateTime.weekday(.abbreviated), anchor: .top).font(.system(size: 9))
            }
        }
        .frame(height: 120)
    }

    // MARK: Détails

    private var details: some View {
        VStack(spacing: 5) {
            if let c = model.current {
                row(L("Status"), Model.label(c.kp), Model.color(for: c.kp))
            }
            if let p = model.peakNext24h {
                row(L("Peak forecast (24 h)"), String(format: "Kp %.1f", p.kp), Model.color(for: p.kp))
            }
            if model.coordinate != nil {
                row(L("Location"), model.place?.isEmpty == false ? model.place! : "—", nil)
                if let m = model.geomagLat { row(L("Geomagnetic latitude"), String(format: "%.1f°", m), nil) }
                if let n = model.kpNeeded {
                    row(L("Kp needed here (northern horizon)"), n == 0 ? "0" : String(format: "≈ %.1f", n), .purple)
                }
            } else {
                row(L("Position"), model.error ?? L("waiting for permission"), nil)
            }
            if let e = model.error, model.coordinate != nil { row(L("Error"), e, .red) }
        }
    }

    // MARK: Liste par jour

    private var days: some View {
        VStack(spacing: 5) {
            ForEach(model.dailyMax, id: \.day) { d in
                HStack {
                    Circle().fill(Model.color(for: d.kp)).frame(width: 8, height: 8)
                    Text(Self.dayLabel(d.day)).font(.system(size: 12))
                    if d.predicted { Text(L("fcst.")).font(.system(size: 9)).foregroundStyle(.secondary) }
                    Spacer()
                    Text(String(format: "Kp %.1f", d.kp)).font(.system(size: 12, weight: .semibold))
                }
            }
        }
    }

    // MARK: Alertes

    private var alertSettings: some View {
        DisclosureGroup(L("Alerts"), isExpanded: $model.alertsExpanded) {
            VStack(alignment: .leading, spacing: 6) {
                Stepper(value: $model.alertThreshold, in: 3...9, step: 1) {
                    Text(L("Alert if forecast Kp > %.0f", model.alertThreshold)).font(.system(size: 12))
                }
                Toggle(L("Notification Center"), isOn: $model.notifyCenter).font(.system(size: 12))
                Toggle("iMessage", isOn: $model.imessageOn).font(.system(size: 12))
                if model.imessageOn {
                    TextField(L("Numbers / emails, comma-separated"), text: $model.imessageTo).textFieldStyle(.roundedBorder)
                }
                Toggle(L("Email (Mail app)"), isOn: $model.mailOn).font(.system(size: 12))
                if model.mailOn {
                    TextField(L("Addresses, comma-separated"), text: $model.mailTo).textFieldStyle(.roundedBorder)
                }
                Button(L("Send a test alert"), action: model.onTestAlert).font(.system(size: 12))
            }
            .padding(.top, 6)
        }
        .font(.system(size: 11))
        .padding(.top, 4)
    }

    // MARK: Helpers

    private func section(_ t: String) -> some View {
        Text(t).font(.system(size: 11)).foregroundStyle(.secondary).padding(.top, 4)
    }

    private func row(_ k: String, _ v: String, _ c: Color?) -> some View {
        HStack {
            Text(k).font(.system(size: 12)).foregroundStyle(.secondary)
            Spacer()
            Text(v).font(.system(size: 12, weight: .semibold)).foregroundStyle(c ?? .primary)
                .lineLimit(1).truncationMode(.tail)
        }
    }

    private static func dayLabel(_ d: Date) -> String {
        let cal = Calendar.current
        if cal.isDateInToday(d) { return L("Today") }
        if cal.isDateInTomorrow(d) { return L("Tomorrow") }
        return d.formatted(.dateTime.weekday(.wide).day().month(.abbreviated)).capitalized
    }
}

struct Ring: View {
    let progress: Double
    let color: Color
    let big: String
    let caption: String
    let size: CGFloat

    var body: some View {
        ZStack {
            Circle().stroke(Color.secondary.opacity(0.2), lineWidth: size * 0.12)
            Circle().trim(from: 0, to: max(0.001, min(1, progress)))
                .stroke(color, style: StrokeStyle(lineWidth: size * 0.12, lineCap: .butt))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text(big).font(.system(size: size * 0.26, weight: .semibold))
                Text(caption).font(.system(size: size * 0.12)).foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
    }
}
