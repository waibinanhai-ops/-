import SwiftUI

// MARK: - 剪贴板卡片（Premium 设计）

struct ClipCardView: View {
    let entry: ClipEntry
    var onCopy: () -> Void
    var onTogglePin: () -> Void
    var onToggleFavorite: () -> Void
    var onDelete: () -> Void

    @State private var thumbnailImage: NSImage?
    @State private var fullImage: NSImage?
    @State private var isHovering: Bool = false
    @State private var isTextHovering: Bool = false
    @State private var isImageHovering: Bool = false
    @State private var showDetail: Bool = false

    private let accentBlue = Color(red: 0.29, green: 0.56, blue: 0.85)

    var body: some View {
        cardRow
            .padding(.vertical, 6).padding(.horizontal, 10)
            .background(cardSurface)
            .overlay(cardHighlightBorder)
            .overlay(pinAccentLine)
            .scaleEffect(isHovering ? 1.03 : 1.0)
            .shadow(color: .black.opacity(isHovering ? 0.18 : 0.02), radius: isHovering ? 12 : 1, x: 0, y: isHovering ? 5 : 0)
            .animation(.spring(response: 0.5, dampingFraction: 0.55), value: isHovering)
            .contentShape(Rectangle())
            .onHover { hovering in
                isHovering = hovering
            }
            .onTapGesture { onCopy() }
            .contextMenu { cardContextMenu }
            .sheet(isPresented: $showDetail) { DetailView(entry: entry) }
    }

    // MARK: - Layout

    private var cardRow: some View {
        HStack(alignment: .center, spacing: 8) {
            typeIconView.frame(width: 28, height: 28)

            VStack(alignment: .leading, spacing: 3) {
                switch entry.contentType {
                case .text, .url: textPreview
                case .image: imageThumbnail
                }
                cardFooter
            }

            Spacer(minLength: 4)

            VStack(spacing: 2) {
                favoriteButton
                if entry.isFavorited { pinButton }
                deleteButton
            }
        }
    }

    // MARK: - Surface

