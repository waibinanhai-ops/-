#!/usr/bin/env python3
"""
全自动多机位合板 → FCP 7 XML 生成器
=====================================
绕过达芬奇 API 限制，直接生成含多机位结构的 FCP 7 XML。

流程:
  1. 扫描素材文件夹 (A机/B机/C机 + CLIP + 音频)
  2. 连接达芬奇 → 创建工程 → 导入素材 → 设置 Camera # → 清除音频 Camera #
  3. 从达芬奇 API 读取所有片段时间码/路径/时长等元数据
  4. 按 Camera # 分组，直接生成含 <multiclip> 的 FCP 7 XML

用法:
  python3 generate_xml.py <素材文件夹> <XML导出目录>
"""

import os, sys, re, urllib.parse
from xml.etree.ElementTree import Element, SubElement, tostring

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
from python_get_resolve import GetResolve

VIDEO_EXTS = {'.mp4','.mov','.mxf','.braw','.r3d','.avi','.mts','.m2t','.m2ts','.mkv','.webm'}
AUDIO_EXTS = {'.wav','.mp3'}
CAM_PATTERN = re.compile(r'^([a-zA-Z])机?$')


# ═══════════════════════════════════════════════════════════════
# FILESYSTEM SCAN
# ═══════════════════════════════════════════════════════════════

def scan(source_dir):
    d = os.path.basename(source_dir.rstrip('/'))
    vd = os.path.join(source_dir, '视频')
    if not os.path.isdir(vd):
        raise SystemExit(f'视频目录不存在: {vd}')

    cameras, skipped = {}, []
    for fn in sorted(os.listdir(vd)):
        fp = os.path.join(vd, fn)
        if not os.path.isdir(fp): continue
        m = CAM_PATTERN.match(fn)
        if m: cameras.setdefault(m.group(1).lower(), []).append(fp)
        else: skipped.append(fn)
    if not cameras:
        raise SystemExit('未找到字母命名的机位文件夹')

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
        'date': d, 'video_dir': vd, 'cameras': cameras,
        'clip_dirs': clip_dirs, 'video_files': video_files,
        'audio_files': sorted(audio_files), 'skipped': skipped,
    }


# ═══════════════════════════════════════════════════════════════
# RESOLVE IMPORT + METADATA EXTRACTION
# ═══════════════════════════════════════════════════════════════

def setup_resolve_project(resolve, info):
    """创建/加载工程，导入素材，设置元数据。返回 (project, dateFolder)。"""
    pm = resolve.GetProjectManager()
    date = info['date']

    proj = pm.CreateProject(date) or pm.LoadProject(date)
    if not proj:
        raise SystemExit(f'无法创建/加载工程: {date}')

    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()

    folder = mp.AddSubFolder(root, date)
    if not folder:
        for sf in root.GetSubFolderList():
            if sf.GetName() == date: folder = sf; break
    if not folder:
        raise SystemExit('无法创建媒体池文件夹')

    mp.SetCurrentFolder(folder)

    # 检查是否已有片断（避免重复导入）
    existing = folder.GetClipList()
    if existing:
        # 检查 Camera # 是否已正确设置
        has_cam = any(
            c.GetMetadata('Camera #') in ('a','b','c','d','e','f')
            for c in existing[:20]
        )
        if has_cam:
            print(f'  (已有 {len(existing)} 个片段，跳过导入)')
            return proj, folder

    # 导入视频素材
    for cam in sorted(info['video_files'].keys()):
        files = info['video_files'][cam]
        if not files: continue
        print(f'  导入 [{cam}]: {len(files)} 个文件...')
        imported = mp.ImportMedia(files)
        if imported:
            for clip in imported:
                if clip: clip.SetMetadata('Camera #', cam)

    # 导入音频
    if info['audio_files']:
        print(f'  导入音频: {len(info["audio_files"])} 个文件...')
        imported = mp.ImportMedia(info['audio_files'])
        if imported:
            for clip in imported:
                if clip:
                    # 清除录音设备自带的 Camera #
                    old = clip.GetMetadata('Camera #') or ''
                    if old.strip() and old.strip().lower() not in 'abcdef':
                        clip.SetMetadata('Camera #', '')

    return proj, folder


