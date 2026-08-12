# 多机位合板自动化 - 完整文档

## 背景

用户使用 DaVinci Resolve 进行多机位视频合板 (Multi-cam Sync)。素材来源为摄影机 SD 卡直接拷贝的文件夹结构。

目标：输入一个日期文件夹路径 + XML 导出路径，自动完成合板并导出 FCP 7 XML 给 Premiere Pro 使用。

---

## 素材文件夹结构

```
/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0118/
├── 视频/
│   ├── A机/              ← 字母机位，合板 ✅
│   │   ├── M4ROOT/CLIP/  ← Sony 摄影机结构，CLIP 内含 .MP4 + .XML
│   │   ├── SONY/
│   │   └── private/
│   ├── B机/              ← 字母机位，合板 ✅
│   │   └── M4ROOT/CLIP/
│   ├── action/           ← 非字母机位，跳过 ⏭️
│   ├── pocket/           ← 非字母机位，跳过 ⏭️
│   └── 航拍/             ← 非字母机位，跳过 ⏭️
└── 音频/
    └── Sound_20260118A/  ← 递归查找所有 .WAV/.mp3
        ├── 01-18-26/     ← 录音机 WAV 文件
        └── Tentacle/     ← Tentacle 时间码同步器文件
```

### 关键规则
- **只处理字母命名的机位**：`A机`, `B机`, `C机`, `a`, `b`, `c` 等（正则: `^([a-zA-Z])机?$`）
- **跳过其他一切**：`action`, `pocket`, `航拍` 等，无论里面有没有 CLIP
- **子机位不区分**：`A机/卡1`, `A机/卡2` 都归入 Camera # = "a"
- **CLIP 文件夹**：递归查找每个机位下的 `CLIP` 文件夹
- **视频格式**：`.mp4`, `.mov`, `.mxf`, `.braw`, `.r3d`, `.avi`, `.mts`, `.m2t`, `.m2ts`, `.mkv`, `.webm`
- **音频格式**：`.wav`, `.mp3`（不区分大小写）

---

## 完整手动流程（达芬奇操作）

### 前置
打开 DaVinci Resolve → 新建工程（默认命名和位置）

### 第一阶段：导入素材并设置摄影机编号
1. 在日期文件夹的 `视频/` 下找到所有字母机位（A机/B机/C机...）
2. 在达芬奇媒体池创建以日期命名的文件夹（如 "0118"）
3. 逐个机位：
   - 找到该机位下的 CLIP 文件夹（递归查找）
   - 将 CLIP 中所有视频文件拖入达芬奇文件夹
   - 弹窗选择「更改」
   - 全选该机位素材 → 元数据中设置摄影机编号 = 对应字母（a/b/c，不区分子机位 a1/a2）

### 第二阶段：音频同步
4. 全选达芬奇文件夹内所有**视频**片段（音频暂不导入）
5. 右键 → 音频同步 → 从音频轨道中更新时间码

### 第三阶段：导入音频
6. 在原始日期文件夹下递归查找所有 `.wav` / `.mp3` 文件
7. 全部拖入同一达芬奇文件夹
8. 音频文件不设摄影机编号（达芬奇会自动清除录音设备的 Camera #）

### 第四阶段：创建多机位片段
9. 全选文件夹内所有素材（视频 + 音频）
10. 右键 → 使所选片段新建多机位片段
    - 帧率：与原视频素材一致
    - 角度命名方式：**元数据摄影机**
    - **取消**「将片段移动到原始片段文件夹」
    - **勾选**「检测来自相同摄影机的片段」
    - 检测方式：**元数据摄影机编号**
11. 点击「创建」

### 第五阶段：时间线操作 + 导出 XML
12. 选中新建的多机位片段 → 右键 → 在时间线上打开 → 进入剪辑页面
13. 复制剪辑线上所有内容（Cmd+A → Cmd+C）
14. 在媒体池中选中第一个音频文件 → 右键 → 使所选片段新建时间线
    - 时间线名称：原始文件夹名称（拍摄日期，如 "0118"）
    - 其他设置不变 → 创建
15. 删除新时间线上的所有内容 → Cmd+V 粘贴
16. 在媒体池中选中当前时间线 → 右键 → 时间线 → 导出 → AAF/XML/EDL...
    - 格式：**FCP 7 XML V5**
    - 输出：`.xml` 文件

---

## 自动化实现

### 脚本位置
`/Volumes/可事传媒/ai缓存/ai编程/multicam_sync/`

### 文件说明

| 文件 | 用途 | 状态 |
|------|------|------|
| `auto_sync.py` | **主脚本**（推荐使用） | ✅ |
| `final_sync.py` | 尝试全自动（含 API 时间线操作，不稳定） | ⚠️ |
| `generate_xml.py` | 尝试手写 XML（格式错误，已弃用） | ❌ |
| `export_multitrack.py` | 尝试分轨导出（时间码不完整） | ❌ |
| `python_get_resolve.py` | Resolve API 连接辅助 | ✅ |
| `run_multicam_sync.sh` | 旧版启动脚本 | ⚠️ |

### `auto_sync.py` 使用方式

