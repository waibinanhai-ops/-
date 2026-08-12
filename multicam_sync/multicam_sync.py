#!/usr/bin/env python3
"""
多机位合板自动化脚本
========================
自动完成 DaVinci Resolve 中的素材导入和摄影机编号设置。
手动步骤（多机位创建 + XML 导出）提供清晰指引。

用法:
    python3 multicam_sync.py <素材文件夹路径> <XML导出路径>

示例:
    python3 multicam_sync.py \\
        "/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/0119" \\
        "/Volumes/可事传媒/2026/赋能者/后期组/02_Dit/04_XML/0802"

前置条件:
    - DaVinci Resolve 必须正在运行
    - Python >= 3.6
    - 环境变量已设置 (见 run_multicam_sync.sh)
"""

import os
import sys
import re

# ── Resolve API 导入 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

RESOLVE_API_PATH = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
if RESOLVE_API_PATH not in sys.path:
    sys.path.append(RESOLVE_API_PATH)

from python_get_resolve import GetResolve


# ── 配置 ──────────────────────────────────────────────────────────
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mxf', '.braw', '.r3d', '.avi',
                    '.mts', '.m2t', '.m2ts', '.mkv', '.webm'}
AUDIO_EXTENSIONS = {'.wav', '.mp3'}
CAMERA_PATTERN = re.compile(r'^([a-zA-Z])机?$')


# ── 文件系统扫描 ──────────────────────────────────────────────────

def scan_project(source_dir):
    """扫描素材目录，返回结构化的项目信息。"""
    date_name = os.path.basename(source_dir.rstrip('/'))
    video_dir = os.path.join(source_dir, "视频")

    if not os.path.isdir(video_dir):
        print(f"❌ 视频目录不存在: {video_dir}")
        return None

    cameras = {}
    skipped = []
    for folder_name in sorted(os.listdir(video_dir)):
        folder_path = os.path.join(video_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        match = CAMERA_PATTERN.match(folder_name)
        if match:
            camera_letter = match.group(1).lower()
            if camera_letter not in cameras:
                cameras[camera_letter] = []
            cameras[camera_letter].append(folder_path)
        else:
            skipped.append(folder_name)

    if not cameras:
        print("❌ 未找到任何字母命名的机位文件夹 (如 A机/B机/C机 等)")
        print(f"   视频目录内容: {os.listdir(video_dir)}")
        return None

    clip_folders = {}
    for cam_letter, cam_paths in cameras.items():
        clips = []
        for cam_path in cam_paths:
            for root, dirs, files in os.walk(cam_path):
                if os.path.basename(root) == "CLIP":
                    clips.append(root)
        clip_folders[cam_letter] = clips

    video_files = {}
    for cam_letter, clips in clip_folders.items():
        files = []
        for clip_folder in clips:
            for f in sorted(os.listdir(clip_folder)):
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    files.append(os.path.join(clip_folder, f))
        video_files[cam_letter] = files

    audio_files = []
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(root, f))

    return {
        "date_name": date_name,
        "video_dir": video_dir,
        "cameras": cameras,
        "clip_folders": clip_folders,
        "video_files": video_files,
        "audio_files": sorted(audio_files),
        "skipped": skipped,
    }


def print_scan_result(info):
    """打印扫描结果"""
    print(f"\n{'='*60}")
    print(f"📁 项目日期: {info['date_name']}")
    print(f"📂 视频目录: {info['video_dir']}")
    print(f"\n🎥 识别到的机位:")
    for cam_letter in sorted(info['cameras'].keys()):
        clip_count = len(info['clip_folders'].get(cam_letter, []))
        file_count = len(info['video_files'].get(cam_letter, []))
        print(f"  机位 [{cam_letter}]: {clip_count} 个 CLIP, {file_count} 个视频")
    if info['skipped']:
        print(f"\n⏭️  跳过的文件夹: {', '.join(info['skipped'])}")
    print(f"\n🎵 音频文件: {len(info['audio_files'])} 个")
    print(f"{'='*60}\n")


# ── DaVinci Resolve 操作 ──────────────────────────────────────────

def import_camera_clips(mediaPool, cam_letter, video_files):
    """导入一个机位的所有视频素材并设置摄影机编号。"""
    if not video_files:
        print(f"  ⚠️  机位 [{cam_letter}] 无视频文件，跳过")
        return []

    print(f"  📥 机位 [{cam_letter}]: 导入 {len(video_files)} 个文件...")
    imported = mediaPool.ImportMedia(video_files)
    if not imported:
        print(f"    ❌ 导入失败")
        return []

    camera_clips = []
    for clip in imported:
        if clip:
            # 关键：达芬奇中"摄影机编号"的元数据键名为 "Camera #"（带 # 和空格）
            clip.SetMetadata("Camera #", cam_letter)
            camera_clips.append(clip)

    print(f"    ✅ {len(camera_clips)} 个片段, 摄影机编号 = '{cam_letter}'")
    return camera_clips


