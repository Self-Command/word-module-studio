"""One Pandoc-to-OMML chain; no silent FormulaParser or image fallback."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from lxml import etree as E
from .runtime import require_actions, WordError, run
from .package import Package, M, W, NS
from .context import LayoutContext
from .migration.math_layout import tree, wrap, restore
from .migration.docx_layout import math_width_pt
from .migration.semantic_import import normalize_aligned


def convert(formula, mode='display'):
    require_actions()
    if mode not in ('inline', 'display'): raise WordError('INVALID_MATH_MODE')
    formula = normalize_aligned(formula)
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        ast = json.loads(run(['pandoc', '-f', 'markdown', '-t', 'json'], input_text='placeholder'))
        ast['blocks'] = [{'t': 'Para', 'c': [{'t': 'Math', 'c': [{'t': 'DisplayMath' if mode == 'display' else 'InlineMath'}, formula]}]}]
        native = folder / 'formula.docx'
        run(['pandoc', '-f', 'json', '-t', 'docx', '-o', native], input_text=json.dumps(ast))
        package = Package(native)
        matches = list(package.xml('word/document.xml').iter(M + 'oMath'))
        if len(matches) != 1: raise WordError('FORMULA_CONVERSION_FAILED', formula)
        return deepcopy(matches[0])


def apply(package, item, props, *, metrics=None):
    require_actions()
    allowed = {'formula', 'mode', 'number', 'number_width_twips', 'size_pt', 'wrap', 'operation'}
    if set(props) - allowed: raise WordError('MATH_PROPERTY_UNSUPPORTED')
    target = item['element']
    mode = props.get('mode', 'display')
    formula = convert(props['formula'], mode)
    context = LayoutContext.resolve(package, item)
    size = props.get('size_pt', 10)
    number_width = props.get('number_width_twips', 600) if props.get('number') else 0
    budget = (min(context.column_widths_twips) - number_width) / 20 - 8
    if budget <= 0: raise WordError('EQUATION_NUMBER_REGION_TOO_WIDE')
    original = tree(formula)
    changes = wrap(formula, budget, size, metrics=metrics) if props.get('wrap', True) else []
    if tree(restore(formula, changes)) != original: raise WordError('FORMULA_RECOVERY_FAILED')
    if math_width_pt(formula, size, metrics) > budget + 0.1: raise WordError('FORMULA_CANNOT_FIT', str(props.get('number', 'unlabelled')))
    if mode == 'inline':
        if target.tag != W + 'p': raise WordError('INLINE_MATH_REQUIRES_PARAGRAPH')
        target.append(formula)
    else:
        p = E.Element(W + 'p')
        ppr = E.SubElement(p, W + 'pPr')
        E.SubElement(ppr, W + 'keepLines')
        if not props.get('number'):
            E.SubElement(ppr, W + 'jc').set(W + 'val', 'center')
            display = E.SubElement(p, M + 'oMathPara')
            display.append(formula)
        elif any(formula.iter(M + 'eqArr')) or len(list(formula.iter(M + 'mr'))) > 1:
            table = _equation_table(formula, '(' + str(props['number']) + ')', min(context.column_widths_twips), number_width)
            _append(target, table)
            return {'original_math': original, 'changes': changes, 'mode': mode, 'number': props['number'], 'layout': 'centered-multiline', 'budget_pt': budget}
        else:
            tabs = E.SubElement(ppr, W + 'tabs')
            center = E.SubElement(tabs, W + 'tab'); center.set(W + 'val', 'center'); center.set(W + 'pos', str((min(context.column_widths_twips) - number_width) // 2))
            right = E.SubElement(tabs, W + 'tab'); right.set(W + 'val', 'right'); right.set(W + 'pos', str(min(context.column_widths_twips)))
            E.SubElement(E.SubElement(p, W + 'r'), W + 'tab')
            p.append(formula)
            E.SubElement(E.SubElement(p, W + 'r'), W + 'tab')
            E.SubElement(E.SubElement(p, W + 'r'), W + 't').text = '(' + str(props['number']) + ')'
        _append(target, p)
    return {'original_math': original, 'changes': changes, 'mode': mode, 'number': props.get('number'), 'budget_pt': budget}


def _append(target, node):
    if target.tag == W + 'body':
        section = target.find(W + 'sectPr')
        target.insert(list(target).index(section), node) if section is not None else target.append(node)
    elif target.tag in (W + 'sdtContent', W + 'tc'): target.append(node)
    elif target.getparent() is not None: target.addnext(node)
    else: raise WordError('MATH_TARGET_UNSUPPORTED')


def _equation_table(formula, number, width, number_width):
    table = E.Element(W + 'tbl')
    props = E.SubElement(table, W + 'tblPr')
    tbl_width = E.SubElement(props, W + 'tblW'); tbl_width.set(W + 'w', str(width)); tbl_width.set(W + 'type', 'dxa')
    E.SubElement(props, W + 'jc').set(W + 'val', 'center')
    borders = E.SubElement(props, W + 'tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'): E.SubElement(borders, W + side).set(W + 'val', 'nil')
    E.SubElement(props, W + 'tblLayout').set(W + 'type', 'fixed')
    E.SubElement(props, W + 'tblCaption').set(W + 'val', 'word-module-studio-equation-layout')
    grid = E.SubElement(table, W + 'tblGrid')
    row = E.SubElement(table, W + 'tr')
    E.SubElement(E.SubElement(row, W + 'trPr'), W + 'cantSplit')
    for index, cell_width in enumerate((width - number_width, number_width)):
        E.SubElement(grid, W + 'gridCol').set(W + 'w', str(cell_width))
        cell = E.SubElement(row, W + 'tc')
        cell_props = E.SubElement(cell, W + 'tcPr')
        cell_w = E.SubElement(cell_props, W + 'tcW'); cell_w.set(W + 'w', str(cell_width)); cell_w.set(W + 'type', 'dxa')
        E.SubElement(cell_props, W + 'vAlign').set(W + 'val', 'center')
        p = E.SubElement(cell, W + 'p')
        E.SubElement(E.SubElement(p, W + 'pPr'), W + 'jc').set(W + 'val', 'center' if index == 0 else 'right')
        if index == 0:
            display = E.SubElement(p, M + 'oMathPara'); display.append(formula)
        else: E.SubElement(E.SubElement(p, W + 'r'), W + 't').text = number
    return table
