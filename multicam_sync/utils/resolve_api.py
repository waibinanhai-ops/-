"""
Resolve API 连接封装
====================
封装 python_get_resolve.py 的 GetResolve()，
提供统一的连接、项目管理、媒体池操作接口。
"""

import os
import sys
from typing import Any, Optional

# Ensure Resolve API modules are on path
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")


def get_resolve() -> Optional[Any]:
    """
    获取 Resolve API 实例。
    返回 None 表示达芬奇未运行或 API 不可用。
    """
    try:
        from python_get_resolve import GetResolve
        return GetResolve()
    except ImportError as e:
        print(f"⚠️  无法导入 python_get_resolve: {e}")
        return None
    except Exception as e:
        print(f"⚠️  Resolve API 连接失败: {e}")
        return None


def ensure_connected() -> Any:
    """确保已连接达芬奇，否则抛出 SystemExit。"""
    resolve = get_resolve()
    if not resolve:
        raise SystemExit("❌ 达芬奇未运行或 API 不可用。请先打开 DaVinci Resolve。")
    return resolve


def get_or_create_project(resolve: Any, name: str) -> Any:
    """获取或创建达芬奇工程。"""
    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(name)
    if not proj:
        proj = pm.CreateProject(name)
    if not proj:
        raise SystemExit(f"无法创建/加载工程: {name}")
    return proj


def get_or_create_folder(mp: Any, name: str) -> Any:
    """在媒体池根目录获取或创建子文件夹。"""
    root = mp.GetRootFolder()
    folder = mp.AddSubFolder(root, name)
    if not folder:
        for sf in root.GetSubFolderList():
            if sf.GetName() == name:
                folder = sf
                break
    return folder


def import_files(mp: Any, file_paths: list[str]) -> list:
    """导入文件到当前媒体池文件夹。返回导入的 MediaPoolItem 列表。"""
    if not file_paths:
        return []
    imported = mp.ImportMedia(file_paths)
    if imported:
        return [c for c in imported if c]
    return []


def set_clip_metadata(clips: list, key: str, value: str) -> int:
    """批量设置片段元数据。返回成功设置的片段数。"""
    count = 0
    for clip in clips:
        try:
            if clip:
                clip.SetMetadata(key, value)
                count += 1
        except Exception:
            pass
    return count


def get_clip_list_in_folder(mp: Any, folder) -> list:
    """获取文件夹中所有片段。"""
    try:
        return folder.GetClipList() or []
    except Exception:
        return []
