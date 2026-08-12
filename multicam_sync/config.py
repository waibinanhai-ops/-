"""
统一多机位合板 Pipeline — 配置常量
=====================================
所有项目路径、环境变量、应用名等集中管理。
CLI 参数和环墧变量可覆盖默认值。
"""

import os
import sys

# ── DaVinci Resolve ──────────────────────────────────────────
RESOLVE_SCRIPT_API = os.environ.get(
    "RESOLVE_SCRIPT_API",
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
)
RESOLVE_SCRIPT_LIB = os.environ.get(
    "RESOLVE_SCRIPT_LIB",
    "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
)
RESOLVE_MODULES_PATH = os.path.join(RESOLVE_SCRIPT_API, "Modules")

# ── Premiere Pro ─────────────────────────────────────────────
PREMIERE_APP_SEARCH_DIR = "/Applications"
PREMIERE_APP_PATTERN = "Adobe Premiere Pro"

# Template and default paths (can be overridden via CLI)
DEFAULT_TEMPLATE_PATH = "/Volumes/可事传媒/2026/赋能者/后期组/01_剪辑组/项目_集数_剪辑师_日期_2025_2.prproj"
DEFAULT_PROJECT_EXPORT_DIR = "/Volumes/可事传媒/2026/赋能者/素材/原始素材/非洲/赞比亚/合板"
DEFAULT_XML_EXPORT_DIR = "/Volumes/可事传媒/2026/赋能者/后期组/02_Dit/04_XML"

# ── File type constants ──────────────────────────────────────
VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".braw", ".r3d", ".avi", ".mts", ".m2t", ".m2ts", ".mkv", ".webm"}
AUDIO_EXTS = {".wav", ".mp3"}
CAM_PATTERN_STR = r"^([a-zA-Z])机?$"

# ── State file ───────────────────────────────────────────────
STATE_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MultiCamPipeline")
STATE_FILENAME = "pipeline_state.json"

# ── Media pool bin structure (Premiere Pro) ──────────────────
PREMIERE_BIN_ROOT = ["素材", "原始素材"]  # Parent bins for date bin
PREMIERE_BIN_CATEGORIES = {
    "a": "字母机位 A 机",
    "b": "字母机位 B 机",
    "c": "字母机位 C 机",
    "sound": "音频",
    "action": "运动相机",
    "pocket": "口袋相机",
}
# Non-letter camera folders to import in Premiere (skipped by DaVinci)
PREMIERE_NON_LETTER_CATEGORIES = ["action", "pocket", "航拍"]

# ── Pipeline steps ───────────────────────────────────────────
class Step:
    """Pipeline step identifiers."""
    SCANNING = "SCANNING"
    RESOLVE_CONNECT = "RESOLVE_CONNECT"
    RESOLVE_CREATE_PROJECT = "RESOLVE_CREATE_PROJECT"
    RESOLVE_IMPORT_VIDEO = "RESOLVE_IMPORT_VIDEO"
    RESOLVE_AUDIO_SYNC = "RESOLVE_AUDIO_SYNC"
    RESOLVE_IMPORT_AUDIO = "RESOLVE_IMPORT_AUDIO"
    RESOLVE_CREATE_MULTICAM = "RESOLVE_CREATE_MULTICAM"
    RESOLVE_EXPORT_XML = "RESOLVE_EXPORT_XML"
    PREMIERE_CONNECT = "PREMIERE_CONNECT"
    PREMIERE_CREATE_PROJECT = "PREMIERE_CREATE_PROJECT"
    PREMIERE_CREATE_BINS = "PREMIERE_CREATE_BINS"
    PREMIERE_IMPORT_MEDIA = "PREMIERE_IMPORT_MEDIA"
    PREMIERE_IMPORT_XML = "PREMIERE_IMPORT_XML"
    COMPLETE = "COMPLETE"

# Steps that require manual user confirmation
MANUAL_CHECKPOINTS = {
    Step.RESOLVE_AUDIO_SYNC,
    Step.RESOLVE_CREATE_MULTICAM,
}

# Steps in execution order
ALL_STEPS = [
    Step.SCANNING,
    Step.RESOLVE_CONNECT,
    Step.RESOLVE_CREATE_PROJECT,
    Step.RESOLVE_IMPORT_VIDEO,
    Step.RESOLVE_AUDIO_SYNC,
    Step.RESOLVE_IMPORT_AUDIO,
    Step.RESOLVE_CREATE_MULTICAM,
    Step.RESOLVE_EXPORT_XML,
    Step.PREMIERE_CONNECT,
    Step.PREMIERE_CREATE_PROJECT,
    Step.PREMIERE_CREATE_BINS,
    Step.PREMIERE_IMPORT_MEDIA,
    Step.PREMIERE_IMPORT_XML,
    Step.COMPLETE,
]
