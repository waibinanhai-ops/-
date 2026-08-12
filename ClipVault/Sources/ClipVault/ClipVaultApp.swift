import SwiftUI
import SwiftData

/// 全局共享的 ModelContainer（App 启动时初始化一次）
struct AppContainer {
    static let shared: ModelContainer = {
        do {
            let schema = Schema([ClipEntry.self])

            // 显式指定数据库存储路径
            let appSupport = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            ).first!

            let storeDir = appSupport.appendingPathComponent("ClipVault", isDirectory: true)
            try? FileManager.default.createDirectory(at: storeDir, withIntermediateDirectories: true)

            let storeURL = storeDir.appendingPathComponent("ClipVault.store")

            let config = ModelConfiguration(schema: schema, url: storeURL)

            return try ModelContainer(for: schema, configurations: [config])
        } catch {
            fatalError("无法初始化 SwiftData ModelContainer: \(error)")
        }
    }()
}

/// 剪贴板管家 — App 入口
@main
struct ClipVaultApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    init() {
        // 初始化 UserDefaults 默认值
        if UserDefaults.standard.integer(forKey: "retentionDays") == 0 {
            UserDefaults.standard.set(3, forKey: "retentionDays")
        }
    }

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}
