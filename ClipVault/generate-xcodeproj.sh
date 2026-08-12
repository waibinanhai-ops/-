#!/bin/bash
# ============================================================
# 为 ClipVault 创建 Xcode 项目
# 打开 Package.swift 后 Xcode 会自动创建 scheme
# 此脚本确保项目可在 Xcode 中正确构建和运行
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "📦 正在创建 Xcode 项目结构..."

# 1. 确认源文件都在正确位置
echo "  检查源文件..."
swift package describe 2>/dev/null | head -5

# 2. 为 SPM 项目创建 xcscheme（用于 Xcode 运行）
XCODEPROJ="$PROJECT_DIR/ClipVault.xcodeproj"
mkdir -p "$XCODEPROJ/xcshareddata/xcschemes"

# 3. 创建启动 scheme
cat > "$XCODEPROJ/xcshareddata/xcschemes/ClipVault.xcscheme" << 'XCODE'
<?xml version="1.0" encoding="UTF-8"?>
<Scheme
   LastUpgradeVersion = "1530"
   version = "1.7">
   <BuildAction
      parallelizeBuildables = "YES"
      buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry
            buildForTesting = "YES"
            buildForRunning = "YES"
            buildForProfiling = "YES"
            buildForArchiving = "YES"
            buildForAnalyzing = "YES">
            <BuildableReference
               BuildableIdentifier = "primary"
               BlueprintIdentifier = "ClipVault"
               BuildableName = "ClipVault"
               BlueprintName = "ClipVault"
               ReferencedContainer = "container:..">
            </BuildableReference>
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      shouldUseLaunchSchemeArgsEnv = "YES">
      <Testables>
      </Testables>
   </TestAction>
   <LaunchAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      launchStyle = "0"
      useCustomWorkingDirectory = "NO"
      ignoresPersistentStateOnLaunch = "NO"
      debugDocumentVersioning = "YES"
      debugServiceExtension = "internal"
      allowLocationSimulation = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
         <BuildableReference
            BuildableIdentifier = "primary"
            BlueprintIdentifier = "ClipVault"
            BuildableName = "ClipVault"
            BlueprintName = "ClipVault"
            ReferencedContainer = "container:..">
         </BuildableReference>
      </BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction
      buildConfiguration = "Release"
      shouldUseLaunchSchemeArgsEnv = "YES"
      savedToolIdentifier = ""
      useCustomWorkingDirectory = "NO"
      debugDocumentVersioning = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
         <BuildableReference
            BuildableIdentifier = "primary"
            BlueprintIdentifier = "ClipVault"
            BuildableName = "ClipVault"
            BlueprintName = "ClipVault"
            ReferencedContainer = "container:..">
         </BuildableReference>
      </BuildableProductRunnable>
   </ProfileAction>
   <AnalyzeAction
      buildConfiguration = "Debug">
   </AnalyzeAction>
   <ArchiveAction
      buildConfiguration = "Release"
      revealArchiveInOrganizer = "YES">
   </ArchiveAction>
</Scheme>
XCODE

echo "✅ Xcode 项目已创建"
echo ""
echo "📋 在 Xcode 中运行："
echo "   1. 双击 ClipVault.xcodeproj 或 open Package.swift"
echo "   2. 选择 Scheme: ClipVault"
echo "   3. 按 Cmd+R 运行"
echo "   4. 菜单栏会出现剪贴板图标"
echo ""
echo "💡 注意: 首次运行需要授予辅助功能权限"
echo "   系统设置 → 隐私与安全性 → 辅助功能"
