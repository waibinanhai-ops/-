import SwiftUI
import SwiftData

struct ContentView: View {
    @Query(sort: \ClipEntry.copiedAt, order: .reverse, animation: .default)
    private var allEntries: [ClipEntry]

    @State private var searchText: String = ""
    @State private var showSettings: Bool = false
    @State private var showFavoritesOnly: Bool = false

    let panelController: ClipPanelController

    private var displayEntries: [ClipEntry] {
        var filtered = allEntries
        if showFavoritesOnly { filtered = filtered.filter { $0.isFavorited } }
        else { filtered = filtered.filter { !$0.isFavorited } }
        if !searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let q = searchText.lowercased()
            filtered = filtered.filter { e in
                if let t = e.searchToken, t.contains(q) { return true }
                if let t = e.textContent, t.lowercased().contains(q) { return true }
                return false
            }
        }
        return filtered.sorted { a, b in
            if a.isPinned != b.isPinned { return a.isPinned }
            return a.copiedAt > b.copiedAt
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // 顶栏：Logo + 设置
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "clipboard").font(.system(size: 14, weight: .semibold)).foregroundColor(.secondary)
                    Text("剪贴板").font(.system(size: 13, weight: .semibold)).foregroundColor(.secondary)
                }
                Spacer()
                Text("\(allEntries.count)").font(.system(size: 11, weight: .medium)).foregroundColor(.secondary.opacity(0.6))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Capsule().fill(.ultraThinMaterial))
                Button(action: { showSettings = true }) {
                    Image(systemName: "gearshape").font(.system(size: 13)).foregroundColor(.secondary.opacity(0.7))
                }.buttonStyle(.plain)
                Button(action: { NSApplication.shared.terminate(nil) }) {
                    Image(systemName: "power").font(.system(size: 13)).foregroundColor(.secondary.opacity(0.7))
                }.buttonStyle(.plain)
            }
            .padding(.horizontal, 14).padding(.top, 14).padding(.bottom, 8)

            // 搜索 + 标签
            VStack(spacing: 8) {
                SearchBarView(text: $searchText, onFocusChange: { focused in
                    if focused { panelController.makeKey() }
                })
                Picker("", selection: $showFavoritesOnly) {
                    Text("全部").tag(false)
                    Text("⭐ 收藏").tag(true)
                }
                .pickerStyle(.segmented)
                .colorMultiply(.secondary)
            }
            .padding(.horizontal, 14).padding(.bottom, 8)

            // 分割线
            Rectangle().fill(Color.white.opacity(0.06)).frame(height: 1).padding(.horizontal, 14)

            // 内容区
            if displayEntries.isEmpty {
                EmptyStateView(hasSearchQuery: !searchText.isEmpty || showFavoritesOnly)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 2) {
                        ForEach(displayEntries) { entry in
                            ClipCardView(
                                entry: entry,
                                onCopy: { copyToClipboard(entry) },
                                onTogglePin: { DataService.shared.togglePin(entry) },
                                onToggleFavorite: { DataService.shared.toggleFavorite(entry) },
                                onDelete: { DataService.shared.deleteEntry(entry) }
                            )
                        }
                    }
                    .padding(.horizontal, 10).padding(.vertical, 8)
                }
            }

            // 底部分割 + 提示
            Rectangle().fill(Color.white.opacity(0.06)).frame(height: 1).padding(.horizontal, 14)
            HStack {
                Text("Cmd+Shift+V 快速打开").font(.system(size: 9)).foregroundColor(.secondary.opacity(0.5))
                Spacer()
                Text("点击卡片复制").font(.system(size: 9)).foregroundColor(.secondary.opacity(0.5))
            }
            .padding(.horizontal, 14).padding(.vertical, 7)
        }
        .frame(width: 360, height: 500)
        .background(Color.clear)
        .sheet(isPresented: $showSettings) { SettingsView(isPresented: $showSettings) }
    }

    private func copyToClipboard(_ entry: ClipEntry) {
        let pb = NSPasteboard.general; pb.clearContents()
        switch entry.contentType {
        case .text, .url: if let t = entry.textContent { pb.setString(t, forType: .string) }
        case .image: if let p = entry.imagePath, let img = ImageStorageService.shared.loadImage(relativePath: p) { pb.writeObjects([img]) }
        }
    }
}

#Preview { ContentView(panelController: ClipPanelController()).modelContainer(AppContainer.shared) }
