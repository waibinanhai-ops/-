#!/usr/bin/env python3
"""
多机位合板 - 最终方案
=====================
Phase 1: 自动导入视频 + Camera # → 暂停（你做音频同步）
Phase 2: 自动导入音频 → 暂停（你做多机位片段）
Phase 3: 自动完成时间线操作 + 导出 XML

用法:
  python3 auto_sync.py <素材文件夹> <XML导出路径>
"""

import os, sys, re, pickle, tempfile, subprocess
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
from python_get_resolve import GetResolve

VIDEO_EXTS = {'.mp4','.mov','.mxf','.braw','.r3d','.avi','.mts','.m2t','.m2ts','.mkv','.webm'}
AUDIO_EXTS = {'.wav','.mp3'}
CAM_PATTERN = re.compile(r'^([a-zA-Z])机?$')
STATE_FILE = os.path.join(tempfile.gettempdir(), 'multicam_auto_state.pkl')


def scan(source_dir):
    d = os.path.basename(source_dir.rstrip('/'))
    vd = os.path.join(source_dir, '视频')
    if not os.path.isdir(vd): raise SystemExit(f'视频目录不存在: {vd}')
    cameras, skipped = {}, []
    for fn in sorted(os.listdir(vd)):
        fp = os.path.join(vd, fn)
        if not os.path.isdir(fp): continue
        m = CAM_PATTERN.match(fn)
        if m: cameras.setdefault(m.group(1).lower(), []).append(fp)
        else: skipped.append(fn)
    if not cameras: raise SystemExit('未找到字母机位')
    clip_dirs = {}
    for cam, paths in cameras.items():
        dirs = []
        for p in paths:
            for r, ds, fs in os.walk(p):
                if os.path.basename(r) == 'CLIP': dirs.append(r)
        clip_dirs[cam] = dirs
    video_files = {}
    for cam, dirs in clip_dirs.items():
        files = []
        for cd in dirs:
            for f in sorted(os.listdir(cd)):
                if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                    files.append(os.path.join(cd, f))
        video_files[cam] = files
    audio_files = []
    for r, ds, fs in os.walk(source_dir):
        for f in fs:
            if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                audio_files.append(os.path.join(r, f))
    return {
        'date': d, 'source_dir': source_dir, 'cameras': cameras,
        'video_files': video_files, 'audio_files': sorted(audio_files),
        'skipped': skipped,
    }


def applescript(script):
    """Run an AppleScript command."""
    try:
        result = subprocess.run(['osascript', '-e', script],
                                capture_output=True, text=True, timeout=30)
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return str(e)


# ══════════════════════════════════════════════════
# PHASE 1: Import videos
# ══════════════════════════════════════════════════

def phase1(info):
    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')
    pm = resolve.GetProjectManager()
    date = info['date']
    proj = pm.CreateProject(date) or pm.LoadProject(date)
    if not proj: raise SystemExit(f'无法创建工程: {date}')
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()
    folder = mp.AddSubFolder(root, date)
    if not folder:
        for sf in root.GetSubFolderList():
            if sf.GetName() == date: folder = sf; break
    mp.SetCurrentFolder(folder)

    total_video = 0
    for cam in sorted(info['video_files'].keys()):
        files = info['video_files'][cam]
        if not files: continue
        print(f'  [{cam}] {len(files)} 个文件...')
        imported = mp.ImportMedia(files)
        if imported:
            count = 0
            for c in imported:
                if c:
                    c.SetMetadata('Camera #', cam)
                    count += 1
            total_video += count
            print(f'       {count}, Camera # = "{cam}"')

    state = {
        'date': date, 'source_dir': info['source_dir'],
        'xml_dir': info.get('xml_dir', '/tmp'),
        'audio_files': info['audio_files'],
        'phase': 'awaiting_audio_sync',
    }
    with open(STATE_FILE, 'wb') as f: pickle.dump(state, f)

    print(f'\n{"="*60}')
    print(f'✅ 导入 {total_video} 个视频片段')
    print(f'')
    print(f'🛑 请操作: 媒体池 "{date}" → 全选视频 → 右键 →')
    print(f'   音频同步 → 从音频轨道中更新时间码')
    print(f'')
    print(f'   完成后运行: python3 auto_sync.py --continue')
    print(f'{"="*60}')


# ══════════════════════════════════════════════════
# PHASE 2: Import audio, pause for multi-cam
# ══════════════════════════════════════════════════

def phase2():
    if not os.path.exists(STATE_FILE):
        raise SystemExit('请先运行 Phase 1')
    with open(STATE_FILE, 'rb') as f:
        state = pickle.load(f)

    date = state['date']
    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')
    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(date)
    if not proj: raise SystemExit(f'无法加载: {date}')
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()
    folder = None
    for sf in root.GetSubFolderList():
        if sf.GetName() == date: folder = sf; break
    if not folder: raise SystemExit(f'找不到文件夹: {date}')

    # Import audio files
    audio_files = state.get('audio_files', [])
    if audio_files:
        print(f'📥 导入音频: {len(audio_files)} 个...')
        imported = mp.ImportMedia(audio_files)
        if imported:
            for c in imported:
                if c:
                    old = c.GetMetadata('Camera #') or ''
                    if old.strip() and old.strip().lower() not in 'abcdef':
                        c.SetMetadata('Camera #', '')

    state['phase'] = 'awaiting_multicam'
    with open(STATE_FILE, 'wb') as f: pickle.dump(state, f)

    print(f'')
    print(f'{"="*60}')
    print(f'✅ 音频已导入 ({len(audio_files)} 个)')
    print(f'')
    print(f'🛑 请操作: 媒体池 "{date}" → 全选所有片段 → 右键 →')
    print(f'   使所选片段新建多机位片段')
    print(f'   - 角度命名: 元数据摄影机')
    print(f'   - 取消「将片段移动到原始片段文件夹」')
    print(f'   - 勾选「检测来自相同摄影机的片段」')
    print(f'   - 检测方式: 元数据摄影机编号')
    print(f'')
    print(f'   完成后运行: python3 auto_sync.py --continue')
    print(f'{"="*60}')


