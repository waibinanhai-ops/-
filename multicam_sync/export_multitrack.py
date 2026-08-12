#!/usr/bin/env python3
"""
多机位合板 → FCP 7 XML (Resolve 原生格式 + 分轨)
====================================================
采用 Resolve 原生导出的 FCP 7 XML 结构，将不同机位的片段放在不同视频轨道上。
Premiere Pro 可以直接导入并按轨道创建多机位序列。

用法:
  python3 export_multitrack.py <素材文件夹> <XML导出目录>
"""

import os, sys, re, urllib.parse
from xml.etree.ElementTree import Element, SubElement, tostring
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/")
from python_get_resolve import GetResolve

VIDEO_EXTS = {'.mp4','.mov','.mxf','.braw','.r3d','.avi','.mts','.m2t','.m2ts','.mkv','.webm'}
AUDIO_EXTS = {'.wav','.mp3'}
CAM_PATTERN = re.compile(r'^([a-zA-Z])机?$')


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
        raise SystemExit('未找到字母机位')
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
        'video_files': video_files,
        'audio_files': sorted(audio_files), 'skipped': skipped,
    }


def tc_to_frames(tc, fps):
    try:
        parts = str(tc).replace(';',':').split(':')
        if len(parts) == 4:
            return (int(parts[0])*3600+int(parts[1])*60+int(parts[2]))*int(round(fps))+int(parts[3])
    except: pass
    return 0


def resolve_import(resolve, info):
    """Import clips into Resolve and return (project, folder)."""
    pm = resolve.GetProjectManager()
    date = info['date']
    proj = pm.CreateProject(date) or pm.LoadProject(date)
    if not proj:
        raise SystemExit(f'无法加载工程: {date}')
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()
    folder = mp.AddSubFolder(root, date)
    if not folder:
        for sf in root.GetSubFolderList():
            if sf.GetName() == date: folder = sf; break
    mp.SetCurrentFolder(folder)

    existing = folder.GetClipList()
    if existing:
        has_cam = any(c.GetMetadata('Camera #') in 'abcdef' for c in existing[:20])
        if has_cam:
            print(f'  (已有 {len(existing)} 片段, 跳过导入)')
            return proj, folder

    for cam in sorted(info['video_files'].keys()):
        files = info['video_files'][cam]
        if not files: continue
        print(f'  导入 [{cam}]: {len(files)} 个...')
        imported = mp.ImportMedia(files)
        if imported:
            for c in imported:
                if c: c.SetMetadata('Camera #', cam)

    if info['audio_files']:
        print(f'  导入音频: {len(info["audio_files"])} 个...')
        imported = mp.ImportMedia(info['audio_files'])
        if imported:
            for c in imported:
                if c:
                    old = c.GetMetadata('Camera #') or ''
                    if old.strip() and old.strip().lower() not in 'abcdef':
                        c.SetMetadata('Camera #', '')
    return proj, folder


def extract_clips(folder):
    """Extract all clip metadata, grouped by camera."""
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

        # For audio files, calculate frames from Duration if needed
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
            'sample_rate': props.get('Sample Rate', '48000'),
        }
        if cam and cam in 'abcdef':
            cameras[cam].append(data)
        elif ext in AUDIO_EXTS:
            audio.append(data)
    return cameras, audio


# ═══════════════════════════════════════════════════════════
# FCP 7 XML BUILD - Resolve-compatible format, multi-track
# ═══════════════════════════════════════════════════════════

def _el(parent, tag, text=None, **attrs):
    e = SubElement(parent, tag, **attrs)
    if text is not None: e.text = str(text)
    return e


