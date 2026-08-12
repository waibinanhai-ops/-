#!/usr/bin/env python3
"""
多机位合板 - 混合自动化方案
============================
自动完成导入 + 元数据设置。
音频同步步骤暂停，等你手动完成后继续。

用法:
  第一次运行: python3 sync_assist.py <素材文件夹> <XML导出路径>
  音频同步后: python3 sync_assist.py --continue
"""

import os, sys, re, urllib.parse, pickle, tempfile
from xml.etree.ElementTree import Element, SubElement, tostring
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
from python_get_resolve import GetResolve

VIDEO_EXTS = {'.mp4','.mov','.mxf','.braw','.r3d','.avi','.mts','.m2t','.m2ts','.mkv','.webm'}
AUDIO_EXTS = {'.wav','.mp3'}
CAM_PATTERN = re.compile(r'^([a-zA-Z])机?$')
STATE_FILE = os.path.join(tempfile.gettempdir(), 'multicam_sync_state.pkl')


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
# PHASE 1: Import
# ══════════════════════════════════════════════════

def phase1_import(info):
    """导入素材到 Resolve，设置 Camera #，然后暂停等用户做音频同步。"""
    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')

    pm = resolve.GetProjectManager()
    date = info['date']

    # Create/load project
    proj = pm.CreateProject(date) or pm.LoadProject(date)
    if not proj: raise SystemExit(f'无法创建工程: {date}')

    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()

    folder = mp.AddSubFolder(root, date)
    if not folder:
        for sf in root.GetSubFolderList():
            if sf.GetName() == date: folder = sf; break
    mp.SetCurrentFolder(folder)

    # Import video clips
    total_video = 0
    for cam in sorted(info['video_files'].keys()):
        files = info['video_files'][cam]
        if not files: continue
        print(f'  📥 [{cam}] 导入 {len(files)} 个文件...')
        imported = mp.ImportMedia(files)
        if imported:
            count = 0
            for c in imported:
                if c:
                    c.SetMetadata('Camera #', cam)
                    count += 1
            total_video += count
            print(f'       ✅ {count} 个, Camera # = "{cam}"')

    # Import audio
    if info['audio_files']:
        print(f'  📥 音频: 导入 {len(info["audio_files"])} 个文件...')
        imported = mp.ImportMedia(info['audio_files'])
        if imported:
            for c in imported:
                if c:
                    old = c.GetMetadata('Camera #') or ''
                    if old.strip() and old.strip().lower() not in 'abcdef':
                        c.SetMetadata('Camera #', '')

    print(f'\n{"="*60}')
    print(f'✅ 导入完成！')
    print(f'   工程: {date}')
    print(f'   机位: {", ".join(sorted(info["video_files"].keys()))}')
    print(f'   视频: {total_video} 个')
    print(f'   音频: {len(info["audio_files"])} 个')
    print(f'{"="*60}')

    # ── 保存状态 ──
    state = {
        'date': date,
        'source_dir': info['source_dir'],
        'video_files': info['video_files'],
        'audio_files': info['audio_files'],
        'skipped': info['skipped'],
        'phase': 'awaiting_sync',
    }
    with open(STATE_FILE, 'wb') as f:
        pickle.dump(state, f)

    print(f'''
╔══════════════════════════════════════════════════════════╗
║  🛑 请在达芬奇中手动操作：                              ║
║                                                        ║
║  在媒体池 "{date}" 文件夹中:                       ║
║  1. 全选所有视频片段 (Cmd+A)                          ║
║  2. 右键 → 音频同步 → 从音频轨道中更新时间码          ║
║                                                        ║
║  完成后输入:                                           ║
║  python3 sync_assist.py --continue <XML导出路径>       ║
╚══════════════════════════════════════════════════════════╝
''')


# ══════════════════════════════════════════════════
# PHASE 2: Read synced data + Generate XML
# ══════════════════════════════════════════════════

