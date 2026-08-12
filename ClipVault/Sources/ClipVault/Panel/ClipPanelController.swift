import AppKit
import OSLog
import SwiftUI

/// 浮动面板控制器：高级磨砂玻璃风格
@MainActor
final class ClipPanelController: NSObject {

    private var panel: NSPanel?
    private var hostingView: NSHostingView<AnyView>?
    private var globalMouseMonitor: Any?
    private var localKeyMonitor: Any?
    private var isPanelVisible: Bool = false
    private let logger = Logger(subsystem: "com.clipvault.app", category: "PanelController")

    private let panelSize = NSSize(width: 360, height: 500)

    override init() {
        super.init()
        setupPanel()
    }

    func togglePanel(relativeTo statusButton: NSButton?) {
        isPanelVisible ? closePanel() : showPanel(relativeTo: statusButton)
    }

    func showPanel(relativeTo statusButton: NSButton?) {
        guard let panel = panel else { return }
        if let button = statusButton {
            let origin = calculatePanelOrigin(relativeTo: button)
            panel.setFrame(NSRect(origin: origin, size: panelSize), display: true)
        }
        panel.orderFrontRegardless()
        isPanelVisible = true
        startGlobalMouseMonitor()
        startLocalKeyMonitor()
    }

    func closePanel() {
        panel?.close()
        isPanelVisible = false
        stopGlobalMouseMonitor()
        stopLocalKeyMonitor()
    }

    // MARK: - Setup

    private func setupPanel() {
        let panel = NSPanel(
            contentRect: NSRect(origin: .zero, size: panelSize),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.animationBehavior = .utilityWindow
        panel.becomesKeyOnlyIfNeeded = true
        panel.isReleasedWhenClosed = false

        let contentView = panel.contentView!
        contentView.wantsLayer = true

        // 底层：深磨砂玻璃
        let baseBlur = NSVisualEffectView(frame: contentView.bounds)
        baseBlur.material = .hudWindow
        baseBlur.blendingMode = .behindWindow
        baseBlur.state = .active
        baseBlur.wantsLayer = true
        baseBlur.layer?.cornerRadius = 20
        baseBlur.layer?.masksToBounds = true
        baseBlur.autoresizingMask = [.width, .height]
        contentView.addSubview(baseBlur, positioned: .below, relativeTo: nil)

        // 中层：轻薄磨砂叠加（增加层次）
        let topBlur = NSVisualEffectView(frame: contentView.bounds)
        topBlur.material = .menu
        topBlur.blendingMode = .withinWindow
        topBlur.state = .active
        topBlur.wantsLayer = true
        topBlur.layer?.cornerRadius = 20
        topBlur.layer?.masksToBounds = true
        topBlur.autoresizingMask = [.width, .height]
        topBlur.alphaValue = 0.6
        contentView.addSubview(topBlur, positioned: .above, relativeTo: baseBlur)

        // 内边框光晕
        let borderLayer = CALayer()
        borderLayer.cornerRadius = 20
        borderLayer.borderWidth = 1
        borderLayer.borderColor = NSColor.white.withAlphaComponent(0.1).cgColor
        borderLayer.frame = contentView.bounds
        borderLayer.autoresizingMask = [.layerWidthSizable, .layerHeightSizable]
        contentView.layer?.addSublayer(borderLayer)

        // SwiftUI 视图
        let swiftUIView = ContentView(panelController: self)
            .modelContainer(AppContainer.shared)
        let hostingView = NSHostingView(rootView: AnyView(swiftUIView))
        hostingView.autoresizingMask = [.width, .height]
        hostingView.frame = contentView.bounds
        contentView.addSubview(hostingView)

        self.hostingView = hostingView
        self.panel = panel
        logger.info("NSPanel 已创建（Premium 磨砂玻璃风格）")
    }

    // MARK: - Positioning

    private func calculatePanelOrigin(relativeTo statusButton: NSButton) -> NSPoint {
        guard let buttonWindow = statusButton.window else { return NSPoint(x: 100, y: 100) }
        let buttonRect = buttonWindow.convertToScreen(statusButton.frame)
        let screen = statusButton.window?.screen ?? NSScreen.main ?? NSScreen.screens.first!
        let visibleFrame = screen.visibleFrame

        var x = buttonRect.midX - panelSize.width / 2
        let y = buttonRect.minY - panelSize.height - 10
        x = max(x, visibleFrame.minX + 12)
        x = min(x, visibleFrame.maxX - panelSize.width - 12)

        return NSPoint(x: x, y: y < visibleFrame.minY ? buttonRect.maxY + 10 : y)
    }

    // MARK: - Mouse

    private func startGlobalMouseMonitor() {
        globalMouseMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] _ in
            Task { @MainActor [weak self] in self?.handleGlobalClick() }
        }
    }

    private func stopGlobalMouseMonitor() {
        if let m = globalMouseMonitor { NSEvent.removeMonitor(m); globalMouseMonitor = nil }
    }

    private func handleGlobalClick() {
        guard let panel = panel, isPanelVisible else { return }
        if !panel.frame.contains(NSEvent.mouseLocation) { closePanel() }
    }

    // MARK: - Keyboard

    private func startLocalKeyMonitor() {
        localKeyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == 53 { Task { @MainActor in self.closePanel() } }
            return event
        }
    }

    private func stopLocalKeyMonitor() {
        if let m = localKeyMonitor { NSEvent.removeMonitor(m); localKeyMonitor = nil }
    }

    // MARK: - Public Key Window Control

    /// 强制面板成为 key window（搜索框获得焦点时调用）
    func makeKey() {
        panel?.makeKey()
    }
}
