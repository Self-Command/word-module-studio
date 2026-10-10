"""Reversible outer operator breaks using native OMML; never split nested atoms."""
from copy import deepcopy
import re
from lxml import etree as E
from .package import M
from .migration.math_layout import tree, restore
from .migration.docx_layout import math_width_pt
from .runtime import WordError, require_actions


DEFAULT_STRATEGY = 'outer_array'  # Native m:brk is ignored by pinned LO: run 38052432267.


def wrap(root, budget, size, metrics=None, *, strategy=DEFAULT_STRATEGY):
    require_actions()
    if strategy not in ('native', 'outer_array'): raise WordError('INVALID_MATH_BREAK_STRATEGY')
    if math_width_pt(root, size, metrics) <= budget: return []
    # Existing author arrays/alignment are already a multi-line object and remain exact.
    if any(root.iter(M + 'eqArr')) or root.find(M + 'm') is not None: return []
    before = E.tostring(root, encoding='unicode')
    tokens = []
    depth = 0
    for child in list(root):
        if child.tag != M + 'r': tokens.append(child); continue
        text = child.find(M + 't')
        if text is None: tokens.append(child); continue
        pieces, piece = [], ''
        for character in text.text or '':
            if depth == 0 and character in '=<>≤≥+−-×∧∨' and piece:
                pieces.append(piece); piece = ''
            piece += character
            if character in '([{': depth += 1
            elif character in ')]}': depth = max(0, depth - 1)
        if piece: pieces.append(piece)
        if len(pieces) <= 1: tokens.append(child)
        else:
            for piece in pieces:
                clone = deepcopy(child); clone.find(M + 't').text = piece; tokens.append(clone)
    groups, current = [], []
    for token in tokens:
        literal = token.findtext(M + 't', '') if token.tag == M + 'r' else ''
        if current and re.match(r'^[=<>≤≥+−×∧∨-]', literal): groups.append(current); current = []
        current.append(token)
    if current: groups.append(current)
    rows, row, used = [], [], 0
    for group in groups:
        width = sum(math_width_pt(t, size, metrics) for t in group)
        if row and used + width > budget - 8: rows.append(row); row = []; used = 0
        row.extend(group); used += width
    if row: rows.append(row)
    if len(rows) < 2: return []
    for child in list(root): root.remove(child)
    if strategy == 'native':
        for index, row in enumerate(rows):
            if index:
                first = row[0]
                if first.tag != M + 'r': raise WordError('INVALID_OUTER_MATH_BREAK')
                props = first.find(M + 'rPr')
                if props is None: props = E.Element(M + 'rPr'); first.insert(0, props)
                if props.find(M + 'brk') is None: E.SubElement(props, M + 'brk')
            root.extend(row)
    else:
        array = E.SubElement(root, M + 'eqArr'); props = E.SubElement(array, M + 'eqArrPr')
        E.SubElement(props, M + 'baseJc').set(M + 'val', 'center')
        for row in rows:
            entry = E.SubElement(array, M + 'e')
            if row[0].tag == M + 'r':
                literal = row[0].findtext(M + 't', '')
                if literal and literal[0] in '=<>≤≥+−-×∧∨':
                    # Operator emulator is a native atom, retaining the original symbol.
                    operator = deepcopy(row[0]); operator.find(M + 't').text = literal[0]
                    box = E.SubElement(entry, M + 'box'); prop = E.SubElement(box, M + 'boxPr')
                    E.SubElement(prop, M + 'opEmu').set(M + 'val', '1')
                    E.SubElement(box, M + 'e').append(operator)
                    if len(literal) > 1: row[0].find(M + 't').text = literal[1:]
                    else: row.pop(0)
            entry.extend(row)
    changes = [{'path': [], 'before': before, 'after': E.tostring(root, encoding='unicode'), 'rows': len(rows), 'strategy': strategy}]
    if tree(restore(root, changes)) != tree(E.fromstring(before.encode())): raise WordError('FORMULA_RECOVERY_FAILED')
    return changes
