# Premiere 多机位合板自动化 — 交接说明

更新日期：2026-08-07（Asia/Shanghai）

## 当前目标

通过 Adobe Premiere Pro 2026 自动完成多机位素材的整理导入。当前处理对象：

- 源素材：`/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0118`
- Premiere 工程：`/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/合板/赞比亚合板.prproj`

## 已验证：步骤 1（新建工程）

- 实际模板是 `/Volumes/可事传媒/2026/赋能者/后期组/01_剪辑组/项目_集数_剪辑师_日期_2025_2.prproj`；用户最初写的 `_2025_1` 并不存在。
- 模板与当前 Premiere 版本兼容，无转换弹窗。
- 创建目标工程的可靠方式：复制模板到目标路径，再用 Premiere 打开目标。
- Premiere 的 AppleScript 式菜单点击不可靠；关闭模板的可靠方式是 **HID 级点击“文件 → 关闭所有项目”**，再仅打开目标工程。
- 已用窗口检测确认最后只加载 `赞比亚合板.prproj`。

## 当前状态：步骤 2（素材整理导入）

### 规则（用户已确认）

- 目标 Bin 层级：`素材/原始素材/0118/{a,b,sound,action,pocket}`。`sound` 与各机位同级，均在日期 Bin 内。
- 主机位 A/B/C 等：识别大小写不敏感的字母机位；A1/A2 等按数字顺序处理，但统一进入字母 Bin（如 `a`）。主机位仅从其 `M4ROOT/CLIP` 导入有效视频（MP4/MOV/MXF 等），忽略 XML、LRF、THM、`SUB` 代理。
- 音频：识别 `音频`、`sound` 等目录，递归导入 WAV/MP3 等到 `sound`。
- 其他类别：`action`、`pocket`、`航拍` 等不需要定位 CLIP，递归导入其中所有有效视频，到同名 Bin。
- 可采用 Premiere 媒体引用或复制后导入；以自动化的准确、稳定为准。源文件不能被删除或移动。

### 本次素材扫描结果

- A 机 `视频/A机/M4ROOT/CLIP`：114 段视频。
- B 机 `视频/B机/M4ROOT/CLIP`：100 段视频。
- `视频/pocket`：5 段视频。
- `视频/action`：9 段视频。
- `音频`：17 段音频。

### Premiere 界面操作进度

- 已创建日期 Bin `0118`，用户随后手动双击进入。
- `a` 已经由用户视觉确认命名正确。
- 已发送创建 `b`、`sound`、`action`、`pocket` 的指令；需要在继续前目视确认这 4 个 Bin 都存在且命名正确。
- 当前轮尚未执行任何素材导入操作。

## 下一个最小步骤

1. 请用户确认 `0118` 下的 5 个分类 Bin 完整正确。
2. 只测试 A 机导入：进入 A 机 CLIP 目录、全选、导入，关闭 XML 失败提示。
3. 在 `a` Bin 中核对是否为 114 段视频；数量一致后再处理 B 机。
4. 逐类处理 B、sound、pocket、action；每类完成并核对后才进行下一类。

## 辅助脚本（临时，不保证重启后仍在）

- `/tmp/step2_open.swift`：先点击项目面板空白处、Esc、HID `Ctrl+P`，打开导入窗口；已验证成功。
- `/tmp/check_pr_windows.swift`：查看 Premiere 窗口状态。
- `/tmp/premiere_close_all.swift`：HID 点击“关闭所有项目”。
- `/tmp/premiere_dont_save.swift`：寻找并点击“不保存”。
- `/tmp/premiere_create_bin_paste.swift`：用 `Cmd+B` 新建 Bin，再用剪贴板粘贴名称；此方式已由 `a` 验证有效。
- `/tmp/premiere_undo.swift`：撤销操作；仅应在确认目标是本自动化刚创建的空 Bin 时使用。

## 日志

- 开发日志目录：`/Volumes/可事传媒/ai缓存/ai编程/multicam_sync/dev-logs/`
- 当日日志：`2026-08-07.md`
- 已设置本 Codex 任务的每日 18:00 日志心跳自动化；其他 AI 不会自动继承它，需要自行建立等效自动化或持续维护日志。
