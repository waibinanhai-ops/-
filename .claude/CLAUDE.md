# 多机位合板自动化 — 项目指令

## 项目信息
- **仓库**：https://github.com/waibinanhai-ops/-.git
- **分支**：main
- **用途**：达芬奇 / Premiere Pro 多机位合板自动化

## 目录速查
| 路径 | 说明 |
|------|------|
| `multicam_sync/` | 核心同步模块 |
| `multicam_sync/scanner/` | 素材扫描与机位识别 |
| `multicam_sync/state/` | 流水线状态管理 |
| `multicam_sync/utils/` | 工具集（AppleScript、Resolve API、日志） |
| `multicam_sync/resolve/` | 达芬奇集成（⚠️ 目录名是 resolve，不是 davinci） |
| `multicam_sync/premiere/` | Premiere Pro 集成 |
| `multicam_sync/swift/` | Swift 工具 |
| `multicam_sync/research/` | 研究脚本 |
| `multicam_sync/dev-logs/` | 开发日志 |
| `ClipVault/` | 独立剪贴板管理工具（Swift） |

---

## 提交到 GitHub 工作流

### 触发条件
当用户说出以下任意短语时，**立即进入引导流程**（不要先执行 git 命令）：
- "提交到 GitHub" / "提交到 github" / "提交代码"
- "commit" / "commit 一下" / "帮我 commit"
- "push" / "推到 GitHub" / "推上去"
- "上传到 GitHub"

### 引导流程

**依次询问以下 4 个问题，每次只问一个，等用户回答后再问下一个：**

#### 第 1 问：变更类型
> 这次变更是什么类型？

选项：
- `feat` — 新功能
- `fix` — 修复 bug
- `refactor` — 重构（不改功能）
- `chore` — 维护 / 杂项
- `docs` — 文档

#### 第 2 问：影响模块
> 影响了哪个模块？

常用模块名：
- `scanner` — 素材扫描
- `state` — 状态管理
- `utils` — 工具函数
- `resolve` — 达芬奇集成
- `premiere` — Premiere Pro 集成
- `swift` — Swift 工具
- `ClipVault` — 剪贴板工具
- `admin` — 仓库维护

可输入多个，逗号分隔（如 `scanner, utils`）

#### 第 3 问：变更描述
> 用一句话描述这次改了什么？

- 中文，尽量简洁（≤50 字）
- 用动词开头（如「支持 BRAW 扫描」「修复断点续传 bug」）

#### 第 4 问：来源署名（可选）
> 这次代码是谁写的 / 谁报告的？

- 可选，输入 `@` 开头（如 `@zhangsan`）
- 跳过则不加来源标记

### 自动执行

收集完以上信息后，AI 按以下顺序自动执行：

```
1. 生成 commit message：{type}({scope}): {描述} [{来源}]
   示例：feat(scanner): 支持 BRAW 格式扫描 [@zhangsan]
         fix(state): 修复断点续传状态丢失
         chore(admin): 更新 CLAUDE.md 提交流程

2. 更新 CHANGELOG.md：
   - 在 ## [Unreleased] 段落下，按类型追加到对应的 ### Added / Fixed / Changed 小节
   - 格式：- {type}({scope}): {描述} ({commit_hash_短})
   
3. 提交：
   git add -A
   git commit -m "{生成的 message}"
   
4. 推送：
   git push origin main
   （Token 已存入系统钥匙串，推送时自动使用）
   
5. 汇报：
   - Commit hash（短）
   - 推送状态
   - 当前 CHANGELOG.md 的 Unreleased 条目数
```

### 注意
- 推送前执行 `git pull --rebase` 防止冲突
- 如果 push 被拒（非 fast-forward），先 rebase 再 push
- 不要把 token 打印到终端输出中
