import SwiftUI

struct EmptyStateView: View {
    let hasSearchQuery: Bool

    var body: some View {
        VStack(spacing: 14) {
            Spacer()
            ZStack {
                Circle().fill(.ultraThinMaterial).frame(width: 72, height: 72)
                Image(systemName: hasSearchQuery ? "magnifyingglass" : "tray")
                    .font(.system(size: 28, weight: .light)).foregroundColor(.secondary.opacity(0.4))
            }
            VStack(spacing: 4) {
                Text(hasSearchQuery ? "没有匹配记录" : "剪贴板为空")
                    .font(.system(size: 13, weight: .medium)).foregroundColor(.secondary.opacity(0.6))
                Text(hasSearchQuery ? "试试其他关键词" : "复制文字或图片后会自动出现")
                    .font(.system(size: 11)).foregroundColor(.secondary.opacity(0.35))
            }
            Spacer()
        }
    }
}

#Preview {
    HStack(spacing: 20) {
        EmptyStateView(hasSearchQuery: false).frame(width: 180, height: 300).background(.regularMaterial)
        EmptyStateView(hasSearchQuery: true).frame(width: 180, height: 300).background(.regularMaterial)
    }
}
