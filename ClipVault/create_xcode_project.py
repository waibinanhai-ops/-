#!/usr/bin/env python3
"""为 ClipVault 生成完整的 Xcode 项目 (.xcodeproj/project.pbxproj)"""

import os, uuid, hashlib, sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(PROJECT_DIR, "Sources", "ClipVault")
XCODEPROJ = os.path.join(PROJECT_DIR, "ClipVault.xcodeproj")
PBXPROJ = os.path.join(XCODEPROJ, "project.pbxproj")
INFOPLIST = os.path.join(PROJECT_DIR, "Info.plist")

PRODUCT_NAME = "ClipVault"
BUNDLE_ID = "com.clipvault.app"
DEPLOYMENT_TARGET = "14.0"

def gen_id(seed="", length=24):
    """生成 pbxproj 风格的 24 位十六进制 ID"""
    h = hashlib.md5(f"{seed}{uuid.uuid4()}".encode()).hexdigest().upper()
    return h[:length]

def collect_sources(base_dir):
    """收集所有 Swift 源文件"""
    sources = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d != "Resources"]
        for f in sorted(files):
            if f.startswith("._"):
                continue
            if f.endswith(".swift"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, base_dir)
                sources.append((f, rel, full))
    return sources

def collect_groups(base_dir):
    """收集目录结构用于创建 PBXGroup"""
    groups = {}
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d != "Resources"]
        rel = os.path.relpath(root, base_dir)
        if rel == ".":
            continue
        groups[rel] = sorted(dirs)
    return groups

