import AppKit
import OSLog
import SwiftData
import SwiftUI

/// AppDelegate: 管理菜单栏图标、浮动面板和所有服务的生命周期
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {

    // MARK: - Properties

    private var statusItem: NSStatusItem?
    private var panelController: ClipPanelController?
    private let clipboardMonitor = ClipboardMonitor.shared
    private let shortcutService = ShortcutService()
    private let cleanupService = CleanupService()
    private let logger = Logger(subsystem: "com.clipvault.app", category: "AppDelegate")

    // MARK: - NSApplicationDelegate

    func applicationDidFinishLaunching(_ notification: Notification) {
        logger.info("ClipVault 启动中...")

        // 1. 设置 DataService 的 ModelContext
        let context = ModelContext(AppContainer.shared)
        DataService.shared.modelContext = context

        // 2. 创建菜单栏图标
        setupStatusItem()

        // 3. 创建浮动面板
        setupPanel()

        // 4. 启动剪贴板监听
        setupClipboardMonitor()

        // 5. 启动自动清理
        cleanupService.start()

        // 6. 注册全局快捷键
        setupShortcut()

        // 7. 注册系统通知
        setupNotifications()

        logger.info("ClipVault 启动完成")
    }

    func applicationWillTerminate(_ notification: Notification) {
        clipboardMonitor.stop()
        cleanupService.stop()
        shortcutService.stop()
        logger.info("ClipVault 已退出")
    }

    // MARK: - Setup Methods

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem?.button {
            if let image = NSImage(
                systemSymbolName: "clipboard",
                accessibilityDescription: "剪贴板管家"
            ) {
                image.isTemplate = true
                button.image = image
            } else {
                button.title = "📋"
            }

            button.toolTip = "剪贴板管家"
            button.target = self
            button.action = #selector(togglePanel)
            button.sendAction(on: [.leftMouseUp])
        }
    }

    private func setupPanel() {
        panelController = ClipPanelController()
    }

    private func setupClipboardMonitor() {
        clipboardMonitor.onNewContent = { content in
            let appName = ClipboardService.frontmostAppName()
            _ = DataService.shared.saveEntry(
                content: content,
                sourceAppName: appName
            )
        }
        clipboardMonitor.start()
    }

    private func setupShortcut() {
        shortcutService.onShortcutTriggered = { [weak self] in
            self?.togglePanel()
        }
        shortcutService.registerDefaultShortcut()
    }

    private func setupNotifications() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screenParametersChanged),
            name: NSApplication.didChangeScreenParametersNotification,
            object: nil
        )
    }

    // MARK: - Panel Actions

    @objc private func togglePanel() {
        panelController?.togglePanel(relativeTo: statusItem?.button)
    }

    @objc private func screenParametersChanged() {
        panelController?.closePanel()
    }
}