def build_clipitem(clip, idx, timeline_fps, start_frame=0):
    """Build a single clipitem matching Resolve's native format exactly."""
    clip_fps_i = int(round(clip['fps']))
    frames = clip['frames']

    ci = Element('clipitem', id=f"{clip['name']} {idx}")
    _el(ci, 'name', clip['name'])
    _el(ci, 'duration', str(frames))

    r = SubElement(ci, 'rate')
    _el(r, 'timebase', str(int(round(timeline_fps))))
    _el(r, 'ntsc', 'FALSE')

    _el(ci, 'start', str(start_frame))
    _el(ci, 'end', str(start_frame + frames))
    _el(ci, 'enabled', 'TRUE')
    _el(ci, 'in', '0')
    _el(ci, 'out', str(frames))

    # File element (matches Resolve native format)
    fe = Element('file', id=f"{clip['name']} 2")
    _el(fe, 'duration', str(frames))

    fr = SubElement(fe, 'rate')
    _el(fr, 'timebase', str(clip_fps_i))
    _el(fr, 'ntsc', 'FALSE')

    _el(fe, 'name', clip['name'])
    _el(fe, 'pathurl', 'file://' + urllib.parse.quote(clip['path'], safe='/'))

    # Timecode
    ftc = SubElement(fe, 'timecode')
    _el(ftc, 'string', clip['start_tc'])
    _el(ftc, 'displayformat', 'NDF')
    ftcr = SubElement(ftc, 'rate')
    _el(ftcr, 'timebase', str(clip_fps_i))
    _el(ftcr, 'ntsc', 'FALSE')

    # Media
    fm = SubElement(fe, 'media')
    fv = SubElement(fm, 'video')
    _el(fv, 'duration', str(frames))
    sc = SubElement(fv, 'samplecharacteristics')
    _el(sc, 'width', str(clip['width']))
    _el(sc, 'height', str(clip['height']))

    fa = SubElement(fm, 'audio')
    _el(fa, 'channelcount', str(max(clip['audio_ch'], 2)))

    # Attach file element to clipitem
    ci.append(fe)

    # Compositemode (Resolve always includes this)
    _el(ci, 'compositemode', 'normal')

    # Filter with Basic Motion (matching Resolve native export)
    filt = SubElement(ci, 'filter')
    _el(filt, 'enabled', 'TRUE')
    _el(filt, 'start', '0')
    _el(filt, 'end', str(frames))
    eff = SubElement(filt, 'effect')
    _el(eff, 'name', 'Basic Motion')
    _el(eff, 'effectid', 'basic')
    _el(eff, 'effecttype', 'motion')
    _el(eff, 'mediatype', 'video')
    _el(eff, 'effectcategory', 'motion')
    for pname, pid, val, vmin, vmax in [
        ('Scale', 'scale', '100', '0', '10000'),
        ('Rotation', 'rotation', '0', '-100000', '100000'),
    ]:
        param = SubElement(eff, 'parameter')
        _el(param, 'name', pname)
        _el(param, 'parameterid', pid)
        _el(param, 'value', val)
        _el(param, 'valuemin', vmin)
        _el(param, 'valuemax', vmax)
    # Center parameter (has sub-elements)
    param = SubElement(eff, 'parameter')
    _el(param, 'name', 'Center')
    _el(param, 'parameterid', 'center')
    val = SubElement(param, 'value')
    _el(val, 'horiz', '0')
    _el(val, 'vert', '0')
    # Anchor Point parameter
    param = SubElement(eff, 'parameter')
    _el(param, 'name', 'Anchor Point')
    _el(param, 'parameterid', 'anchorPoint')
    val = SubElement(param, 'value')
    _el(val, 'horiz', '0')
    _el(val, 'vert', '0')

    return ci


