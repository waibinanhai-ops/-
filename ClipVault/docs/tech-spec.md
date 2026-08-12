# 剪贴板管家 (ClipVault) — 技术规范

## 技术栈

| 层面 | 选型 | 版本要求 |
|------|------|----------|
| 语言 | Swift | 5.9+ |
| UI 框架 | SwiftUI + AppKit 混合 | macOS 14+ |
| 数据持久化 | SwiftData (SQLite) | macOS 14+ |
| 设置存储 | UserDefaults / @AppStorage | - |
| 图片存储 | 磁盘文件 (Application Support) | - |
| 包管理 | Swift Package Manager | 5.9+ |
| 最小部署 | macOS 14 (Sonoma) | - |

## 项目结构

```
ClipVault/
├── Package.swift
├── Resources/
│   └── Info.plist
├── Sources/ClipVault/
│   ├── ClipVaultApp.swift              # @main 入口
│   ├── AppDelegate.swift               # 菜单栏、面板、生命周期
│   ├── Model/
│   │   └── ClipEntry.swift             # SwiftData 数据模型
│   ├── Service/
│   │   ├── ClipboardMonitor.swift      # 剪贴板轮询监听
│   │   ├── ClipboardService.swift      # 剪贴板内容提取
│   │   ├── DataService.swift           # 数据 CRUD 操作
│   │   ├── ImageStorageService.swift   # 图片文件存储
│   │   ├── CleanupService.swift        # 定时过期清理
│   │   └── ShortcutService.swift       # 全局快捷键
│   ├── UI/
│   │   ├── ContentView.swift            # 主视图（搜索+列表）
│   │   ├── ClipListView.swift          # 卡片列表
│   │   ├── ClipCardView.swift          # 单条卡片
│   │   ├── SearchBarView.swift         # 搜索框
│   │   ├── DetailView.swift            # 内容详情
│   │   ├── SettingsView.swift          # 设置页
│   │   └── EmptyStateView.swift        # 空状态
│   ├── Panel/
│   │   └── ClipPanelController.swift   # NSPanel 管理
│   └── Extension/
│       ├── NSImage+Extensions.swift    # 图片工具
│       └── Date+Extensions.swift       # 日期格式化
├── docs/                               # 项目文档
└── dev-logs/                           # 开发日志
```

## 核心架构模式

### 1. SwiftUI + AppKit 混合模式

- **SwiftUI (70%)**: 所有 UI 视图组件，数据绑定，状态管理
- **AppKit (30%)**: NSStatusItem（菜单栏）、NSPanel（浮动面板）、NSEvent（全局监听）、NSPasteboard（剪贴板）

### 2. 数据流

```
NSPasteboard → ClipboardMonitor (定时轮询)
  → ClipboardService (提取内容+哈希)
    → DataService (去重+写入 SwiftData)
      → SwiftUI @Query (自动刷新 UI)
```

### 3. 单例服务

- `DataService.shared` - 数据操作
- `ImageStorageService.shared` - 图片文件操作
- 其余服务由 AppDelegate 持有和管理生命周期

## 数据模型

单一模型 `ClipEntry`：

| 属性 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键，唯一 |
| contentTypeRaw | String | text / image / url |
| textContent | String? | 文字内容 |
| imagePath | String? | 图片相对路径 |
| fileSize | Int64 | 文件大小 |
| sourceAppName | String? | 来源 App |
| copiedAt | Date | 复制时间 |
| expiresAt | Date | 过期时间 |
| isPinned | Bool | 是否置顶 |
| contentHash | String | SHA-256 |
| searchToken | String? | 搜索关键词 |

## 存储路径

- **数据库**: SwiftData 默认位置 (`~/Library/Application Support/ClipVault/`)
- **图片**: `~/Library/Application Support/ClipVault/Images/{uuid8}/clip_yyyymmdd_HHmmss.png`
- **缩略图**: `~/Library/Application Support/ClipVault/Thumbnails/{uuid8}/thumb_yyyymmdd_HHmmss.jpg`
- **设置**: UserDefaults standard

## 关键实现决策

1. **图片存磁盘而非数据库**：避免 SQLite 膨胀，保持查询性能
2. **去重仅比对最近一条**：平衡性能与功能
3. **面板使用 NSPanel.nonactivatingPanel**：不抢夺焦点
4. **非沙盒模式**：需要 Accessibility 权限才能使用全局快捷键
5. **LSUIElement = YES**：隐藏 Dock 图标，仅菜单栏

## 编译与构建

```bash
# 编译
cd ClipVault
swift build -c release

# 运行
swift run -c release
```