```
# Phase 1: 导入视频 + Camera #，然后暂停等用户做音频同步
python3 auto_sync.py "/素材/日期文件夹" "/XML/导出目录"

# Phase 2 (--continue): 导入音频，然后暂停等用户创建多机位片段
python3 auto_sync.py --continue

# Phase 3 (--continue): 尝试自动完成时间线操作 + 导出
python3 auto_sync.py --continue
```

### 当前自动化程度

| 步骤 | 自动化 | 说明 |
|------|--------|------|
| 扫描文件夹 | ✅ 全自动 | 正则匹配机位 + 递归查找 CLIP |
| 创建工程 + 导入视频 | ✅ 全自动 | `ImportMedia` + `SetMetadata("Camera #", cam)` |
| 设置 Camera # | ✅ 全自动 | 关键：元数据键名是 `"Camera #"` (带 # 号) |
| 音频同步 | ✋ 手动 | Resolve API 不支持此操作 |
| 导入音频 + 清除 Camera # | ✅ 全自动 | 录音设备自带 Camera # 会被清除 |
| 创建多机位片段 | ✋ 手动 | Resolve API 不支持此操作 |
| 时间线操作 | ✋ 手动 | AppleScript 尝试过但不稳定 |
| 导出 FCP 7 XML | ✋ 手动 | API 可导出但需先有多机位时间线 |

### Resolve Python API 环境变量

```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```

前置条件：
- DaVinci Resolve 必须正在运行
- Python >= 3.6
- 环境变量需正确设置

---

## 达芬奇 API 关键发现

### 可用的 API
- `GetProjectManager().CreateProject(name)` / `LoadProject(name)`
- `GetMediaPool().AddSubFolder(parent, name)` / `SetCurrentFolder(folder)`
- `GetMediaPool().ImportMedia([file_paths])` - 导入素材
- `MediaPoolItem.SetMetadata("Camera #", value)` - **注意必须是 "Camera #"，不是 "Camera"**
- `MediaPoolItem.GetMetadata(key)` / `GetClipProperty()` - 读取元数据
- `GetMediaPool().CreateEmptyTimeline(name)` / `CreateTimelineFromClips(name, [clips])`
- `GetMediaPool().AppendToTimeline([clips])` - 追加片段到时间线
- `Timeline.Export(path, resolve.EXPORT_FCP_7_XML)` - 导出 FCP 7 XML
- `Timeline.SetStartTimecode(tc)` - 设置时间线起始时间码
- `Timeline.AddTrack(type)` / `DeleteTrack(type, index)`
- `Timeline.GetItemListInTrack(type, index)` / `DeleteClips([items])`

### 不可用的 API
- **无法创建多机位片段**：没有 `CreateMultiCamClip` 或类似函数
- **无法执行音频同步**：`AutoSyncAudio` 存在但行为与「从音频轨道中更新时间码」不同
- **无法模拟右键菜单操作**：上下文菜单只能通过 GUI 自动化

### AppleScript GUI 自动化
- 已获得辅助功能权限（`System Events` 可控制 Resolve）
- 达芬奇使用 Qt 框架，UI 元素可访问性差（多数元素名为 `missing value`）
- 菜单栏可访问：文件、编辑、片段、时间线、调色等
- 右键上下文菜单难以自动化
- `keystroke` 命令可用（模拟 Cmd+A/C/V 等快捷键）

### 其他尝试过但失败的方案
1. **手写 FCP 7 XML**：Premiere 打不开，格式要求严格
2. **Resolve API 直接分轨导出**：时间码对齐不正确
3. **Resolve API AppendToTimeline 的 recordFrame**：对音频片段无效
4. **全自动 AppleScript 流程**：菜单项不稳定，Qt UI 难以导航

---

## 示例数据

### 0118 项目
- 路径：`/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0118`
- A机：114 个 MP4（50fps, 3840x2160）
- B机：约 100 个 MP4
- 音频：17 个 WAV
- 导出：`/Volumes/可事传媒/2026/赋能者/后期组/02_Dit/04_XML/0802/0118.xml`

### 0119 项目
- 路径：`/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0119`
- A机：350 个 MP4
- B机：260 个 MP4
- 音频：27 个 WAV（含 2 个 Tentacle 时码器文件）

### 0120 项目
- 路径：`/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0120`
- A机：221 个 MP4（含 A1/A2 两个子卡）
- B机：276 个 MP4（含 B1/B2 两个子卡）
- 音频：32 个 WAV + LAVD/LAVC
- 跳过：action, pocket, 航拍

---

## 给接手 AI 的建议

1. **不要尝试手写 FCP 7 XML**：格式太复杂，Premiere 无法导入
2. **不要试图全自动 GUI 操作**：达芬奇 Qt UI 可访问性太差
3. **最佳方向**：接受「导入全自动 + 同步/多机位手动」的混合模式
4. **可能的突破口**：研究达芬奇的 Lua 脚本 API 是否有 Python API 未暴露的内部函数
5. **可能的突破口 2**：研究是否可以设置达芬奇键盘快捷键，然后用 `osascript keystroke` 触发
6. **如果达芬奇 Studio 版本有更多 API**：当前用户使用的是免费版还是 Studio 版待确认
