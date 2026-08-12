"""
结构化日志 — 写入 dev-logs/ 目录
===============================
每行 JSON，按日期分文件，自动添加时间戳。
"""

import json
import os
import time
from datetime import datetime
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(SCRIPT_DIR, "dev-logs")


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def _log_file() -> str:
    """当前日期的日志文件路径。"""
    _ensure_log_dir()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"{date_str}.jsonl")


def log(level: str, message: str, **extra: Any):
    """写入一条结构化日志。"""
    entry = {
        "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "level": level.upper(),
        "message": message,
    }
    entry.update(extra)
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def info(message: str, **extra):
    log("INFO", message, **extra)


def warn(message: str, **extra):
    log("WARN", message, **extra)


def error(message: str, **extra):
    log("ERROR", message, **extra)


def step_start(step: str, **extra):
    log("STEP_START", step, step_name=step, **extra)


def step_done(step: str, duration_ms: int = 0, **extra):
    log("STEP_DONE", f"Completed: {step}", step_name=step, duration_ms=duration_ms, **extra)


def summary_report(data: dict):
    """写入流水线完成汇总。"""
    _ensure_log_dir()
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(LOG_DIR, f"{date_str}_summary.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            **data,
        }, f, ensure_ascii=False, indent=2)
