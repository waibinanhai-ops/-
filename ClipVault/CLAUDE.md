# CLAUDE.md — ClipVault 项目工作指引

## 项目概述

剪贴板管家 (ClipVault) 是一款 macOS 菜单栏历史剪贴板管理工具。详见 [docs/requirements.md](docs/requirements.md)。

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| 开发需求 | [docs/requirements.md](docs/requirements.md) | 功能和需求文档 |
| 技术规范 | [docs/tech-spec.md](docs/tech-spec.md) | 技术栈、架构、实现决策 |
| 设计规范 | [docs/design-spec.md](docs/design-spec.md) | 色彩、字体、布局、交互规范 |
| 执行计划 | [docs/execution-plan.md](docs/execution-plan.md) | 分阶段开发步骤和验收标准 |
| 架构说明 | [docs/architecture.md](docs/architecture.md) | 整体架构、数据流、模块职责 |
| 开发日志 | [dev-logs/](dev-logs/) | 每日开发记录 |

## 工作说明

### 开发节奏
- **一次只做一个阶段**，不要跨阶段同时进行
- **每个阶段结束时编译验证**，确保代码可编译
- **不要一口气写完所有代码**，每阶段完成后停下来汇报进度
- 每完成一个文件，检查是否可编译

### 代码规范
- 遵循项目现有的 Swift 代码风格
- 所有公开方法和类型添加文档注释
- 使用 `// MARK: -` 分隔代码段落
- 错误使用 `OSLog` 记录，不静默吞掉
- UI 组件使用 SwiftUI，系统交互使用 AppKit

### 文件修改前
- 先查阅 [docs/tech-spec.md](docs/tech-spec.md) 了解技术规范
- 先查阅 [docs/design-spec.md](docs/design-spec.md) 了解设计规范
- 先查阅 [docs/architecture.md](docs/architecture.md) 了解模块依赖关系

### 编译验证
```bash
cd /Volumes/可事传媒/ai缓存/ai编程/ClipVault
swift build 2>&1
```

### 每次工作结束后
- 更新 [dev-logs/](dev-logs/) 中的开发日志
- 更新 [docs/execution-plan.md](docs/execution-plan.md) 中的完成状态

### 需要用户决策时
- 使用 AskUserQuestion 工具，提供清晰的选项
- 不要替用户做会影响功能或体验的决定
- 选项配合简要说明

### 风险提醒
- 此项目需要 Accessibility 权限（全局快捷键）
- 非沙盒模式运行
- 剪贴板监听涉及用户隐私，所有数据仅本地存储
