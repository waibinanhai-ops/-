"""把 Resolve 多机位因同机位时间码重叠而排除的素材补到上层视频轨。

该模块不改动既有 A/B/C 合板轨，而是把每个机位缺失的完整源片段按其
Start TC 放入新的、更高的视频轨。适用于已启用“检测来自相同摄影机的片段”
且必须保留该设置的多机位流程。
"""

from __future__ import annotations

import argparse
from collections import Counter
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


if __package__ in (None, ""):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

from config import Step
from resolve.export_xml import expected_track_counts, timeline_track_counts
from scanner.scanner import scan
from state.manager import load_state, mark_step_completed, save_state
from utils.resolve_api import ensure_connected


def _path(value: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(value)))


def _clip_path(clip: Any) -> str:
    value = clip.GetClipProperty("File Path")
    if not value:
        value = (clip.GetClipProperty() or {}).get("File Path", "")
    return _path(value) if value else ""


def _frames(tc: str, fps: int) -> int:
    try:
        hours, minutes, seconds, frames = (int(part) for part in tc.split(":"))
    except ValueError as exc:
        raise RuntimeError(f"无法解析时间码：{tc!r}") from exc
    return ((hours * 3600 + minutes * 60 + seconds) * fps) + frames


def _duration_frames(clip: Any, fps: int) -> int:
    duration = str(clip.GetClipProperty("Duration") or "")
    frames = _frames(duration, fps)
    if frames <= 0:
        raise RuntimeError(f"片段时长无效：{clip.GetName()} ({duration!r})")
    return frames


def _date_folder(media_pool: Any, date: str) -> Any:
    folders = [
        folder for folder in (media_pool.GetRootFolder().GetSubFolderList() or [])
        if folder.GetName() == date
    ]
    if len(folders) != 1:
        raise RuntimeError(f"媒体池中应有唯一的 {date} 文件夹，实际 {len(folders)} 个。")
    return folders[0]


def _timeline(project: Any, name: str) -> Any:
    matches = [
        project.GetTimelineByIndex(index)
        for index in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(index)
        and project.GetTimelineByIndex(index).GetName() == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"工程中应有唯一的 {name} 时间线，实际 {len(matches)} 条。")
    return matches[0]


def _timeline_paths(timeline: Any, track_limit: int | None = None) -> set[str]:
    paths: set[str] = set()
    last_track = track_limit or timeline.GetTrackCount("video")
    for index in range(1, last_track + 1):
        for item in timeline.GetItemListInTrack("video", index) or []:
            media = item.GetMediaPoolItem()
            if media:
                path = _clip_path(media)
                if path:
                    paths.add(path)
    return paths


def _external_audio_track_multiplicity(clip: Any) -> int:
    """Return the number of timeline tracks Resolve creates for an audio clip.

    Stereo-or-fewer-channel WAV files occupy one audio track.  Resolve expands
    files with more than two channels into one mono track per channel when
    they are appended with ``mediaType=2``.  Counting the resulting slots is
    necessary for a complete FCP 7 XML validation.
    """
    value = (clip.GetClipProperty() or {}).get("Audio Ch", 2)
    try:
        channels = int(float(value))
    except (TypeError, ValueError):
        channels = 2
    return 1 if channels <= 2 else channels


def _external_audio_path_counts(timeline: Any, start_track: int) -> Counter[str]:
    """Count external-audio timeline items by their source media path."""
    paths: Counter[str] = Counter()
    for index in range(start_track, timeline.GetTrackCount("audio") + 1):
        for item in timeline.GetItemListInTrack("audio", index) or []:
            media = item.GetMediaPoolItem()
            if media:
                path = _clip_path(media)
                if path:
                    paths[path] += 1
    return paths


def _record_offset(timeline: Any, fps: int) -> int:
    """从一个完整源片段推导 Resolve 源时间线相对于 Start TC 的偏移。"""
    for index in range(1, timeline.GetTrackCount("video") + 1):
        for item in timeline.GetItemListInTrack("video", index) or []:
            if item.GetSourceStartFrame() != 0:
                continue
            media = item.GetMediaPoolItem()
            if not media:
                continue
            tc = str(media.GetClipProperty("Start TC") or "")
            if tc:
                return int(item.GetStart()) - _frames(tc, fps)
    raise RuntimeError("找不到可用于推导时间码落点的完整源片段。")


@dataclass(frozen=True)
class SupplementalClip:
    camera: str
    name: str
    source_path: str
    start_tc: str
    record_frame: int


