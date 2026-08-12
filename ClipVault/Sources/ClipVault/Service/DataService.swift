import Foundation
import OSLog
import SwiftData

/// 数据服务层：封装 SwiftData 的增删改查操作
@MainActor
final class DataService: ObservableObject {

    // MARK: - Singleton

    static let shared = DataService()

    // MARK: - Private Properties

    private let logger = Logger(subsystem: "com.clipvault.app", category: "DataService")

    /// SwiftData ModelContext（由外部注入）
    var modelContext: ModelContext?

    /// 最大存储条目数
    private let maxEntries = 10_000

    // MARK: - Init

    private init() {}

    // MARK: - Public Methods - CRUD

    /// 保存新的剪贴板条目
    /// - Returns: 如果是重复内容则返回 nil
    func saveEntry(
        content: ClipboardService.ClipboardContent,
        sourceAppName: String?
    ) -> ClipEntry? {
        guard let context = modelContext else {
            logger.error("ModelContext 未初始化")
            return nil
        }

        // 1. 计算哈希
        let hash = ClipboardService.computeHash(for: content)

        // 2. 去重：与最近一条记录比较
        if let lastEntry = mostRecentEntry(),
           lastEntry.contentHash == hash {
            logger.debug("跳过重复内容")
            return nil
        }

        // 3. 构建条目
        let entry: ClipEntry
        let retentionDays = UserDefaults.standard.integer(forKey: "retentionDays")

        switch content {
        case .text(let string):
            entry = ClipEntry(
                contentType: .text,
                textContent: string,
                sourceAppName: sourceAppName,
                retentionDays: retentionDays,
                contentHash: hash,
                searchToken: string.lowercased()
            )

        case .image(let image, _):
            // 在主 actor 上保存图片文件
            if let result = ImageStorageService.shared.saveImage(image) {
                entry = ClipEntry(
                    contentType: .image,
                    imagePath: result.imagePath,
                    fileSize: result.fileSize,
                    sourceAppName: sourceAppName,
                    retentionDays: retentionDays,
                    contentHash: hash,
                    searchToken: nil
                )
            } else {
                logger.error("图片保存失败")
                return nil
            }

        case .url(let urlString):
            entry = ClipEntry(
                contentType: .url,
                textContent: urlString,
                sourceAppName: sourceAppName,
                retentionDays: retentionDays,
                contentHash: hash,
                searchToken: urlString.lowercased()
            )
        }

        // 4. 插入数据库
        context.insert(entry)
        try? context.save()

        // 5. 检查容量上限
        enforceEntryLimit()

        logger.info("新条目已保存: \(entry.contentTypeRaw)")

        return entry
    }

    /// 删除条目（同时删除关联的图片文件）
    func deleteEntry(_ entry: ClipEntry) {
        // 优先用 entry 所属的 context，确保和 @Query 用同一个 context
        guard let context = entry.modelContext ?? modelContext else { return }

        // 删除图片文件
        if entry.contentType == .image, let imagePath = entry.imagePath {
            ImageStorageService.shared.deleteImage(relativePath: imagePath)
        }

        context.delete(entry)
        try? context.save()

        logger.debug("条目已删除: \(entry.id)")
    }

    /// 切换置顶状态
    func togglePin(_ entry: ClipEntry) {
        entry.isPinned.toggle()
        try? (entry.modelContext ?? modelContext)?.save()
    }

    /// 切换收藏状态
    func toggleFavorite(_ entry: ClipEntry) {
        entry.isFavorited.toggle()
        try? (entry.modelContext ?? modelContext)?.save()
    }

    /// 重新计算所有未置顶条目的过期时间
    func recalculateExpiryDates(retentionDays: Int) {
        guard let context = modelContext else { return }

        let descriptor = FetchDescriptor<ClipEntry>(
            predicate: #Predicate { !$0.isPinned }
        )

        if let entries = try? context.fetch(descriptor) {
            for entry in entries {
                entry.updateExpiry(retentionDays: retentionDays)
            }
            try? context.save()
        }

        logger.info("已重新计算过期时间 (保留 \(retentionDays) 天)")
    }

    /// 批量删除过期条目
    func deleteExpiredEntries() -> Int {
        guard let context = modelContext else { return 0 }

        let now = Date()
        let descriptor = FetchDescriptor<ClipEntry>(
            predicate: #Predicate { $0.expiresAt < now && !$0.isPinned }
        )

        guard let expiredEntries = try? context.fetch(descriptor),
              !expiredEntries.isEmpty else {
            return 0
        }

        for entry in expiredEntries {
            if entry.contentType == .image, let imagePath = entry.imagePath {
                ImageStorageService.shared.deleteImage(relativePath: imagePath)
            }
            context.delete(entry)
        }

        try? context.save()
        logger.info("已清理 \(expiredEntries.count) 条过期记录")

        return expiredEntries.count
    }

    /// 获取最近一条记录
    func mostRecentEntry() -> ClipEntry? {
        guard let context = modelContext else { return nil }

        var descriptor = FetchDescriptor<ClipEntry>(
            sortBy: [SortDescriptor(\.copiedAt, order: .reverse)]
        )
        descriptor.fetchLimit = 1

        return try? context.fetch(descriptor).first
    }

    /// 清空所有历史记录
    func clearAllHistory() {
        guard let context = modelContext else { return }

        let descriptor = FetchDescriptor<ClipEntry>()
        if let allEntries = try? context.fetch(descriptor) {
            for entry in allEntries {
                if entry.contentType == .image, let imagePath = entry.imagePath {
                    ImageStorageService.shared.deleteImage(relativePath: imagePath)
                }
                context.delete(entry)
            }
            try? context.save()
        }

        ImageStorageService.shared.clearAll()
        logger.info("所有历史记录已清空")
    }

    // MARK: - Private Methods

    /// 强制执行条目数量上限
    private func enforceEntryLimit() {
        guard let context = modelContext else { return }

        let countDescriptor = FetchDescriptor<ClipEntry>()
        let totalCount = (try? context.fetchCount(countDescriptor)) ?? 0

        guard totalCount > maxEntries else { return }

        // 删除最旧的非置顶条目
        let excess = totalCount - maxEntries
        var descriptor = FetchDescriptor<ClipEntry>(
            predicate: #Predicate { !$0.isPinned },
            sortBy: [SortDescriptor(\.copiedAt, order: .forward)]
        )
        descriptor.fetchLimit = excess

        if let oldestEntries = try? context.fetch(descriptor) {
            for entry in oldestEntries {
                if entry.contentType == .image, let imagePath = entry.imagePath {
                    ImageStorageService.shared.deleteImage(relativePath: imagePath)
                }
                context.delete(entry)
            }
            try? context.save()
            logger.info("已自动清理 \(oldestEntries.count) 条超出上限的记录")
        }
    }
}
