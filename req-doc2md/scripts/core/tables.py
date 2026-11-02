"""Table grid model and renderers for DOCX AST and Excel worksheets."""
from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from . import astutil
from .util import ensure_dir, write_json


@dataclass
class Cell:
    blocks: list = field(default_factory=list)
    rowspan: int = 1
    colspan: int = 1
    text: str = ''
    md: str = ''
    html: str = ''
    is_header: bool = False
    row: int = 0
    col: int = 0


@dataclass
class TableData:
    index: int
    col_count: int
    rows: list[list[Cell]]
    header_rows: int = 1
    caption: str = ''
    merges: list[dict] = field(default_factory=list)
    grid: list[list[Cell | None]] = field(default_factory=list)
    placeholder: str = ''
    format: str = ''
    markdown: str = ''
    csv_path: str = ''
    json_path: str = ''
    warnings: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        meaningful_html = re.compile(r'<(img|table|ul|ol|li|pre|hr)\b', re.I)
        for row in self.grid:
            for cell in row:
                if cell is None:
                    continue
                if (cell.text or '').strip():
                    return False
                if meaningful_html.search(cell.html or ''):
                    return False
        return True

    def is_simple(self) -> bool:
        if self.merges or self.header_rows != 1 or not self.rows:
            return False
        for row in self.rows:
            for cell in row:
                if '\n' in cell.md or '<br>' in cell.md:
                    return False
                for block in cell.blocks:
                    if isinstance(block, dict) and block.get('t') not in ('Para', 'Plain'):
                        return False
        return True


def _cell_from_ast(cell_raw) -> Cell:
    # Cell = [attr, alignment, rowspan, colspan, blocks]
    if not isinstance(cell_raw, list) or len(cell_raw) < 5:
        return Cell(text='', md='', html='')
    rowspan = int(cell_raw[2] or 1)
    colspan = int(cell_raw[3] or 1)
    blocks = cell_raw[4] if isinstance(cell_raw[4], list) else []
    text = astutil.plain_text(blocks).strip()
    return Cell(
        blocks=blocks,
        rowspan=max(1, rowspan),
        colspan=max(1, colspan),
        text=text,
        md=astutil.render_cell_md(blocks).strip(),
        html=astutil.render_blocks_html(blocks).strip(),
    )


def build_grid(rows: list[list[Cell]], col_count: int) -> tuple[list[list[Cell | None]], int, list[dict]]:
    if not rows:
        return [], max(1, col_count), []
    needed = max(
        [col_count]
        + [sum(max(1, cell.colspan) for cell in row) for row in rows]
        + [1]
    )
    grid: list[list[Cell | None]] = [[None] * needed for _ in rows]
    occupied: set[tuple[int, int]] = set()
    merges: list[dict] = []
    seen: set[int] = set()

    for r, row in enumerate(rows):
        col = 0
        for cell in row:
            while (r, col) in occupied and col < needed:
                col += 1
            if col >= needed:
                break
            cell.row = r
            cell.col = col
            rs = max(1, min(cell.rowspan, len(rows) - r))
            cs = max(1, min(cell.colspan, needed - col))
            cell.rowspan = rs
            cell.colspan = cs
            for rr in range(r, r + rs):
                for cc in range(col, col + cs):
                    grid[rr][cc] = cell
                    occupied.add((rr, cc))
            if (rs > 1 or cs > 1) and id(cell) not in seen:
                seen.add(id(cell))
                merges.append({'row': r, 'col': col, 'rowspan': rs, 'colspan': cs})
            col += cs
    return grid, needed, merges


def from_ast_table(node: dict, index: int, header_rows: int = 1) -> TableData:
    c = node.get('c') or []
    col_count = len(c[2]) if len(c) > 2 and isinstance(c[2], list) else 0
    caption = ''
    if len(c) > 1 and isinstance(c[1], list):
        short = c[1][0] if c[1] else None
        long = c[1][1] if len(c[1]) > 1 else None
        caption = astutil.plain_text(long).strip() or (str(short).strip() if short else '')
    raw_rows: list = []
    if len(c) > 3 and isinstance(c[3], list) and len(c[3]) > 1:
        raw_rows.extend(c[3][1] or [])
    if len(c) > 4 and isinstance(c[4], list):
        for body in c[4]:
            if isinstance(body, list) and len(body) > 3:
                raw_rows.extend(body[3] or [])
    rows: list[list[Cell]] = []
    for row_raw in raw_rows:
        cells_raw = row_raw[1] if isinstance(row_raw, list) and len(row_raw) > 1 else []
        rows.append([_cell_from_ast(cell) for cell in cells_raw])
    header_rows = max(0, min(int(header_rows or 0), len(rows)))
    grid, col_count, merges = build_grid(rows, col_count)
    for r, row in enumerate(rows):
        for cell in row:
            cell.is_header = r < header_rows
    return TableData(
        index=index,
        col_count=col_count,
        rows=rows,
        header_rows=header_rows,
        caption=caption,
        merges=merges,
        grid=grid,
    )