@dataclass(frozen=True)
class SupplementResult:
    timeline_name: str
    supplemental_tracks: dict[str, int]
    missing: dict[str, list[SupplementalClip]]
    xml_path: str
    manifest_path: str


def _write_manifest(path: str, result: SupplementResult) -> None:
    lines = [
        f"{result.timeline_name} 重叠时间码补轨清单",
        "",
        "以下素材被 Resolve 多机位的“检测来自相同摄影机的片段”排除，",
        "已按 Start TC 放到独立的上层视频轨；底层 A/B/C 轨未改动。",
        "",
    ]
    for camera in sorted(result.missing):
        clips = result.missing[camera]
        track = result.supplemental_tracks.get(camera)
        lines.append(
            f"[{camera.upper()}] {len(clips)} 个"
            + (f"，补充视频轨 V{track}" if track else "，无须补轨")
        )
        for clip in clips:
            lines.append(f"- {clip.name} | Start TC {clip.start_tc} | {clip.source_path}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def supplement_and_export(
    source_dir: str,
    xml_path: str,
    *,
    overwrite: bool = False,
    resolve: Any | None = None,
) -> SupplementResult:
    """补齐重叠素材、验证全量视频，再导出 FCP 7 XML 与清单。"""
    source_dir = os.path.abspath(source_dir)
    xml_path = os.path.abspath(xml_path)
    if os.path.exists(xml_path) and not overwrite:
        raise RuntimeError(f"XML 已存在，拒绝覆盖：{xml_path}")

    info = scan(source_dir)
    state = load_state(source_dir)
    if not state:
        raise RuntimeError("找不到流水线断点状态。")
    project_name = state.get("resolve", {}).get("project_name") or info["date"]
    resolve = resolve or ensure_connected()
    project = resolve.GetProjectManager().LoadProject(project_name)
    if not project:
        raise RuntimeError(f"无法加载工程：{project_name}")
    timeline = _timeline(project, info["date"])
    fps = int(round(float(timeline.GetSetting("timelineFrameRate"))))
    if fps != 50:
        raise RuntimeError(f"时间线必须为 50fps，实际为 {fps}fps。")
    media_pool = project.GetMediaPool()
    folder = _date_folder(media_pool, info["date"])
    clips_by_path = {_clip_path(clip): clip for clip in folder.GetClipList() or []}
    expected = {
        camera: {_path(path) for path in paths}
        for camera, paths in info["video_files"].items()
    }
    base_track_count = len(expected)
    base_actual = _timeline_paths(timeline, base_track_count)
    actual = _timeline_paths(timeline)
    missing_paths = {
        camera: sorted(paths - base_actual)
        for camera, paths in expected.items()
    }
    if set().union(*missing_paths.values()) - set(clips_by_path):
        raise RuntimeError("媒体池中找不到需要补轨的源片段。")

    offset = _record_offset(timeline, fps)
    if not project.SetCurrentTimeline(timeline):
        raise RuntimeError("无法切换到目标时间线。")
    media_pool.SetCurrentFolder(folder)

    missing: dict[str, list[SupplementalClip]] = {}
    supplemental_tracks: dict[str, int] = {
        camera: index
        for camera in expected
        for index in range(base_track_count + 1, timeline.GetTrackCount("video") + 1)
        if timeline.GetTrackName("video", index) == f"补充-{camera.upper()}（时间码重叠）"
    }
    appended: list[Any] = []
    try:
        for camera in sorted(missing_paths):
            paths = missing_paths[camera]
            if not paths:
                missing[camera] = []
                continue
            sources = []
            for source_path in paths:
                clip = clips_by_path[source_path]
                tc = str(clip.GetClipProperty("Start TC") or "")
                sources.append((clip, tc, _frames(tc, fps) + offset))
            sources.sort(key=lambda source: (source[2], source[0].GetName()))
            paths_to_add = [source for source in sources if _clip_path(source[0]) not in actual]
            track_index = supplemental_tracks.get(camera)
            if paths_to_add and track_index is None:
                if not timeline.AddTrack("video"):
                    raise RuntimeError(f"无法添加 {camera.upper()} 补充视频轨。")
                track_index = timeline.GetTrackCount("video")
                supplemental_tracks[camera] = track_index
                timeline.SetTrackName("video", track_index, f"补充-{camera.upper()}（时间码重叠）")
            entries: list[SupplementalClip] = []
            for clip, tc, record_frame in sources:
                entries.append(SupplementalClip(
                    camera=camera,
                    name=clip.GetName(),
                    source_path=_clip_path(clip),
                    start_tc=tc,
                    record_frame=record_frame,
                ))
            for clip, tc, record_frame in paths_to_add:
                assert track_index is not None
                duration = _duration_frames(clip, fps)
                result = media_pool.AppendToTimeline([{
                    "mediaPoolItem": clip,
                    "startFrame": 0,
                    "endFrame": duration - 1,
                    "mediaType": 1,
                    "trackIndex": track_index,
                    "recordFrame": record_frame,
                }]) or []
                if len(result) != 1:
                    raise RuntimeError(f"无法补入片段：{clip.GetName()}")
                item = result[0]
                appended.append(item)
                if item.GetTrackTypeAndIndex() != ["video", track_index]:
                    raise RuntimeError(f"补轨落在错误轨道：{clip.GetName()}")
                if int(item.GetStart()) != record_frame:
                    raise RuntimeError(
                        f"补轨时间码落点错误：{clip.GetName()}，"
                        f"实际 {item.GetStart()}，预期 {record_frame}。"
                    )
            missing[camera] = entries
    except Exception:
        if appended:
            timeline.DeleteClips(appended, False)
        raise

    actual_paths = _timeline_paths(timeline)
    expected_paths = set().union(*expected.values())
    if actual_paths != expected_paths:
        raise RuntimeError(
            f"补轨后视频集合校验失败：实际 {len(actual_paths)}，预期 {len(expected_paths)}。"
        )
    video_counts, actual_audio = timeline_track_counts(timeline)
    expected_external_audio = Counter({
        _path(path): _external_audio_track_multiplicity(clips_by_path[_path(path)])
        for path in info["audio_files"]
    })
    expected_audio = [
        *video_counts[:base_track_count],
        *([1] * sum(expected_external_audio.values())),
    ]
    if sorted(actual_audio) != sorted(expected_audio):
        raise RuntimeError(f"音频轨校验失败：实际 {actual_audio}，预期 {expected_audio}。")
    actual_external_audio = _external_audio_path_counts(timeline, base_track_count + 1)
    if actual_external_audio != expected_external_audio:
        raise RuntimeError(
            "外录音频来源或声道展开校验失败："
            f"实际 {dict(actual_external_audio)}，预期 {dict(expected_external_audio)}。"
        )

    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    if not timeline.Export(xml_path, resolve.EXPORT_FCP_7_XML):
        raise RuntimeError("Resolve FCP 7 XML 导出失败。")
    root = ET.parse(xml_path).getroot()
    if root.attrib.get("version") != "5":
        raise RuntimeError(f"FCP XML 版本错误：{root.attrib.get('version')!r}")
    xml_video = [len(track.findall("clipitem")) for track in root.findall(".//sequence/media/video/track")]
    xml_audio = [len(track.findall("clipitem")) for track in root.findall(".//sequence/media/audio/track")]
    video_counts, _ = timeline_track_counts(timeline)
    if xml_video != video_counts or sorted(xml_audio) != sorted(expected_audio):
        raise RuntimeError("导出 XML 的轨道结构与 Resolve 时间线不一致。")

    manifest_path = os.path.join(os.path.dirname(xml_path), f"{info['date']}_重叠时间码补轨清单.txt")
    result = SupplementResult(
        timeline_name=info["date"],
        supplemental_tracks=supplemental_tracks,
        missing=missing,
        xml_path=xml_path,
        manifest_path=manifest_path,
    )
    _write_manifest(manifest_path, result)
    state.setdefault("resolve", {})["timeline_name"] = info["date"]
    state["resolve"]["supplemental_overlap_tracks"] = supplemental_tracks
    state["xml_export_path"] = xml_path
    state["overlap_manifest_path"] = manifest_path
    mark_step_completed(state, Step.RESOLVE_EXPORT_XML)
    save_state(source_dir, state)
    resolve.GetProjectManager().SaveProject()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="补充重叠时间码素材并导出 FCP 7 XML。")
    parser.add_argument("source_dir")
    parser.add_argument("xml_path")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = supplement_and_export(args.source_dir, args.xml_path, overwrite=args.overwrite)
    print(
        f"✅ 补轨完成：{result.timeline_name}，"
        + "，".join(f"{camera.upper()}→V{track}" for camera, track in result.supplemental_tracks.items())
        + f"；XML {result.xml_path}；清单 {result.manifest_path}"
    )


if __name__ == "__main__":
    main()
