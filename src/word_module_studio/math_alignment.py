"""Map texmath's equation-array separators to native aligned matrix columns.

texmath emits a bare ampersand run for an RL array separator. Word/Writer can
show that literal. A native matrix retains each author cell and its alignment.
Literal symbols with run properties and separators inside nested atoms stay intact.
"""
from lxml import etree as E
from .package import M


def adapt(root):
    records = []
    for array in list(root.iter(M + 'eqArr')):
        rows = []
        for entry in array.findall(M + 'e'):
            cells = [[]]
            for child in list(entry):
                if child.tag == M + 'r' and child.findtext(M + 't') == '&' and child.find(M + 'rPr') is None:
                    cells.append([])
                else: cells[-1].append(child)
            rows.append(cells)
        count = max((len(cells) for cells in rows), default=0)
        if count <= 1: continue
        matrix = E.Element(M + 'm', dict(array.attrib)); props = E.SubElement(matrix, M + 'mPr')
        E.SubElement(props, M + 'baseJc').set(M + 'val', 'center')
        E.SubElement(props, M + 'plcHide').set(M + 'val', 'on')
        columns = E.SubElement(props, M + 'mcs')
        for index in range(count):
            column = E.SubElement(E.SubElement(columns, M + 'mc'), M + 'mcPr')
            E.SubElement(column, M + 'count').set(M + 'val', '1')
            E.SubElement(column, M + 'mcJc').set(M + 'val', 'right' if index % 2 == 0 else 'left')
        for cells in rows:
            row = E.SubElement(matrix, M + 'mr')
            for index in range(count): E.SubElement(row, M + 'e').extend(cells[index] if index < len(cells) else [])
        array.getparent().replace(array, matrix)
        records.append({'operation': 'texmath_alignment_to_native_columns', 'rows': len(rows), 'columns': count,
            'reason': 'Preserve author alignment without displaying texmath separator ampersands'})
    return records
