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
    allowed = {'formula', 'mode', 'number', 'number_width_twips', 'size_pt', 'wrap', 'operation', 'bookmarks', 'policy', 'break_strategy'}
    if set(props) - allowed: raise WordError('MATH_PROPERTY_UNSUPPORTED')
    target = item['element']
    mode = props.get('mode', 'display')
    formula = convert(props['formula'], mode)
    context = LayoutContext.resolve(package, item)
    size = props.get('size_pt', 10)
    math_font = package.xml('word/settings.xml').find('m:mathPr/m:mathFont', namespaces=NS)
    family = math_font.get(M + 'val') if math_font is not None else None
    for math_run in formula.iter(M + 'r'):
        properties = math_run.find(W + 'rPr')
        if properties is None:
            properties = E.Element(W + 'rPr')
            math_run.insert(1 if math_run.find(M + 'rPr') is not None else 0, properties)
        old_size = properties.find(W + 'sz')
        if old_size is not None: properties.remove(old_size)
        E.SubElement(properties, W + 'sz').set(W + 'val', str(round(size * 2)))
        if family:
            old_fonts = properties.find(W + 'rFonts')
            if old_fonts is not None: properties.remove(old_fonts)
            fonts = E.Element(W + 'rFonts'); fonts.set(W + 'ascii', family); fonts.set(W + 'hAnsi', family)
            properties.insert(0, fonts)
    number_width = props.get('number_width_twips', 600) if props.get('number') else 0
    budget = (context.available_width_twips - number_width) / 20 - 8
    if budget <= 0: raise WordError('EQUATION_NUMBER_REGION_TOO_WIDE')
    formula_id = 'eq_' + __import__('hashlib').sha256((props['formula'] + ':' + str(props.get('number', ''))).encode()).hexdigest()[:16]
    formula.set('{' + NS['wms'] + '}formula', formula_id)
    original = tree(formula)
    policy = props.get('policy', 'practical')
    if policy not in ('practical', 'safe_wrap', 'fail'): raise WordError('INVALID_MATH_POLICY')
    from .math_breaks import DEFAULT_STRATEGY
    strategy = props.get('break_strategy', DEFAULT_STRATEGY)
    if policy == 'practical':
        from .math_breaks import wrap as outer_wrap
        changes = outer_wrap(formula, budget, size, metrics=metrics, strategy=strategy) if props.get('wrap', True) else []
    else: changes = wrap(formula, budget, size, metrics=metrics) if policy == 'safe_wrap' and props.get('wrap', True) else []
    if tree(restore(formula, changes)) != original: raise WordError('FORMULA_RECOVERY_FAILED')
    measured = math_width_pt(formula, size, metrics)
    if measured > budget + 0.1:
        from .runtime import write_json
        diagnostics = Path('build/formula-overflows'); diagnostics.mkdir(parents=True, exist_ok=True)
        name = __import__('hashlib').sha256(E.tostring(formula)).hexdigest()[:16]
        (diagnostics / (name + '.xml')).write_bytes(E.tostring(formula, pretty_print=True))
        write_json(diagnostics / (name + '.json'), {'number': props.get('number'), 'budget_pt': budget,
            'measured_pt': measured, 'parts': [{'kind': E.QName(c).localname, 'width_pt': math_width_pt(c, size, metrics)} for c in formula]})
        if policy != 'practical': raise WordError('FORMULA_CANNOT_FIT', f"{props.get('number', 'unlabelled')}: {measured:.2f} pt exceeds {budget:.2f} pt; {name}")
    formula_id = 'eq_' + __import__('hashlib').sha256((props['formula'] + ':' + str(props.get('number', ''))).encode()).hexdigest()[:16]
    formula.set('{' + NS['wms'] + '}formula', formula_id)
    adjustment = measured > budget + .1
    result = {'formula_id': formula_id, 'original_math': original, 'changes': changes, 'mode': mode, 'number': props.get('number'),
        'budget_pt': budget, 'estimated_width_pt': measured, 'policy': policy, 'break_strategy': strategy,
        'layout_status': 'needs_minor_adjustment' if adjustment else 'pass',
        'manual_adjustments': [{'formula_id': formula_id, 'reason': 'Estimated width needs real page review', 'suggestion': 'Adjust an outer operator break or continuation alignment; retain all mathematical content'}] if adjustment else [],
        'visual_review_required': True}
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
            table = _equation_table(formula, '(' + str(props['number']) + ')', context.available_width_twips, number_width)
            _append(target, table)
            _number_bookmarks(package, table, props)
            return {**result, 'layout': 'centered-multiline'}
        else:
            tabs = E.SubElement(ppr, W + 'tabs')
            center = E.SubElement(tabs, W + 'tab'); center.set(W + 'val', 'center'); center.set(W + 'pos', str((context.available_width_twips - number_width) // 2))
            right = E.SubElement(tabs, W + 'tab'); right.set(W + 'val', 'right'); right.set(W + 'pos', str(context.available_width_twips))
            E.SubElement(E.SubElement(p, W + 'r'), W + 'tab')
            p.append(formula)
            E.SubElement(E.SubElement(p, W + 'r'), W + 'tab')
            E.SubElement(E.SubElement(p, W + 'r'), W + 't').text = '(' + str(props['number']) + ')'
        _append(target, p)
        _number_bookmarks(package, p, props)
    return result


def fit_inline(package, element, size, metrics, *, policy='practical', strategy=None):
    """Reversible fitting uses the owning cell's budget as well as the column."""
    context = LayoutContext.resolve(package, {'element': element, 'part': 'word/document.xml'})
    budget = context.available_width_twips / 20 - 4
    from .math_breaks import DEFAULT_STRATEGY
    strategy = strategy or DEFAULT_STRATEGY
    formula_id = 'eq_' + __import__('hashlib').sha256(E.tostring(element)).hexdigest()[:16]
    element.set('{' + NS['wms'] + '}formula', formula_id)
    original = tree(element)
    if policy == 'practical':
        from .math_breaks import wrap as outer_wrap
        changes = outer_wrap(element, budget, size, metrics=metrics, strategy=strategy)
    else: changes = wrap(element, budget, size, metrics=metrics) if policy == 'safe_wrap' else []
    if tree(restore(element, changes)) != original: raise WordError('INLINE_MATH_RECOVERY_FAILED')
    adjustment = math_width_pt(element, size, metrics) > budget + .1
    if adjustment and policy != 'practical': raise WordError('INLINE_FORMULA_CANNOT_FIT', element.getroottree().getpath(element))
    return {'element': element, 'formula_id': formula_id, 'original_math': original, 'changes': changes, 'budget_pt': budget, 'policy': policy,
        'layout_status': 'needs_minor_adjustment' if adjustment else 'pass', 'manual_adjustments': ['Review inline operator break/alignment'] if adjustment else []}


def _number_bookmarks(package, element, props):
    from .references import bookmark
    if not props.get('bookmarks'): return
    text = next(t for t in element.iter(W + 't') if t.text == '(' + str(props['number']) + ')')
    run = text.getparent(); text.text = str(props['number'])
    start, end = E.Element(W + 'r'), E.Element(W + 'r')
    E.SubElement(start, W + 't').text = '('; E.SubElement(end, W + 't').text = ')'
    run.addprevious(start); run.addnext(end)
    for name in props.get('bookmarks', []):
        if not __import__('re').fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,39}', name): raise WordError('INVALID_BOOKMARK_NAME')
        bookmark(package, run.getparent(), run, name)


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
        margins = E.SubElement(cell_props, W + 'tcMar')
        for side in ('top', 'left', 'bottom', 'right'):
            margin = E.SubElement(margins, W + side); margin.set(W + 'w', '0'); margin.set(W + 'type', 'dxa')
        E.SubElement(cell_props, W + 'vAlign').set(W + 'val', 'center')
        p = E.SubElement(cell, W + 'p')
        E.SubElement(E.SubElement(p, W + 'pPr'), W + 'jc').set(W + 'val', 'center' if index == 0 else 'right')
        if index == 0:
            display = E.SubElement(p, M + 'oMathPara'); display.append(formula)
        else: E.SubElement(E.SubElement(p, W + 'r'), W + 't').text = number
    return table
