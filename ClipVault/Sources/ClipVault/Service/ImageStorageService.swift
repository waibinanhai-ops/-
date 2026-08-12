import AppKit
import Foundation
import OSLog

/// 图片文件存储服务
/// 将图片以 PNG 格式存储在磁盘上，数据库仅存文件路径
@MainActor
final class ImageStorageService {

    // MARK: - Singleton

    static let shared = ImageStorageService()

    // MARK: - Private Properties

    private let fileManager: FileManager
    private let logger = Logger(subsystem: "com.clipvault.app", category: "ImageStorage")

    // MARK: - Computed Properties

    /// 图片存储根目录: ~/Library/Application Support/ClipVault/Images/
    var baseDirectory: URL {
        let appSupport = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!

        let clipVaultDir = appSupport.appendingPathComponent("ClipVault", isDirectory: true)
        return clipVaultDir.appendingPathComponent("Images", isDirectory: true)
    }

    /// 缩略图存储根目录
    var thumbnailDirectory: URL {
        let appSupport = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!

        let clipVaultDir = appSupport.appendingPathComponent("ClipVault", isDirectory: true)
        return clipVaultDir.appendingPathComponent("Thumbnails", isDirectory: true)
    }

    // MARK: - Init

    private init() {
        self.fileManager = FileManager.default
        createDirectoriesIfNeeded()
    }

    // MARK: - Public Methods

    /// 保存图片到磁盘
    func saveImage(_ image: NSImage) -> (imagePath: String, thumbnailPath: String, fileSize: Int64)? {
        guard let pngData = image.pngData else {
            logger.error("无法将图片转换为 PNG 数据")
            return nil
        }

        let subDirName = UUID().uuidString.prefix(8)
        let subDir = baseDirectory.appendingPathComponent(String(subDirName), isDirectory: true)
        let thumbSubDir = thumbnailDirectory.appendingPathComponent(String(subDirName), isDirectory: true)

        do {
            try fileManager.createDirectory(at: subDir, withIntermediateDirectories: true)
            try fileManager.createDirectory(at: thumbSubDir, withIntermediateDirectories: true)
        } catch {
            logger.error("创建图片子目录失败: \(error.localizedDescription)")
            return nil
        }

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyyMMdd_HHmmss"
        let timestamp = dateFormatter.string(from: Date())

        // 保存原图 (PNG)
        let originalFileName = "clip_\(timestamp).png"
        let originalURL = subDir.appendingPathComponent(originalFileName)

        do {
            try pngData.write(to: originalURL, options: .atomic)
        } catch {
            logger.error("保存原图失败: \(error.localizedDescription)")
            return nil
        }

        // 保存缩略图 (JPEG, 200px)
        let thumbnailFileName = "thumb_\(timestamp).jpg"
        let thumbnailURL = thumbSubDir.appendingPathComponent(thumbnailFileName)

        if let thumbnail = image.thumbnail(maxSize: 200),
           let jpegData = thumbnail.jpegData(compression: 0.7) {
            do {
                try jpegData.write(to: thumbnailURL, options: .atomic)
            } catch {
                logger.warning("保存缩略图失败: \(error.localizedDescription)")
            }
        }

        let relativePath = "\(subDirName)/\(originalFileName)"
        let thumbRelativePath = "\(subDirName)/\(thumbnailFileName)"
        let fileSize = Int64(pngData.count)

        logger.info("图片已保存: \(relativePath) (\(fileSize) bytes)")

        return (relativePath, thumbRelativePath, fileSize)
    }

    /// 加载原图
    func loadImage(relativePath: String) -> NSImage? {
        let fullURL = baseDirectory.appendingPathComponent(relativePath)
        guard fileManager.fileExists(atPath: fullURL.path) else {
            logger.warning("图片文件不存在: \(relativePath)")
            return nil
        }
        return NSImage(contentsOf: fullURL)
    }

    /// 加载缩略图
    func loadThumbnail(relativePath: String) -> NSImage? {
        let components = relativePath.split(separator: "/")
        guard components.count == 2 else { return nil }

        let subDir = components[0]
        let originalName = String(components[1])
        let thumbName = originalName
            .replacingOccurrences(of: "clip_", with: "thumb_")
            .replacingOccurrences(of: ".png", with: ".jpg")

        let thumbPath = "\(subDir)/\(thumbName)"
        let fullURL = thumbnailDirectory.appendingPathComponent(thumbPath)

        guard fileManager.fileExists(atPath: fullURL.path) else {
            return loadImage(relativePath: relativePath)?.thumbnail(maxSize: 200)
        }
        return NSImage(contentsOf: fullURL)
    }

    /// 删除图片及其缩略图
    func deleteImage(relativePath: String) {
        let components = relativePath.split(separator: "/")
        guard components.count == 2 else { return }

        let subDir = String(components[0])

        let imageSubDir = baseDirectory.appendingPathComponent(subDir, isDirectory: true)
        let thumbSubDir = thumbnailDirectory.appendingPathComponent(subDir, isDirectory: true)

        if fileManager.fileExists(atPath: imageSubDir.path) {
            try? fileManager.removeItem(at: imageSubDir)
        }

        if fileManager.fileExists(atPath: thumbSubDir.path) {
            try? fileManager.removeItem(at: thumbSubDir)
        }

        logger.debug("图片已删除: \(subDir)")
    }

    /// 获取图片存储总大小
    func totalStorageSize() -> Int64 {
        var totalSize: Int64 = 0
        for dir in [baseDirectory, thumbnailDirectory] {
            guard let enumerator = fileManager.enumerator(
                at: dir,
                includingPropertiesForKeys: [.fileSizeKey],
                options: [.skipsHiddenFiles]
            ) else { continue }

            for case let fileURL as URL in enumerator {
                if let resourceValues = try? fileURL.resourceValues(forKeys: [.fileSizeKey]),
                   let size = resourceValues.fileSize {
                    totalSize += Int64(size)
                }
            }
        }
        return totalSize
    }

    /// 清理所有图片文件
    func clearAll() {
        for dir in [baseDirectory, thumbnailDirectory] {
            if fileManager.fileExists(atPath: dir.path) {
                try? fileManager.removeItem(at: dir)
                try? fileManager.createDirectory(at: dir, withIntermediateDirectories: true)
            }
        }
        logger.info("所有图片文件已清理")
    }

    // MARK: - Private Methods

    private func createDirectoriesIfNeeded() {
        for dir in [baseDirectory, thumbnailDirectory] {
            if !fileManager.fileExists(atPath: dir.path) {
                try? fileManager.createDirectory(
                    at: dir,
                    withIntermediateDirectories: true
                )
            }
        }
    }
}
