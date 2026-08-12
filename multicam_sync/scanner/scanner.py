"""
素材扫描器 — 从源文件夹提取机位、音频、其他素材信息
=====================================================
从 auto_sync.py 的 scan() 函数提取并扩展。
同时支持 DaVinci Resolve（仅字母机位）和 Premiere Pro（所有素材）的需求。
"""

import os
import re
from collections import defaultdict
from typing import TypedDict

from config import VIDEO_EXTS, AUDIO_EXTS, CAM_PATTERN_STR

CAM_PATTERN = re.compile(CAM_PATTERN_STR)


class ScanResult(TypedDict):
    date: str
    source_dir: str
    cameras: dict[str, list[str]]           # cam_letter → [folder_paths]
    video_files: dict[str, list[str]]       # cam_letter → [video_file_paths]
    audio_files: list[str]                  # all audio file paths
    skipped: list[str]                      # skipped folder names in 视频/
    non_letter_media: dict[str, list[str]]  # folder_name → [media_files] (action, pocket, 航拍...)
    total_video_count: int
    total_audio_count: int


def scan(source_dir: str) -> ScanResult:
    """
    扫描素材文件夹结构。

    参数:
        source_dir: 日期文件夹路径 (如 .../赞比亚/0118)

    返回:
        ScanResult 字典，包含 cameras, video_files, audio_files, non_letter_media 等
    """
    date = os.path.basename(source_dir.rstrip("/"))
    video_dir = os.path.join(source_dir, "视频")
    if not os.path.isdir(video_dir):
        raise SystemExit(f"视频目录不存在: {video_dir}")

    # ── 1. 扫描视频子目录 → 分类字母机位 / 非字母机位 ──
    cameras: dict[str, list[str]] = {}
    skipped: list[str] = []
    non_letter_dirs: dict[str, str] = {}  # folder_name → full_path

    for fn in sorted(os.listdir(video_dir)):
        fp = os.path.join(video_dir, fn)
        if not os.path.isdir(fp):
            continue
        m = CAM_PATTERN.match(fn)
        if m:
            cameras.setdefault(m.group(1).lower(), []).append(fp)
        else:
            skipped.append(fn)
            non_letter_dirs[fn] = fp

    if not cameras:
        raise SystemExit(f"未找到字母命名的机位文件夹 (如 A机/B机/C机)")

    # ── 2. 递归查找每个字母机位的 CLIP 文件夹 ──
    clip_dirs: dict[str, list[str]] = {}
    for cam, paths in cameras.items():
        dirs = []
        for p in paths:
            for r, ds, fs in os.walk(p):
                if os.path.basename(r) == "CLIP":
                    dirs.append(r)
        clip_dirs[cam] = dirs

    # ── 3. 提取 CLIP 中的视频文件 ──
    video_files: dict[str, list[str]] = defaultdict(list)
    total_video = 0
    for cam, dirs in clip_dirs.items():
        files = []
        for cd in dirs:
            for f in sorted(os.listdir(cd)):
                if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                    files.append(os.path.join(cd, f))
        video_files[cam] = files
        total_video += len(files)

    # ── 4. 递归查找所有音频文件 ──
    audio_files = []
    for r, ds, fs in os.walk(source_dir):
        for f in fs:
            if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                audio_files.append(os.path.join(r, f))
    audio_files.sort()

    # ── 5. 扫描非字母机位的媒体文件（供 Premiere Pro 使用）──
    non_letter_media: dict[str, list[str]] = {}
    for dir_name, dir_path in non_letter_dirs.items():
        media = []
        for r, ds, fs in os.walk(dir_path):
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
                    media.append(os.path.join(r, f))
        if media:
            non_letter_media[dir_name] = sorted(media)

    return {
        "date": date,
        "source_dir": source_dir,
        "cameras": cameras,
        "video_files": dict(video_files),
        "audio_files": audio_files,
        "skipped": skipped,
        "non_letter_media": non_letter_media,
        "total_video_count": total_video,
        "total_audio_count": len(audio_files),
    }


def format_scan_summary(info: ScanResult) -> str:
    """生成人类可读的扫描摘要。"""
    lines = [
        "=" * 60,
        f"📋 素材扫描: {info['date']}",
        f"   路径: {info['source_dir']}",
        "",
        "✂️  字母机位 (→ DaVinci + Premiere):",
    ]
    for cam in sorted(info["video_files"]):
        count = len(info["video_files"][cam])
        paths = info["cameras"].get(cam, [])
        path_str = ", ".join(os.path.basename(p) for p in paths)
        lines.append(f"   [{cam}] {count} 个视频  ({path_str})")

    lines.append(f"\n🔊 音频: {info['total_audio_count']} 个文件")
    lines.append(f"📹 视频总计: {info['total_video_count']} 个片段")

    if info.get("non_letter_media"):
        lines.append(f"\n📦 非字母机位 (→ 仅 Premiere):")
        for dir_name, media in sorted(info["non_letter_media"].items()):
            lines.append(f"   [{dir_name}] {len(media)} 个文件")

    if info.get("skipped"):
        lines.append(f"\n⏭️  跳过 (不匹配机位模式): {', '.join(sorted(info['skipped']))}")

    lines.append("=" * 60)
    return "\n".join(lines)
