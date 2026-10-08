"""DaVinci Resolve 模块 1：工程创建、视频导入与 Camera # 设置。

该模块只处理字母机位的视频素材；不导入音频，也不执行音频同步或创建多机位片段。
可直接运行：

    python3 resolve/import_video.py /path/to/0118
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
from state.manager import (
    create_initial_state,
    load_state,
    mark_step_completed,
    save_state,
)
from utils.resolve_api import (
    ensure_connected,
    import_files,
)


IMPORT_BATCH_SIZE = 100


@dataclass(frozen=True)
class VideoImportResult:
    """模块 1 成功完成后的导入与校验结果。"""

    project_name: str
    folder_name: str
    expected_count: int
    imported_count: int
    existing_count: int
    metadata_updated_count: int
    timeline_fps: float


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
    """返回当前媒体池文件夹中按源文件路径索引的视频片段。"""
    clips_by_path: dict[str, Any] = {}
    for clip in folder.GetClipList() or []:
        path = _clip_file_path(clip)
        if path:
            clips_by_path[_normalise_path(path)] = clip
    return clips_by_path


def _get_or_create_date_folder(media_pool: Any, name: str) -> Any:
    """返回根目录中唯一的日期文件夹；仅不存在时才创建。

    Resolve 的 ``AddSubFolder`` 允许同名文件夹，因此不能以其返回值判断
    文件夹是否已存在。先遍历根目录能避免断点续跑时重复创建 Bin。
    """
    root = media_pool.GetRootFolder()
    existing = [
        folder for folder in (root.GetSubFolderList() or [])
        if folder.GetName() == name
    ]
    if len(existing) > 1:
        raise RuntimeError(
            f"媒体池根目录存在 {len(existing)} 个同名文件夹“{name}”。"
            "请先保留唯一正确的文件夹后再续跑。"
        )
    if existing:
        return existing[0]
    return media_pool.AddSubFolder(root, name)


def _update_camera_metadata(clips: list[Any], camera: str) -> int:
    """为片段写入正确的 Resolve ``Camera #`` 元数据并返回写入数。"""
    updated = 0
    for clip in clips:
        try:
            current = clip.GetMetadata("Camera #")
            if current != camera:
                if clip.SetMetadata("Camera #", camera) is not False:
                    updated += 1
        except Exception as exc:
            raise RuntimeError(f"无法为机位 {camera} 设置 Camera #: {exc}") from exc
    return updated


def _scan_snapshot(info: ScanResult) -> dict[str, Any]:
    """将扫描结果中与模块 1 相关的可 JSON 序列化字段保存进状态。"""
    return {
        "date": info["date"],
        "video_files": info["video_files"],
        "skipped": info["skipped"],
        "total_video_count": info["total_video_count"],
    }


def _load_or_create_state(source_dir: str, xml_export_dir: str) -> dict[str, Any]:
    """加载已存在的流水线状态；首次运行则创建它。"""
    state = load_state(source_dir)
    if state is None:
        state = create_initial_state(source_dir, xml_export_dir=xml_export_dir)
    elif state.get("source_dir") != source_dir:
        raise RuntimeError("状态文件中的 source_dir 与本次输入不一致，拒绝继续执行。")
    return state


def _normalise_fps(fps: float) -> tuple[float, str]:
    """校验并格式化传给 Resolve 的时间线帧率。"""
    value = float(fps)
    if value <= 0:
        raise ValueError(f"帧率必须大于 0，实际为 {fps!r}。")
    return value, f"{value:g}"


def _load_or_create_project_with_fps(resolve: Any, name: str, fps: float) -> Any:
    """创建工程时先固定帧率；既有工程只校验，绝不强行改写。"""
    target_fps, setting_value = _normalise_fps(fps)
    project_manager = resolve.GetProjectManager()
    project = project_manager.LoadProject(name)
    if project:
        actual = float(project.GetSetting("timelineFrameRate"))
        if actual != target_fps:
            raise RuntimeError(
                f"既有工程 {name} 的时间线帧率为 {actual:g}fps，"
                f"与本次要求的 {target_fps:g}fps 不一致。"
                "Resolve 在创建时间线后会锁定帧率，请使用匹配的工程或新建工程。"
            )
        return project

    project = project_manager.CreateProject(name)
    if not project:
        raise RuntimeError(f"无法创建 Resolve 工程：{name}")
    if project.SetSetting("timelineFrameRate", setting_value) is False:
        raise RuntimeError(f"无法将新工程 {name} 的时间线帧率设为 {setting_value}fps。")
    actual = float(project.GetSetting("timelineFrameRate"))
    if actual != target_fps:
        raise RuntimeError(
            f"新工程 {name} 的时间线帧率校验失败：实际 {actual:g}fps，"
            f"预期 {target_fps:g}fps。"
        )
    return project


def _mark_and_save(source_dir: str, state: dict[str, Any], step: str) -> None:
    """只在步骤成功后标记完成，保证中断后能安全续跑。"""
    mark_step_completed(state, step)
    save_state(source_dir, state)


def _expected_camera_paths(info: ScanResult) -> dict[str, str]:
    """返回 ``规范化路径 → 小写机位字母`` 映射。"""
    return {
        _normalise_path(path): camera
        for camera, paths in info["video_files"].items()
        for path in paths
    }


