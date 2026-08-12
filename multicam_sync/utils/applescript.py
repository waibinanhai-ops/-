"""
AppleScript 工具封装
====================
统一的 AppleScript 执行和结果解析。
用于 DaVinci Resolve 菜单操作和 GUI 自动化。
"""

import subprocess
import time
from typing import Optional


def run(script: str, timeout: int = 30) -> str:
    """
    执行 AppleScript 并返回输出。

    参数:
        script: AppleScript 源代码
        timeout: 超时秒数

    返回:
        stdout 或 stderr 输出（去空白）
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        return output
    except subprocess.TimeoutExpired:
        return "ERROR: AppleScript timed out"
    except Exception as e:
        return f"ERROR: {e}"


def run_file(script_path: str, timeout: int = 30) -> str:
    """执行 AppleScript 文件。"""
    try:
        result = subprocess.run(
            ["osascript", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        return output
    except subprocess.TimeoutExpired:
        return "ERROR: AppleScript timed out"
    except Exception as e:
        return f"ERROR: {e}"


def click_menu(app_name: str, menu_path: list[str], delay: float = 0.3) -> str:
    """
    点击应用菜单栏的菜单项。

    参数:
        app_name: 进程名，如 "Resolve" 或 "Adobe Premiere Pro 2026"
        menu_path: 菜单路径，如 ["片段", "在时间线上打开"]
        delay: 每次点击后的延迟秒数

    返回:
        执行结果字符串

    示例:
        click_menu("Resolve", ["片段", "音频同步", "从音频轨道中更新时间码"])
    """
    if len(menu_path) < 2:
        return "ERROR: menu_path 至少需要 2 个元素 [菜单名, 菜单项, ...]"

    script_lines = [
        f'tell application "System Events"',
        f'    tell process "{app_name}"',
        f"        set frontmost to true",
        f"        delay {delay}",
    ]

    # Click the top-level menu
    script_lines.append(f'        click menu bar item "{menu_path[0]}" of menu bar 1')
    script_lines.append(f"        delay {delay}")

    # Click each submenu item
    for i, item in enumerate(menu_path[1:]):
        if i == 0:
            parent = f'menu "{menu_path[0]}" of menu bar 1'
        else:
            parent = f'menu "{menu_path[i]}" of menu item "{menu_path[i-1]}" of menu "{menu_path[0]}" of menu bar 1'

        # For the last item, click menu item
        if i == len(menu_path) - 2:
            script_lines.append(
                f'        click menu item "{item}" of {parent}'
            )
        else:
            # Intermediate items need submenu navigation (hover/click to open submenu)
            script_lines.append(
                f'        click menu item "{item}" of {parent}'
            )
        script_lines.append(f"        delay {delay}")

    script_lines.append("    end tell")
    script_lines.append("end tell")

    return run("\n".join(script_lines), timeout=10)


def keystroke(app_name: str, key: str, modifiers: Optional[list[str]] = None,
              delay: float = 0.3) -> str:
    """
    向指定应用发送按键。

    参数:
        app_name: 进程名
        key: 按键字符（支持 "a", "c", "v", "n", "return", "escape" 等）
        modifiers: 修饰键列表 ["command down", "shift down", "option down"]
        delay: 延迟

    返回:
        执行结果
    """
    mod_str = ""
    if modifiers:
        mod_str = " using {" + ", ".join(modifiers) + "}"

    # Map common keys to AppleScript keystroke representations
    key_map = {
        "return": "return",
        "escape": "escape",
        "tab": "tab",
        "space": "space",
        "delete": "delete",
        "left": "left",
        "right": "right",
        "up": "up",
        "down": "down",
        "home": "home",
        "end": "end",
    }
    apple_key = key_map.get(key.lower(), f'"{key}"')

    script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set frontmost to true
                delay {delay}
                keystroke {apple_key}{mod_str}
            end tell
        end tell
    '''
    return run(script, timeout=10)


def is_app_running(app_name: str) -> bool:
    """检查应用是否正在运行。"""
    result = run(f'''
        tell application "System Events"
            return exists process "{app_name}"
        end tell
    ''')
    return "true" in result.lower()


def get_app_pid(app_name: str) -> Optional[int]:
    """获取应用的 PID。"""
    result = run(f'''
        tell application "System Events"
            return unix id of process "{app_name}"
        end tell
    ''')
    try:
        return int(result)
    except (ValueError, TypeError):
        return None