def phase2_continue(xml_dir):
    """音频同步完成后，读取更新后的元数据，生成 XML。"""
    if not os.path.exists(STATE_FILE):
        raise SystemExit('没有找到状态文件，请先运行导入步骤')

    with open(STATE_FILE, 'rb') as f:
        state = pickle.load(f)

    if state.get('phase') != 'awaiting_sync':
        raise SystemExit(f'状态异常: {state.get("phase")}')

    date = state['date']

    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')

    pm = resolve.GetProjectManager()
    proj = pm.LoadProject(date)
    if not proj: raise SystemExit(f'无法加载工程: {date}')

    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()

    # Find the date folder
    folder = None
    for sf in root.GetSubFolderList():
        if sf.GetName() == date:
            folder = sf
            break
    if not folder:
        raise SystemExit(f'找不到媒体池文件夹: {date}')

    # Read updated clip metadata (timecodes may have been updated by audio sync)
    print('📊 读取更新后的元数据...')
    cameras = defaultdict(list)
    audio = []

    for clip in folder.GetClipList():
        name = clip.GetName() or 'unknown'
        props = clip.GetClipProperty() or {}
        cam = (clip.GetMetadata('Camera #') or '').strip()

        fps_str = str(props.get('FPS', '24')).split()[0]
        try: fps = float(fps_str)
        except: fps = 25.0

        frames = int(props.get('Frames', '0') or '0')
        res = str(props.get('Resolution', '1920x1080'))
        if 'x' in res: w, h = map(int, res.split('x'))
        else: w, h = 1920, 1080

        ext = os.path.splitext(name)[1].lower()
        if ext in AUDIO_EXTS and frames == 0:
            dur = props.get('Duration', '00:00:00:00')
            frames = tc_to_frames(dur, fps)

        data = {
            'name': name,
            'path': props.get('File Path', ''),
            'fps': fps,
            'start_tc': props.get('Start TC', '00:00:00:00'),
            'end_tc': props.get('End TC', '00:00:00:00'),
            'frames': frames,
            'width': w, 'height': h,
            'audio_ch': int(props.get('Audio Ch', '0') or '0'),
        }

        if cam and cam in 'abcdef':
            cameras[cam].append(data)
        elif ext in AUDIO_EXTS:
            audio.append(data)

    for cam in sorted(cameras):
        # Show first clip's timecode to verify sync
        if cameras[cam]:
            c = cameras[cam][0]
            print(f'   [{cam}]: {len(cameras[cam])} clips, '
                  f'first TC={c["start_tc"]}')
    print(f'   音频: {len(audio)} files')

    # Timeline FPS
    all_fps = [c['fps'] for clips in cameras.values() for c in clips]
    source_fps = max(set(all_fps), key=all_fps.count) if all_fps else 50
    t_fps = 25 if source_fps >= 50 else int(source_fps)

    # Generate XML
    print(f'📝 生成 FCP 7 XML (分轨, {t_fps}fps)...')
    xml_str = generate_xml(cameras, audio, date, t_fps)

    os.makedirs(xml_dir, exist_ok=True)
    path = os.path.join(xml_dir, f"{date}.xml")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    print(f'\n{"="*60}')
    print(f'✅ 完成!')
    print(f'   输出: {path} ({os.path.getsize(path)/1024/1024:.1f} MB)')
    print(f'   轨道: {len(cameras)} 条视频轨 ({", ".join(sorted(cameras.keys()))})')
    print(f'   视频: {sum(len(v) for v in cameras.values())} clips')
    print(f'   音频: {len(audio)} clips')
    print(f'{"="*60}')

    # Clean up state
    os.remove(STATE_FILE)


# ══════════════════════════════════════════════════
# XML Generation
# ══════════════════════════════════════════════════

def _el(parent, tag, text=None, **attrs):
    e = SubElement(parent, tag, **attrs)
    if text is not None: e.text = str(text)
    return e