def build_xml_multitrack(cameras, audio_clips, date_name, timeline_fps=24):
    """
    Build FCP 7 XML in Resolve-native format with separate tracks per camera.
    """
    fps_i = int(round(timeline_fps))

    # Find global sync start (earliest timecode across all clips)
    sync_start = None
    for clips in cameras.values():
        for c in clips:
            fs = tc_to_frames(c['start_tc'], c['fps'])
            if sync_start is None or fs < sync_start:
                sync_start = fs
    if sync_start is None: sync_start = 0

    # Calculate max end frame
    max_end = 0
    for clips in cameras.values():
        for c in clips:
            end_f = tc_to_frames(c['start_tc'], c['fps']) + c['frames']
            if end_f > max_end: max_end = end_f

    # Convert to timeline fps
    total_dur = max_end - sync_start
    if timeline_fps not in (50, 60):
        total_dur = int(total_dur * timeline_fps / 50)  # Approximate conversion

    # ── Root ──
    root = Element('xmeml', version='5')
    seq = SubElement(root, 'sequence')
    _el(seq, 'name', f"{date_name}")
    _el(seq, 'duration', str(total_dur))

    r = SubElement(seq, 'rate')
    _el(r, 'timebase', str(fps_i)); _el(r, 'ntsc', 'FALSE')

    _el(seq, 'in', '-1'); _el(seq, 'out', '-1')

    # Timeline timecode
    tc = SubElement(seq, 'timecode')
    _el(tc, 'string', '01:00:00:00')
    _el(tc, 'frame', str(fps_i * 3600))
    _el(tc, 'displayformat', 'NDF')
    tr = SubElement(tc, 'rate')
    _el(tr, 'timebase', str(fps_i)); _el(tr, 'ntsc', 'FALSE')

    media = SubElement(seq, 'media')
    video = SubElement(media, 'video')

    # ── One track per camera ──
    clip_idx = 0
    for cam_letter in sorted(cameras.keys()):
        clips = sorted(cameras[cam_letter],
                       key=lambda c: tc_to_frames(c['start_tc'], c['fps']))
        if not clips: continue

        track = SubElement(video, 'track')
        cum_start = 0

        for i, clip in enumerate(clips):
            clip_start = tc_to_frames(clip['start_tc'], clip['fps'])
            offset = clip_start - sync_start
            # Convert offset to timeline fps if needed
            if timeline_fps not in (50, 60) and clip['fps'] > 30:
                offset = int(offset * timeline_fps / clip['fps'])

            ci = build_clipitem(clip, clip_idx, timeline_fps, start_frame=offset)
            track.append(ci)
            clip_idx += 1
            cum_start = offset + clip['frames']

    # ── Audio tracks ──
    if audio_clips:
        aud = SubElement(media, 'audio')
        for i, ac in enumerate(audio_clips):
            at = SubElement(aud, 'track')
            aci = Element('clipitem', id=f"audio_{i}")
            _el(aci, 'name', ac['name'])
            _el(aci, 'duration', str(ac['frames']))
            ar = SubElement(aci, 'rate')
            _el(ar, 'timebase', str(fps_i)); _el(ar, 'ntsc', 'FALSE')
            _el(aci, 'start', '0')
            _el(aci, 'end', str(ac['frames']))
            _el(aci, 'enabled', 'TRUE')
            _el(aci, 'in', '0')
            _el(aci, 'out', str(ac['frames']))

            afe = Element('file', id=f"audio_{i}_f")
            _el(afe, 'name', ac['name'])
            _el(afe, 'pathurl', 'file://' + urllib.parse.quote(ac['path'], safe='/'))
            _el(afe, 'duration', str(ac['frames']))
            afr = SubElement(afe, 'rate')
            _el(afr, 'timebase', str(fps_i))

            afm = SubElement(afe, 'media')
            afa = SubElement(afm, 'audio')
            _el(afa, 'channelcount', str(max(ac.get('audio_ch', 2), 2)))
            aci.append(afe)
            at.append(aci)

    return _prettify(root)


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


# ═══════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source_dir, xml_dir = sys.argv[1], sys.argv[2]

    print('🔍 扫描...')
    info = scan(source_dir)
    print(f'   日期: {info["date"]}')
    for cam in sorted(info['video_files']):
        print(f'   [{cam}]: {len(info["video_files"][cam])} clips')
    print(f'   音频: {len(info["audio_files"])}')
    if info['skipped']: print(f'   跳过: {info["skipped"]}')

    print('🔌 连接达芬奇...')
    resolve = GetResolve()
    if not resolve: raise SystemExit('达芬奇未运行')

    print('📥 导入素材...')
    proj, folder = resolve_import(resolve, info)

    print('📊 读取元数据...')
    cameras, audio = extract_clips(folder)
    for cam in sorted(cameras):
        print(f'   [{cam}]: {len(cameras[cam])} clips')
    print(f'   音频: {len(audio)}')

    # Timeline FPS (prefer 25 or 24 for editing-friendly timelines)
    all_fps = [c['fps'] for clips in cameras.values() for c in clips]
    source_fps = max(set(all_fps), key=all_fps.count) if all_fps else 50
    # Use 25fps for 50fps source (half-speed, common offline editing workflow)
    if source_fps >= 50: t_fps = 25
    elif source_fps >= 29: t_fps = int(source_fps)
    else: t_fps = int(source_fps)
    print(f'   时间线帧率: {t_fps}')

    print('📝 生成分轨 FCP 7 XML...')
    xml = build_xml_multitrack(cameras, audio, info['date'], t_fps)
    out = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
    out += tostring(xml, encoding='unicode')

    os.makedirs(xml_dir, exist_ok=True)
    path = os.path.join(xml_dir, f"{info['date']}.xml")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)

    print(f'\n{"="*60}')
    print(f'✅ 完成!')
    print(f'   输出: {path} ({os.path.getsize(path)/1024/1024:.1f} MB)')
    print(f'   轨道: {len(cameras)} 条视频轨 ({", ".join(sorted(cameras.keys()))})')
    print(f'   视频: {sum(len(v) for v in cameras.values())} clips')
    print(f'   音频: {len(audio)} clips')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
