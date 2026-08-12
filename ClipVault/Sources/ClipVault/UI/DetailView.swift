import SwiftUI

/// 内容详情视图（查看完整文字或大图）
struct DetailView: View {
    let entry: ClipEntry

    @Environment(\.dismiss) private var dismiss
    @State private var fullImage: NSImage?

    var body: some View {
        VStack(spacing: 0) {
            // 标题栏
            HStack {
                Text("内容详情")
                    .font(.system(size: 15, weight: .semibold))

                Spacer()

                Button(action: copyContent) {
                    Label("复制", systemImage: "doc.on.doc")
                        .font(.system(size: 12))
                }

                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            Divider()

            // 内容区域
            ScrollView {
                switch entry.contentType {
                case .text, .url:
                    if let text = entry.textContent {
                        Text(text)
                            .font(.system(size: 13))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(16)
                    }

                case .image:
                    if let imagePath = entry.imagePath {
                        Group {
                            if let image = fullImage {
                                Image(nsImage: image)
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                                    .frame(maxWidth: .infinity)
                            } else {
                                ProgressView()
                                    .frame(height: 200)
                            }
                        }
                        .padding(16)
                        .task {
                            fullImage = await Task.detached {
                                await ImageStorageService.shared.loadImage(relativePath: imagePath)
                            }.value
                        }
                    }
                }
            }

            // 底部信息
            Divider()
            HStack {
                if let appName = entry.sourceAppName {
                    Text("来源: \(appName)")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
                Spacer()
                Text(entry.copiedAt.fullDateTimeString)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .frame(width: 500, height: 400)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func copyContent() {
        ClipboardMonitor.shared.skipNextChange = true
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()

        switch entry.contentType {
        case .text, .url:
            if let text = entry.textContent {
                pasteboard.setString(text, forType: .string)
            }
        case .image:
            if let imagePath = entry.imagePath,
               let image = ImageStorageService.shared.loadImage(relativePath: imagePath) {
                pasteboard.writeObjects([image])
            }
        }
    }
}

// MARK: - Preview

#Preview {
    DetailView(entry: ClipEntry(
        contentType: .text,
        textContent: "这是详细的文本内容预览。在详情视图中可以查看完整的复制内容。",
        sourceAppName: "Safari",
        contentHash: "xyz",
        searchToken: "详细文本"
    ))
}
