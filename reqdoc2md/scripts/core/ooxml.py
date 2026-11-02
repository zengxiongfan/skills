"""OOXML package inspection: relationships, OLE objects and table metadata."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
O = '{urn:schemas-microsoft-com:office:office}'
V = '{urn:schemas-microsoft-com:vml}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


@dataclass
class Relationship:
    r_id: str
    type: str
    target: str
    mode: str = ''


@dataclass
class OleObject:
    index: int
    r_id: str
    prog_id: str
    target: str
    ole_num: int
    context: str = ''
    preview_r_id: str | None = None
    preview_media: str | None = None


@dataclass
class TableMeta:
    index: int
    depth: int
    rows: int
    cols: int
    header_rows: int
    grid_span: int
    v_merge_restart: int
    v_merge_continue: int
    caption: str = ''
    has_nested_table: bool = False


@dataclass
class PackageStats:
    embeddings: int = 0
    media: int = 0
    tables: int = 0
    top_tables: int = 0
    grid_span: int = 0
    v_merge_restart: int = 0
    v_merge_continue: int = 0
    comments: int = 0
    insertions: int = 0
    deletions: int = 0
    textboxes: int = 0
    headers: int = 0
    footers: int = 0
    colors: int = 0
    highlights: int = 0
    underlines: int = 0
    shadings: int = 0
    hidden: int = 0
    strikes: int = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


class DocxPackage:
    """Read-only view over a .docx package."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.z = zipfile.ZipFile(self.path)
        self.names = self.z.namelist()
        if 'word/document.xml' not in self.names:
            raise ValueError(f'不是有效的 docx（缺少 word/document.xml）: {self.path}')
        self.document_xml = self.z.read('word/document.xml')
        self.root = ET.fromstring(self.document_xml)
        self.rels = self._load_rels()
        self.parent = {child: parent for parent in self.root.iter() for child in parent}
        self.order = {id(elem): i for i, elem in enumerate(self.root.iter())}
        self._ole_cache: list[OleObject] | None = None
        self._table_cache: list[TableMeta] | None = None
        self._stats: PackageStats | None = None
        self._list_cache: list[dict] | None = None

    def close(self) -> None:
        try:
            self.z.close()
        except Exception:
            pass

    def __enter__(self) -> 'DocxPackage':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- package access ----------

    def has(self, name: str) -> bool:
        return name in self.names

    def read(self, name: str) -> bytes:
        return self.z.read(name)

    def _load_rels(self) -> dict[str, Relationship]:
        rels: dict[str, Relationship] = {}
        name = 'word/_rels/document.xml.rels'
        if name not in self.names:
            return rels
        try:
            root = ET.fromstring(self.z.read(name))
        except Exception:
            return rels
        for rel in root:
            rid = rel.get('Id')
            if not rid:
                continue
            rels[rid] = Relationship(
                r_id=rid,
                type=(rel.get('Type') or '').split('/')[-1],
                target=rel.get('Target') or '',
                mode=rel.get('TargetMode') or '',
            )
        return rels

    def rel_target(self, r_id: str) -> str | None:
        rel = self.rels.get(r_id)
        if not rel or rel.mode == 'External':
            return None
        return rel.target

    # ---------- OLE ----------

    def _ole_contexts(self) -> dict[str, str]:
        contexts: dict[str, str] = {}
        last_text = ''
        last_para = ''
        for elem in self.root.iter():
            if elem.tag == W + 'p':
                last_para = ''
            elif elem.tag == W + 't':
                if elem.text:
                    text = elem.text.strip()
                    if text:
                        last_text = text
                        last_para += text
            elif elem.tag == O + 'OLEObject':
                rid = elem.get(R + 'id')
                if rid:
                    contexts[rid] = (last_para or last_text).strip()
        return contexts

    def iter_ole_objects(self) -> list[OleObject]:
        if self._ole_cache is not None:
            return self._ole_cache

        found: dict[str, dict] = {}

        def preview_from_container(container) -> tuple[str | None, str | None]:
            img = container.find('.//' + V + 'imagedata')
            if img is not None:
                rid = img.get(R + 'id')
            else:
                blip = container.find('.//' + A + 'blip')
                rid = blip.get(R + 'embed') if blip is not None else None
            if not rid:
                return None, None
            target = self.rel_target(rid)
            return rid, Path(target).name if target else None

        for tag in (W + 'object', W + 'pict'):
            for container in self.root.iter(tag):
                ole = container.find('.//' + O + 'OLEObject')
                if ole is None:
                    continue
                rid = ole.get(R + 'id')
                if not rid:
                    continue
                preview_r, preview_media = preview_from_container(container)
                found[rid] = {
                    'prog_id': ole.get('ProgID') or '',
                    'preview_r_id': preview_r,
                    'preview_media': preview_media,
                }

        # OLE objects not wrapped in an object/pict container
        for ole in self.root.iter(O + 'OLEObject'):
            rid = ole.get(R + 'id')
            if not rid or rid in found:
                continue
            found[rid] = {
                'prog_id': ole.get('ProgID') or '',
                'preview_r_id': None,
                'preview_media': None,
            }

        contexts = self._ole_contexts()
        objects: list[OleObject] = []
        order: list[tuple[int, str]] = []
        for rid in found:
            rel = self.rels.get(rid)
            if not rel or rel.type not in ('oleObject', 'package'):
                continue
            target = rel.target
            if not target or 'embeddings/' not in target:
                continue
            m = re.search(r'oleObject(\d+)', target)
            ole_num = int(m.group(1)) if m else 0
            # locate document order via the <o:OLEObject> element
            pos = 10 ** 9
            for elem in self.root.iter(O + 'OLEObject'):
                if elem.get(R + 'id') == rid:
                    pos = self.order.get(id(elem), pos)
                    break
            order.append((pos, rid))
        order.sort()
        for index, (_, rid) in enumerate(order, 1):
            rel = self.rels[rid]
            info = found[rid]
            m = re.search(r'oleObject(\d+)', rel.target)
            objects.append(OleObject(
                index=index,
                r_id=rid,
                prog_id=info['prog_id'],
                target=rel.target,
                ole_num=int(m.group(1)) if m else index,
                context=(contexts.get(rid) or '').strip(),
                preview_r_id=info['preview_r_id'],
                preview_media=info['preview_media'],
            ))
        self._ole_cache = objects
        return objects

    # ---------- tables ----------

    def iter_tables(self) -> list[TableMeta]:
        if self._table_cache is not None:
            return self._table_cache
        metas: list[TableMeta] = []

        def node_text(elem) -> str:
            return ''.join(t.text or '' for t in elem.iter(W + 't')).strip()

        def previous_paragraph_caption(tbl) -> str:
            parent = self.parent.get(tbl)
            if parent is None:
                return ''
            siblings = list(parent)
            try:
                idx = siblings.index(tbl)
            except ValueError:
                return ''
            for prev in reversed(siblings[:idx]):
                if prev.tag == W + 'p':
                    text = node_text(prev)
                    if text and re.match(r'^(表|表\s*\d|Table)', text):
                        return text[:120]
                    if text:
                        return ''
                elif prev.tag in (W + 'tbl',):
                    break
            return ''

        def walk(elem, depth: int) -> None:
            for child in list(elem):
                if child.tag == W + 'tbl':
                    rows = child.findall(W + 'tr')
                    grid_cols = child.findall(f'{W}tblGrid/{W}gridCol')
                    col_count = len(grid_cols)
                    if not col_count:
                        col_count = max((len(tr.findall(W + 'tc')) for tr in rows), default=0)
                    grid_span = 0
                    vm_restart = 0
                    vm_continue = 0
                    header_rows = 0
                    for tr in rows:
                        tr_pr = tr.find(W + 'trPr')
                        if tr_pr is not None and tr_pr.find(W + 'tblHeader') is not None:
                            header_rows += 1
                        for tc in tr.findall(W + 'tc'):
                            tc_pr = tc.find(W + 'tcPr')
                            if tc_pr is None:
                                continue
                            gs = tc_pr.find(W + 'gridSpan')
                            if gs is not None:
                                # one gridSpan element = one horizontally merged cell,
                                # regardless of how many columns it spans
                                grid_span += 1
                            vm = tc_pr.find(W + 'vMerge')
                            if vm is not None:
                                val = vm.get(W + 'val') or 'continue'
                                if val == 'restart':
                                    vm_restart += 1
                                else:
                                    vm_continue += 1
                    caption = ''
                    cap_el = child.find(f'{W}tblPr/{W}tblCaption')
                    if cap_el is not None:
                        caption = (cap_el.get(W + 'val') or '').strip()
                    if not caption:
                        caption = previous_paragraph_caption(child)
                    has_nested = any(
                        sub.tag == W + 'tbl' for tr in rows for tc in tr.findall(W + 'tc') for sub in tc.iter()
                    )
                    metas.append(TableMeta(
                        index=len(metas) + 1,
                        depth=depth,
                        rows=len(rows),
                        cols=col_count,
                        header_rows=header_rows,
                        grid_span=grid_span,
                        v_merge_restart=vm_restart,
                        v_merge_continue=vm_continue,
                        caption=caption,
                        has_nested_table=has_nested,
                    ))
                    walk(child, depth + 1)
                else:
                    walk(child, depth)

        walk(self.root, 0)
        self._table_cache = metas
        return metas

    # ---------- list items ----------

    def _numbering_indents(self) -> dict[tuple[str, str], int]:
        """Map (numId, ilvl) to the left indent from word/numbering.xml."""
        if 'word/numbering.xml' not in self.names:
            return {}
        try:
            root = ET.fromstring(self.z.read('word/numbering.xml'))
        except Exception:
            return {}
        nums: dict[str, str] = {}
        for num in root.findall(W + 'num'):
            nid = num.get(W + 'numId')
            aid = num.find(W + 'abstractNumId')
            if nid and aid is not None:
                nums[nid] = aid.get(W + 'val') or ''
        abstract: dict[str, dict[str, int]] = {}
        for an in root.findall(W + 'abstractNum'):
            aid = an.get(W + 'abstractNumId') or ''
            levels: dict[str, int] = {}
            for lvl in an.findall(W + 'lvl'):
                ilvl = lvl.get(W + 'ilvl') or '0'
                ind = lvl.find(f'{W}pPr/{W}ind')
                if ind is None:
                    continue
                left = ind.get(W + 'left')
                if left is None:
                    left = ind.get(W + 'leftChars')
                try:
                    if left is not None:
                        levels[ilvl] = int(left)
                except ValueError:
                    pass
            abstract[aid] = levels
        out: dict[tuple[str, str], int] = {}
        for nid, aid in nums.items():
            for ilvl, left in abstract.get(aid, {}).items():
                out[(nid, ilvl)] = left
        return out

    def iter_list_items(self) -> list[dict]:
        """List paragraphs carrying Word numbering, with their visual left indent."""
        if self._list_cache is not None:
            return self._list_cache
        indents = self._numbering_indents()
        items: list[dict] = []
        gap = 0
        for p in self.root.iter(W + 'p'):
            ancestors = []
            cur = p
            while cur in self.parent:
                cur = self.parent[cur]
                ancestors.append(cur.tag)
                if cur.tag == W + 'tbl':
                    break
            if W + 'tbl' in ancestors:
                continue
            ppr = p.find(W + 'pPr')
            if ppr is None:
                continue
            num_pr = ppr.find(W + 'numPr')
            if num_pr is None:
                text = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
                if text:
                    gap += 1
                continue
            num_id_el = num_pr.find(W + 'numId')
            ilvl_el = num_pr.find(W + 'ilvl')
            num_id = (num_id_el.get(W + 'val') if num_id_el is not None else '') or ''
            ilvl = (ilvl_el.get(W + 'val') if ilvl_el is not None else '0') or '0'
            text = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
            if not text:
                continue
            left = None
            ind = ppr.find(W + 'ind')
            if ind is not None:
                left = ind.get(W + 'left')
            if left is None:
                left = indents.get((num_id, ilvl))
            try:
                left_int = int(left) if left is not None else None
            except ValueError:
                left_int = None
            if left_int is None:
                continue
            items.append({'text': text, 'num_id': num_id, 'ilvl': ilvl, 'left': left_int, 'gap': gap})
            gap = 0
        self._list_cache = items
        return items

    # ---------- stats ----------

    def stats(self) -> PackageStats:
        if self._stats is not None:
            return self._stats
        st = PackageStats()
        st.embeddings = len([n for n in self.names if n.startswith('word/embeddings/') and not n.endswith('/')])
        st.media = len([n for n in self.names if n.startswith('word/media/') and not n.endswith('/')])
        metas = self.iter_tables()
        st.tables = len(metas)
        st.top_tables = len([m for m in metas if m.depth == 0])
        st.grid_span = sum(m.grid_span for m in metas)
        st.v_merge_restart = sum(m.v_merge_restart for m in metas)
        st.v_merge_continue = sum(m.v_merge_continue for m in metas)
        st.insertions = len([
            e for e in self.root.iter(W + 'ins')
            if ''.join(t.text or '' for t in e.iter(W + 't')).strip()
        ])
        st.deletions = len([
            e for e in self.root.iter(W + 'del')
            if ''.join(t.text or '' for t in e.iter(W + 'delText')).strip()
        ])
        st.textboxes = len(list(self.root.iter(W + 'txbxContent')))
        st.headers = len([n for n in self.names if re.match(r'word/header\d+\.xml$', n)])
        st.footers = len([n for n in self.names if re.match(r'word/footer\d+\.xml$', n)])
        st.colors = len(re.findall(r'<w:color\s', self.document_xml.decode('utf-8', errors='replace')))
        st.highlights = len(re.findall(r'<w:highlight\s', self.document_xml.decode('utf-8', errors='replace')))
        st.underlines = len(re.findall(r'<w:u\s', self.document_xml.decode('utf-8', errors='replace')))
        st.shadings = len(re.findall(r'<w:shd\s', self.document_xml.decode('utf-8', errors='replace')))
        st.hidden = len(re.findall(r'<w:vanish', self.document_xml.decode('utf-8', errors='replace')))
        st.strikes = len(re.findall(r'<w:strike', self.document_xml.decode('utf-8', errors='replace')))
        st.comments = 0
        if 'word/comments.xml' in self.names:
            try:
                croot = ET.fromstring(self.z.read('word/comments.xml'))
                st.comments = len(list(croot.iter(W + 'comment')))
            except Exception:
                pass
        self._stats = st
        return st
