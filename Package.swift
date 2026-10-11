// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "KPDetector",
    platforms: [.macOS(.v13)],
    targets: [.executableTarget(name: "KPDetector", path: "Sources/KPDetector",
                                  swiftSettings: [.unsafeFlags(["-O", "-wmo"])])]
)