def _escape_pipe(text: str) -> str:
    text = (text or '').replace('\r', ' ').replace('\n', '<br>')
    return text.replace('|', '\\|').strip() or ' '


def render_pipe(table: TableData) -> str | None:
    if not table.is_simple() or not table.grid:
        return None
    rows = table.grid
    header = rows[0]
    head = '| ' + ' | '.join(_escape_pipe(cell.md if cell else '') for cell in header) + ' |'
    sep = '| ' + ' | '.join('---' for _ in header) + ' |'
    body = []
    for row in rows[1:]:
        body.append('| ' + ' | '.join(_escape_pipe(cell.md if cell else '') for cell in row) + ' |')
    return '\n'.join([head, sep] + body)


def _cell_html(cell: Cell | None) -> str:
    if cell is None:
        return ''
    if cell.html:
        return cell.html
    return html.escape(cell.text or '').replace('\n', '<br>')


def render_table_html(table: TableData) -> str:
    if not table.grid:
        return ''
    header_rows = max(0, min(table.header_rows, len(table.grid)))
    # A merge crossing the header boundary makes <thead>/<tbody> split invalid; use one tbody.
    crosses = any(cell and cell.row < header_rows < cell.row + cell.rowspan for row in table.grid for cell in row)
    out: list[str] = ['<table>']
    if header_rows and not crosses:
        out.append('<thead>')
        for r in range(header_rows):
            out.append(_render_row(table, r, 'th'))
        out.append('</thead>')
        out.append('<tbody>')
        for r in range(header_rows, len(table.grid)):
            out.append(_render_row(table, r, 'td'))
        out.append('</tbody>')
    else:
        out.append('<tbody>')
        for r in range(len(table.grid)):
            out.append(_render_row(table, r, 'th' if r < header_rows else 'td'))
        out.append('</tbody>')
    out.append('</table>')
    return '\n'.join(out)


def _render_row(table: TableData, r: int, default_tag: str) -> str:
    cells: list[str] = []
    for c in range(table.col_count):
        cell = table.grid[r][c] if r < len(table.grid) and c < len(table.grid[r]) else None
        if cell is None:
            cells.append(f'<{default_tag}></{default_tag}>')
            continue
        if cell.row != r or cell.col != c:
            continue
        attrs = ''
        if cell.rowspan > 1:
            attrs += f' rowspan="{cell.rowspan}"'
        if cell.colspan > 1:
            attrs += f' colspan="{cell.colspan}"'
        tag = 'th' if cell.is_header else default_tag
        cells.append(f'<{tag}{attrs}>{_cell_html(cell)}</{tag}>')
    return '<tr>' + ''.join(cells) + '</tr>'


def render_table_csv(table: TableData, path: str | Path) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in table.grid:
            writer.writerow([(cell.text if cell else '') for cell in row])
    return p


def table_to_json(table: TableData) -> dict:
    cells = []
    seen: set[int] = set()
    for row in table.grid:
        for cell in row:
            if cell is None or id(cell) in seen:
                continue
            seen.add(id(cell))
            cells.append({
                'r': cell.row,
                'c': cell.col,
                'rowspan': cell.rowspan,
                'colspan': cell.colspan,
                'text': cell.text,
                'header': cell.is_header,
            })
    return {
        'id': f'tbl-{table.index:03d}',
        'caption': table.caption,
        'rows': len(table.grid),
        'cols': table.col_count,
        'header_rows': table.header_rows,
        'merges': table.merges,
        'cells': cells,
    }


def write_table_files(table: TableData, tables_dir: str | Path, table_id: str | None = None) -> tuple[Path, Path]:
    tid = table_id or f'tbl-{table.index:03d}'
    d = ensure_dir(tables_dir)
    csv_path = d / f'{tid}.csv'
    json_path = d / f'{tid}.json'
    render_table_csv(table, csv_path)
    write_json(json_path, table_to_json(table))
    return csv_path, json_path