def extract_metadata(folder):
    """从媒体池读取所有片段的元数据。"""
    clips = folder.GetClipList()
    cameras = {}
    audio = []

    for clip in clips:
        name = clip.GetName() or 'unknown'
        props = clip.GetClipProperty() or {}
        cam = (clip.GetMetadata('Camera #') or '').strip()

        fps_str = str(props.get('FPS', '24')).split()[0]
        try: fps = float(fps_str)
        except ValueError: fps = 25.0

        frames = int(props.get('Frames', '0') or '0')
        res_str = str(props.get('Resolution', '1920x1080'))
        if 'x' in res_str:
            w, h = map(int, res_str.split('x'))
        else:
            w, h = 1920, 1080

        is_audio = os.path.splitext(name)[1].lower() in AUDIO_EXTS

        # For audio files, calculate duration from Duration string
        if is_audio and frames == 0:
            dur_str = props.get('Duration', '00:00:00:00')
            frames = tc_to_frames(dur_str, fps)

        data = {
            'name': name,
            'path': props.get('File Path', ''),
            'fps': fps,
            'start_tc': props.get('Start TC', '00:00:00:00'),
            'frames': frames,
            'width': w, 'height': h,
            'audio_ch': int(props.get('Audio Ch', '0') or '0'),
            'sample_rate': props.get('Sample Rate', '48000'),
        }

        if cam and cam in 'abcdef':
            cameras.setdefault(cam, []).append(data)
        elif is_audio:
            audio.append(data)
        # else: skip clips that are neither camera video nor external audio

    return cameras, audio


# ═══════════════════════════════════════════════════════════════
# FCP 7 XML GENERATION
# ═══════════════════════════════════════════════════════════════

def tc_to_frames(tc, fps):
    try:
        parts = str(tc).replace(';',':').split(':')
        if len(parts) == 4:
            return (int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])) * int(round(fps)) + int(parts[3])
    except: pass
    return 0


def build_xml(cameras, audio_clips, date_name, timeline_fps):
    fps_i = int(round(timeline_fps))

    # Find the earliest start timecode across all clips as sync reference
    sync_start = None
    for clips in cameras.values():
        for c in clips:
            fs = tc_to_frames(c['start_tc'], c['fps'])
            if sync_start is None or fs < sync_start:
                sync_start = fs
    if sync_start is None:
        sync_start = 0

    # Calculate total timeline duration
    max_dur = 0
    for clips in cameras.values():
        for c in clips:
            end_f = tc_to_frames(c['start_tc'], c['fps']) + c['frames']
            if end_f > max_dur: max_dur = end_f
    total_frames = max_dur - sync_start

    # ── Build XML ──
    root = Element('xmeml', version='5')
    seq = SubElement(root, 'sequence')

    _el(seq, 'name', date_name)
    _el(seq, 'duration', str(total_frames))

    r = SubElement(seq, 'rate')
    _el(r, 'timebase', str(fps_i)); _el(r, 'ntsc', 'FALSE')

    _el(seq, 'in', '-1'); _el(seq, 'out', '-1')

    tc = SubElement(seq, 'timecode')
    _el(tc, 'string', '01:00:00:00')
    _el(tc, 'frame', str(fps_i*3600))
    _el(tc, 'displayformat', 'NDF')
    tr = SubElement(tc, 'rate')
    _el(tr, 'timebase', str(fps_i)); _el(tr, 'ntsc', 'FALSE')

    media = SubElement(seq, 'media')
    video = SubElement(media, 'video')
    track = SubElement(video, 'track')

    # ── Multiclip ──
    mc = SubElement(track, 'clipitem', id='multicam_1')
    _el(mc, 'name', date_name)
    _el(mc, 'duration', str(total_frames))
    mr = SubElement(mc, 'rate')
    _el(mr, 'timebase', str(fps_i)); _el(mr, 'ntsc', 'FALSE')
    _el(mc, 'start', '0'); _el(mc, 'end', str(total_frames))
    _el(mc, 'enabled', 'TRUE')
    _el(mc, 'in', '0'); _el(mc, 'out', str(total_frames))

    multiclip = SubElement(mc, 'multiclip')

    for cam_letter in sorted(cameras.keys()):
        clips = sorted(cameras[cam_letter],
                       key=lambda c: tc_to_frames(c['start_tc'], c['fps']))
        if not clips: continue

        angle = SubElement(multiclip, 'angle',
                           angleid=cam_letter, name=cam_letter)

        cum = 0
        for i, clip in enumerate(clips):
            clip_start = tc_to_frames(clip['start_tc'], clip['fps'])
            # Calculate position relative to sync reference
            # Clips should be placed at their relative timecode offset
            offset = clip_start - sync_start

            ci = SubElement(angle, 'clipitem',
                            id=f"{clip['name']}_{i}")
            _el(ci, 'name', clip['name'])
            _el(ci, 'duration', str(clip['frames']))

            cr = SubElement(ci, 'rate')
            _el(cr, 'timebase', str(int(round(clip['fps']))))
            _el(cr, 'ntsc', 'FALSE')

            _el(ci, 'start', str(offset))
            _el(ci, 'end', str(offset + clip['frames']))
            _el(ci, 'enabled', 'TRUE')
            _el(ci, 'in', '0')
            _el(ci, 'out', str(clip['frames']))

            # File element
            fe = SubElement(ci, 'file', id=f"f_{clip['name']}_{i}")
            _el(fe, 'duration', str(clip['frames']))
            fr = SubElement(fe, 'rate')
            _el(fr, 'timebase', str(int(round(clip['fps']))))
            _el(fr, 'ntsc', 'FALSE')
            _el(fe, 'name', clip['name'])
            _el(fe, 'pathurl',
                'file://' + urllib.parse.quote(clip['path'], safe='/'))

            # File timecode
            ft = SubElement(fe, 'timecode')
            _el(ft, 'string', clip['start_tc'])
            _el(ft, 'displayformat', 'NDF')
            ftr = SubElement(ft, 'rate')
            _el(ftr, 'timebase', str(int(round(clip['fps']))))
            _el(ftr, 'ntsc', 'FALSE')

            # Media info
            fm = SubElement(fe, 'media')
            fv = SubElement(fm, 'video')
            _el(fv, 'duration', str(clip['frames']))
            sc = SubElement(fv, 'samplecharacteristics')
            _el(sc, 'width', str(clip['width']))
            _el(sc, 'height', str(clip['height']))
            fa = SubElement(fm, 'audio')
            _el(fa, 'channelcount', str(max(clip['audio_ch'], 2)))

            # Compositemode for each clipitem
            _el(ci, 'compositemode', 'normal')

            cum = offset + clip['frames']

    _el(multiclip, 'synctype', 'timecode')
    first_cam = sorted(cameras.keys())[0]
    _el(multiclip, 'activevideoangle', first_cam)
    _el(multiclip, 'activeaudioangle', first_cam)
    _el(mc, 'compositemode', 'normal')

    # ── Audio clips ──
    if audio_clips:
        aud_media = SubElement(media, 'audio')
        for i, ac in enumerate(audio_clips):
            at = SubElement(aud_media, 'track')
            aci = SubElement(at, 'clipitem', id=f'audio_{i}')
            _el(aci, 'name', ac['name'])
            _el(aci, 'duration', str(ac['frames']))
            ar = SubElement(aci, 'rate')
            _el(ar, 'timebase', str(fps_i)); _el(ar, 'ntsc', 'FALSE')
            _el(aci, 'enabled', 'TRUE')

            afe = SubElement(aci, 'file', id=f'af_{i}')
            _el(afe, 'name', ac['name'])
            _el(afe, 'pathurl',
                'file://' + urllib.parse.quote(ac['path'], safe='/'))
            _el(afe, 'duration', str(ac['frames']))
            afr = SubElement(afe, 'rate')
            _el(afr, 'timebase',
                str(int(round(ac.get('fps', timeline_fps)))))

            afm = SubElement(afe, 'media')
            afa = SubElement(afm, 'audio')
            _el(afa, 'channelcount', str(max(ac.get('audio_ch', 2), 2)))

    # ── Pretty-print ──
    return _prettify(root)


