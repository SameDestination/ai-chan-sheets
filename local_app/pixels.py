"""Native-pixel sheets, adapted from lmy414/ai-chan-sheets (CC BY-NC-SA 4.0).

The row layout and white-alpha treatment follow upstream commit
51c15559ac7ebc6bbfb22e1769ba46716f976d5d. Verification below is independent:
it reopens saved files and reconstructs geometry rather than trusting claims.
Original reference illustrations are NOT licensed by this module's license.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import warnings

from PIL import Image, ImageDraw, ImageFont

MAX_ASSET_PIXELS = 25_000_000
MAX_BOARD_PIXELS = 160_000_000
MAX_EDGE = 32_768
DEFAULTS = dict(margin=110, gap_x=56, gap_y=56, pad_x=28,
                label_h=92, cell_bottom=56, title_h=96, header_h=268,
                footer_h=132, target_aspect=1.6, max_memory_mb=2048)


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _manifest_hash(manifest):
    # The export pointer is written only after verification. It cannot participate
    # in its own content hash; all source/approval/selection fields still do.
    return hashlib.sha256(_canonical({k: v for k, v in manifest.items() if k != 'export'})).hexdigest()


def _path(project, relative):
    _need(isinstance(relative, str) and relative and '\\' not in relative
          and ':' not in relative, '文件路径必须是工程内的相对路径')
    rel = PurePosixPath(relative)
    _need(not rel.is_absolute() and '..' not in rel.parts
          and all(part not in ('', '.') for part in rel.parts), '不安全的文件路径')
    root = Path(project).resolve()
    candidate = (root / Path(*rel.parts)).resolve()
    _need(candidate.is_relative_to(root) and candidate != root, '文件超出工程目录')
    return candidate


def _read(path):
    try:
        _need(Path(path).stat().st_size <= 8 * 1024**2, 'JSON 文件超过 8 MiB 上限')
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'无法读取 JSON: {Path(path).name}: {exc}') from exc


def _atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(_canonical(value))
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _save(image, path, format='PNG', **settings):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        image.save(temp, format=format, **settings)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _preview(image, bound):
    factor = min(1.0, bound/max(image.size))
    size = (max(1,round(image.width*factor)), max(1,round(image.height*factor)))
    return image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image.copy()


def _open(path, max_pixels=MAX_ASSET_PIXELS):
    try:
        _need(Path(path).stat().st_size <= (512 if max_pixels > MAX_ASSET_PIXELS else 128) * 1024**2,
              '图像文件超过安全大小上限')
        # The master has an explicit lower bound than Pillow's bomb-error limit.
        # Suppress only its warning locally, after retaining our own hard checks.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', Image.DecompressionBombWarning)
            im = Image.open(path)
        w, h = im.size
        _need(w > 0 and h > 0 and max(w, h) <= MAX_EDGE
              and w * h <= max_pixels, f'图像尺寸超过安全上限: {w} × {h}')
        _need(getattr(im, 'n_frames', 1) == 1, '只接受单帧图像')
        im.load()
        return im
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f'图像损坏或尺寸过大: {Path(path).name}') from exc


def _white(image):
    rgba = image.convert('RGBA')
    bg = Image.new('RGBA', rgba.size, 'white')
    try:
        bg.alpha_composite(rgba)
        return bg.convert('RGB')
    finally:
        rgba.close()
        bg.close()


def _integer(value, name, minimum=0, maximum=MAX_EDGE):
    _need(type(value) is int and minimum <= value <= maximum,
          f'{name} 必须是 {minimum}–{maximum} 之间的整数')
    return value


def _manifest(manifest):
    _need(isinstance(manifest, dict), '制作清单必须是对象')
    sections = manifest.get('sections')
    tasks = manifest.get('tasks')
    _need(isinstance(sections, list) and len(sections) == 4, '必须有四个有序分区')
    _need(isinstance(tasks, list) and tasks and len(tasks) <= 100,
          '任务清单不能为空，最多 100 项')
    groups = [s.get('group') for s in sections]
    _need(all(isinstance(g, str) and g and '/' not in g and '\\' not in g
              and ':' not in g and g not in ('.', '..') for g in groups)
          and len(set(groups)) == 4, '分区名称无效或重复')
    ids = [t.get('id') for t in tasks]
    _need(all(isinstance(tid, str) and tid and '/' not in tid and '\\' not in tid
              and ':' not in tid and tid not in ('.', '..') for tid in ids)
          and len(set(ids)) == len(ids), '任务 ID 无效或重复')
    _need(all(t.get('group') in groups for t in tasks), '任务分区不存在')
    counts = [sum(t['group'] == g for t in tasks) for g in groups]
    _need(all(counts), '最终设定板不能含空分区')
    preset = manifest.get('preset', 'custom')
    _need(preset in ('upstream22', 'custom'), '未知清单预设')
    if preset == 'upstream22':
        _need(counts == [3, 8, 4, 7], '默认预设必须是 3/8/4/7，共 22 项')
    return sections, tasks


def _selected(project, manifest, selected):
    sections, tasks = _manifest(manifest)
    _need(isinstance(selected, list) and len(selected) == len(tasks), '所选素材数与清单不符')
    mapping = manifest.get('selections', {})
    expected = {t['id']: t for t in tasks}
    _need(isinstance(mapping, dict) and set(mapping) == set(expected),
          '每项任务必须显式选择一个已批准版本')
    ids = [a.get('id') for a in selected]
    _need(len(set(ids)) == len(ids) and set(ids) == set(expected), '所选素材遗漏、重复或多余')
    by_id = {a['id']: a for a in selected}
    result = []
    for task in tasks:
        a = by_id[task['id']]
        tid = task['id']
        version = _integer(a.get('version'), 'version', 1, 9999)
        _need(type(mapping[tid]) is int and mapping[tid] == version, f'版本选择不匹配: {tid}')
        _need(a.get('group') == task['group'], f'素材分区不匹配: {tid}')
        image_path = _path(project, a.get('file'))
        rec_path = _path(project, a.get('record_file'))
        _need(image_path.is_file() and rec_path.is_file(), f'素材或生成记录缺失: {tid}')
        record = _read(rec_path)
        _need(record.get('execution_mode') != 'offline_fixture' or manifest.get('example') is True,
              '离线夹具只能进入明确标注的示例工程')
        _need(record.get('status') == 'success'
              and record.get('review_status') == 'approved'
              and not record.get('stale', False), f'素材尚未成功、人工批准或已过期: {tid}')
        _need(record.get('id', record.get('task_id')) == tid
              and record.get('group') == task['group']
              and record.get('version') == version, f'生成记录身份不匹配: {tid}')
        recorded_file = record.get('output', record.get('file'))
        _need(recorded_file == a['file'], f'生成记录路径不匹配: {tid}')
        digest = _hash(image_path)
        _need(digest == a.get('sha256')
              and digest == record.get('output_sha256', record.get('sha256')),
              f'素材哈希不匹配: {tid}')
        with _open(image_path) as im:
            dims = list(im.size)
        _need(dims == [a.get('width'), a.get('height')]
              and dims == record.get('dimensions'), f'素材实际尺寸不匹配: {tid}')
        if 'revision' in record:
            _need(record['revision'] == manifest.get('revision'), f'清单版本已变更: {tid}')
        result.append(dict(id=tid, group=task['group'], label=str(a.get('label') or task.get('label') or tid),
                           file=a['file'], record_file=a['record_file'], sha256=digest,
                           width=dims[0], height=dims[1], version=version))
    _need(len({a['sha256'] for a in result}) == len(result), '存在重复的素材图像')
    _need(len({a['file'] for a in result}) == len(result), '多项任务引用同一个素材文件')
    _need(len({a['record_file'] for a in result}) == len(result), '多项任务引用同一生成记录')
    return result


def _options(options):
    config = DEFAULTS.copy()
    options = options or {}
    _need(isinstance(options, dict) and not (set(options) - set(config) - {'font'}), '未知拼板选项')
    config.update({k: v for k, v in options.items() if k in config})
    for key in ('margin', 'gap_x', 'gap_y', 'pad_x', 'label_h', 'cell_bottom', 'title_h', 'header_h', 'footer_h'):
        _integer(config[key], key, 8, 4096)
    _need(isinstance(config['target_aspect'], (int, float))
          and 1.3 <= config['target_aspect'] <= 2.4, '横版目标宽高比必须在 1.3–2.4')
    _integer(config['max_memory_mb'], 'max_memory_mb', 64, 16384)
    return config


def _font_path(requested=None):
    if requested:
        path = Path(requested)
        _need(path.is_file(), '指定的中文字体不存在')
        return path
    windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
    candidates = [windir / 'Fonts' / 'msyh.ttc', windir / 'Fonts' / 'simhei.ttf',
                  Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
                  Path('/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc')]
    for path in candidates:
        if path.is_file():
            return path
    raise ValueError('缺少中文字体；请安装微软雅黑 / Noto Sans CJK，或显式指定 font 文件')


def _text(draw, xy, text, width, font_path, size=40, fill='#272840'):
    # Use actual measured glyph bounds. Never draw an overflowing caption.
    text = str(text).replace('\n', ' ')
    _need(len(text) <= 4096, '标题过长（最多 4096 字符）')
    for current in range(size, 7, -1):
        font = ImageFont.truetype(str(font_path), current)
        if draw.textlength(text, font=font) <= width:
            draw.text(xy, text, font=font, fill=fill)
            return
    raise ValueError('标题无法在保留文字区内排下；请缩短标题或增加显式边距')


def _available_memory():
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ('total', 'available', 'page_total', 'page_available', 'virtual_total',
                 'virtual_available', 'extended')]
        state = Memory()
        state.length = ctypes.sizeof(state)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return state.available
    try:
        return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    except (AttributeError, OSError, ValueError):
        return None


def _resources(project, w, h, selected, config, require_disk=True):
    _need(max(w, h) <= MAX_EDGE and w * h <= MAX_BOARD_PIXELS,
          f'母版 {w} × {h} 超过安全上限；请显式调整布局或使用自定义分组')
    memory = w * h * 10 + max(a['width'] * a['height'] for a in selected) * 20 + 96 * 1024**2
    disk = w * h * 9 + 128 * 1024**2
    available = _available_memory()
    _need(memory <= config['max_memory_mb'] * 1024**2,
          f'估计需要 {math.ceil(memory / 1024**2)} MiB，超过 max_memory_mb；请释放资源或显式提高限额')
    _need(available is None or memory <= available * .8, '可用内存不足；请关闭其它程序后重试')
    if require_disk:
        _need(shutil.disk_usage(project).free >= disk, '工程磁盘空间不足；请释放空间后重试')
    return dict(memory_bytes=memory, disk_bytes=disk, available_memory_bytes=available,
                max_memory_mb=config['max_memory_mb'], max_board_pixels=MAX_BOARD_PIXELS)


def _layout(selected, sections, config):
    rows = []
    c = config
    for section in sections:
        assets = [a for a in selected if a['group'] == section['group']]
        cw = max(a['width'] for a in assets) + c['pad_x'] * 2
        ch = max(a['height'] for a in assets) + c['label_h'] + c['cell_bottom']
        rows.append((section, assets, cw, ch, len(assets) * cw + (len(assets) - 1) * c['gap_x']))
    block = max(row[4] for row in rows)
    base_w = block + c['margin'] * 2
    base_h = c['header_h'] + sum(c['title_h'] + row[3] for row in rows) + c['gap_y'] * 3 + c['footer_h']
    ratio = base_w / base_h
    w, h = base_w, base_h
    if ratio < 1.3:
        w = math.ceil(h * c['target_aspect'])
    elif ratio > 2.4:
        h = math.ceil(w / c['target_aspect'])
    dx = (w - base_w) // 2
    placements, rendered_sections = [], []
    cursor = c['header_h']
    for section, assets, cw, ch, rw in rows:
        row_start = c['margin'] + dx + (block - rw) // 2
        sec = dict(group=section['group'], title=section.get('title', section['group']),
                   note=section.get('note', ''), y=cursor, count=len(assets))
        cursor += c['title_h']
        for number, asset in enumerate(assets):
            cx = row_start + number * (cw + c['gap_x'])
            x = cx + (cw - asset['width']) // 2
            y = cursor + c['label_h'] + (ch - c['label_h'] - c['cell_bottom'] - asset['height']) // 2
            placements.append(dict(id=asset['id'], group=asset['group'], file=asset['file'],
                                   record_file=asset['record_file'], version=asset['version'],
                                   x=x, y=y, width=asset['width'], height=asset['height'],
                                   scale=1.0, cell=[cx, cursor, cw, ch]))
        sec['crop'] = [max(0, row_start - 40), max(0, sec['y'] - 30),
                       min(w, row_start + rw + 40), cursor + ch + min(30, c['gap_y'])]
        rendered_sections.append(sec)
        cursor += ch + c['gap_y']
    return dict(board_dimensions=[w, h], placements=placements, sections=rendered_sections,
                padding=dict(base_dimensions=[base_w, base_h], horizontal_added=w-base_w,
                             vertical_added=h-base_h, reason='明确增加留白以满足横版宽高比；素材像素保持 1:1'))


def _compose(project: Path, manifest: dict, selected: list[dict], options: dict | None = None) -> dict:
    """Write a new export version; only return verified=True after disk verification."""
    project = Path(project).resolve()
    _need(project.is_dir(), '工程目录不存在')
    assets = _selected(project, manifest, selected)
    config = _options(options)
    font_path = _font_path((options or {}).get('font'))
    geometry = _layout(assets, manifest['sections'], config)
    w, h = geometry['board_dimensions']
    estimates = _resources(project, w, h, assets, config)
    export_root = project / 'exports'
    _need(not export_root.exists() or export_root.resolve().is_relative_to(project), '导出目录超出工程')
    export_root.mkdir(exist_ok=True)
    number = 1
    while (export_root / f'v{number:03d}').exists():
        number += 1
    relative = f'exports/v{number:03d}'
    final = project / relative
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=export_root))
    files = []
    try:
        board = Image.new('RGB', (w, h), 'white')
        try:
            draw = ImageDraw.Draw(board)
            draw.rectangle((0, 0, w, 14), fill='#7361aa')
            _text(draw, (config['margin'], 50), manifest.get('name', '角色设定板'),
                  w - config['margin'] * 2, font_path, size=72)
            _text(draw, (config['margin'], 156), f'{len(assets)} 张独立素材 · 原生像素 1:1 · v{number:03d}',
                  w-config['margin']*2, font_path, size=36, fill='#666b7e')
            for sec in geometry['sections']:
                _text(draw, (config['margin'], sec['y']), sec['title'],
                      w-config['margin']*2, font_path, size=min(48, int(config['title_h']*.42)))
                if sec['note']:
                    _text(draw, (config['margin'], sec['y'] + int(config['title_h']*.6)), sec['note'],
                          w-config['margin']*2, font_path, size=min(26, int(config['title_h']*.27)), fill='#666b7e')
            by_id = {asset['id']: asset for asset in assets}
            for p in geometry['placements']:
                asset = by_id[p['id']]
                cx, cy, cw, ch = p['cell']
                draw.rounded_rectangle((cx, cy, cx+cw-1, cy+ch-1), radius=16,
                                       fill='#fafafd', outline='#e1e2ee', width=2)
                _text(draw, (cx+config['pad_x'], cy+12), asset['label'], cw-config['pad_x']*2,
                      font_path, size=min(42, config['label_h']//2))
                with _open(_path(project, asset['file'])) as original:
                    rgb = _white(original)
                    try:
                        board.paste(rgb, (p['x'], p['y']))
                    finally:
                        rgb.close()
                caption = f"{asset['width']}×{asset['height']} · 1:1"
                _text(draw, (cx+config['pad_x'], cy+ch-config['cell_bottom']+8), caption,
                      cw-config['pad_x']*2, font_path, size=min(26, config['cell_bottom']//2), fill='#666b7e')
            _text(draw, (config['margin'], h-config['footer_h']+30),
                  manifest.get('unseen_design') or '未见结构须另行人工审定；像素核验不代表艺术审核。',
                  w-config['margin']*2, font_path, size=28, fill='#666b7e')
            _save(board, staging/'master.png', compress_level=6)
        finally:
            board.close()
        # Reopen the exact saved master, and process one preview/slice at a time.
        with _open(staging/'master.png', MAX_BOARD_PIXELS) as master:
            for name, bound, kind in [('browse.jpg', 4200, 'browse'), ('overview.jpg', 4000, 'overview')]:
                preview = _preview(master, bound)
                try:
                    _save(preview, staging/name, 'JPEG', quality=90, subsampling=0)
                    files.append(dict(kind=kind, file=f'{relative}/{name}', dimensions=list(preview.size),
                                      sha256=_hash(staging/name)))
                finally:
                    preview.close()
            for i, sec in enumerate(geometry['sections'], 1):
                crop = master.crop(tuple(sec['crop']))
                try:
                    name = f'section-{i:02d}-native.png'
                    _save(crop, staging/name, compress_level=6)
                    files.append(dict(kind='native_slice', group=sec['group'], file=f'{relative}/{name}',
                                      crop=sec['crop'], dimensions=list(crop.size), sha256=_hash(staging/name)))
                    crop.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
                    name = f'section-{i:02d}-preview.jpg'
                    _save(crop, staging/name, 'JPEG', quality=90, subsampling=0)
                    files.append(dict(kind='section_preview', group=sec['group'], file=f'{relative}/{name}',
                                      dimensions=list(crop.size), sha256=_hash(staging/name)))
                finally:
                    crop.close()
        index = dict(schema_version=1, revision=manifest.get('revision'),
                     manifest_sha256=_manifest_hash(manifest),
                     export_version=number, master=f'{relative}/master.png',
                     master_sha256=_hash(staging/'master.png'), assets=assets,
                     config=config, font=font_path.name, estimates=estimates,
                     files=files, original_scale=1.0, **geometry)
        _atomic_json(staging/'layout.json', index)
        result = dict(directory=relative, index=f'{relative}/layout.json',
                      index_sha256=_hash(staging/'layout.json'), master=index['master'],
                      master_sha256=index['master_sha256'], report=f'{relative}/report.json',
                      dimensions=[w,h], estimates=estimates, files=files, verified=False)
        os.replace(staging, final)
        report = verify(project, manifest, assets, result)
        _atomic_json(final/'report.json', report)
        result['verified'] = True
        result['verification'] = report
        return result
    except Exception:
        # Never overwrite/delete an older version or falsely mark a failed one VERIFIED.
        if final.exists() and not (final/'report.json').exists():
            _atomic_json(final/'report.json', dict(verified=False, status='failed'))
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _rect(rect, w, h, description):
    _need(isinstance(rect, list) and len(rect) == 4, f'{description} 矩形无效')
    x, y, rw, rh = [_integer(n, description) for n in rect]
    _need(rw > 0 and rh > 0 and x+rw <= w and y+rh <= h, f'{description} 越界或为空')
    return x, y, rw, rh


def _overlap(a, b):
    return a[0] < b[0]+b[2] and b[0] < a[0]+a[2] and a[1] < b[1]+b[3] and b[1] < a[1]+a[3]


def _verify(project: Path, manifest: dict, selected: list[dict], export: dict) -> dict:
    """Independent verifier: raises ValueError for missing, stale or altered output."""
    project = Path(project).resolve()
    assets = _selected(project, manifest, selected)
    _need(isinstance(export, dict), '导出索引参数无效')
    index_path = _path(project, export.get('index'))
    _need(index_path.is_file() and _hash(index_path) == export.get('index_sha256'), '布局索引哈希不符或缺失')
    idx = _read(index_path)
    _need(idx.get('manifest_sha256') == _manifest_hash(manifest)
          and idx.get('revision') == manifest.get('revision'), '导出对应的清单已过期')
    _need(idx.get('assets') == assets and idx.get('original_scale') == 1.0,
          '索引素材列表与当前选择不一致或已缩放')
    master_path = _path(project, export.get('master'))
    directory = _path(project, export.get('directory'))
    _need(index_path.parent == directory and index_path.name == 'layout.json'
          and master_path.parent == directory
          and master_path.name == 'master.png' and idx.get('master') == export.get('master'),
          '母版选择必须与精确导出索引一致')
    _need(master_path.is_file() and _hash(master_path) == idx.get('master_sha256')
          == export.get('master_sha256'), '母版哈希不符或缺失')
    config = _options(idx.get('config'))
    placements = idx.get('placements')
    sections = idx.get('sections')
    _need(isinstance(placements, list) and len(placements) == len(assets), 'placements 遗漏、重复、多余或为空')
    ordered_ids = [a['id'] for section in manifest['sections'] for a in assets
                   if a['group'] == section['group']]
    _need([p.get('id') for p in placements] == ordered_ids, 'placements 任务对应或顺序不符')
    _need(isinstance(sections, list) and len(sections) == 4, '分区索引不完整')
    _need([s.get('group') for s in sections] == [s['group'] for s in manifest['sections']], '分区顺序或分组不符')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', Image.DecompressionBombWarning)
        with Image.open(master_path) as header:
            header_w,header_h = header.size
    _resources(project,header_w,header_h,assets,config,require_disk=False)
    with _open(master_path, MAX_BOARD_PIXELS) as master:
        _need(master.format == 'PNG' and master.mode == 'RGB', '母版必须是无损 RGB PNG')
        w, h = master.size
        _need([w,h] == idx.get('board_dimensions') == export.get('dimensions'), '母版实际尺寸与索引不符')
        _need(w > h and 1.3 <= w/h <= 2.4, '母版必须横版，宽高比 1.3–2.4')
        # Independently reconstruct all row/cell geometry from actual asset dimensions.
        row_specs = []
        for section in manifest['sections']:
            group_assets = [a for a in assets if a['group'] == section['group']]
            cell_width = max(a['width'] for a in group_assets)+2*config['pad_x']
            cell_height = max(a['height'] for a in group_assets)+config['label_h']+config['cell_bottom']
            row_width = cell_width*len(group_assets)+config['gap_x']*(len(group_assets)-1)
            row_specs.append((group_assets, cell_width, cell_height, row_width))
        block_width = max(spec[3] for spec in row_specs)
        initial_w = block_width+2*config['margin']
        initial_h = config['header_h']+sum(config['title_h']+r[2] for r in row_specs)+3*config['gap_y']+config['footer_h']
        expected_w, expected_h = initial_w, initial_h
        if initial_w/initial_h < 1.3:
            expected_w = math.ceil(initial_h*config['target_aspect'])
        elif initial_w/initial_h > 2.4:
            expected_h = math.ceil(initial_w/config['target_aspect'])
        _need((w,h) == (expected_w,expected_h), '无法从素材尺寸和显式留白重建母版尺寸')
        padding = idx.get('padding', {})
        _need(padding.get('base_dimensions') == [initial_w,initial_h]
              and padding.get('horizontal_added') == w-initial_w
              and padding.get('vertical_added') == h-initial_h, '留白记录与实测几何不一致')
        cursor = config['header_h']
        cells, rectangles, crops = [], [], {}
        by_id = {p['id']:p for p in placements}
        matches = 0
        for sec, spec in zip(sections, row_specs):
            group_assets,cw,ch,rw = spec
            row_x = config['margin']+(w-initial_w)//2+(block_width-rw)//2
            _need(sec.get('y') == cursor and sec.get('count') == len(group_assets), '分区起点或素材数不符')
            top = cursor
            cursor += config['title_h']
            expected_crop = [max(0,row_x-40),max(0,top-30),min(w,row_x+rw+40),cursor+ch+min(30,config['gap_y'])]
            _need(sec.get('crop') == expected_crop, '分区切片范围与实测布局不符')
            crops[sec['group']] = expected_crop
            for order, asset in enumerate(group_assets):
                p = by_id[asset['id']]
                expected_cell = [row_x+order*(cw+config['gap_x']),cursor,cw,ch]
                _need(p.get('cell') == expected_cell, f"格子几何无法重建: {asset['id']}")
                cell = _rect(p['cell'], w,h,'格子')
                rect = _rect([p.get('x'),p.get('y'),p.get('width'),p.get('height')],w,h,'素材')
                x,y,aw,ah = rect
                _need(p.get('file') == asset['file'] and p.get('group') == asset['group']
                      and p.get('record_file') == asset['record_file'] and p.get('version') == asset['version']
                      and p.get('scale') == 1.0 and [aw,ah] == [asset['width'],asset['height']], 'placement 记录、版本、文件、尺寸或 scale 不符')
                _need(x == cell[0]+(cw-aw)//2
                      and y == cursor+config['label_h']+(ch-config['label_h']-config['cell_bottom']-ah)//2,
                      '素材未按原像素在格子里居中')
                _need(x >= cell[0] and y >= cell[1] and x+aw <= cell[0]+cw
                      and y+ah <= cell[1]+ch, '素材超出格子')
                for previous in rectangles:
                    _need(not _overlap(rect,previous), '素材相互重叠')
                for previous in cells:
                    _need(not _overlap(cell,previous), '格子相互重叠')
                rectangles.append(rect)
                cells.append(cell)
                with _open(_path(project,asset['file'])) as image:
                    expected = _white(image)
                    patch = master.crop((x,y,x+aw,y+ah))
                    try:
                        _need(patch.tobytes() == expected.tobytes(), f"母版像素逐字节不一致: {asset['id']}")
                    finally:
                        expected.close()
                        patch.close()
                matches += 1
            cursor += ch+config['gap_y']
        files = idx.get('files')
        _need(isinstance(files,list) and len(files) == 10, '预览或四个原像素切片不完整')
        expected_names = {'browse.jpg','overview.jpg'} | {f'section-{i:02d}-{kind}.{ext}'
            for i in range(1,5) for kind,ext in [('native','png'),('preview','jpg')]}
        _need({PurePosixPath(f.get('file','')).name for f in files} == expected_names, '导出文件重复、遗漏或多余')
        slice_count = 0
        for entry in files:
            path = _path(project,entry.get('file'))
            _need(path.parent == directory and path.is_file() and _hash(path) == entry.get('sha256'), '导出文件缺失或哈希不符')
            if path.name in ('browse.jpg', 'overview.jpg'):
                _need(entry.get('kind') == path.stem, '预览文件类型不匹配')
            else:
                section_number = int(path.name.split('-')[1])
                expected_group = manifest['sections'][section_number-1]['group']
                expected_kind = 'native_slice' if path.suffix == '.png' else 'section_preview'
                _need(entry.get('group') == expected_group and entry.get('kind') == expected_kind,
                      '分区预览或切片与对应分区不匹配')
            with _open(path,MAX_BOARD_PIXELS) as image:
                _need(list(image.size) == entry.get('dimensions'), '导出文件尺寸不符')
                if entry.get('kind') == 'native_slice':
                    box = crops.get(entry.get('group'))
                    _need(box is not None and entry.get('crop') == box and image.format == 'PNG'
                          and image.mode == 'RGB' and list(image.size) == [box[2]-box[0],box[3]-box[1]], '原像素切片范围、格式或尺寸不符')
                    patch = master.crop(tuple(box))
                    try:
                        _need(image.tobytes() == patch.tobytes(), '原像素切片与母版逐字节不一致')
                    finally:
                        patch.close()
                    slice_count += 1
                else:
                    cap = 4200 if entry.get('kind') == 'browse' else 4000
                    _need(image.format == 'JPEG' and max(image.size) <= cap, '浏览预览格式或长边超限')
        _need(slice_count == 4, '必须核验四个原像素切片')
    return dict(status='pass', verified=True, native=export['master'],
                master_sha256=export['master_sha256'], index_sha256=export['index_sha256'],
                dimensions=[w,h], aspect_ratio=round(w/h,6), asset_count=len(assets),
                byte_match=matches, native_slices_verified=slice_count,
                checks=['selected_versions','approved_success_records','one_to_one_mapping',
                        'hashes','actual_dimensions','reconstructed_geometry','bounds',
                        'overlaps','scale_1','saved_master_pixels','native_slice_pixels'],
                artwork_approval='separate human review; pixel verification is not artistic approval')


def compose(project: Path, manifest: dict, selected: list[dict], options: dict | None = None) -> dict:
    try:
        return _compose(project, manifest, selected, options)
    except (OSError, KeyError, TypeError, IndexError, AttributeError, OverflowError, Image.DecompressionBombError) as exc:
        raise ValueError(f'无法生成完整设定板: {exc}') from exc


def verify(project: Path, manifest: dict, selected: list[dict], export: dict) -> dict:
    try:
        return _verify(project, manifest, selected, export)
    except (OSError, KeyError, TypeError, IndexError, AttributeError, OverflowError, Image.DecompressionBombError) as exc:
        raise ValueError(f'独立核验失败: {exc}') from exc