def generate_xml(cameras, audio_clips, date_name, timeline_fps=25):
    fps_i = int(round(timeline_fps))

    sync_start = None
    for clips in cameras.values():
        for c in clips:
            fs = tc_to_frames(c['start_tc'], c['fps'])
            if sync_start is None or fs < sync_start:
                sync_start = fs
    if sync_start is None: sync_start = 0

    max_end = 0
    for clips in cameras.values():
        for c in clips:
            ef = tc_to_frames(c['start_tc'], c['fps']) + c['frames']
            if ef > max_end: max_end = ef

    total_dur = max(max_end - sync_start, 1)
    if timeline_fps not in (50, 60):
        total_dur = int(total_dur * timeline_fps / 50)

    root = Element('xmeml', version='5')
    seq = SubElement(root, 'sequence')
    _el(seq, 'name', date_name)
    _el(seq, 'duration', str(total_dur))
    r = SubElement(seq, 'rate')
    _el(r, 'timebase', str(fps_i)); _el(r, 'ntsc', 'FALSE')
    _el(seq, 'in', '-1'); _el(seq, 'out', '-1')

    tc = SubElement(seq, 'timecode')
    _el(tc, 'string', '01:00:00:00')
    _el(tc, 'frame', str(fps_i * 3600))
    _el(tc, 'displayformat', 'NDF')
    tr = SubElement(tc, 'rate')
    _el(tr, 'timebase', str(fps_i)); _el(tr, 'ntsc', 'FALSE')

    media = SubElement(seq, 'media')
    video = SubElement(media, 'video')

    clip_idx = 0
    for cam_letter in sorted(cameras.keys()):
        clips = sorted(cameras[cam_letter],
                       key=lambda c: tc_to_frames(c['start_tc'], c['fps']))
        if not clips: continue

        track = SubElement(video, 'track')
        for clip in clips:
            clip_start = tc_to_frames(clip['start_tc'], clip['fps'])
            offset = clip_start - sync_start
            if timeline_fps not in (50, 60):
                offset = int(offset * timeline_fps / 50)

            ci = Element('clipitem', id=f"{clip['name']} {clip_idx}")
            _el(ci, 'name', clip['name'])
            frames = clip['frames']
            _el(ci, 'duration', str(frames))
            cr = SubElement(ci, 'rate')
            _el(cr, 'timebase', str(fps_i)); _el(cr, 'ntsc', 'FALSE')
            _el(ci, 'start', str(offset))
            _el(ci, 'end', str(offset + frames))
            _el(ci, 'enabled', 'TRUE')
            _el(ci, 'in', '0'); _el(ci, 'out', str(frames))

            fe = Element('file', id=f"{clip['name']} 2")
            _el(fe, 'duration', str(frames))
            fr = SubElement(fe, 'rate')
            _el(fr, 'timebase', str(int(round(clip['fps']))))
            _el(fr, 'ntsc', 'FALSE')
            _el(fe, 'name', clip['name'])
            _el(fe, 'pathurl',
                'file://' + urllib.parse.quote(clip['path'], safe='/'))
            ftc = SubElement(fe, 'timecode')
            _el(ftc, 'string', clip['start_tc'])
            _el(ftc, 'displayformat', 'NDF')
            ftcr = SubElement(ftc, 'rate')
            _el(ftcr, 'timebase', str(int(round(clip['fps']))))
            _el(ftcr, 'ntsc', 'FALSE')
            fm = SubElement(fe, 'media')
            fv = SubElement(fm, 'video')
            _el(fv, 'duration', str(frames))
            sc = SubElement(fv, 'samplecharacteristics')
            _el(sc, 'width', str(clip['width']))
            _el(sc, 'height', str(clip['height']))
            fa = SubElement(fm, 'audio')
            _el(fa, 'channelcount', str(max(clip.get('audio_ch', 2), 2)))
            ci.append(fe)
            _el(ci, 'compositemode', 'normal')

            # Basic Motion filter (matches Resolve native format)
            filt = SubElement(ci, 'filter')
            _el(filt, 'enabled', 'TRUE')
            _el(filt, 'start', '0'); _el(filt, 'end', str(frames))
            eff = SubElement(filt, 'effect')
            _el(eff, 'name', 'Basic Motion')
            _el(eff, 'effectid', 'basic')
            _el(eff, 'effecttype', 'motion')
            _el(eff, 'mediatype', 'video')
            _el(eff, 'effectcategory', 'motion')
            for pn, pid, val, vmin, vmax in [
                ('Scale', 'scale', '100', '0', '10000'),
                ('Rotation', 'rotation', '0', '-100000', '100000'),
            ]:
                p = SubElement(eff, 'parameter')
                _el(p, 'name', pn); _el(p, 'parameterid', pid)
                _el(p, 'value', val)
                _el(p, 'valuemin', vmin); _el(p, 'valuemax', vmax)
            for pn, pid in [('Center', 'center'), ('Anchor Point', 'anchorPoint')]:
                p = SubElement(eff, 'parameter')
                _el(p, 'name', pn); _el(p, 'parameterid', pid)
                v = SubElement(p, 'value')
                _el(v, 'horiz', '0'); _el(v, 'vert', '0')

            track.append(ci)
            clip_idx += 1

    # Audio
    if audio_clips:
        aud = SubElement(media, 'audio')
        for i, ac in enumerate(audio_clips):
            at = SubElement(aud, 'track')
            aci = Element('clipitem', id=f"audio_{i}")
            _el(aci, 'name', ac['name'])
            _el(aci, 'duration', str(ac['frames']))
            ar = SubElement(aci, 'rate')
            _el(ar, 'timebase', str(fps_i)); _el(ar, 'ntsc', 'FALSE')
            _el(aci, 'start', '0'); _el(aci, 'end', str(ac['frames']))
            _el(aci, 'enabled', 'TRUE')
            _el(aci, 'in', '0'); _el(aci, 'out', str(ac['frames']))

            afe = Element('file', id=f"audio_{i}_f")
            _el(afe, 'name', ac['name'])
            _el(afe, 'pathurl',
                'file://' + urllib.parse.quote(ac['path'], safe='/'))
            _el(afe, 'duration', str(ac['frames']))
            afr = SubElement(afe, 'rate')
            _el(afr, 'timebase', str(fps_i))
            afm = SubElement(afe, 'media')
            afa = SubElement(afm, 'audio')
            _el(afa, 'channelcount', str(max(ac.get('audio_ch', 2), 2)))
            aci.append(afe)
            at.append(aci)

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE xmeml>\n' +
            tostring(_prettify(root), encoding='unicode'))


def _prettify(elem, level=0):
    indent = '    '
    i = '\n' + level * indent
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent
        if elem.tail is None: elem.tail = i if level else '\n'
        for child in elem:
            _prettify(child, level + 1)
        if child.tail is None:
            child.tail = i if level else '\n'
    else:
        if level and elem.tail is None:
            elem.tail = i if level else '\n'
    return elem


# ══════════════════════════════════════════════════

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--continue':
        xml_dir = sys.argv[2] if len(sys.argv) > 2 else '.'
        phase2_continue(xml_dir)
        return

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source_dir = sys.argv[1]
    xml_dir = sys.argv[2]

    print('🔍 扫描素材...')
    info = scan(source_dir)
    print(f'   日期: {info["date"]}')
    for cam in sorted(info['video_files']):
        print(f'   [{cam}]: {len(info["video_files"][cam])} clips')
    print(f'   音频: {len(info["audio_files"])}')
    if info['skipped']: print(f'   跳过: {info["skipped"]}')

    info['xml_dir'] = xml_dir
    phase1_import(info)


if __name__ == '__main__':
    main()