def _el(parent, tag, text=None, **attrs):
    e = SubElement(parent, tag, **attrs)
    if text is not None: e.text = str(text)
    return e


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
        if elem.tail is None:
            elem.tail = i if level else '\n'
    else:
        if level and elem.tail is None:
            elem.tail = i if level else '\n'
    return elem


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source_dir = sys.argv[1]
    xml_dir = sys.argv[2]

    # 1. Scan
    print('🔍 扫描素材...')
    info = scan(source_dir)
    print(f'   日期: {info["date"]}')
    print(f'   机位: {dict((k, len(v)) for k,v in info["video_files"].items())}')
    print(f'   音频: {len(info["audio_files"])} 个')
    if info['skipped']:
        print(f'   跳过: {info["skipped"]}')

    # 2. Resolve
    print('🔌 连接达芬奇...')
    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')

    print('📥 导入素材...')
    proj, folder = setup_resolve_project(resolve, info)

    # 3. Extract metadata
    print('📊 读取元数据...')
    cameras, audio = extract_metadata(folder)
    for cam in sorted(cameras):
        print(f'   [{cam}]: {len(cameras[cam])} 个片段')
    print(f'   音频: {len(audio)} 个文件')

    # 4. Timeline FPS
    all_fps = [c['fps'] for clips in cameras.values() for c in clips]
    t_fps = max(set(all_fps), key=all_fps.count) if all_fps else 25
    common = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]
    t_fps = min(common, key=lambda r: abs(r - t_fps))
    print(f'   时间线帧率: {t_fps}')

    # 5. Generate XML
    print('📝 生成多机位 FCP 7 XML...')
    xml = build_xml(cameras, audio, info['date'], t_fps)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
    xml_str += tostring(xml, encoding='unicode')

    os.makedirs(xml_dir, exist_ok=True)
    out_path = os.path.join(xml_dir, f"{info['date']}.xml")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    size = os.path.getsize(out_path) / (1024*1024)
    print(f'\n{"="*60}')
    print(f'✅ 完成!')
    print(f'   输出: {out_path} ({size:.1f} MB)')
    print(f'   机位: {", ".join(sorted(cameras.keys()))}')
    print(f'   视频: {sum(len(v) for v in cameras.values())} 片段')
    print(f'   音频: {len(audio)} 文件')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
