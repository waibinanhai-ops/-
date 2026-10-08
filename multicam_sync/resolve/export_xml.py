"""DaVinci Resolve 模块 3：展开多机位源时间线并导出 FCP 7 XML。

Resolve 的 Python API 不能直接把多机位片段展开为普通时间线。本模块结合
Resolve 20 的“源时间线”界面完成展开：将多机位片段载入源时间线，复制其轨道，
再粘贴到同名的普通时间线，最后使用 Resolve 原生引擎导出 FCP 7 XML。

可直接运行：

    python3 resolve/export_xml.py /path/to/0118 /path/to/0118.xml
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable


if __package__ in (None, ""):
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

from config import Step
from scanner.scanner import ScanResult, scan
from state.manager import load_state, mark_step_completed, save_state
from utils.applescript import run as run_applescript
from utils.resolve_api import ensure_connected


RESOLVE_PROCESS = "Resolve"
OPEN_IN_TIMELINE_MENU = "在时间线上打开"


@dataclass(frozen=True)
class ExportResult:
    """模块 3 成功完成后的时间线与 XML 校验结果。"""

    timeline_name: str
    xml_path: str
    xml_size: int
    video_item_counts: list[int]
    audio_item_counts: list[int]


def _find_date_folder(media_pool: Any, date: str) -> Any:
    """返回根目录中唯一的日期媒体池文件夹。"""
    matches = [
        folder for folder in (media_pool.GetRootFolder().GetSubFolderList() or [])
        if folder.GetName() == date
    ]
    if len(matches) != 1:
        raise RuntimeError(f"媒体池根目录应有唯一的“{date}”文件夹，实际找到 {len(matches)} 个。")
    return matches[0]


def _find_multicam_clip(folder: Any, expected_name: str = "") -> Any:
    """从日期文件夹中定位用户创建的多机位片段。"""
    clips = folder.GetClipList() or []
    if expected_name:
        for clip in clips:
            if clip.GetName() == expected_name:
                return clip

    matches = []
    for clip in clips:
        properties = clip.GetClipProperty() or {}
        clip_type = str(properties.get("Type", "")).lower()
        if "多机位" in clip_type or "multicam" in clip_type:
            matches.append(clip)
    if len(matches) != 1:
        raise RuntimeError(f"应有唯一的多机位片段，实际找到 {len(matches)} 个。")
    return matches[0]


def _timeline_by_name(project: Any, name: str) -> Any | None:
    """从当前项目查找同名时间线。"""
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline and timeline.GetName() == name:
            return timeline
    return None


def expected_track_counts(info: ScanResult) -> tuple[list[int], list[int]]:
    """根据扫描结果计算展开后时间线应有的轨道片段数。

    每个机位有一条视频轨和一条机内音频轨；每个独立音频文件占一条音频轨。
    """
    video_counts = [len(info["video_files"][camera]) for camera in sorted(info["video_files"])]
    return video_counts, [*video_counts, *([1] * len(info["audio_files"]))]


def timeline_track_counts(timeline: Any) -> tuple[list[int], list[int]]:
    """读取时间线每条视频/音频轨中的片段数。"""
    video_counts = [
        len(timeline.GetItemListInTrack("video", index) or [])
        for index in range(1, timeline.GetTrackCount("video") + 1)
    ]
    audio_counts = [
        len(timeline.GetItemListInTrack("audio", index) or [])
        for index in range(1, timeline.GetTrackCount("audio") + 1)
    ]
    return video_counts, audio_counts


def remove_empty_video_tracks(timeline: Any) -> int:
    """移除源时间线展开时由纯音频片段生成的空视频轨。

    Resolve 在把多机位源时间线粘贴到普通时间线时，会为每条独立 WAV
    生成一条没有片段的 video track。它们不含任何素材，且会干扰 FCP 7
    XML 的轨道结构校验，因此只从后向前删除这些空轨。
    """
    removed = 0
    for index in range(timeline.GetTrackCount("video"), 0, -1):
        if timeline.GetItemListInTrack("video", index) or []:
            continue
        if timeline.DeleteTrack("video", index) is False:
            raise RuntimeError(f"无法删除空视频轨：V{index}。")
        removed += 1
    return removed


def validate_track_counts(
    actual_video: list[int],
    actual_audio: list[int],
    expected_video: list[int],
    expected_audio: list[int],
) -> None:
    """确保展开后的普通时间线没有丢失视频或音频轨。

    Resolve 会因独立音频的排列顺序而重排 audio tracks；顺序不影响 XML
    内容，所以音频按片段数的多重集合校验。视频轨的顺序仍须严格对应机位。
    """
    if actual_video != expected_video:
        raise RuntimeError(f"视频轨校验失败：实际 {actual_video}，预期 {expected_video}。")
    if sorted(actual_audio) != sorted(expected_audio):
        raise RuntimeError(
            f"音频轨校验失败：实际 {actual_audio}，预期 {expected_audio}（顺序不限）。"
        )


def _source_timeline_copy_script() -> str:
    """生成 Resolve 20 源时间线复制到当前时间线的 AppleScript。"""
    return f'''
tell application "System Events"
    tell process "{RESOLVE_PROCESS}"
        set frontmost to true
        -- 切到剪辑页 (Shift+4)
        key code 21 using shift down
        delay 1
        click menu item "{OPEN_IN_TIMELINE_MENU}" of menu 1 of menu bar item "片段" of menu bar 1
        delay 1
        -- 显示源时间线 (Option+Q)，源侧默认获得焦点。
        key code 12 using {{option down}}
        delay 1
        keystroke "a" using {{command down}}
        delay 0.3
        keystroke "c" using {{command down}}
        delay 0.5
        -- Q 在源时间线和目标时间线之间切换焦点。
        key code 12
        delay 0.5
        keystroke "v" using {{command down}}
    end tell
end tell
'''


def _validate_export_xml(
    xml_path: str,
    expected_video: list[int],
    expected_audio: list[int],
) -> None:
    """验证 Resolve 原生导出的 FCP 7 XML 版本与轨道结构。"""
    if not os.path.isfile(xml_path) or os.path.getsize(xml_path) == 0:
        raise RuntimeError("Resolve 未生成 XML 文件。")
    root = ET.parse(xml_path).getroot()
    if root.attrib.get("version") != "5":
        raise RuntimeError(f"XML 版本错误：{root.attrib.get('version')!r}，预期 '5'。")

    video_counts = [
        len(track.findall("clipitem"))
        for track in root.findall(".//sequence/media/video/track")
    ]
    audio_counts = [
        len(track.findall("clipitem"))
        for track in root.findall(".//sequence/media/audio/track")
    ]
    validate_track_counts(video_counts, audio_counts, expected_video, expected_audio)


def export_xml(
    source_dir: str,
    xml_path: str,
    *,
    overwrite: bool = False,
    resolve: Any | None = None,
    applescript_runner: Callable[[str], str] = run_applescript,
) -> ExportResult:
    """展开多机位源时间线，创建日期时间线并导出 FCP 7 XML。

    首次执行会通过 Resolve GUI 复制只读源时间线到普通时间线；中断后重跑时，
    若同名时间线已通过结构校验，会直接从该时间线导出，避免重复粘贴。
    """
    source_dir = os.path.abspath(source_dir)
    xml_path = os.path.abspath(xml_path)
    info = scan(source_dir)
    state = load_state(source_dir)
    if state is None or Step.RESOLVE_CREATE_MULTICAM not in state.get("completed_steps", []):
        raise RuntimeError("多机位片段尚未确认完成，不能导出 XML。")
    if os.path.exists(xml_path) and not overwrite:
        raise RuntimeError(f"XML 已存在，拒绝覆盖：{xml_path}")

    expected_video, expected_audio = expected_track_counts(info)
    resolve = resolve or ensure_connected()
    project_name = state.get("resolve", {}).get("project_name") or info["date"]
    project = resolve.GetProjectManager().LoadProject(project_name)
    if not project:
        raise RuntimeError(f"无法加载 Resolve 工程：{project_name}")
    media_pool = project.GetMediaPool()
    folder = _find_date_folder(media_pool, info["date"])

    timeline = _timeline_by_name(project, info["date"])
    if timeline:
        remove_empty_video_tracks(timeline)
        actual_video, actual_audio = timeline_track_counts(timeline)
        validate_track_counts(actual_video, actual_audio, expected_video, expected_audio)
        project.SetCurrentTimeline(timeline)
    else:
        multicam = _find_multicam_clip(
            folder,
            state.get("resolve", {}).get("multicam_clip_name", ""),
        )
        timeline = media_pool.CreateEmptyTimeline(info["date"])
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError(f"无法创建或切换到时间线：{info['date']}")
        if media_pool.SetSelectedClip(multicam) is False:
            raise RuntimeError("无法选中多机位片段。")
        output = applescript_runner(_source_timeline_copy_script())
        if output.startswith("ERROR:"):
            raise RuntimeError(f"Resolve GUI 自动化失败：{output}")
        time.sleep(3)
        remove_empty_video_tracks(timeline)
        actual_video, actual_audio = timeline_track_counts(timeline)
        validate_track_counts(actual_video, actual_audio, expected_video, expected_audio)

    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    if not timeline.Export(xml_path, resolve.EXPORT_FCP_7_XML):
        raise RuntimeError("Resolve FCP 7 XML 导出失败。")
    _validate_export_xml(xml_path, expected_video, expected_audio)

    state["resolve"]["timeline_name"] = info["date"]
    state["xml_export_path"] = xml_path
    mark_step_completed(state, Step.RESOLVE_EXPORT_XML)
    save_state(source_dir, state)
    return ExportResult(
        timeline_name=info["date"],
        xml_path=xml_path,
        xml_size=os.path.getsize(xml_path),
        video_item_counts=expected_video,
        audio_item_counts=expected_audio,
    )


def main() -> None:
    """模块 3 的命令行入口。"""
    parser = argparse.ArgumentParser(description="展开多机位时间线并导出 FCP 7 XML。")
    parser.add_argument("source_dir", help="拍摄日期文件夹，例如 .../赞比亚/0118")
    parser.add_argument("xml_path", help="FCP 7 XML 输出文件完整路径")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已有 XML")
    args = parser.parse_args()

    result = export_xml(args.source_dir, args.xml_path, overwrite=args.overwrite)
    print(
        "✅ 模块 3 完成："
        f"时间线 {result.timeline_name}，视频轨 {result.video_item_counts}，"
        f"音频轨 {result.audio_item_counts}，XML {result.xml_path} "
        f"({result.xml_size} bytes)。"
    )


if __name__ == "__main__":
    main()