def print_manual_steps(info, xml_export_dir):
    """打印需要手动完成的操作步骤。"""
    cam_list = ', '.join(sorted(info['cameras'].keys()))
    date_name = info['date_name']
    xml_path = os.path.join(xml_export_dir, f"{date_name}.xml")

    print(f"""
{'='*60}
⚠️  自动导入完成！以下步骤需要在达芬奇中手动操作：
{'='*60}

📋 步骤 1：音频同步
   在媒体池 "{date_name}" 文件夹中:
   - 全选所有视频片段 (Ctrl+A / Cmd+A)
   - 右键 → 音频同步 → 从音频轨道中更新时间码

📋 步骤 2：创建多机位片段
   在媒体池 "{date_name}" 文件夹中:
   - 全选所有片段 (视频 {info.get('total_video', '?')} 个 + 音频 {len(info['audio_files'])} 个)
   - 右键 → 使所选片段新建多机位片段
   - 帧率：与原视频一致
   - 角度命名方式：元数据摄影机
   - ❌ 取消「将片段移动到原始片段文件夹」
   - ✅ 勾选「检测来自相同摄影机的片段」
   - 检测方式：元数据摄影机编号
   - 点击「创建」

📋 步骤 3：导出 XML
   - 选中新建的多机位片段 → 右键 → 在时间线上打开
   - 复制剪辑线上所有内容 (Ctrl+A → Ctrl+C)
   - 在 master 中，选中第一个音频文件 → 右键 → 使所选片段新建时间线
     → 时间线名称: "{date_name}"，其他不变 → 创建
   - 删除新时间线上的所有内容 → 粘贴之前复制的内容
   - 在 master 中选中当前时间线 → 右键 → 时间线 → 导出 → AAF/XML/EDL...
   - 保存路径: {xml_export_dir}
   - 格式: FCP 7 XML V5

✅ 导出文件: {xml_path}
{'='*60}
""")


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source_dir = sys.argv[1]
    xml_export_dir = sys.argv[2]

    # ── Phase 0: 扫描文件系统 ──
    info = scan_project(source_dir)
    if not info:
        sys.exit(1)

    print_scan_result(info)

    total_video = sum(len(files) for files in info['video_files'].values())
    info['total_video'] = total_video

    if total_video == 0:
        print("❌ 没有找到视频文件")
        sys.exit(1)

    # ── Phase 1: 连接 DaVinci Resolve ──
    print("🔌 连接 DaVinci Resolve...")
    resolve = GetResolve()
    if not resolve:
        print("❌ 无法连接 DaVinci Resolve，请确保软件已打开")
        sys.exit(1)

    projectManager = resolve.GetProjectManager()

    # ── Phase 2: 创建/加载工程 ──
    print(f"📁 工程: {info['date_name']}")
    project = projectManager.CreateProject(info['date_name'])
    if not project:
        project = projectManager.LoadProject(info['date_name'])
        if not project:
            print(f"❌ 无法创建或加载工程 '{info['date_name']}'")
            sys.exit(1)
        print("  ✅ 已加载现有工程")
    else:
        print("  ✅ 已创建")

    mediaPool = project.GetMediaPool()
    rootFolder = mediaPool.GetRootFolder()

    # ── Phase 3: 创建媒体池文件夹 ──
    print(f"📂 媒体池文件夹: {info['date_name']}")
    dateFolder = mediaPool.AddSubFolder(rootFolder, info['date_name'])
    if not dateFolder:
        for sf in rootFolder.GetSubFolderList():
            if sf.GetName() == info['date_name']:
                dateFolder = sf
                break
    if not dateFolder:
        print("❌ 无法创建媒体池文件夹")
        sys.exit(1)

    mediaPool.SetCurrentFolder(dateFolder)

    # ── Phase 4: 逐个机位导入素材 ──
    print(f"\n── 导入视频素材 ──")
    for cam_letter in sorted(info['video_files'].keys()):
        import_camera_clips(mediaPool, cam_letter, info['video_files'][cam_letter])

    # ── Phase 5: 导入音频文件 ──
    if info['audio_files']:
        print(f"\n── 导入音频 ──")
        print(f"  📥 {len(info['audio_files'])} 个音频文件...")
        audio_clips = mediaPool.ImportMedia(info['audio_files'])
        audio_count = 0
        cleared_count = 0
        for c in (audio_clips or []):
            if c:
                audio_count += 1
                # 清除音频文件可能自带的设备 Camera # 元数据
                existing_cam = c.GetMetadata("Camera #")
                if existing_cam and existing_cam.strip():
                    c.SetMetadata("Camera #", "")
                    cleared_count += 1
        print(f"  ✅ {audio_count} 个音频 (不设摄影机编号)")
        if cleared_count > 0:
            print(f"  🧹 清除了 {cleared_count} 个音频文件的设备自带 Camera #")
    else:
        print(f"\n── 导入音频 ──")
        print(f"  ⚠️  未找到音频文件")

    # ── 完成自动部分，打印手动步骤 ──
    print(f"\n✅ 自动导入完成！")
    print(f"   机位: {len(info['cameras'])} 个 ({', '.join(sorted(info['cameras'].keys()))})")
    print(f"   视频: {total_video} 个 (摄影机编号已设置)")
    print(f"   音频: {len(info['audio_files'])} 个")

    print_manual_steps(info, xml_export_dir)


if __name__ == "__main__":
    main()