# ══════════════════════════════════════════════════
# PHASE 3: Timeline + Export
# ══════════════════════════════════════════════════

def phase3():
    if not os.path.exists(STATE_FILE):
        raise SystemExit('请先运行 Phase 1')
    with open(STATE_FILE, 'rb') as f:
        state = pickle.load(f)

    date = state['date']
    xml_dir = state['xml_dir']

    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')
    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(date)
    if not proj: raise SystemExit(f'无法加载: {date}')
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()

    folder = None
    for sf in root.GetSubFolderList():
        if sf.GetName() == date: folder = sf; break
    if not folder: raise SystemExit(f'找不到文件夹: {date}')

    # Find the multi-cam clip (it's a clipitem in the folder)
    clips = folder.GetClipList()
    multicam_clip = None
    audio_clip = None

    for clip in clips:
        name = clip.GetName() or ''
        ext = os.path.splitext(name)[1].lower()
        if ext in AUDIO_EXTS and not audio_clip:
            audio_clip = clip
        # Multi-cam clip is typically named after the folder
        if name == date and not ext:
            multicam_clip = clip

    if not multicam_clip:
        # Try to find any clip that might be the multi-cam
        for clip in clips:
            name = clip.GetName() or ''
            if name == date:
                multicam_clip = clip
                break

    if not multicam_clip:
        print('⚠️  找不到多机位片段，尝试查找...')
        # List all clips for debugging
        for clip in clips[:10]:
            print(f'    {clip.GetName()}')

    # Use AppleScript to automate the timeline operations
    print('🎬 自动执行时间线操作...')

    # 1. Select the multi-cam clip
    if multicam_clip:
        mp.SetSelectedClip(multicam_clip)
        print('   已选中多机位片段')

        # 2. Trigger "Open in Timeline" via AppleScript
        # Use the Clip menu: 片段 → 在时间线上打开
        applescript('''
            tell application "System Events"
                tell process "Resolve"
                    set frontmost to true
                    delay 0.3
                    -- Click menu: 片段 → 在时间线上打开
                    click menu item "在时间线上打开" of menu "片段" of menu bar 1
                end tell
            end tell
        ''')
        print('   已打开时间线')
        import time; time.sleep(2)

    # 3. Select all + Copy
    applescript('''
        tell application "System Events"
            tell process "Resolve"
                keystroke "a" using command down
                delay 0.3
                keystroke "c" using command down
                delay 0.3
            end tell
        end tell
    ''')
    print('   已复制')

    # 4. Select first audio clip + create new timeline
    if audio_clip:
        mp.SetSelectedClip(audio_clip)

    applescript('''
        tell application "System Events"
            tell process "Resolve"
                delay 0.3
                -- Right-click context: 使所选片段新建时间线
                -- Try via menu first, then keystroke
                keystroke "n" using {command down}
                delay 0.5
            end tell
        end tell
    ''')

    import time; time.sleep(1)

    # Find the new timeline
    timeline = None
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if t:
            timeline = t
            print(f'   当前时间线: {t.GetName()}')

    if not timeline:
        print('❌ 找不到时间线')
        sys.exit(1)

    # 5. Delete all + Paste
    # First delete existing content
    for track_type in ('video', 'audio'):
        for ti in range(timeline.GetTrackCount(track_type), 0, -1):
            items = timeline.GetItemListInTrack(track_type, ti)
            if items:
                timeline.DeleteClips(items, False)

    # Paste
    applescript('''
        tell application "System Events"
            tell process "Resolve"
                keystroke "v" using command down
                delay 1
            end tell
        end tell
    ''')

    import time; time.sleep(2)

    # 6. Export as FCP 7 XML
    print('📤 导出 FCP 7 XML...')
    os.makedirs(xml_dir, exist_ok=True)
    xml_path = os.path.join(xml_dir, f'{date}.xml')
    result = timeline.Export(xml_path, resolve.EXPORT_FCP_7_XML)

    if result:
        size = os.path.getsize(xml_path) / (1024*1024)
        print(f'\n{"="*60}')
        print(f'✅ 完成!')
        print(f'   输出: {xml_path} ({size:.1f} MB)')
        print(f'{"="*60}')
    else:
        print('❌ 导出失败')

    os.remove(STATE_FILE)


# ══════════════════════════════════════════════════

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--continue':
        # Check current phase
        if not os.path.exists(STATE_FILE):
            raise SystemExit('没有状态文件')
        with open(STATE_FILE, 'rb') as f:
            state = pickle.load(f)
        phase = state.get('phase', '')
        if phase == 'awaiting_audio_sync':
            phase2()
        elif phase == 'awaiting_multicam':
            phase3()
        else:
            print(f'未知状态: {phase}')
        return

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source_dir = sys.argv[1]
    xml_dir = sys.argv[2]

    print('🔍 扫描...')
    info = scan(source_dir)
    print(f'   日期: {info["date"]}')
    for cam in sorted(info['video_files']):
        print(f'   [{cam}]: {len(info["video_files"][cam])} clips')
    if info['skipped']: print(f'   跳过: {info["skipped"]}')

    info['xml_dir'] = xml_dir
    phase1(info)


if __name__ == '__main__':
    main()