def pbx_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def write_pbxproj():
    sources = collect_sources(SOURCES_DIR)
    groups = collect_groups(SOURCES_DIR)

    # 预先创建所有 ID
    ids = {}
    def id_for(key):
        if key not in ids:
            ids[key] = gen_id(key)
        return ids[key]

    # 项目根 ID
    proj_id = id_for("PBXProject")
    main_group_id = id_for("mainGroup")
    sources_group_id = id_for("sourcesGroup")
    products_group_id = id_for("productsGroup")
    target_id = id_for("nativeTarget")
    product_ref_id = id_for("productRef")
    build_config_list_proj = id_for("buildConfigListProj")
    build_config_list_target = id_for("buildConfigListTarget")
    build_config_debug_proj = id_for("buildConfigDebugProj")
    build_config_release_proj = id_for("buildConfigReleaseProj")
    build_config_debug_target = id_for("buildConfigDebugTarget")
    build_config_release_target = id_for("buildConfigReleaseTarget")
    sources_build_phase = id_for("sourcesBuildPhase")
    frameworks_build_phase = id_for("frameworksBuildPhase")
    resources_build_phase = id_for("resourcesBuildPhase")

    # 子目录 group ID
    subgroup_ids = {}
    for g in sorted(groups.keys()):
        subgroup_ids[g] = id_for(f"group_{g}")

    # 文件 ID
    file_ref_ids = {}
    build_file_ids = {}
    for fname, relpath, _ in sources:
        ref_id = id_for(f"fileRef_{relpath}")
        build_id = id_for(f"buildFile_{relpath}")
        file_ref_ids[relpath] = ref_id
        build_file_ids[relpath] = build_id

    # Info.plist ref
    info_plist_ref = id_for("infoPlistRef")
    info_plist_build = id_for("infoPlistBuild")

    # Build settings
    swift_flags = '$(inherited)'
    ld_flags = '$(inherited)'

    lines = []
    def w(s=""):
        lines.append(s + "\n")

    w("// !$*UTF8*$!")
    w("{")
    w(f"\tarchiveVersion = 1;")
    w(f"\tclasses = {{}};")
    w(f"\tobjectVersion = 56;")
    w(f"\tobjects = {{")
    w()

    # === PBXBuildFile section ===
    w("/* Begin PBXBuildFile section */")
    for fname, relpath, _ in sources:
        w(f"\t\t{build_file_ids[relpath]} /* {fname} in Sources */ = {{isa = PBXBuildFile; fileRef = {file_ref_ids[relpath]} /* {fname} */; }};")
    w("/* End PBXBuildFile section */")
    w()

    # === PBXFileReference section ===
    w("/* Begin PBXFileReference section */")
    for fname, relpath, fullpath in sources:
        w(f"\t\t{file_ref_ids[relpath]} /* {fname} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = \"{fname}\"; sourceTree = \"<group>\"; }};")
    w(f"\t\t{product_ref_id} /* {PRODUCT_NAME}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = \"{PRODUCT_NAME}.app\"; sourceTree = BUILT_PRODUCTS_DIR; }};")
    w(f"\t\t{info_plist_ref} /* Info.plist */ = {{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = \"<group>\"; }};")
    w("/* End PBXFileReference section */")
    w()

    # === PBXGroup section ===
    w("/* Begin PBXGroup section */")
    # Main group
    w(f"\t\t{main_group_id} = {{")
    w(f"\t\t\tisa = PBXGroup;")
    w(f"\t\t\tchildren = (")
    w(f"\t\t\t\t{sources_group_id} /* Sources */,")
    w(f"\t\t\t\t{info_plist_ref} /* Info.plist */,")
    w(f"\t\t\t\t{products_group_id} /* Products */,")
    w(f"\t\t\t);")
    w(f"\t\t\tsourceTree = \"<group>\";")
    w(f"\t\t}};")

    # Sources group
    w(f"\t\t{sources_group_id} = {{")
    w(f"\t\t\tisa = PBXGroup;")
    w(f"\t\t\tchildren = (")
    # Subgroups
    for g in sorted(groups.keys()):
        w(f"\t\t\t\t{subgroup_ids[g]} /* {os.path.basename(g)} */,")
    # Root-level files in Sources/ClipVault/
    for fname, relpath, _ in sources:
        if '/' not in relpath:
            w(f"\t\t\t\t{file_ref_ids[relpath]} /* {fname} */,")
    w(f"\t\t\t);")
    w(f"\t\t\tpath = \"{os.path.relpath(SOURCES_DIR, PROJECT_DIR)}\";")
    w(f"\t\t\tsourceTree = \"<group>\";")
    w(f"\t\t}};")

    # Subgroups
    for g in sorted(groups.keys()):
        w(f"\t\t{subgroup_ids[g]} /* {os.path.basename(g)} */ = {{")
        w(f"\t\t\tisa = PBXGroup;")
        w(f"\t\t\tchildren = (")
        for fname, relpath, _ in sources:
            if os.path.dirname(relpath) == g:
                w(f"\t\t\t\t{file_ref_ids[relpath]} /* {fname} */,")
        w(f"\t\t\t);")
        w(f"\t\t\tname = \"{os.path.basename(g)}\";")
        w(f"\t\t\tpath = \"{os.path.basename(g)}\";")
        w(f"\t\t\tsourceTree = \"<group>\";")
        w(f"\t\t}};")

    # Products group
    w(f"\t\t{products_group_id} = {{")
    w(f"\t\t\tisa = PBXGroup;")
    w(f"\t\t\tchildren = (")
    w(f"\t\t\t\t{product_ref_id} /* {PRODUCT_NAME}.app */,")
    w(f"\t\t\t);")
    w(f"\t\t\tname = Products;")
    w(f"\t\t\tsourceTree = \"<group>\";")
    w(f"\t\t}};")
    w("/* End PBXGroup section */")
    w()

    # === PBXNativeTarget section ===
    w("/* Begin PBXNativeTarget section */")
    w(f"\t\t{target_id} /* {PRODUCT_NAME} */ = {{")
    w(f"\t\t\tisa = PBXNativeTarget;")
    w(f"\t\t\tbuildConfigurationList = {build_config_list_target} /* Build configuration list for PBXNativeTarget \"{PRODUCT_NAME}\" */;")
    w(f"\t\t\tbuildPhases = (")
    w(f"\t\t\t\t{sources_build_phase} /* Sources */,")
    w(f"\t\t\t\t{frameworks_build_phase} /* Frameworks */,")
    w(f"\t\t\t\t{resources_build_phase} /* Resources */,")
    w(f"\t\t\t);")
    w(f"\t\t\tbuildRules = ();")
    w(f"\t\t\tdependencies = ();")
    w(f"\t\t\tname = \"{PRODUCT_NAME}\";")
    w(f"\t\t\tproductName = \"{PRODUCT_NAME}\";")
    w(f"\t\t\tproductReference = {product_ref_id} /* {PRODUCT_NAME}.app */;")
    w(f"\t\t\tproductType = \"com.apple.product-type.application\";")
    w(f"\t\t}};")
    w("/* End PBXNativeTarget section */")
    w()

    # === PBXProject section ===
    w("/* Begin PBXProject section */")
    w(f"\t\t{proj_id} /* Project object */ = {{")
    w(f"\t\t\tisa = PBXProject;")
    w(f"\t\t\tattributes = {{")
    w(f"\t\t\t\tBuildIndependentTargetsInParallel = 1;")
    w(f"\t\t\t\tLastSwiftUpdateCheck = 1530;")
    w(f"\t\t\t\tLastUpgradeCheck = 1530;")
    w(f"\t\t\t\tTargetAttributes = {{")
    w(f"\t\t\t\t\t{target_id} = {{")
    w(f"\t\t\t\t\t\tCreatedOnToolsVersion = 15.3;")
    w(f"\t\t\t\t\t}};")
    w(f"\t\t\t\t}};")
    w(f"\t\t\t}};")
    w(f"\t\t\tbuildConfigurationList = {build_config_list_proj} /* Build configuration list for PBXProject \"{PRODUCT_NAME}\" */;")
    w(f"\t\t\tcompatibilityVersion = \"Xcode 14.0\";")
    w(f"\t\t\tdevelopmentRegion = \"zh-Hans\";")
    w(f"\t\t\thasScannedForEncodings = 0;")
    w(f"\t\t\tknownRegions = (")
    w(f"\t\t\t\ten,")
    w(f"\t\t\t\tBase,")
    w(f"\t\t\t\t\"zh-Hans\",")
    w(f"\t\t\t);")
    w(f"\t\t\tmainGroup = {main_group_id};")
    w(f"\t\t\tproductRefGroup = {products_group_id} /* Products */;")
    w(f"\t\t\tprojectDirPath = \"\";")
    w(f"\t\t\tprojectRoot = \"\";")
    w(f"\t\t\ttargets = (")
    w(f"\t\t\t\t{target_id} /* {PRODUCT_NAME} */,")
    w(f"\t\t\t);")
    w(f"\t\t}};")
    w("/* End PBXProject section */")
    w()

    # === PBXSourcesBuildPhase section ===
    w("/* Begin PBXSourcesBuildPhase section */")
    w(f"\t\t{sources_build_phase} /* Sources */ = {{")
    w(f"\t\t\tisa = PBXSourcesBuildPhase;")
    w(f"\t\t\tbuildActionMask = 2147483647;")
    w(f"\t\t\tfiles = (")
    for fname, relpath, _ in sources:
        w(f"\t\t\t\t{build_file_ids[relpath]} /* {fname} in Sources */,")
    w(f"\t\t\t);")
    w(f"\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    w(f"\t\t}};")
    w("/* End PBXSourcesBuildPhase section */")
    w()

    # === PBXFrameworksBuildPhase section ===
    w("/* Begin PBXFrameworksBuildPhase section */")
    w(f"\t\t{frameworks_build_phase} /* Frameworks */ = {{")
    w(f"\t\t\tisa = PBXFrameworksBuildPhase;")
    w(f"\t\t\tbuildActionMask = 2147483647;")
    w(f"\t\t\tfiles = (")
    w(f"\t\t\t);")
    w(f"\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    w(f"\t\t}};")
    w("/* End PBXFrameworksBuildPhase section */")
    w()

    # === PBXResourcesBuildPhase section ===
    w("/* Begin PBXResourcesBuildPhase section */")
    w(f"\t\t{resources_build_phase} /* Resources */ = {{")
    w(f"\t\t\tisa = PBXResourcesBuildPhase;")
    w(f"\t\t\tbuildActionMask = 2147483647;")
    w(f"\t\t\tfiles = (")
    w(f"\t\t\t);")
    w(f"\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    w(f"\t\t}};")
    w("/* End PBXResourcesBuildPhase section */")
    w()

    # === XCBuildConfiguration section ===
    w("/* Begin XCBuildConfiguration section */")
    # Debug - Project
    w(f"\t\t{build_config_debug_proj} /* Debug */ = {{")
    w(f"\t\t\tisa = XCBuildConfiguration;")
    w(f"\t\t\tbuildSettings = {{")
    w(f"\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;")
    w(f"\t\t\t\tCLANG_ANALYZER_NONNULL = YES;")
    w(f"\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = \"gnu++20\";")
    w(f"\t\t\t\tCLANG_ENABLE_MODULES = YES;")
    w(f"\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;")
    w(f"\t\t\t\tCOPY_PHASE_STRIP = NO;")
    w(f"\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;")
    w(f"\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;")
    w(f"\t\t\t\tENABLE_TESTABILITY = YES;")
    w(f"\t\t\t\tGCC_DYNAMIC_NO_PIC = NO;")
    w(f"\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;")
    w(f"\t\t\t\tGCC_PREPROCESSOR_DEFINITIONS = (\"DEBUG=1\",);")
    w(f"\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;")
    w(f"\t\t\t\tMACOSX_DEPLOYMENT_TARGET = {DEPLOYMENT_TARGET};")
    w(f"\t\t\t\tMTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;")
    w(f"\t\t\t\tONLY_ACTIVE_ARCH = YES;")
    w(f"\t\t\t\tSDKROOT = macosx;")
    w(f"\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;")
    w(f"\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = \"-Onone\";")
    w(f"\t\t\t}};")
    w(f"\t\t\tname = Debug;")
    w(f"\t\t}};")

    # Release - Project
    w(f"\t\t{build_config_release_proj} /* Release */ = {{")
    w(f"\t\t\tisa = XCBuildConfiguration;")
    w(f"\t\t\tbuildSettings = {{")
    w(f"\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;")
    w(f"\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = \"gnu++20\";")
    w(f"\t\t\t\tCLANG_ENABLE_MODULES = YES;")
    w(f"\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;")
    w(f"\t\t\t\tCOPY_PHASE_STRIP = NO;")
    w(f"\t\t\t\tDEBUG_INFORMATION_FORMAT = \"dwarf-with-dsym\";")
    w(f"\t\t\t\tENABLE_NS_ASSERTIONS = NO;")
    w(f"\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;")
    w(f"\t\t\t\tGCC_OPTIMIZATION_LEVEL = s;")
    w(f"\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;")
    w(f"\t\t\t\tMACOSX_DEPLOYMENT_TARGET = {DEPLOYMENT_TARGET};")
    w(f"\t\t\t\tMTL_ENABLE_DEBUG_INFO = NO;")
    w(f"\t\t\t\tSDKROOT = macosx;")
    w(f"\t\t\t\tSWIFT_COMPILATION_MODE = wholemodule;")
    w(f"\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = \"-O\";")
    w(f"\t\t\t\tVALIDATE_PRODUCT = YES;")
    w(f"\t\t\t}};")
    w(f"\t\t\tname = Release;")
    w(f"\t\t}};")

    # Debug - Target
    w(f"\t\t{build_config_debug_target} /* Debug */ = {{")
    w(f"\t\t\tisa = XCBuildConfiguration;")
    w(f"\t\t\tbuildSettings = {{")
    w(f"\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;")
    w(f"\t\t\t\tCODE_SIGN_STYLE = Automatic;")
    w(f"\t\t\t\tCOMBINE_HIDPI_IMAGES = YES;")
    w(f"\t\t\t\tCURRENT_PROJECT_VERSION = 1;")
    w(f"\t\t\t\tENABLE_HARDENED_RUNTIME = YES;")
    w(f"\t\t\t\tGENERATE_INFOPLIST_FILE = YES;")
    w(f"\t\t\t\tINFOPLIST_FILE = \"{INFOPLIST}\";")
    w(f"\t\t\t\tINFOPLIST_KEY_LSUIElement = YES;")
    w(f"\t\t\t\tINFOPLIST_KEY_NSSupportsAutomaticTermination = NO;")
    w(f"\t\t\t\tINFOPLIST_KEY_NSHumanReadableCopyright = \"Copyright © 2026. All rights reserved.\";")
    w(f"\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (\"$(inherited)\", \"@executable_path/../Frameworks\");")
    w(f"\t\t\t\tMARKETING_VERSION = 1.0;")
    w(f"\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = \"{BUNDLE_ID}\";")
    w(f"\t\t\t\tPRODUCT_NAME = \"$(TARGET_NAME)\";")
    w(f"\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;")
    w(f"\t\t\t\tSWIFT_VERSION = 5.0;")
    w(f"\t\t\t}};")
    w(f"\t\t\tname = Debug;")
    w(f"\t\t}};")

    # Release - Target
    w(f"\t\t{build_config_release_target} /* Release */ = {{")
    w(f"\t\t\tisa = XCBuildConfiguration;")
    w(f"\t\t\tbuildSettings = {{")
    w(f"\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;")
    w(f"\t\t\t\tCODE_SIGN_STYLE = Automatic;")
    w(f"\t\t\t\tCOMBINE_HIDPI_IMAGES = YES;")
    w(f"\t\t\t\tCURRENT_PROJECT_VERSION = 1;")
    w(f"\t\t\t\tENABLE_HARDENED_RUNTIME = YES;")
    w(f"\t\t\t\tGENERATE_INFOPLIST_FILE = YES;")
    w(f"\t\t\t\tINFOPLIST_FILE = \"{INFOPLIST}\";")
    w(f"\t\t\t\tINFOPLIST_KEY_LSUIElement = YES;")
    w(f"\t\t\t\tINFOPLIST_KEY_NSSupportsAutomaticTermination = NO;")
    w(f"\t\t\t\tINFOPLIST_KEY_NSHumanReadableCopyright = \"Copyright © 2026. All rights reserved.\";")
    w(f"\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (\"$(inherited)\", \"@executable_path/../Frameworks\");")
    w(f"\t\t\t\tMARKETING_VERSION = 1.0;")
    w(f"\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = \"{BUNDLE_ID}\";")
    w(f"\t\t\t\tPRODUCT_NAME = \"$(TARGET_NAME)\";")
    w(f"\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;")
    w(f"\t\t\t\tSWIFT_VERSION = 5.0;")
    w(f"\t\t\t}};")
    w(f"\t\t\tname = Release;")
    w(f"\t\t}};")
    w("/* End XCBuildConfiguration section */")
    w()

    # === XCConfigurationList section ===
    w("/* Begin XCConfigurationList section */")
    w(f"\t\t{build_config_list_proj} /* Build configuration list for PBXProject \"{PRODUCT_NAME}\" */ = {{")
    w(f"\t\t\tisa = XCConfigurationList;")
    w(f"\t\t\tbuildConfigurations = (")
    w(f"\t\t\t\t{build_config_debug_proj} /* Debug */,")
    w(f"\t\t\t\t{build_config_release_proj} /* Release */,")
    w(f"\t\t\t);")
    w(f"\t\t\tdefaultConfigurationIsVisible = 0;")
    w(f"\t\t\tdefaultConfigurationName = Release;")
    w(f"\t\t}};")

    w(f"\t\t{build_config_list_target} /* Build configuration list for PBXNativeTarget \"{PRODUCT_NAME}\" */ = {{")
    w(f"\t\t\tisa = XCConfigurationList;")
    w(f"\t\t\tbuildConfigurations = (")
    w(f"\t\t\t\t{build_config_debug_target} /* Debug */,")
    w(f"\t\t\t\t{build_config_release_target} /* Release */,")
    w(f"\t\t\t);")
    w(f"\t\t\tdefaultConfigurationIsVisible = 0;")
    w(f"\t\t\tdefaultConfigurationName = Release;")
    w(f"\t\t}};")
    w("/* End XCConfigurationList section */")
    w()

    w(f"\t}};")
    w(f"\trootObject = {proj_id} /* Project object */;")
    w(f"}}")

    return "".join(lines)

def main():
    os.makedirs(XCODEPROJ, exist_ok=True)
    content = write_pbxproj()
    with open(PBXPROJ, 'w') as f:
        f.write(content)
    print(f"✅ Xcode 项目已创建: {XCODEPROJ}")
    print(f"   包含 {len(collect_sources(SOURCES_DIR))} 个 Swift 源文件")
    print()
    print("📋 在 Xcode 中打开：")
    print(f"   open {XCODEPROJ}")
    print()
    print("💡 然后按 Cmd+R 即可运行")

if __name__ == "__main__":
    main()
