# 剪贴板管家 (ClipVault) — 架构说明

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    AppDelegate                       │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐   │
│  │StatusItem│ │  Panel   │ │ Service Lifecycle │   │
│  │ (菜单栏) │ │ Controller│ │ (启动/停止服务)   │   │
│  └──────────┘ └─────┬────┘ └───────────────────┘   │
│                      │                               │
│              ┌───────▼───────┐                       │
│              │  NSPanel +    │                       │
│              │ NSHostingView │                       │
│              │  (ContentView)│                       │
│              └───────┬───────┘                       │
└──────────────────────┼──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   SwiftUI Layer                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────────┐   │
│  │SearchBar   │ │ClipListView│ │ SettingsView   │   │
│  └────────────┘ └─────┬──────┘ └────────────────┘   │
│                       │                               │
│              ┌────────▼────────┐                      │
│              │  ClipCardView   │                      │
│              │  (LazyVStack)   │                      │
│              └────────┬────────┘                      │
│                       │                               │
│              ┌────────▼────────┐                      │
│              │ SwiftData @Query│                      │
│              └────────┬────────┘                      │
└───────────────────────┼──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│                   Service Layer                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────────┐   │
│  │Clipboard   │ │DataService │ │CleanupService  │   │
│  │Monitor     │─▶ (单例)    │◀│ (定时器)       │   │
│  │(Timer 0.5s)│ └─────┬──────┘ └────────────────┘   │
│  └────────────┘       │                               │
│                       │                               │
│  ┌────────────┐       │        ┌────────────────┐    │
│  │Clipboard   │       │        │ImageStorage    │    │
│  │Service     │───────┘        │Service (单例)  │    │
│  └────────────┘                └────────────────┘    │
│                                                       │
│  ┌────────────┐                                      │
│  │Shortcut    │  NSEvent Global Monitor               │
│  │Service     │  (Cmd+Shift+V)                        │
│  └────────────┘                                      │
└──────────────────────────────────────────────────────┘
```

## 数据流详解

```
1. 用户复制内容 (Cmd+C)
      │
2. NSPasteboard.general 更新
      │
3. ClipboardMonitor 定时器检测到 changeCount 变化
      │
4. ClipboardService.extractContent()
   ├── 检测类型 (text/image/url)
   ├── 过滤敏感类型 (密码管理器)
   └── 返回 ClipboardContent 枚举
      │
5. ClipboardService.computeHash()
   └── SHA-256 哈希值
      │
6. DataService.saveEntry()
   ├── 与最近一条记录比对哈希 → 去重
   ├── 如是图片: ImageStorageService.saveImage() → 写磁盘
   ├── ClipEntry 插入 SwiftData
   └── 触发上限检查 (>10,000 条则删除最旧)
      │
7. SwiftData 自动持久化 → SQLite
      │
8. UI 层 @Query 自动检测数据变化 → 刷新列表
```

## 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| `ClipVaultApp` | 入口，初始化 SwiftData，传递 context | SwiftData |
| `AppDelegate` | 生命周期管理，创建菜单栏和面板 | Panel, Services |
| `ClipPanelController` | NSPanel 定位、显示/隐藏、点击外部关闭 | - |
| `ClipboardMonitor` | 定时轮询剪贴板变化 | ClipboardService |
| `ClipboardService` | 提取内容、计算哈希、获取来源 App | - |
| `DataService` | SwiftData CRUD、去重、上限管理 | SwiftData, ImageStorage |
| `ImageStorageService` | 图片文件/缩略图读写、磁盘管理 | FileManager |
| `CleanupService` | 定时清理过期记录 | DataService |
| `ShortcutService` | 全局快捷键注册 | NSEvent |
| `ContentView` | 主视图容器，组合子视图 | @Query |
| `ClipListView` | LazyVStack 卡片列表 | ClipCardView |
| `ClipCardView` | 单条卡片展示 | - |
| `SearchBarView` | 搜索输入框 | - |
| `DetailView` | 内容详情弹窗 | - |
| `SettingsView` | 设置表单 | UserDefaults |
| `EmptyStateView` | 空列表占位 | - |

## 生命周期

```
App Launch
├── ClipVaultApp.init
│   └── 初始化 SwiftData ModelContainer
├── AppDelegate.applicationDidFinishLaunching
│   ├── 创建 NSStatusItem (菜单栏图标)
│   ├── 创建 ClipPanelController (预加载面板)
│   ├── 设置 DataService.shared.modelContext
│   ├── ClipboardMonitor.start()
│   ├── CleanupService.start()
│   ├── ShortcutService.registerDefaultShortcut()
│   └── 注册通知监听 (唤醒、屏幕变化)
│
App Running
├── 剪贴板变化 → 自动记录
├── 用户点击图标/快捷键 → 显示/隐藏面板
├── 用户在面板操作 → 复制/置顶/删除
├── 定时器 → 每小时清理过期记录
│
App Termination
├── ClipboardMonitor.stop()
├── CleanupService.stop()
├── ShortcutService.stop()
└── 关闭面板
```
