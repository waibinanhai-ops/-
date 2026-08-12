#!/usr/bin/env python3
"""
多机位合板 - 最终版
===================
Phase 1: 自动导入素材 + 设置 Camera # → 暂停等用户做音频同步
Phase 2: 用达芬奇 API 创建正确时间码位置的时间线 → 达芬奇原生导出 FCP 7 XML

用法:
  Phase 1: python3 final_sync.py <素材文件夹> <XML导出路径>
  Phase 2: python3 final_sync.py --continue
"""

import os, sys, re, pickle, tempfile
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
from python_get_resolve import GetResolve

VIDEO_EXTS = {'.mp4','.mov','.mxf','.braw','.r3d','.avi','.mts','.m2t','.m2ts','.mkv','.webm'}
AUDIO_EXTS = {'.wav','.mp3'}
CAM_PATTERN = re.compile(r'^([a-zA-Z])机?$')
STATE_FILE = os.path.join(tempfile.gettempdir(), 'multicam_final_state.pkl')


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


def tc_to_frames(tc, fps):
    try:
        parts = str(tc).replace(';',':').split(':')
        if len(parts) == 4:
            return (int(parts[0])*3600+int(parts[1])*60+int(parts[2]))*int(round(fps))+int(parts[3])
    except: pass
    return 0


# ══════════════════════════════════════════════════
# PHASE 1
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
        print(f'  📥 [{cam}] {len(files)} 个文件...')
        imported = mp.ImportMedia(files)
        if imported:
            count = 0
            for c in imported:
                if c:
                    c.SetMetadata('Camera #', cam)
                    count += 1
            total_video += count
            print(f'       ✅ {count}, Camera # = "{cam}"')

    # 音频文件在 Phase 2 导入（音频同步只需视频片段）
    print(f'\n✅ 导入: {total_video} 个视频片段 (音频将在同步后导入)')

    state = {
        'date': date, 'source_dir': info['source_dir'],
        'xml_dir': info.get('xml_dir', '/tmp'),
        'audio_files': info['audio_files'],
        'phase': 'awaiting_sync',
    }
    with open(STATE_FILE, 'wb') as f: pickle.dump(state, f)

    print(f'''
╔══════════════════════════════════════════════════════════╗
║  🛑 请在达芬奇中操作：                                  ║
║                                                        ║
║  媒体池 "{date}" → 全选视频片段 → 右键 →              ║
║  音频同步 → 从音频轨道中更新时间码                     ║
║                                                        ║
║  完成后运行:                                           ║
║  python3 final_sync.py --continue                      ║
╚══════════════════════════════════════════════════════════╝
''')


