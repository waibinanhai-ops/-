"""
流水线状态管理 — JSON 格式持久化
==================================
替代 pickle，人类可读，跨版本兼容。
支持断点续跑、步骤跳转、手动检查点。
"""

import json
import os
import time
from typing import Any, Optional

from config import STATE_DIR, STATE_FILENAME, Step, ALL_STEPS


def _state_path(source_dir: str) -> str:
    """状态文件路径：直接放在素材文件夹内，便于发现。"""
    return os.path.join(source_dir, ".pipeline_state.json")


def _ensure_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def create_initial_state(
    source_dir: str,
    xml_export_dir: str = "",
    pr_template_path: str = "",
    pr_project_path: str = "",
) -> dict:
    """创建初始状态字典。"""
    return {
        "pipeline_version": "1.0",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "current_step": None,
        "completed_steps": [],
        "source_dir": source_dir,
        "date_name": os.path.basename(source_dir.rstrip("/")),
        "xml_export_dir": xml_export_dir,
        "xml_export_path": "",
        "premiere": {
            "enabled": bool(pr_template_path),
            "template_path": pr_template_path,
            "project_path": pr_project_path,
            "app_name": "",
            "pid": 0,
            "bins_created": [],
            "import_completed": [],
        },
        "resolve": {
            "project_name": "",
            "folder_name": "",
            "multicam_clip_name": "",
            "timeline_name": "",
        },
        "scan_result": {},
        "errors": [],
        "warnings": [],
    }


def save_state(source_dir: str, state: dict) -> str:
    """保存状态到素材文件夹内。"""
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path = _state_path(source_dir)
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return path


def load_state(source_dir: str) -> Optional[dict]:
    """读取状态文件。如果不存在返回 None。"""
    path = _state_path(source_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_state(source_dir: str) -> bool:
    """删除状态文件（重置流水线）。"""
    path = _state_path(source_dir)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def mark_step_completed(state: dict, step: str) -> dict:
    """标记步骤完成，移动到下一步。"""
    if step not in state["completed_steps"]:
        state["completed_steps"].append(step)
    current_idx = ALL_STEPS.index(step) if step in ALL_STEPS else -1
    if current_idx >= 0 and current_idx + 1 < len(ALL_STEPS):
        state["current_step"] = ALL_STEPS[current_idx + 1]
    return state


def is_step_completed(state: dict, step: str) -> bool:
    """检查步骤是否已完成。"""
    return step in state.get("completed_steps", [])


def add_error(state: dict, error: str) -> dict:
    state["errors"].append({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message": error,
    })
    return state


def add_warning(state: dict, warning: str) -> dict:
    state["warnings"].append({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message": warning,
    })
    return state


def get_resume_step(state: dict) -> Optional[str]:
    """获取应该恢复的步骤。返回 None 如果已完成。"""
    if state.get("current_step") == Step.COMPLETE:
        return None
    return state.get("current_step")
