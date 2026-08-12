#!/bin/bash
# 多机位合板 - 一键启动脚本
# 用法: ./run_multicam_sync.sh <素材文件夹> <XML导出文件夹>

# DaVinci Resolve API 环境变量
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/multicam_sync.py" "$@"