    private var cardSurface: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(.regularMaterial.opacity(isHovering ? 0.55 : 0.35))
    }

    private var cardHighlightBorder: some View {
        RoundedRectangle(cornerRadius: 12)
            .stroke(isHovering ? Color.white.opacity(0.15) : Color.white.opacity(0.05), lineWidth: 1)
    }

    private var pinAccentLine: some View {
        RoundedRectangle(cornerRadius: 12)
            .stroke(entry.isPinned ? Color.orange.opacity(0.5) : Color.clear, lineWidth: 1.5)
    }

    // MARK: - Type Icon

    private var typeIconView: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 7)
                .fill(.ultraThinMaterial)
            switch entry.contentType {
            case .text:
                Image(systemName: "doc.text").font(.system(size: 13, weight: .medium)).foregroundColor(accentBlue)
            case .image:
                Image(systemName: "photo").font(.system(size: 13, weight: .medium)).foregroundColor(.green)
            case .url:
                Image(systemName: "link").font(.system(size: 13, weight: .medium)).foregroundColor(.purple)
            }
        }
    }

    // MARK: - Footer

    private var cardFooter: some View {
        HStack(spacing: 6) {
            if let app = entry.sourceAppName {
                Text(app).font(.system(size: 9, weight: .medium)).foregroundColor(.secondary)
            }
            if entry.isFavorited { Text("⭐").font(.system(size: 8)) }
            if entry.isPinned { Text("📌").font(.system(size: 8)) }
            Spacer(minLength: 0)
            Text(entry.copiedAt.relativeTimeDescription)
                .font(.system(size: 9)).foregroundColor(.secondary.opacity(0.7))
        }
    }

    // MARK: - Text Preview

    @ViewBuilder
    private var textPreview: some View {
        if let text = entry.textContent {
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            Text(trimmed)
                .font(.system(size: 12.5))
                .lineLimit(2).lineSpacing(2)
                .foregroundColor(.primary)
                .multilineTextAlignment(.leading)
                .onHover { h in isTextHovering = h }
                .popover(isPresented: $isTextHovering, arrowEdge: .trailing) {
                    let c = Double(trimmed.count)
                    let w = min(max(c * 9 + 50, 200), 450)
                    let h = min(max(ceil(c / 36) * 19 + 45, 70), 350)
                    ScrollView {
                        Text(trimmed).font(.system(size: 13)).textSelection(.enabled)
                            .foregroundColor(.primary).frame(maxWidth: .infinity, alignment: .leading).padding(14)
                    }
                    .frame(width: w, height: h)
                    .background(.regularMaterial)
                    .cornerRadius(12)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 1))
                }
        } else {
            Text("(空内容)").font(.system(size: 12.5)).foregroundColor(.secondary).italic()
        }
    }

    // MARK: - Image Thumbnail

    @ViewBuilder
    private var imageThumbnail: some View {
        if let path = entry.imagePath {
            Group {
                if let thumb = thumbnailImage {
                    Image(nsImage: thumb)
                        .resizable().aspectRatio(contentMode: .fit)
                        .frame(maxHeight: 180)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.white.opacity(0.08), lineWidth: 1))
                        .shadow(color: .black.opacity(0.06), radius: 3, x: 0, y: 2)
                        .onHover { h in isImageHovering = h }
                        .popover(isPresented: $isImageHovering, arrowEdge: .trailing) {
                            Image(nsImage: fullImage ?? thumb)
                                .resizable().aspectRatio(contentMode: .fit)
                                .frame(maxWidth: 480, maxHeight: 380).padding(10)
                                .background(.regularMaterial).cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 1))
                                .task { if fullImage == nil { fullImage = await Task.detached { await ImageStorageService.shared.loadImage(relativePath: path) }.value } }
                        }
                } else {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(.ultraThinMaterial).frame(height: 100)
                        .overlay(ProgressView().scaleEffect(0.6))
                }
            }
            .task { thumbnailImage = await Task.detached { await ImageStorageService.shared.loadThumbnail(relativePath: path) }.value }
        }
    }

    // MARK: - Buttons

    private var favoriteButton: some View {
        ActionButton(icon: entry.isFavorited ? "star.fill" : "star", label: entry.isFavorited ? "已收藏" : "收藏", activeColor: entry.isFavorited ? .yellow : nil, action: onToggleFavorite)
    }
    private var pinButton: some View {
        ActionButton(icon: entry.isPinned ? "pin.slash" : "pin.fill", label: entry.isPinned ? "已置顶" : "置顶", activeColor: entry.isPinned ? .orange : nil, action: onTogglePin)
    }
    private var deleteButton: some View {
        ActionButton(icon: "trash", label: "删除", activeColor: .red, action: onDelete)
    }

    // MARK: - Context Menu

    @ViewBuilder
    private var cardContextMenu: some View {
        Button(action: onCopy) { Label("复制到剪贴板", systemImage: "doc.on.doc") }.keyboardShortcut(.return, modifiers: [])
        Divider()
        Button(action: onToggleFavorite) { Label(entry.isFavorited ? "取消收藏" : "收藏", systemImage: entry.isFavorited ? "star.slash" : "star") }
        if entry.isFavorited {
            Button(action: onTogglePin) { Label(entry.isPinned ? "取消置顶" : "置顶", systemImage: entry.isPinned ? "pin.slash" : "pin.fill") }
        }
        Divider()
        if entry.contentType == .image { Button(action: { showDetail = true }) { Label("查看大图", systemImage: "eye") } }
        Button(role: .destructive, action: onDelete) { Label("删除", systemImage: "trash") }
    }
}

// MARK: - Action Button

struct ActionButton: View {
    let icon: String; let label: String; let activeColor: Color?; let action: () -> Void
    @State private var isHovering: Bool = false
    private let accentBlue = Color(red: 0.29, green: 0.56, blue: 0.85)

    var body: some View {
        let color: Color = isHovering ? (activeColor ?? accentBlue) : .secondary.opacity(0.6)

        Button(action: action) {
            VStack(spacing: 1) {
                Image(systemName: icon).font(.system(size: 11, weight: .medium))
                Text(label).font(.system(size: 7, weight: .medium))
            }
            .foregroundColor(color)
            .frame(width: 32)
            .padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 7)
                    .fill(isHovering ? (activeColor ?? accentBlue).opacity(0.12) : Color.white.opacity(0.03))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .stroke(isHovering ? (activeColor ?? accentBlue).opacity(0.2) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .scaleEffect(isHovering ? 1.08 : 1.0)
        .animation(.spring(response: 0.45, dampingFraction: 0.5), value: isHovering)
        .onHover { h in isHovering = h }
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 8) {
        ClipCardView(entry: ClipEntry(contentType: .text, textContent: "一段很长的示例文字用于测试卡片在 Premium 设计下的...", sourceAppName: "Safari", contentHash: "a", searchToken: "示例"),
            onCopy: {}, onTogglePin: {}, onToggleFavorite: {}, onDelete: {})
        ClipCardView(entry: ClipEntry(contentType: .text, textContent: "已置顶", sourceAppName: "Notes", contentHash: "b", searchToken: "置顶"),
            onCopy: {}, onTogglePin: {}, onToggleFavorite: {}, onDelete: {})
    }
    .frame(width: 380).padding()
    .background(.regularMaterial)
}
