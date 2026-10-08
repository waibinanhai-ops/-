"""DaVinci Resolve 模块 2：导入外部音频。

在用户完成“从音频轨道更新时间码”后运行。本模块把日期目录下递归找到的
WAV/MP3 导入同一媒体池文件夹，并清空每个音频片段的 ``Camera #``。

可直接运行：

    python3 resolve/import_audio.py /path/to/0118 --confirm-audio-sync
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any


if __package__ in (None, ""):
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

from config import Step
from scanner.scanner import ScanResult, format_scan_summary, scan
from state.manager import load_state, mark_step_completed, save_state
from utils.resolve_api import ensure_connected, import_files


IMPORT_BATCH_SIZE = 100


@dataclass(frozen=True)
class AudioImportResult:
    """模块 2 成功完成后的音频导入与校验结果。"""

    project_name: str
    folder_name: str
    expected_count: int
    imported_count: int
    existing_count: int
    cleared_camera_count: int


def _normalise_path(path: str) -> str:
    """将媒体文件路径规范化，供断点续跑时可靠比较。"""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _clip_file_path(clip: Any) -> str:
    """尽量从 Resolve MediaPoolItem 读取原始媒体路径。"""
    try:
        path = clip.GetClipProperty("File Path")
        if isinstance(path, str) and path:
            return path
    except Exception:
        pass

    try:
        properties = clip.GetClipProperty()
        if isinstance(properties, dict):
            path = properties.get("File Path", "")
            if isinstance(path, str):
                return path
    except Exception:
        pass
    return ""


def _folder_clips_by_path(folder: Any) -> dict[str, Any]:
    """返回当前媒体池文件夹中按源文件路径索引的所有片段。"""
    clips_by_path: dict[str, Any] = {}
    for clip in folder.GetClipList() or []:
        path = _clip_file_path(clip)
        if path:
            clips_by_path[_normalise_path(path)] = clip
    return clips_by_path


def _get_date_folder(media_pool: Any, name: str) -> Any:
    """查找唯一的日期文件夹；重复或不存在均拒绝继续。"""
    root = media_pool.GetRootFolder()
    matches = [
        folder for folder in (root.GetSubFolderList() or [])
        if folder.GetName() == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"媒体池根目录应有唯一的“{name}”文件夹，实际找到 {len(matches)} 个。"
        )
    return matches[0]


def _load_state_for_audio(source_dir: str) -> dict[str, Any]:
    """加载并校验模块 1 已创建的断点状态。"""
    state = load_state(source_dir)
    if state is None:
        raise RuntimeError("找不到断点状态。请先完成模块 1 的视频导入。")
    if state.get("source_dir") != source_dir:
        raise RuntimeError("状态文件中的 source_dir 与本次输入不一致，拒绝继续执行。")
    if Step.RESOLVE_IMPORT_VIDEO not in state.get("completed_steps", []):
        raise RuntimeError("视频导入尚未完成，不能导入音频。")
    return state


def _clear_camera_metadata(clips: list[Any]) -> int:
    """清空音频片段可能自带的 ``Camera #``，返回实际清空数。"""
    cleared = 0
    for clip in clips:
        try:
            camera = clip.GetMetadata("Camera #")
            if camera:
                if clip.SetMetadata("Camera #", "") is False:
                    raise RuntimeError("Resolve 拒绝清空 Camera #")
                cleared += 1
        except Exception as exc:
            raise RuntimeError(f"无法清空音频 Camera #: {exc}") from exc
    return cleared


def _verify_import(folder: Any, expected_paths: set[str]) -> int:
    """验证音频均已导入且不携带 ``Camera #``。"""
    clips_by_path = _folder_clips_by_path(folder)
    missing = sorted(expected_paths - set(clips_by_path))
    if missing:
        raise RuntimeError(
            f"音频导入校验失败：缺少 {len(missing)} 个文件，例如 {missing[0]}"
        )

    with_camera: list[str] = []
    for path in expected_paths:
        try:
            camera = clips_by_path[path].GetMetadata("Camera #")
        except Exception as exc:
            raise RuntimeError(f"无法读取音频 Camera #：{path}: {exc}") from exc
        if camera:
            with_camera.append(path)
    if with_camera:
        raise RuntimeError(
            f"音频 Camera # 校验失败：{len(with_camera)} 个仍有值，例如 {with_camera[0]}"
        )
    return len(expected_paths)