def render_table(table: TableData, mode: str = 'auto') -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if table.is_empty():
        table.format = 'empty'
        table.markdown = '（空表）'
        return table.markdown, table.format, warnings
    fmt = mode
    if mode == 'auto':
        fmt = 'pipe' if table.is_simple() else 'html'
    if fmt == 'pipe':
        text = render_pipe(table)
        if text is None:
            warnings.append(f'表 {table.index} 含合并单元格或块级内容，已自动改用 HTML 表格')
            fmt = 'html'
            text = render_table_html(table)
    elif fmt == 'html':
        text = render_table_html(table)
    else:
        fmt = 'auto'
        text = render_pipe(table) or render_table_html(table)
        fmt = 'pipe' if text.startswith('|') else 'html'
    table.format = fmt
    table.markdown = text
    table.warnings.extend(warnings)
    return text, fmt, warnings


# ---------- Excel ----------

def _value_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S') if (value.hour or value.minute or value.second) else value.strftime('%Y-%m-%d')
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, time):
        return value.strftime('%H:%M:%S')
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f'{value:g}'
    return str(value).replace('\r\n', '\n').replace('\r', '\n').strip()


def _plain_cell(text: str) -> Cell:
    text = text or ''
    return Cell(
        blocks=[],
        text=text,
        md=text.replace('\r', ' ').replace('\n', '<br>'),
        html=html.escape(text).replace('\n', '<br>'),
    )


def _trim_table(table: TableData) -> TableData:
    if not table.grid:
        return table
    nonempty: set[tuple[int, int]] = set()
    for r, row in enumerate(table.grid):
        for c, cell in enumerate(row):
            if cell is not None and cell.text.strip():
                for rr in range(r, min(r + cell.rowspan, len(table.grid))):
                    for cc in range(c, min(c + cell.colspan, table.col_count)):
                        nonempty.add((rr, cc))
    if not nonempty:
        return TableData(index=table.index, col_count=1, rows=[], header_rows=0, caption=table.caption)
    min_r = min(r for r, _ in nonempty)
    max_r = max(r for r, _ in nonempty)
    min_c = min(c for _, c in nonempty)
    max_c = max(c for _, c in nonempty)

    rows_out: list[list[Cell]] = []
    for r in range(min_r, max_r + 1):
        row_cells: list[Cell] = []
        for c in range(min_c, max_c + 1):
            cell = table.grid[r][c]
            if cell is None or cell.row != r or cell.col != c:
                continue
            new = Cell(
                blocks=cell.blocks,
                rowspan=max(1, min(cell.row + cell.rowspan, max_r + 1) - r),
                colspan=max(1, min(cell.col + cell.colspan, max_c + 1) - c),
                text=cell.text,
                md=cell.md,
                html=cell.html,
            )
            row_cells.append(new)
        rows_out.append(row_cells)

    header_rows = max(0, min(table.header_rows - min_r, len(rows_out)))
    if header_rows == 0 and len(rows_out) > 1:
        header_rows = 1
    grid, col_count, merges = build_grid(rows_out, max_c - min_c + 1)
    for r, row in enumerate(rows_out):
        for cell in row:
            cell.is_header = r < header_rows
    return TableData(
        index=table.index,
        col_count=col_count,
        rows=rows_out,
        header_rows=header_rows,
        caption=table.caption,
        merges=merges,
        grid=grid,
    )