# ══════════════════════════════════════════════════
# PHASE 2
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

    # 1. Import audio files (after sync is done)
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
        print(f'   ✅ 已导入')

    # 2. Read synced metadata
    print('📊 读取同步后的元数据...')
    cameras = defaultdict(list)
    audio_clips = []
    audio_pool_items = []

    for clip in folder.GetClipList():
        name = clip.GetName() or ''
        props = clip.GetClipProperty() or {}
        cam = (clip.GetMetadata('Camera #') or '').strip()

        fps_str = str(props.get('FPS', '24')).split()[0]
        try: fps = float(fps_str)
        except: fps = 25.0
        frames = int(props.get('Frames', '0') or '0')
        tc = props.get('Start TC', '00:00:00:00')
        res = str(props.get('Resolution', '1920x1080'))
        if 'x' in res: w, h = map(int, res.split('x'))
        else: w, h = 1920, 1080
        ext = os.path.splitext(name)[1].lower()

        if ext in AUDIO_EXTS:
            audio_clips.append({
                'name': name, 'fps': fps, 'tc': tc, 'frames': frames,
                'pool_item': clip,
            })
            audio_pool_items.append(clip)
        elif cam and cam in 'abcdef':
            cameras[cam].append({
                'name': name, 'fps': fps, 'tc': tc, 'frames': frames,
                'w': w, 'h': h, 'pool_item': clip,
            })

    for cam in sorted(cameras):
        c0 = cameras[cam][0]
        print(f'   [{cam}]: {len(cameras[cam])} clips, first TC={c0["tc"]}')

    # Find sync reference (earliest timecode)
    sync_start = None
    for clips in cameras.values():
        for c in clips:
            fs = tc_to_frames(c['tc'], c['fps'])
            if sync_start is None or fs < sync_start: sync_start = fs
    if sync_start is None: sync_start = 0

    # Timeline FPS
    all_fps = [c['fps'] for clips in cameras.values() for c in clips]
    src_fps = max(set(all_fps), key=all_fps.count) if all_fps else 50
    t_fps = 25 if src_fps >= 50 else int(src_fps)

    print(f'   同步起点: frame {sync_start}')
    print(f'   时间线帧率: {t_fps}')

    # Clean old timelines
    for i in range(proj.GetTimelineCount(), 0, -1):
        t = proj.GetTimelineByIndex(i)
        if t: mp.DeleteTimelines([t])

    # Create timeline from first audio clip (as anchor)
    print('📝 创建时间线...')
    first_audio = audio_pool_items[0] if audio_pool_items else list(cameras.values())[0][0]['pool_item']
    timeline = mp.CreateTimelineFromClips(date, [first_audio])
    if not timeline:
        timeline = mp.CreateEmptyTimeline(date)
    if not timeline:
        raise SystemExit('无法创建时间线')

    # Set timeline start to 00:00:00:00 so all clip positions are positive
    timeline.SetStartTimecode('00:00:00:00')
    print(f'   时间线起始 TC: 00:00:00:00')

    # Delete the default content
    for track_type in ('video', 'audio'):
        for ti in range(timeline.GetTrackCount(track_type), 0, -1):
            items = timeline.GetItemListInTrack(track_type, ti)
            if items:
                timeline.DeleteClips(items, False)

    # Add tracks for each camera
    for i in range(len(cameras)):
        timeline.AddTrack('video')

    # Place clips at synced timecode positions
    track_idx = 1  # Video track 1
    total_items = 0
    for cam_letter in sorted(cameras.keys()):
        clips = sorted(cameras[cam_letter],
                       key=lambda c: tc_to_frames(c['tc'], c['fps']))
        print(f'   轨道 {track_idx} [{cam_letter}]: {len(clips)} clips...')

        clip_infos = []
        for c in clips:
            tc_start = tc_to_frames(c['tc'], c['fps'])
            offset = tc_start - sync_start
            # Convert offset to timeline fps
            if abs(t_fps - c['fps']) > 1:
                offset = int(offset * t_fps / c['fps'])
                dur = int(c['frames'] * t_fps / c['fps'])
            else:
                dur = c['frames']

            clip_infos.append({
                'mediaPoolItem': c['pool_item'],
                'startFrame': 0,
                'endFrame': c['frames'],
                'trackIndex': track_idx,
                'recordFrame': float(offset),
                'mediaType': 1,  # Video only
            })

        if clip_infos:
            result = mp.AppendToTimeline(clip_infos)
            if result:
                total_items += len([x for x in result if x])
                print(f'      ✅ {len(clip_infos)} placed')

        track_idx += 1

    # Add audio clips - each on its own track at timecode position
    if audio_clips:
        print(f'   音频轨: {len(audio_clips)} clips...')
        audio_sorted = sorted(audio_clips, key=lambda c: tc_to_frames(c['tc'], c['fps']))
        placed_audio = 0
        for i, ac in enumerate(audio_sorted):
            tc_start = tc_to_frames(ac['tc'], ac['fps'])
            offset = tc_start - sync_start
            if offset < 0: offset = 0
            if abs(t_fps - ac['fps']) > 1:
                offset = int(offset * t_fps / ac['fps'])

            # Add a new audio track for each clip to avoid overlap
            if i > 0:
                timeline.AddTrack('audio', 'mono' if ac.get('audio_ch', 2) <= 1 else 'stereo')

            result = mp.AppendToTimeline([{
                'mediaPoolItem': ac['pool_item'],
                'recordFrame': float(offset),
                'mediaType': 2,
                'trackIndex': i + 1,
            }])
            if result and result[0]:
                placed_audio += 1
        print(f'      ✅ {placed_audio}/{len(audio_sorted)} placed at TC positions')

    # ── Export using Resolve's native engine ──
    xml_dir = state.get('xml_dir', os.path.dirname(state.get('source_dir', '.')))
    # Read xml_dir from state
    if 'xml_dir' not in state:
        # Fallback
        xml_dir = '/tmp'

    print(f'📤 达芬奇原生导出 FCP 7 XML...')
    os.makedirs(xml_dir, exist_ok=True)
    xml_path = os.path.join(xml_dir, f'{date}.xml')
    result = timeline.Export(xml_path, resolve.EXPORT_FCP_7_XML)

    if result:
        size = os.path.getsize(xml_path) / (1024*1024)
        print(f'\n{"="*60}')
        print(f'✅ 完成!')
        print(f'   输出: {xml_path} ({size:.1f} MB)')
        print(f'   轨道: {len(cameras)} 条视频轨')
        print(f'   片段: {total_items} 个 (时间码已对齐)')
        print(f'{"="*60}')
    else:
        print('❌ 导出失败')

    os.remove(STATE_FILE)


# ══════════════════════════════════════════════════

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--continue':
        phase2()
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
    print(f'   音频: {len(info["audio_files"])}')
    if info['skipped']: print(f'   跳过: {info["skipped"]}')

    info['xml_dir'] = xml_dir
    phase1(info)


if __name__ == '__main__':
    main()
