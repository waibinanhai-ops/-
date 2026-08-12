import Foundation
import SwiftData

/// 剪贴板内容类型
enum ClipContentType: String, Codable, CaseIterable {
    case text
    case image
    case url
}

/// 剪贴板历史记录条目
@Model
final class ClipEntry {
    /// 唯一标识
    @Attribute(.unique) var id: UUID

    /// 内容类型: text / image / url
    var contentTypeRaw: String

    /// 文字内容（图片类型时为空）
    var textContent: String?

    /// 图片文件的相对路径（相对于 Application Support/ClipVault/Images/）
    var imagePath: String?

    /// 文件大小（字节）
    var fileSize: Int64

    /// 来源 App 名称（如 "Safari"）
    var sourceAppName: String?

    /// 复制时间
    var copiedAt: Date

    /// 过期时间
    var expiresAt: Date

    /// 是否置顶
    var isPinned: Bool

    /// 是否收藏
    var isFavorited: Bool

    /// 内容哈希 (SHA-256)，用于去重
    var contentHash: String

    /// 搜索关键词（小写化的文字内容前 500 字符）
    var searchToken: String?

    /// 计算属性：内容类型枚举
    var contentType: ClipContentType {
        ClipContentType(rawValue: contentTypeRaw) ?? .text
    }

    /// 计算属性：是否已过期
    var isExpired: Bool {
        Date() > expiresAt
    }

    init(
        id: UUID = UUID(),
        contentType: ClipContentType,
        textContent: String? = nil,
        imagePath: String? = nil,
        fileSize: Int64 = 0,
        sourceAppName: String? = nil,
        copiedAt: Date = Date(),
        retentionDays: Int = 3,
        contentHash: String,
        searchToken: String? = nil
    ) {
        self.id = id
        self.contentTypeRaw = contentType.rawValue
        self.textContent = textContent
        self.imagePath = imagePath
        self.fileSize = fileSize
        self.sourceAppName = sourceAppName
        self.copiedAt = copiedAt
        self.expiresAt = Calendar.current.date(
            byAdding: .day,
            value: retentionDays,
            to: copiedAt
        ) ?? copiedAt.addingTimeInterval(86400 * Double(retentionDays))
        self.isPinned = false
        self.isFavorited = false
        self.contentHash = contentHash
        self.searchToken = searchToken ?? textContent?.lowercased().prefix(500).map { String($0) }.joined()
    }

    /// 更新过期时间（当用户更改保留天数时调用）
    func updateExpiry(retentionDays: Int) {
        guard !isPinned else { return }
        expiresAt = Calendar.current.date(
            byAdding: .day,
            value: retentionDays,
            to: copiedAt
        ) ?? copiedAt.addingTimeInterval(86400 * Double(retentionDays))
    }
}