def _verify_import(folder: Any, expected_paths: dict[str, str]) -> int:
    """验证每个视频均已导入且 ``Camera #`` 与机位一致。"""
    clips_by_path = _folder_clips_by_path(folder)
    missing = sorted(set(expected_paths) - set(clips_by_path))
    if missing:
        raise RuntimeError(
            f"导入校验失败：缺少 {len(missing)} 个视频，例如 {missing[0]}"
        )

    incorrect_metadata: list[str] = []
    for path, camera in expected_paths.items():
        try:
            actual = clips_by_path[path].GetMetadata("Camera #")
        except Exception as exc:
            raise RuntimeError(f"无法读取 Camera #：{path}: {exc}") from exc
        if actual != camera:
            incorrect_metadata.append(path)
    if incorrect_metadata:
        raise RuntimeError(
            "Camera # 校验失败："
            f"{len(incorrect_metadata)} 个视频的摄影机编号不正确，例如 {incorrect_metadata[0]}"
        )
    return len(expected_paths)


def import_videos(
    source_dir: str,
    *,
    xml_export_dir: str = "",
    project_name: str = "",
    fps: float = 50.0,
    resolve: Any | None = None,
) -> VideoImportResult:
    """创建/加载日期工程，导入所有字母机位视频并设置 ``Camera #``。

    已在媒体池中的同源视频会被复用而非重复导入；无论是首次还是续跑，都会
    重新校正其 Camera #。成功后状态写入 ``<source_dir>/.pipeline_state.json``。
    """
    source_dir = os.path.abspath(source_dir)
    info = scan(source_dir)
    if not info["total_video_count"]:
        raise RuntimeError("没有找到可导入的视频文件。")

    state = _load_or_create_state(source_dir, xml_export_dir)
    state["scan_result"] = _scan_snapshot(info)
    _mark_and_save(source_dir, state, Step.SCANNING)

    resolve = resolve or ensure_connected()
    _mark_and_save(source_dir, state, Step.RESOLVE_CONNECT)

    project_name = project_name.strip() or info["date"]
    timeline_fps, _ = _normalise_fps(fps)
    project = _load_or_create_project_with_fps(resolve, project_name, timeline_fps)
    media_pool = project.GetMediaPool()
    folder = _get_or_create_date_folder(media_pool, info["date"])
    if not folder:
        raise RuntimeError(f"无法创建或获取媒体池文件夹: {info['date']}")
    media_pool.SetCurrentFolder(folder)

    state["resolve"]["project_name"] = project_name
    state["resolve"]["folder_name"] = info["date"]
    state["resolve"]["timeline_fps"] = timeline_fps
    _mark_and_save(source_dir, state, Step.RESOLVE_CREATE_PROJECT)

    expected_paths = _expected_camera_paths(info)
    clips_by_path = _folder_clips_by_path(folder)
    existing_paths = set(expected_paths) & set(clips_by_path)
    missing_by_camera: dict[str, list[str]] = {}
    for camera, paths in info["video_files"].items():
        missing_by_camera[camera] = [
            path for path in paths if _normalise_path(path) not in clips_by_path
        ]

    imported_count = 0
    for camera in sorted(missing_by_camera):
        paths = missing_by_camera[camera]
        for index in range(0, len(paths), IMPORT_BATCH_SIZE):
            batch = paths[index:index + IMPORT_BATCH_SIZE]
            imported = import_files(media_pool, batch)
            if len(imported) != len(batch):
                raise RuntimeError(
                    f"机位 {camera} 导入不完整：请求 {len(batch)} 个，"
                    f"Resolve 返回 {len(imported)} 个。"
                )
            imported_count += len(imported)

    # Refresh after importing, then correct both new and existing source clips.
    clips_by_path = _folder_clips_by_path(folder)
    metadata_updated_count = 0
    for camera in sorted(info["video_files"]):
        camera_clips = [
            clips_by_path[_normalise_path(path)]
            for path in info["video_files"][camera]
            if _normalise_path(path) in clips_by_path
        ]
        metadata_updated_count += _update_camera_metadata(camera_clips, camera)

    expected_count = _verify_import(folder, expected_paths)
    _mark_and_save(source_dir, state, Step.RESOLVE_IMPORT_VIDEO)

    return VideoImportResult(
        project_name=project_name,
        folder_name=info["date"],
        expected_count=expected_count,
        imported_count=imported_count,
        existing_count=len(existing_paths),
        metadata_updated_count=metadata_updated_count,
        timeline_fps=timeline_fps,
    )


def main() -> None:
    """模块 1 的命令行入口。"""
    parser = argparse.ArgumentParser(
        description="创建/加载 Resolve 工程，导入视频并设置 Camera #。"
    )
    parser.add_argument("source_dir", help="拍摄日期文件夹，例如 .../赞比亚/0118")
    parser.add_argument(
        "--xml-export-dir",
        default="",
        help="供后续模块使用的 XML 导出目录（模块 1 不会写入 XML）。",
    )
    parser.add_argument(
        "--project-name",
        default="",
        help="Resolve 工程名；未提供时使用日期文件夹名。",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=50.0,
        help="新建 Resolve 工程的时间线帧率，默认 50。既有工程必须与之匹配。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅扫描并输出视频清单，不连接 DaVinci Resolve。",
    )
    args = parser.parse_args()

    info = scan(os.path.abspath(args.source_dir))
    print(format_scan_summary(info))
    if args.dry_run:
        return

    result = import_videos(
        args.source_dir,
        xml_export_dir=args.xml_export_dir,
        project_name=args.project_name,
        fps=args.fps,
    )
    print(
        "✅ 模块 1 完成："
        f"工程 {result.project_name}，视频 {result.expected_count} 个；"
        f"时间线 {result.timeline_fps:g}fps；"
        f"本次新增 {result.imported_count} 个，复用 {result.existing_count} 个，"
        f"更新 Camera # {result.metadata_updated_count} 个。"
    )


if __name__ == "__main__":
    main()
