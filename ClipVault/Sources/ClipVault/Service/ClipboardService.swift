import AppKit
import CryptoKit
import Foundation

/// 剪贴板提取结果
enum ClipboardService {

    // MARK: - Public Types

    /// 剪贴板内容
    enum ClipboardContent {
        case text(String)
        case image(NSImage, Data)  // image + raw PNG data
        case url(String)
    }

    // MARK: - Private Constants

    /// 需要跳过的剪贴板类型（远程剪贴板、密码管理器等）
    private static let skipTypes: Set<NSPasteboard.PasteboardType> = [
        .init("com.apple.is-remote-clipboard"),
        .init("org.nspasteboard.ConcealedType"),
        .init("com.agilebits.onepassword"),
        .init("com.apple.keychain-secret"),
    ]

    // MARK: - Public Methods

    /// 从剪贴板提取内容
    static func extractContent() -> ClipboardContent? {
        let pasteboard = NSPasteboard.general

        // 检查是否需要跳过
        guard let types = pasteboard.types else { return nil }
        for skipType in skipTypes {
            if types.contains(skipType) {
                return nil
            }
        }

        // 优先检测图片
        if types.contains(.png) || types.contains(.tiff) {
            if let image = pasteboard.readObjects(forClasses: [NSImage.self], options: nil)?.first as? NSImage,
               let pngData = image.pngData {
                return .image(image, pngData)
            }
        }

        // 检测 URL
        if types.contains(.URL) {
            if let urlString = pasteboard.string(forType: .URL),
               !urlString.isEmpty {
                return .url(urlString)
            }
        }

        // 检测纯文本
        if types.contains(.string) {
            if let string = pasteboard.string(forType: .string),
               !string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return .text(string)
            }
        }

        return nil
    }

    /// 计算内容哈希（SHA-256）
    static func computeHash(for content: ClipboardContent) -> String {
        let data: Data
        switch content {
        case .text(let string):
            data = Data(string.utf8)
        case .image(_, let pngData):
            data = pngData
        case .url(let urlString):
            data = Data(urlString.utf8)
        }
        let hash = SHA256.hash(data: data)
        return hash.compactMap { String(format: "%02x", $0) }.joined()
    }

    /// 获取当前前台 App 名称
    static func frontmostAppName() -> String? {
        NSWorkspace.shared.frontmostApplication?.localizedName
    }

    /// 获取当前前台 App Bundle ID
    static func frontmostAppBundleID() -> String? {
        NSWorkspace.shared.frontmostApplication?.bundleIdentifier
    }
}
