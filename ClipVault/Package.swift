// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "ClipVault",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "ClipVault",
            targets: ["ClipVault"]
        )
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "ClipVault"
        )
    ]
)
