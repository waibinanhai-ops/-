import SwiftUI

/// 卡片列表容器
struct ClipListView: View {
    let entries: [ClipEntry]
    var onCopy: (ClipEntry) -> Void
    var onTogglePin: (ClipEntry) -> Void
    var onToggleFavorite: (ClipEntry) -> Void
    var onDelete: (ClipEntry) -> Void

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 6) {
                ForEach(entries) { entry in
                    ClipCardView(
                        entry: entry,
                        onCopy: { onCopy(entry) },
                        onTogglePin: { onTogglePin(entry) },
                        onToggleFavorite: { onToggleFavorite(entry) },
                        onDelete: { onDelete(entry) }
                    )
                    .padding(.horizontal, 12)
                }
            }
            .padding(.vertical, 8)
        }
    }
}

// MARK: - Preview

#Preview {
    ClipListView(
        entries: [],
        onCopy: { _ in },
        onTogglePin: { _ in },
        onToggleFavorite: { _ in },
        onDelete: { _ in }
    )
    .frame(width: 380, height: 400)
}
