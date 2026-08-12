import SwiftUI
import ServiceManagement

/// 设置视图
struct SettingsView: View {
    @Binding var isPresented: Bool

    @AppStorage("retentionDays") private var retentionDays: Int = 3
    @AppStorage("launchAtLogin") private var launchAtLogin: Bool = false

    @State private var showClearConfirmation: Bool = false

    /// 主色调 - 淡蓝
    private let accentBlue = Color(red: 0.29, green: 0.56, blue: 0.85)

    var body: some View {
        VStack(spacing: 0) {
            // 标题栏
            HStack {
                Text("设置")
                    .font(.system(size: 16, weight: .semibold))
                Spacer()
                Button(action: { isPresented = false }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 12)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // 保留天数
                    settingsSection(title: "记录保留时间", icon: "clock") {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("超过设定天数的记录将自动删除（置顶记录不受影响）")
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)

                            Picker("", selection: $retentionDays) {
                                Text("1 天").tag(1)
                                Text("3 天").tag(3)
                                Text("5 天").tag(5)
                            }
                            .pickerStyle(.segmented)
                            .frame(width: 220)
                            .onChange(of: retentionDays) { _, newValue in
                                // 更改保留天数后立即清理并重算
                                DataService.shared.recalculateExpiryDates(retentionDays: newValue)
                                CleanupService().performCleanupNow()
                            }
                        }
                    }

                    Divider().padding(.horizontal, 20)

                    // 开机启动
                    settingsSection(title: "开机启动", icon: "power") {
                        HStack {
                            Toggle("", isOn: $launchAtLogin)
                                .toggleStyle(.switch)
                                .onChange(of: launchAtLogin) { _, newValue in
                                    toggleLaunchAtLogin(enabled: newValue)
                                }
                            Text("电脑开机时自动启动剪贴板管家")
                                .font(.system(size: 13))
                                .foregroundColor(.secondary)
                        }
                    }

                    Divider().padding(.horizontal, 20)

                    // 存储信息
                    settingsSection(title: "存储空间", icon: "internaldrive") {
                        VStack(alignment: .leading, spacing: 8) {
                            let imageSize = ImageStorageService.shared.totalStorageSize()
                            let imageSizeMB = Double(imageSize) / 1_048_576.0

                            HStack {
                                Text("图片占用:")
                                    .font(.system(size: 12))
                                Text(String(format: "%.1f MB", imageSizeMB))
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundColor(imageSizeMB > 400 ? .red : .primary)
                            }

                            // 存储进度条
                            GeometryReader { geo in
                                ZStack(alignment: .leading) {
                                    RoundedRectangle(cornerRadius: 3)
                                        .fill(Color(nsColor: .quaternarySystemFill))
                                        .frame(height: 6)

                                    RoundedRectangle(cornerRadius: 3)
                                        .fill(
                                            imageSizeMB > 400
                                                ? Color.red
                                                : imageSizeMB > 200
                                                    ? Color.orange
                                                    : accentBlue
                                        )
                                        .frame(
                                            width: geo.size.width * min(imageSizeMB / 500.0, 1.0),
                                            height: 6
                                        )
                                }
                            }
                            .frame(height: 6)

                            Text("上限 500 MB，超出后自动清理最旧图片")
                                .font(.system(size: 10))
                                .foregroundColor(.secondary)
                        }
                    }

                    Divider().padding(.horizontal, 20)

                    // 清空所有历史
                    settingsSection(title: "数据管理", icon: "xmark.bin") {
                        Button(action: { showClearConfirmation = true }) {
                            Text("清空所有历史记录")
                                .font(.system(size: 13))
                                .foregroundColor(.red)
                        }
                        .buttonStyle(.borderless)
                        .alert("确认清空", isPresented: $showClearConfirmation) {
                            Button("取消", role: .cancel) {}
                            Button("清空", role: .destructive) {
                                DataService.shared.clearAllHistory()
                            }
                        } message: {
                            Text("此操作将删除所有历史记录和图片文件，不可恢复。确定要继续吗？")
                        }
                    }

                    Divider().padding(.horizontal, 20)

                    // 关于
                    settingsSection(title: "关于", icon: "info.circle") {
                        VStack(alignment: .leading, spacing: 8) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("剪贴板管家 v1.0")
                                    .font(.system(size: 13, weight: .medium))
                                Text("一款简洁的 macOS 剪贴板历史管理工具")
                                    .font(.system(size: 11))
                                    .foregroundColor(.secondary)
                                Text("快捷键: Cmd + Shift + V")
                                    .font(.system(size: 11))
                                    .foregroundColor(.secondary)
                            }
                            Button(action: { NSApplication.shared.terminate(nil) }) {
                                Text("退出剪贴板管家")
                                    .font(.system(size: 12))
                                    .foregroundColor(.red)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding(.vertical, 20)
            }
        }
        .frame(width: 380, height: 480)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    // MARK: - Helpers

    @ViewBuilder
    private func settingsSection<Content: View>(
        title: String,
        icon: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .foregroundColor(accentBlue)
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
            }
            content()
        }
        .padding(.horizontal, 20)
    }

    private func toggleLaunchAtLogin(enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            // 登录项注册失败（未签名的开发版本可能出现）
            print("开机启动设置失败: \(error.localizedDescription)")
        }
    }
}

// MARK: - Preview

#Preview {
    SettingsView(isPresented: .constant(true))
}