def import_audio(
    source_dir: str,
    *,
    audio_sync_confirmed: bool,
    resolve: Any | None = None,
) -> AudioImportResult:
    """导入日期目录中的全部音频，清空 Camera # 并推进到多机位创建步骤。

    ``audio_sync_confirmed`` 必须由调用方显式设为 ``True``，防止在人工时间码
    同步完成前误导入音频。已导入的相同源文件会被复用，支持安全续跑。
    """
    if not audio_sync_confirmed:
        raise RuntimeError("请先完成音频同步，并显式确认后再导入音频。")

    source_dir = os.path.abspath(source_dir)
    info: ScanResult = scan(source_dir)
    state = _load_state_for_audio(source_dir)
    state["scan_result"] = {
        **state.get("scan_result", {}),
        "audio_files": info["audio_files"],
        "total_audio_count": info["total_audio_count"],
    }
    mark_step_completed(state, Step.RESOLVE_AUDIO_SYNC)
    save_state(source_dir, state)

    resolve = resolve or ensure_connected()
    project_manager = resolve.GetProjectManager()
    project_name = state.get("resolve", {}).get("project_name") or info["date"]
    project = project_manager.LoadProject(project_name)
    if not project:
        raise RuntimeError(f"无法加载模块 1 创建的 Resolve 工程: {project_name}")
    media_pool = project.GetMediaPool()
    folder = _get_date_folder(media_pool, info["date"])
    media_pool.SetCurrentFolder(folder)

    expected_paths = {_normalise_path(path) for path in info["audio_files"]}
    clips_by_path = _folder_clips_by_path(folder)
    existing_paths = expected_paths & set(clips_by_path)
    missing_paths = [
        path for path in info["audio_files"]
        if _normalise_path(path) not in clips_by_path
    ]

    imported_count = 0
    for index in range(0, len(missing_paths), IMPORT_BATCH_SIZE):
        batch = missing_paths[index:index + IMPORT_BATCH_SIZE]
        imported = import_files(media_pool, batch)
        if len(imported) != len(batch):
            raise RuntimeError(
                f"音频导入不完整：请求 {len(batch)} 个，Resolve 返回 {len(imported)} 个。"
            )
        imported_count += len(imported)

    clips_by_path = _folder_clips_by_path(folder)
    expected_clips = [clips_by_path[path] for path in expected_paths]
    cleared_camera_count = _clear_camera_metadata(expected_clips)
    expected_count = _verify_import(folder, expected_paths)

    mark_step_completed(state, Step.RESOLVE_IMPORT_AUDIO)
    save_state(source_dir, state)
    return AudioImportResult(
        project_name=project_name,
        folder_name=info["date"],
        expected_count=expected_count,
        imported_count=imported_count,
        existing_count=len(existing_paths),
        cleared_camera_count=cleared_camera_count,
    )


def main() -> None:
    """模块 2 的命令行入口。"""
    parser = argparse.ArgumentParser(
        description="导入 Resolve 外部音频并清空 Camera #。"
    )
    parser.add_argument("source_dir", help="拍摄日期文件夹，例如 .../赞比亚/0118")
    parser.add_argument(
        "--confirm-audio-sync",
        action="store_true",
        help="确认已完成“从音频轨道中更新时间码”。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅扫描并输出音频清单，不连接 DaVinci Resolve。",
    )
    args = parser.parse_args()

    info = scan(os.path.abspath(args.source_dir))
    print(format_scan_summary(info))
    if args.dry_run:
        return

    result = import_audio(
        args.source_dir,
        audio_sync_confirmed=args.confirm_audio_sync,
    )
    print(
        "✅ 模块 2 完成："
        f"工程 {result.project_name}，音频 {result.expected_count} 个；"
        f"本次新增 {result.imported_count} 个，复用 {result.existing_count} 个，"
        f"清空 Camera # {result.cleared_camera_count} 个。"
    )


if __name__ == "__main__":
    main()
