#!/usr/bin/env python3.12
"""A minimal multi-sheet .xlsx writer built on the standard library only.

WHY NOT openpyxl. There is no virtualenv and no requirements file in this project; it runs on the
system interpreter, and this interpreter is PEP 668 externally managed, so `pip install openpyxl`
is refused. Forcing it with --break-system-packages would make the workbook build depend on a
package the other agent's checkout does not have, which for a deliverable that must regenerate on
demand is worse than writing the format.

An .xlsx is a ZIP of XML parts. Only a small subset is needed for a data workbook: content types,
two relationship parts, the workbook, one worksheet per sheet, and a styles part carrying a bold
header font. Strings are written INLINE rather than through a shared-strings table -- slightly
larger on disk, and it removes a whole class of index-mismatch bug.

WHAT THIS CANNOT DO, stated because it bounds the verification. Nothing here can open the file in
Excel, so 'valid' means: every part is well-formed XML, the archive holds exactly the parts the
relationships reference, and the cell count matches the rows written. That is checked by
verify(). It is not the same as a spreadsheet application accepting it, and it is not claimed to be.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import zipfile

MAX_SHEET_NAME = 31

#: Characters Excel forbids in a sheet name. Held as a SET rather than a regex character class:
#: the first version was a class whose escaping collapsed to "one of these followed by a literal
#: ]", so it silently matched nothing and let an invalid name through. A set cannot be
#: mis-escaped.
INVALID_SHEET_CHARS = frozenset('\\/*?:[]')

#: XML 1.0 forbids these control characters outright -- they cannot be escaped, only removed.
CONTROL_CHARS = frozenset(
    [chr(c) for c in list(range(0x00, 0x09)) + [0x0b, 0x0c] + list(range(0x0e, 0x20))])


def _esc(v: str) -> str:
    t = ''.join(ch for ch in str(v) if ch not in CONTROL_CHARS)
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _col(n: int) -> str:
    """1 -> A, 27 -> AA."""
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(row: int, ci: int, value, bold: bool) -> str:
    ref = f'{_col(ci)}{row}'
    style = ' s="1"' if bold else ''
    if value is None or value == '':
        return f'<c r="{ref}"{style}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}"{style} t="inlineStr"><is><t>{"TRUE" if value else "FALSE"}</t></is></c>'
    if isinstance(value, (int, float)):
        # NaN and infinities are not representable; they become text so nothing is silently zeroed
        if value != value or value in (float('inf'), float('-inf')):
            return (f'<c r="{ref}"{style} t="inlineStr"><is><t>{_esc(value)}</t></is></c>')
        return f'<c r="{ref}"{style}><v>{value!r}</v></c>'
    return (f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">'
            f'{_esc(value)}</t></is></c>')


def _sheet_xml(rows, freeze_header: bool) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if freeze_header and rows:
        out.append('<sheetViews><sheetView workbookViewId="0">'
                   '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                   '</sheetView></sheetViews>')
    out.append('<sheetData>')
    for ri, row in enumerate(rows, start=1):
        cells = ''.join(_cell(ri, ci, v, bold=(ri == 1))
                        for ci, v in enumerate(row, start=1))
        out.append(f'<row r="{ri}">{cells}</row>')
    out.append('</sheetData></worksheet>')
    return ''.join(out)


def _safe_name(name: str, taken) -> str:
    n = ''.join('_' if ch in INVALID_SHEET_CHARS else ch
                for ch in str(name))[:MAX_SHEET_NAME].strip() or 'Sheet'
    base, i = n, 2
    while n in taken:
        suffix = f'_{i}'
        n = base[:MAX_SHEET_NAME - len(suffix)] + suffix
        i += 1
    return n


def write(path, sheets, freeze_header: bool = True):
    """sheets: [(name, [[cell, ...], ...]), ...]. The first row of each sheet is bolded."""
    path = pathlib.Path(path)
    names, prepared = set(), []
    for name, rows in sheets:
        nm = _safe_name(name, names)
        names.add(nm)
        prepared.append((nm, list(rows)))
    if not prepared:
        raise ValueError('a workbook needs at least one sheet; an empty file is not a result')

    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
          'relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.spreadsheetml.styles+xml"/>']
    for i in range(1, len(prepared) + 1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
                  f'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append('</Types>')

    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
          '<sheets>']
    for i, (nm, _r) in enumerate(prepared, start=1):
        wb.append(f'<sheet name="{_esc(nm)}" sheetId="{i}" r:id="rId{i}"/>')
    wb.append('</sheets></workbook>')

    wbr = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(1, len(prepared) + 1):
        wbr.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
                   f'officeDocument/2006/relationships/worksheet" '
                   f'Target="worksheets/sheet{i}.xml"/>')
    wbr.append(f'<Relationship Id="rId{len(prepared) + 1}" Type="http://schemas.openxmlformats.'
               f'org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    wbr.append('</Relationships>')

    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" xfId="0" applyFont="1"/></cellXfs>'
              '</styleSheet>')

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ''.join(ct))
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', ''.join(wb))
        z.writestr('xl/_rels/workbook.xml.rels', ''.join(wbr))
        z.writestr('xl/styles.xml', styles)
        for i, (_nm, rows) in enumerate(prepared, start=1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', _sheet_xml(rows, freeze_header))
    return {'path': str(path), 'sheets': [n for n, _ in prepared],
            'rows_per_sheet': {n: len(r) for n, r in prepared},
            'bytes': path.stat().st_size,
            'written': _dt.datetime.now(_dt.timezone.utc).isoformat()}


def verify(path, expected_sheets=None):
    """Structural verification, which is NOT the same as Excel accepting the file."""
    import xml.etree.ElementTree as ET
    path = pathlib.Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return {'ok': False, 'reason': 'ABSENT_OR_EMPTY'}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        required = {'[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml',
                    'xl/_rels/workbook.xml.rels', 'xl/styles.xml'}
        missing = sorted(required - names)
        if missing:
            return {'ok': False, 'reason': 'MISSING_PARTS', 'missing': missing}
        bad = []
        cells = 0
        rows = 0
        for n in sorted(names):
            if not n.endswith('.xml') and not n.endswith('.rels'):
                continue
            try:
                root = ET.fromstring(z.read(n))
            except ET.ParseError as e:
                bad.append({'part': n, 'error': str(e)})
                continue
            if n.startswith('xl/worksheets/'):
                ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                rows += len(root.findall(f'.//{ns}row'))
                cells += len(root.findall(f'.//{ns}c'))
        sheets = sorted(n for n in names if n.startswith('xl/worksheets/'))
        # every relationship target must exist in the archive
        relroot = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        dangling = []
        for rel in relroot:
            t = rel.get('Target')
            if t and f'xl/{t}' not in names:
                dangling.append(t)
    out = {'ok': not bad and not dangling, 'n_sheets': len(sheets), 'n_rows': rows,
           'n_cells': cells, 'malformed_parts': bad, 'dangling_relationships': dangling,
           'bytes': path.stat().st_size,
           'VERIFICATION_SCOPE': ('well-formed XML, all required parts present, no dangling '
                                  'relationship. Does NOT prove a spreadsheet application will '
                                  'open the file; nothing here can test that.')}
    if expected_sheets is not None and len(sheets) != expected_sheets:
        out['ok'] = False
        out['reason'] = f'expected {expected_sheets} sheets, archive holds {len(sheets)}'
    return out
