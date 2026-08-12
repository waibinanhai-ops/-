import AppKit
import Foundation
import OSLog

/// 剪贴板监听器：通过轮询 NSPasteboard.changeCount 检测变化
/// 使用 Swift Concurrency (async/await) 代替 Timer，保证 Swift 6 兼容性
@MainActor
final class ClipboardMonitor: ObservableObject {

    // MARK: - Shared

    static let shared = ClipboardMonitor()

    // MARK: - Published

    @Published private(set) var isMonitoring: Bool = false

    // MARK: - Private Properties

    private let pasteboard: NSPasteboard
    private var lastChangeCount: Int
    private var pollingTask: Task<Void, Never>?
    private let pollingInterval: UInt64  // 纳秒
    private let logger = Logger(subsystem: "com.clipvault.app", category: "ClipboardMonitor")

    // MARK: - Skip Next

    /// 设置为 true 可跳过下一次剪贴板变化检测（用于防止自家写入被重复记录）
    var skipNextChange: Bool = false

    // MARK: - Callbacks

    var onNewContent: ((ClipboardService.ClipboardContent) -> Void)?

    // MARK: - Init

    init(
        pasteboard: NSPasteboard = .general,
        pollingInterval: TimeInterval = 0.5
    ) {
        self.pasteboard = pasteboard
        self.pollingInterval = UInt64(pollingInterval * 1_000_000_000)
        self.lastChangeCount = pasteboard.changeCount
    }

    // MARK: - Public Methods

    /// 启动监听
    func start() {
        guard !isMonitoring else { return }
        isMonitoring = true

        // 获取初始 changeCount
        lastChangeCount = pasteboard.changeCount

        // 使用 async Task 循环代替 Timer（更兼容 Swift 6 actor 模型）
        pollingTask = Task { @MainActor [weak self] in
            guard let self = self else { return }
            logger.info("剪贴板监听已启动 (间隔: \(Double(self.pollingInterval) / 1_000_000_000)s)")

            while !Task.isCancelled && self.isMonitoring {
                do {
                    try await Task.sleep(nanoseconds: self.pollingInterval)
                    guard !Task.isCancelled else { break }
                    self.checkPasteboard()
                } catch {
                    // Task.sleep 被取消
                    break
                }
            }
        }

        // 注册系统唤醒通知
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleWakeFromSleep),
            name: NSWorkspace.didWakeNotification,
            object: nil
        )
    }

    /// 停止监听
    func stop() {
        guard isMonitoring else { return }
        isMonitoring = false
        pollingTask?.cancel()
        pollingTask = nil
        NotificationCenter.default.removeObserver(
            self,
            name: NSWorkspace.didWakeNotification,
            object: nil
        )
        logger.info("剪贴板监听已停止")
    }

    // MARK: - Private Methods

    private func checkPasteboard() {
        let currentChangeCount = pasteboard.changeCount
        guard currentChangeCount != lastChangeCount else { return }

        lastChangeCount = currentChangeCount

        // 跳过自家写入（如用户点击面板中的卡片复制）
        if skipNextChange {
            skipNextChange = false
            logger.debug("跳过自家写入的剪贴板变化")
            return
        }

        if let content = ClipboardService.extractContent() {
            logger.debug("检测到新的剪贴板内容")
            onNewContent?(content)
        }
    }

    @objc private func handleWakeFromSleep() {
        lastChangeCount = pasteboard.changeCount - 1
        logger.debug("系统唤醒，重新检查剪贴板")
    }
}
