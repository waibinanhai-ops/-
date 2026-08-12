#!/bin/bash
# ============================================================
# ClipVault 构建脚本
# 使用 Xcode 项目编译并创建 .app 捆绑包
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${1:-Debug}"  # Debug or Release

echo "🔨 构建 ClipVault ($CONFIG)..."

cd "$PROJECT_DIR"

xcodebuild \
    -project ClipVault.xcodeproj \
    -scheme ClipVault \
    -configuration "$CONFIG" \
    build 2>&1 | grep -E "^\*\*|error:|warning:|Build succeeded"

echo ""
echo "✅ 构建完成"
echo "   输出: ~/Library/Developer/Xcode/DerivedData/ClipVault-*/Build/Products/$CONFIG/ClipVault.app"
echo ""
echo "💡 在 Xcode 中打开: open ClipVault.xcodeproj"
echo "   然后按 Cmd+R 即可运行"
