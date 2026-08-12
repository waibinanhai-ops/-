# Changelog

本文件记录「多机位合板」自动化项目的所有显著变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

提交格式：`type(scope): description [source]`

---

## [Unreleased]

### Added
- chore(admin): add project CLAUDE.md with commit workflow (`8494d88`)
- chore(admin): add CHANGELOG.md (`cea0948`)

---

## [0.1.0] — 2026-08-12

### Added

- **项目初始化** — 多机位合板流水线基础设施（`daba72d`）
- `multicam_sync/` — 核心同步模块
  - `scanner/` — 素材扫描与机位识别
  - `state/` — 流水线状态管理
  - `utils/` — 工具集（AppleScript、Resolve API、日志）
  - `resolve/` — 达芬奇（DaVinci Resolve）集成
  - `premiere/` — Premiere Pro 集成
  - `swift/` — Swift 工具链
  - `research/` — 研究脚本（AppleScript 菜单枚举等）
  - `archive/` — 归档
  - `dev-logs/` — 开发日志
- `ClipVault/` — 独立剪贴板管理工具（Swift）
