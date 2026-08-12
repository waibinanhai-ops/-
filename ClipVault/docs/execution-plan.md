# 剪贴板管家 (ClipVault) — 执行计划

## 开发阶段（共 5 个阶段）

### 阶段 1：项目骨架
**目标**: 项目能编译，菜单栏图标出现，空白面板可弹出/关闭

1. ✅ 创建目录结构
2. ✅ 编写 Package.swift + Info.plist
3. ⬜ 编写 ClipVaultApp.swift（@main 入口）
4. ⬜ 编写 AppDelegate.swift（菜单栏 + 面板生命周期）
5. ⬜ 编写 ClipPanelController.swift（NSPanel + 定位）
6. ⬜ 编译验证：菜单栏图标 + 面板弹出

### 阶段 2：数据层
**目标**: 数据模型可工作，文字/图片可存储到数据库

7. ✅ 编写 ClipEntry.swift（数据模型）
8. ✅ 编写 ImageStorageService.swift（图片文件存储）
9. ✅ 编写 Date+Extensions.swift + NSImage+Extensions.swift
10. ⬜ 编写 DataService.swift（CRUD 操作）
11. ⬜ 编译验证：模拟数据写入和查询

### 阶段 3：服务层
**目标**: 剪贴板自动监听，内容自动记录

12. ✅ 编写 ClipboardService.swift（内容提取+哈希）
13. ✅ 编写 ClipboardMonitor.swift（定时轮询）
14. ✅ 编写 CleanupService.swift（过期清理）
15. ✅ 编写 ShortcutService.swift（全局快捷键）
16. ⬜ 编译验证：复制内容后数据库中自动出现记录

### 阶段 4：UI 层
**目标**: 完整的用户界面

17. ⬜ 编写 ContentView.swift（主视图框架）
18. ⬜ 编写 SearchBarView.swift（搜索框）
19. ⬜ 编写 ClipListView.swift（列表容器）
20. ⬜ 编写 ClipCardView.swift（卡片组件）
21. ⬜ 编写 EmptyStateView.swift（空状态）
22. ⬜ 编写 DetailView.swift（详情预览）
23. ⬜ 编写 SettingsView.swift（设置页）
24. ⬜ 编译验证：UI 完整可用

### 阶段 5：集成联调
**目标**: 所有功能串联，编译通过，基本可用

25. ⬜ 将所有服务和 UI 串联
26. ⬜ 编译测试
27. ⬜ 功能验收测试

## 执行原则

- **每阶段末尾编译验证**，不跳步
- **每完成一个文件就检查语法**，不攒到最后
- **遇到编译错误立即修复**，不在错误基础上继续
- **分阶段 Git 提交**（如果有 Git）

## 验收标准

详见 [requirements.md](requirements.md) 中的功能需求 F1-F9。
