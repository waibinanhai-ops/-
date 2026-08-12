import AppKit
import CoreGraphics

extension NSImage {
    /// 生成缩略图（最大边长 maxSize，保持宽高比）
    func thumbnail(maxSize: CGFloat = 200) -> NSImage? {
        let originalSize = self.size
        guard originalSize.width > 0, originalSize.height > 0 else { return nil }

        let scale: CGFloat
        if originalSize.width > originalSize.height {
            scale = min(maxSize / originalSize.width, 1.0)
        } else {
            scale = min(maxSize / originalSize.height, 1.0)
        }

        // 如果原图已经足够小，直接返回副本
        if scale >= 1.0 {
            return self
        }

        let newSize = NSSize(
            width: originalSize.width * scale,
            height: originalSize.height * scale
        )

        let thumbnail = NSImage(size: newSize)
        thumbnail.lockFocus()
        self.draw(
            in: NSRect(origin: .zero, size: newSize),
            from: NSRect(origin: .zero, size: originalSize),
            operation: .copy,
            fraction: 1.0
        )
        thumbnail.unlockFocus()

        return thumbnail
    }

    /// 转换为 PNG 数据
    var pngData: Data? {
        guard let tiffData = self.tiffRepresentation,
              let bitmapRep = NSBitmapImageRep(data: tiffData) else {
            return nil
        }
        return bitmapRep.representation(using: .png, properties: [:])
    }

    /// 转换为 JPEG 数据
    func jpegData(compression: Float = 0.7) -> Data? {
        guard let tiffData = self.tiffRepresentation,
              let bitmapRep = NSBitmapImageRep(data: tiffData) else {
            return nil
        }
        return bitmapRep.representation(
            using: .jpeg,
            properties: [.compressionFactor: compression]
        )
    }

    /// 计算文件大小（基于 PNG 表示）
    var estimatedFileSize: Int64 {
        Int64(pngData?.count ?? 0)
    }
}
