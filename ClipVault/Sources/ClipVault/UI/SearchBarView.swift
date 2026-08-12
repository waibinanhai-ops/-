import SwiftUI

struct SearchBarView: View {
    @Binding var text: String
    @FocusState private var isFocused: Bool
    var onFocusChange: ((Bool) -> Void)?

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12, weight: .medium)).foregroundColor(.secondary.opacity(0.5))
            TextField("搜索...", text: $text)
                .textFieldStyle(.plain).font(.system(size: 12.5))
                .focused($isFocused)
            if !text.isEmpty {
                Button(action: { text = "" }) {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 11)).foregroundColor(.secondary.opacity(0.5))
                }.buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(isFocused ? accentBlue.opacity(0.4) : Color.white.opacity(0.08), lineWidth: 1)
                )
        )
        .animation(.easeInOut(duration: 0.2), value: isFocused)
        .onChange(of: isFocused) { _, newValue in
            if newValue { onFocusChange?(true) }
        }
    }

    private let accentBlue = Color(red: 0.29, green: 0.56, blue: 0.85)
}

#Preview {
    VStack {
        SearchBarView(text: .constant("")).padding()
        SearchBarView(text: .constant("关键词")).padding()
    }.frame(width: 380).background(.regularMaterial)
}