def table_from_xlsx(ws, index: int, header_rows: int = 1, max_rows: int = 2000, max_cols: int = 200) -> TableData:
    max_row = min(int(ws.max_row or 0), max_rows)
    max_col = min(int(ws.max_column or 0), max_cols)
    if max_row <= 0 or max_col <= 0:
        return TableData(index=index, col_count=1, rows=[], header_rows=0)
    merged: dict[tuple[int, int], tuple[int, int]] = {}
    covered: set[tuple[int, int]] = set()
    for rng in ws.merged_cells.ranges:
        min_r, min_c = rng.min_row, rng.min_col
        maxr, maxc = min(rng.max_row, max_row), min(rng.max_col, max_col)
        if min_r > maxr or min_c > maxc:
            continue
        merged[(min_r, min_c)] = (maxr - min_r + 1, maxc - min_c + 1)
        for rr in range(min_r, maxr + 1):
            for cc in range(min_c, maxc + 1):
                if (rr, cc) != (min_r, min_c):
                    covered.add((rr, cc))

    rows: list[list[Cell]] = []
    for r in range(1, max_row + 1):
        row_cells: list[Cell] = []
        for c in range(1, max_col + 1):
            if (r, c) in covered:
                continue
            cell = ws.cell(r, c)
            text = _value_text(cell.value)
            rs, cs = merged.get((r, c), (1, 1))
            row_cells.append(Cell(
                blocks=[],
                rowspan=rs,
                colspan=cs,
                text=text,
                md=text.replace('\r', ' ').replace('\n', '<br>'),
                html=html.escape(text).replace('\n', '<br>'),
            ))
        rows.append(row_cells)
    header_rows = 1 if rows and len(rows) > 1 else 0
    grid, col_count, merges = build_grid(rows, max_col)
    for r, row in enumerate(rows):
        for cell in row:
            cell.is_header = r < header_rows
    table = TableData(
        index=index,
        col_count=col_count,
        rows=rows,
        header_rows=header_rows,
        merges=merges,
        grid=grid,
    )
    return _trim_table(table)


def table_from_xlrd(sheet, index: int, header_rows: int = 1) -> TableData:
    import xlrd
    nrows, ncols = sheet.nrows, sheet.ncols
    merged: dict[tuple[int, int], tuple[int, int]] = {}
    covered: set[tuple[int, int]] = set()
    for rlo, rhi, clo, chi in sheet.merged_cells:
        merged[(rlo + 1, clo + 1)] = (rhi - rlo, chi - clo)
        for r in range(rlo, rhi):
            for c in range(clo, chi):
                if (r, c) != (rlo, clo):
                    covered.add((r + 1, c + 1))
    rows: list[list[Cell]] = []
    for r in range(nrows):
        row_cells: list[Cell] = []
        for c in range(ncols):
            if (r + 1, c + 1) in covered:
                continue
            cell = sheet.cell(r, c)
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                text = ''
            elif cell.ctype == xlrd.XL_CELL_DATE:
                try:
                    text = _value_text(xlrd.xldate_as_datetime(cell.value, sheet.book.datemode))
                except Exception:
                    text = str(cell.value)
            elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                text = 'TRUE' if cell.value else 'FALSE'
            elif cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
                text = str(int(cell.value))
            else:
                text = str(cell.value)
            rs, cs = merged.get((r + 1, c + 1), (1, 1))
            row_cells.append(_plain_cell(text))
            row_cells[-1].rowspan = rs
            row_cells[-1].colspan = cs
        rows.append(row_cells)
    header_rows = 1 if rows and len(rows) > 1 else 0
    grid, col_count, merges = build_grid(rows, ncols)
    for r, row in enumerate(rows):
        for cell in row:
            cell.is_header = r < header_rows
    table = TableData(index=index, col_count=col_count, rows=rows, header_rows=header_rows, merges=merges, grid=grid)
    return _trim_table(table)


def workbook_to_markdown(wb, mode: str = 'auto', start_index: int = 1) -> tuple[str, list[TableData], list[str]]:
    parts: list[str] = []
    tables: list[TableData] = []
    warnings: list[str] = []
    idx = start_index
    for ws in wb.worksheets:
        table = table_from_xlsx(ws, idx)
        text, fmt, warns = render_table(table, mode)
        warnings.extend(warns)
        title = ws.title or f'Sheet{idx}'
        parts.append(f'## {title}\n')
        if table.rows:
            parts.append(text + '\n')
        else:
            parts.append('（空工作表）\n')
        tables.append(table)
        idx += 1
    return '\n'.join(parts).strip() + '\n', tables, warnings


def xlrd_workbook_to_markdown(wb, mode: str = 'auto', start_index: int = 1) -> tuple[str, list[TableData], list[str]]:
    parts: list[str] = []
    tables: list[TableData] = []
    warnings: list[str] = []
    idx = start_index
    for sheet_name in wb.sheet_names():
        sheet = wb.sheet_by_name(sheet_name)
        table = table_from_xlrd(sheet, idx)
        text, fmt, warns = render_table(table, mode)
        warnings.extend(warns)
        parts.append(f'## {sheet_name}\n')
        if table.rows:
            parts.append(text + '\n')
        else:
            parts.append('（空工作表）\n')
        tables.append(table)
        idx += 1
    return '\n'.join(parts).strip() + '\n', tables, warnings
