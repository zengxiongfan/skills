"""OLE / OOXML embedded-object extraction.

The important cases in Word requirement documents are:
* Package  -> \x01Ole10Native stream with the original file name and bytes
* Excel.Sheet.12 / .8 -> a workbook stored in a CFB package stream
* Word.Document.12 / .8 -> a docx stored in a CFB package stream
* PBrush -> a bitmap preview, Visio -> a raw .vsd
"""
from __future__ import annotations

import io
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .ooxml import W, DocxPackage, OleObject
from .util import ensure_dir, sha256_bytes, unique_stem

CFB_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
END_OF_CHAIN = 0xFFFFFFFE
FREE_SECT = 0xFFFFFFFF
FAT_SECT = 0xFFFFFFFD
DIF_SECT = 0xFFFFFFFC


class CFBError(Exception):
    pass


class CFB:
    """Minimal Compound File Binary reader (sector chains, mini stream)."""

    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 512 or data[:8] != CFB_SIGNATURE:
            raise CFBError('not a CFB file')
        self.sector_size = 1 << struct.unpack('<H', data[30:32])[0]
        self.mini_sector_size = 1 << struct.unpack('<H', data[32:34])[0]
        if self.sector_size not in (512, 4096) or self.mini_sector_size not in (64,):
            raise CFBError('unsupported sector size')
        self.mini_cutoff = struct.unpack('<I', data[56:60])[0]
        self.num_fat = struct.unpack('<I', data[44:48])[0]
        self.first_dir = struct.unpack('<I', data[48:52])[0]
        self.first_minifat = struct.unpack('<I', data[60:64])[0]
        self.num_minifat = struct.unpack('<I', data[64:68])[0]
        self.first_difat = struct.unpack('<I', data[68:72])[0]
        self.num_difat = struct.unpack('<I', data[72:76])[0]
        self.major = struct.unpack('<H', data[26:28])[0]
        self.fat = self._read_fat()
        self.entries = self._read_directory()
        self.root = self.entries[0] if self.entries else None
        self.ministream = b''
        if self.root and self.root['size'] > 0:
            self.ministream = self._read_fat_chain(self.root['start'], self.root['size'])
        self.minifat = self._read_minifat()

    def _sector(self, sid: int) -> bytes:
        off = (sid + 1) * self.sector_size
        return self.data[off:off + self.sector_size]

    def _read_fat(self) -> list[int]:
        difat: list[int] = list(struct.unpack('<109I', self.data[76:76 + 436]))
        sid = self.first_difat
        seen = 0
        while sid not in (END_OF_CHAIN, FREE_SECT) and seen < max(0, self.num_difat):
            sec = self._sector(sid)
            if len(sec) < self.sector_size:
                break
            values = list(struct.unpack(f'<{self.sector_size // 4}I', sec))
            difat.extend(values[:-1])
            sid = values[-1]
            seen += 1
        fat: list[int] = []
        for sid in difat[:max(0, self.num_fat)]:
            if sid in (END_OF_CHAIN, FREE_SECT, FAT_SECT, DIF_SECT):
                continue
            sec = self._sector(sid)
            if len(sec) < self.sector_size:
                break
            fat.extend(struct.unpack(f'<{self.sector_size // 4}I', sec))
        if not fat:
            raise CFBError('empty FAT')
        return fat

    def _read_chain(self, start: int, size: int, table: list[int], sector_reader, max_sector: int | None = None) -> bytes:
        chunks: list[bytes] = []
        sid = start
        total = 0
        seen: set[int] = set()
        while sid not in (END_OF_CHAIN, FREE_SECT) and sid < len(table) and sid not in seen:
            seen.add(sid)
            chunk = sector_reader(sid)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if size and total >= size:
                break
            sid = table[sid]
            if max_sector is not None and len(seen) > max_sector:
                break
        data = b''.join(chunks)
        return data[:size] if size else data

    def _read_fat_chain(self, start: int, size: int) -> bytes:
        return self._read_chain(start, size, self.fat, self._sector)

    def _read_minifat(self) -> list[int]:
        if self.num_minifat <= 0 or self.first_minifat in (END_OF_CHAIN, FREE_SECT):
            return []
        raw = self._read_fat_chain(self.first_minifat, self.num_minifat * self.sector_size)
        if not raw:
            return []
        return list(struct.unpack(f'<{len(raw) // 4}I', raw[:len(raw) // 4 * 4]))

    def _read_mini_chain(self, start: int, size: int) -> bytes:
        chunks: list[bytes] = []
        sid = start
        total = 0
        seen: set[int] = set()
        while sid not in (END_OF_CHAIN, FREE_SECT) and sid not in seen:
            seen.add(sid)
            off = sid * self.mini_sector_size
            chunk = self.ministream[off:off + self.mini_sector_size]
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total >= size:
                break
            if sid >= len(self.minifat):
                break
            sid = self.minifat[sid]
        return b''.join(chunks)[:size]

    def _read_directory(self) -> list[dict]:
        raw = self._read_fat_chain(self.first_dir, 0)
        entries: list[dict] = []
        for off in range(0, len(raw) - 127, 128):
            e = raw[off:off + 128]
            name_len = struct.unpack('<H', e[64:66])[0]
            if name_len <= 0 or name_len > 64:
                entries.append({'name': '', 'type': 0, 'start': 0, 'size': 0})
                continue
            try:
                name = e[:name_len - 2].decode('utf-16-le', errors='replace')
            except Exception:
                name = ''
            obj_type = e[66]
            start = struct.unpack('<I', e[116:120])[0]
            size = struct.unpack('<Q', e[120:128])[0]
            if self.major == 3:
                size &= 0xFFFFFFFF
            entries.append({'name': name, 'type': obj_type, 'start': start, 'size': size})
        return entries

    def read_stream(self, name: str) -> bytes | None:
        target = name.casefold()
        for entry in self.entries:
            if entry['name'].casefold() == target:
                if entry['size'] == 0:
                    return b''
                if entry['size'] < self.mini_cutoff:
                    return self._read_mini_chain(entry['start'], entry['size'])
                return self._read_fat_chain(entry['start'], entry['size'])
        return None


def _valid_zip(data: bytes, must_contain: str | None = None) -> bool:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        if must_contain and must_contain not in names:
            return False
        return True
    except Exception:
        return False


def _find_zip(data: bytes, must_contain: str | None = None) -> bytes | None:
    start = data.find(b'PK\x03\x04')
    if start < 0:
        return None
    end = data.rfind(b'PK\x05\x06')
    if end >= 0:
        end += 22
        try:
            comment_len = struct.unpack('<H', data[end - 2:end])[0]
            end += comment_len
        except Exception:
            end = len(data)
    else:
        end = len(data)
    candidate = data[start:end]
    if _valid_zip(candidate, must_contain):
        return candidate
    # try progressively shorter tails if the EOCD guessing overshot
    for trim in (0, 2, 4, 8, 16, 64, 256):
        candidate = data[start:end - trim] if trim else data[start:end]
        if _valid_zip(candidate, must_contain):
            return candidate
    return None


def _find_bmp(data: bytes) -> bytes | None:
    best: tuple[int, int] | None = None
    for m in re.finditer(b'BM', data):
        pos = m.start()
        if pos + 54 > len(data):
            continue
        size = struct.unpack('<I', data[pos + 2:pos + 6])[0]
        dib = struct.unpack('<I', data[pos + 14:pos + 18])[0]
        if dib not in (12, 40, 52, 56, 108, 124):
            continue
        if size <= 0 or pos + size > len(data):
            continue
        if best is None or size > best[0]:
            best = (size, pos)
    if not best:
        return None
    size, pos = best
    return data[pos:pos + size]


def _find_data_start(data: bytes, start: int) -> int | None:
    candidates: list[tuple[int, int]] = []
    signatures = [
        (b'PK\x03\x04', 0), (b'\x89PNG\r\n\x1a\n', 0), (b'\xff\xd8\xff', 0),
        (b'BM', 14), (b'%PDF', 0), (CFB_SIGNATURE, 0), (b'{\\rtf', 0),
    ]
    for sig, _ in signatures:
        pos = data.find(sig, start)
        if pos >= 0:
            if sig == b'BM':
                if not _find_bmp(data[pos:pos + 54 + 8]):
                    continue
            candidates.append((pos, len(sig)))
    if not candidates:
        return None
    return min(candidates)[0]


def _decode_name(raw: bytes) -> str:
    for enc in ('gbk', 'cp936', 'utf-8', 'latin1'):
        try:
            text = raw.decode(enc)
            if text:
                return text
        except Exception:
            continue
    return raw.decode('latin1', errors='replace')


def parse_ole10native(data: bytes) -> tuple[str | None, bytes | None]:
    stream = None
    try:
        cfb = CFB(data)
        stream = cfb.read_stream('\x01Ole10Native')
    except Exception:
        stream = None
    if not stream:
        return None, None
    try:
        pos = 6
        end = stream.find(b'\x00', pos)
        if end < 0:
            return None, None
        filename = _decode_name(stream[pos:end]).strip()
        pos = end + 1
        end2 = stream.find(b'\x00', pos)
        if end2 >= 0:
            pos = end2 + 1
        data_start = _find_data_start(stream, pos)
        if data_start is None:
            data_start = pos
        payload = stream[data_start:]
        if not payload:
            payload = stream
        return filename or None, payload
    except Exception:
        return None, None


def extract_xlsx(data: bytes) -> tuple[bytes | None, str | None]:
    if data[:4] == b'PK\x03\x04' and _valid_zip(data, 'xl/workbook.xml'):
        return data, 'xlsx'
    try:
        cfb = CFB(data)
        for name in ('package', 'Package'):
            stream = cfb.read_stream(name)
            if stream and stream[:4] == b'PK\x03\x04' and _valid_zip(stream, 'xl/workbook.xml'):
                return stream, 'xlsx'
        for name in ('Workbook', 'Book'):
            stream = cfb.read_stream(name)
            if stream and len(stream) > 8:
                return stream, 'xls'
    except Exception:
        pass
    z = _find_zip(data, 'xl/workbook.xml')
    if z:
        return z, 'xlsx'
    return None, None


def extract_docx(data: bytes) -> bytes | None:
    if data[:4] == b'PK\x03\x04' and _valid_zip(data, 'word/document.xml'):
        return data
    try:
        cfb = CFB(data)
        for name in ('package', 'Package'):
            stream = cfb.read_stream(name)
            if stream and stream[:4] == b'PK\x03\x04' and _valid_zip(stream, 'word/document.xml'):
                return stream
    except Exception:
        pass
    return _find_zip(data, 'word/document.xml')


def extract_bmp(data: bytes) -> bytes | None:
    bmp = _find_bmp(data)
    if bmp:
        return bmp
    try:
        cfb = CFB(data)
        for entry in cfb.entries:
            if entry['name'] and entry['size'] > 0:
                stream = cfb.read_stream(entry['name'])
                if stream:
                    bmp = _find_bmp(stream)
                    if bmp:
                        return bmp
    except Exception:
        pass
    return None


# ---------- attachment orchestration ----------

@dataclass
class AttachmentResult:
    records: list[dict] = field(default_factory=list)
    by_media: dict[str, dict] = field(default_factory=dict)
    image_records: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    next_image_idx: int = 1
    used_names: set[str] = field(default_factory=set)


def _candidate(context: str, content: str | None, number: int) -> str:
    for text in (context, content or ''):
        text = (text or '').strip()
        if not text:
            continue
        text = re.split(r'[，。：:；;,\n]', text)[0].strip()
        text = re.sub(r'(如下|见下[方面]?|见附件|以下附件)$', '', text).strip()
        if len(text) > 2 and not re.match(r'^[\d\s\.\、\(\)（）]+$', text):
            return text[:60]
    return f'附件{number}'


def _docx_first_text(data: bytes) -> str:
    """First meaningful paragraph of an embedded docx, used for naming."""
    try:
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read('word/document.xml'))
    except Exception:
        return ''
    for p in root.iter(W + 'p'):
        text = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        if len(text) > 1 and text not in ('附件', '附件说明') and not re.match(r'^附件\d+$', text):
            return text
    return ''


def _save_image(images_dir: Path, data: bytes, idx: int, suffix: str = '.png') -> str:
    ensure_dir(images_dir)
    name = f'image_{idx}{suffix}'
    (images_dir / name).write_bytes(data)
    return name


def _convert_bmp_to_png(data: bytes) -> bytes | None:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return None


def extract_attachments(
    pkg: DocxPackage,
    assets_dir: str | Path,
    base_name: str,
    options,
    image_start: int = 1,
    used_names: set[str] | None = None,
    depth: int = 0,
) -> AttachmentResult:
    assets_dir = Path(assets_dir)
    images_dir = assets_dir / 'images'
    attachments_dir = assets_dir / 'attachments'
    result = AttachmentResult(next_image_idx=image_start, used_names=used_names or set())
    if depth > getattr(options, 'max_depth', 5):
        result.warnings.append({'code': 'ole_depth', 'message': 'OLE 嵌套超过最大深度，已停止递归'})
        return result

    def add_record(**kwargs) -> dict:
        original = kwargs.get('original_name', '') or ''
        saved = kwargs.get('saved_name', '') or ''
        display = kwargs.get('display_name', '')
        if not display:
            generic = re.match(r'^(附件|图片|对象)\d+(\.|$)', original, re.I)
            display = original if (original and not generic) else (saved or original)
        rec = {
            'id': f'att-{len(result.records) + 1:03d}',
            'rId': kwargs.get('r_id', ''),
            'prog_id': kwargs.get('prog_id', ''),
            'type': kwargs.get('type', 'other'),
            'original_name': original,
            'display_name': display,
            'saved_name': saved,
            'saved_rel': kwargs.get('saved_rel', ''),
            'md_name': kwargs.get('md_name', ''),
            'md_rel': kwargs.get('md_rel', ''),
            'sha256': kwargs.get('sha256', ''),
            'size': kwargs.get('size', 0),
            'status': kwargs.get('status', 'ok'),
            'depth': depth,
            'preview': kwargs.get('preview', ''),
            'is_image': kwargs.get('is_image', False),
        }
        result.records.append(rec)
        preview = rec.get('preview')
        if preview:
            result.by_media[preview] = rec
        return rec

    def save_attachment(name: str, payload: bytes) -> str:
        ensure_dir(attachments_dir)
        (attachments_dir / name).write_bytes(payload)
        return name

    def handle_excel(payload: bytes, original_name: str, ext: str, r_id: str, prog: str, preview: str, context: str, ole_num: int) -> None:
        suffix = ext if ext in ('.xlsx', '.xls') else '.xlsx'
        wb = None
        sheet_names: list[str] = []
        try:
            if suffix == '.xls':
                import xlrd
                wb = xlrd.open_workbook(file_contents=payload)
                sheet_names = list(wb.sheet_names())
            else:
                from openpyxl import load_workbook
                wb = load_workbook(io.BytesIO(payload), data_only=True)
                sheet_names = list(wb.sheetnames)
        except Exception:
            wb = None
        original_stem = Path(original_name).stem
        sheet_name = next((s for s in sheet_names if not re.match(r'^Sheet\d+$', str(s), re.I)), '')
        preferred = original_stem if not re.match(r'^附件\d+$', original_stem) else (sheet_name or '')
        base = unique_stem(_candidate(preferred, context, ole_num), result.used_names)
        saved_name = f'{base}{suffix}'
        save_attachment(saved_name, payload)
        md_name = f'{base}.md'
        md_text = ''
        styles = None
        try:
            if wb is not None:
                if suffix == '.xls':
                    from .tables import xlrd_workbook_to_markdown
                    md_text, _tables, _warns = xlrd_workbook_to_markdown(wb, getattr(options, 'table_format', 'auto'))
                else:
                    from .tables import workbook_to_markdown
                    from .styles import extract_xlsx_styles
                    md_text, _tables, _warns = workbook_to_markdown(wb, getattr(options, 'table_format', 'auto'))
                    styles = extract_xlsx_styles(wb)
                    wb.close()
                (attachments_dir / md_name).write_text(md_text, encoding='utf-8')
                if styles is not None:
                    from .util import write_json
                    write_json(attachments_dir / f'{base}{suffix}.styles.json', styles)
            else:
                raise RuntimeError('工作簿无法打开')
        except Exception as exc:
            result.warnings.append({'code': 'excel_md', 'message': f'Excel 附件转文本失败 {original_name}: {exc}', 'location': saved_name})
        add_record(
            r_id=r_id, prog_id=prog, type='xlsx' if suffix == '.xlsx' else 'xls',
            original_name=original_name, saved_name=saved_name,
            saved_rel=f'{base_name}_files/attachments/{saved_name}',
            md_name=md_name if md_text else '',
            md_rel=f'{base_name}_files/attachments/{md_name}' if md_text else '',
            sha256=sha256_bytes(payload), size=len(payload),
            preview=preview, is_image=False,
        )

    def handle_docx(payload: bytes, original_name: str, r_id: str, prog: str, preview: str, context: str, ole_num: int) -> None:
        content = _docx_first_text(payload)
        original_stem = Path(original_name).stem
        preferred = original_stem if not re.match(r'^附件\d+$', original_stem) else content
        base = unique_stem(_candidate(context, preferred, ole_num), result.used_names)
        saved_name = f'{base}.docx'
        save_attachment(saved_name, payload)
        md_name = f'{base}.md'
        md_text = ''
        try:
            from .convert_docx import convert_docx_bytes_to_md
            md_text, next_idx = convert_docx_bytes_to_md(
                payload, assets_dir, base_name, options, result.next_image_idx, depth + 1, result.used_names
            )
            result.next_image_idx = next_idx
            (attachments_dir / md_name).write_text(md_text, encoding='utf-8')
        except Exception as exc:
            result.warnings.append({'code': 'docx_nested', 'message': f'嵌入 docx 转换失败 {original_name}: {exc}', 'location': saved_name})
        add_record(
            r_id=r_id, prog_id=prog, type='docx',
            original_name=original_name, saved_name=saved_name,
            saved_rel=f'{base_name}_files/attachments/{saved_name}',
            md_name=md_name if md_text else '',
            md_rel=f'{base_name}_files/attachments/{md_name}' if md_text else '',
            sha256=sha256_bytes(payload), size=len(payload),
            preview=preview, is_image=False,
        )

    def handle_doc(payload: bytes, original_name: str, r_id: str, prog: str, preview: str, context: str, ole_num: int) -> None:
        md_text = ''
        docx_bytes = None
        content = ''
        error = None
        try:
            from .convert_docx import convert_doc_bytes_to_docx, convert_docx_bytes_to_md
            docx_bytes = convert_doc_bytes_to_docx(payload, original_name)
            content = _docx_first_text(docx_bytes)
        except Exception as exc:
            error = exc
        preferred = content or Path(original_name).stem
        base = unique_stem(_candidate(context, preferred, ole_num), result.used_names)
        saved_name = f'{base}.doc'
        save_attachment(saved_name, payload)
        md_name = f'{base}.md'
        if docx_bytes is not None:
            try:
                from .convert_docx import convert_docx_bytes_to_md
                md_text, next_idx = convert_docx_bytes_to_md(
                    docx_bytes, assets_dir, base_name, options, result.next_image_idx, depth + 1, result.used_names
                )
                result.next_image_idx = next_idx
                (attachments_dir / md_name).write_text(md_text, encoding='utf-8')
            except Exception as exc:
                error = exc
        if error is not None:
            result.warnings.append({'code': 'doc_convert', 'message': f'旧版 .doc 附件无法转换 {original_name}: {error}', 'location': saved_name})
        add_record(
            r_id=r_id, prog_id=prog, type='doc', original_name=original_name,
            saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
            md_name=md_name if md_text else '',
            md_rel=f'{base_name}_files/attachments/{md_name}' if md_text else '',
            sha256=sha256_bytes(payload), size=len(payload), preview=preview,
        )

    for ole in pkg.iter_ole_objects():
        target = ole.target
        name = f'word/{target}'
        if name not in pkg.names:
            result.warnings.append({'code': 'ole_missing', 'message': f'OLE 目标不存在: {target}'})
            continue
        data = pkg.read(name)
        prog = ole.prog_id or ''
        preview = ole.preview_media or ''
        context = ole.context or ''
        if prog == 'Package':
            original_name, payload = parse_ole10native(data)
            if not original_name or payload is None:
                original_name = f'附件{ole.ole_num}.bin'
                payload = data
            ext = Path(original_name).suffix.lower()
            if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                image_data = payload
                suffix = ext
                if ext == '.bmp':
                    png = _convert_bmp_to_png(payload)
                    if png:
                        image_data, suffix = png, '.png'
                idx = result.next_image_idx
                saved_name = _save_image(images_dir, image_data, idx, suffix)
                result.next_image_idx += 1
                rel = f'{base_name}_files/images/{saved_name}'
                rec = add_record(r_id=ole.r_id, prog_id=prog, type='image', original_name=original_name,
                                 saved_name=saved_name, saved_rel=rel, sha256=sha256_bytes(payload),
                                 size=len(payload), preview=preview, is_image=True)
                result.image_records.append({'id': f'img-{len(result.image_records) + 1:03d}', 'media': preview, 'path': rel, 'alt': original_name})
            elif ext in ('.xlsx', '.xls'):
                handle_excel(payload, original_name, ext, ole.r_id, prog, preview, context, ole.ole_num)
            elif ext == '.docx':
                handle_docx(payload, original_name, ole.r_id, prog, preview, context, ole.ole_num)
            elif ext == '.doc':
                handle_doc(payload, original_name, ole.r_id, prog, preview, context, ole.ole_num)
            else:
                base = unique_stem(_candidate(context, Path(original_name).stem, ole.ole_num), result.used_names)
                saved_name = f'{base}{ext or ".bin"}'
                save_attachment(saved_name, payload)
                add_record(r_id=ole.r_id, prog_id=prog, type=ext.lstrip('.') or 'bin', original_name=original_name,
                           saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                           sha256=sha256_bytes(payload), size=len(payload), preview=preview)
        elif prog.startswith('Excel.Sheet'):
            xdata, kind = extract_xlsx(data)
            if not xdata:
                base = unique_stem(f'附件{ole.ole_num}', result.used_names)
                saved_name = f'{base}.bin'
                save_attachment(saved_name, data)
                result.warnings.append({'code': 'ole_excel', 'message': f'无法从 OLE 提取 Excel: {target}', 'location': saved_name})
                add_record(r_id=ole.r_id, prog_id=prog, type='bin', original_name=saved_name,
                           saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                           sha256=sha256_bytes(data), size=len(data), preview=preview)
            else:
                ext = '.xls' if kind == 'xls' else '.xlsx'
                handle_excel(xdata, f'附件{ole.ole_num}{ext}', ext, ole.r_id, prog, preview, context, ole.ole_num)
        elif prog.startswith('Word.Document'):
            ddata = extract_docx(data)
            if not ddata:
                base = unique_stem(f'附件{ole.ole_num}', result.used_names)
                saved_name = f'{base}.bin'
                save_attachment(saved_name, data)
                result.warnings.append({'code': 'ole_word', 'message': f'无法从 OLE 提取 Word: {target}', 'location': saved_name})
                add_record(r_id=ole.r_id, prog_id=prog, type='bin', original_name=saved_name,
                           saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                           sha256=sha256_bytes(data), size=len(data), preview=preview)
            else:
                handle_docx(ddata, f'附件{ole.ole_num}.docx', ole.r_id, prog, preview, context, ole.ole_num)
        elif prog == 'PBrush':
            bmp = extract_bmp(data)
            if bmp:
                png = _convert_bmp_to_png(bmp)
                image_data = png or bmp
                suffix = '.png' if png else '.bmp'
                idx = result.next_image_idx
                saved_name = _save_image(images_dir, image_data, idx, suffix)
                result.next_image_idx += 1
                rel = f'{base_name}_files/images/{saved_name}'
                add_record(r_id=ole.r_id, prog_id=prog, type='image', original_name=f'图片{ole.ole_num}',
                           saved_name=saved_name, saved_rel=rel, sha256=sha256_bytes(bmp),
                           size=len(bmp), preview=preview, is_image=True)
                result.image_records.append({'id': f'img-{len(result.image_records) + 1:03d}', 'media': preview, 'path': rel, 'alt': f'图片{ole.ole_num}'})
            else:
                base = unique_stem(f'图片{ole.ole_num}', result.used_names)
                saved_name = f'{base}.bin'
                save_attachment(saved_name, data)
                result.warnings.append({'code': 'ole_brush', 'message': f'无法从 PBrush 提取 BMP: {target}', 'location': saved_name})
                add_record(r_id=ole.r_id, prog_id=prog, type='bin', original_name=saved_name,
                           saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                           sha256=sha256_bytes(data), size=len(data), preview=preview)
        elif prog.startswith('Visio.'):
            base = unique_stem(_candidate(context, None, ole.ole_num), result.used_names)
            saved_name = f'{base}.vsd'
            save_attachment(saved_name, data)
            add_record(r_id=ole.r_id, prog_id=prog, type='vsd', original_name=f'附件{ole.ole_num}.vsd',
                       saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                       sha256=sha256_bytes(data), size=len(data), preview=preview)
        else:
            base = unique_stem(_candidate(context, None, ole.ole_num), result.used_names)
            saved_name = f'{base}.bin'
            save_attachment(saved_name, data)
            result.warnings.append({'code': 'ole_unknown', 'message': f'未知 OLE ProgID: {prog or "(空)"}，原件已保留', 'location': saved_name})
            add_record(r_id=ole.r_id, prog_id=prog, type='bin', original_name=saved_name,
                       saved_name=saved_name, saved_rel=f'{base_name}_files/attachments/{saved_name}',
                       sha256=sha256_bytes(data), size=len(data), preview=preview)

    return result
