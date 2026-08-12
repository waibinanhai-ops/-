import Foundation
import OSLog

/// 定时清理服务：每小时检查并删除过期记录
@MainActor
final class CleanupService: ObservableObject {

    // MARK: - Private Properties

    private var timer: Timer?
    private let checkInterval: TimeInterval = 3600 // 1 小时
    private let logger = Logger(subsystem: "com.clipvault.app", category: "CleanupService")

    // MARK: - Public Methods

    /// 启动定时清理
    func start() {
        guard timer == nil else { return }

        // 启动时立即执行一次清理
        performCleanup()

        // 每小时执行一次
        timer = Timer.scheduledTimer(
            withTimeInterval: checkInterval,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.performCleanup()
            }
        }

        logger.info("自动清理服务已启动 (间隔: \(self.checkInterval)s)")
    }

    /// 停止清理
    func stop() {
        timer?.invalidate()
        timer = nil
    }

    /// 立即执行清理（当用户更改保留天数时调用）
    func performCleanupNow() {
        performCleanup()
    }

    // MARK: - Private Methods

    private func performCleanup() {
        let deletedCount = DataService.shared.deleteExpiredEntries()
        if deletedCount > 0 {
            logger.info("自动清理: 已删除 \(deletedCount) 条过期记录")
        }
    }
}
