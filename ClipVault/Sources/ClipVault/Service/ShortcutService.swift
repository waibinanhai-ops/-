import AppKit
import Carbon
import OSLog

/// 全局快捷键服务
@MainActor
final class ShortcutService {

    // MARK: - Private Properties

    private var eventMonitor: Any?
    private let logger = Logger(subsystem: "com.clipvault.app", category: "ShortcutService")

    // MARK: - Callbacks

    var onShortcutTriggered: (() -> Void)?

    // MARK: - Init

    init() {}

    deinit {
        // deinit 运行在非隔离上下文，直接清理
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
        }
    }

    // MARK: - Public Methods

    /// 注册全局快捷键 (默认 Cmd+Shift+V)
    func registerDefaultShortcut() {
        // 使用 NSEvent 全局事件监听
        eventMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: .keyDown
        ) { [weak self] event in
            // Cmd+Shift+V
            if event.modifierFlags.intersection(.deviceIndependentFlagsMask) == [.command, .shift],
               event.keyCode == 9 { // 'V' key
                Task { @MainActor [weak self] in
                    self?.logger.debug("全局快捷键触发: Cmd+Shift+V")
                    self?.onShortcutTriggered?()
                }
            }
        }

        if eventMonitor != nil {
            logger.info("全局快捷键已注册 (Cmd+Shift+V)")
        } else {
            logger.error("全局快捷键注册失败：需要辅助功能权限")
        }
    }

    /// 停止监听
    func stop() {
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
            eventMonitor = nil
            logger.info("全局快捷键已注销")
        }
    }

    // MARK: - Key Codes Reference
    //
    // V = 0x09
    // C = 0x08
    // X = 0x07
    // A = 0x00
    // ...
}
