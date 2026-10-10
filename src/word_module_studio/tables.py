"""Column-constrained data tables, merges, headers and explicit continuations."""
from copy import deepcopy
from lxml import etree as E
from .package import W, NS, ID
from .context import LayoutContext
from .runtime import require_actions, WordError
from .captions import caption


def _set(parent, name, attributes=None):
    old = parent.find(W + name)
    if old is not None: parent.remove(old)
    node = E.SubElement(parent, W + name)
    for key, value in (attributes or {}).items(): node.set(W + key, str(value))
    return node


def apply(package, target, props):
    require_actions()
    table = target['element']
    if table.tag != W + 'tbl': raise WordError('TABLE_REQUIRED')
    operation = props.get('operation', 'format')
    if operation == 'merge': return merge(table, props)
    allowed = {'operation', 'widths_twips', 'three_line', 'header_rows', 'split_rows', 'title', 'number', 'caption_position'}
    if set(props) - allowed: raise WordError('TABLE_PROPERTY_UNSUPPORTED')
    context = LayoutContext.resolve(package, target)
    budget = min(context.column_widths_twips)
    grid = table.find(W + 'tblGrid')
    if grid is None: raise WordError('TABLE_GRID_MISSING')
    columns = len(grid)
    widths = props.get('widths_twips', [budget // columns] * columns)
    if len(widths) != columns or min(widths) <= 0 or sum(widths) > budget: raise WordError('TABLE_CANNOT_FIT', target['id'])
    table_props = table.find(W + 'tblPr')
    if table_props is None: table_props = E.Element(W + 'tblPr'); table.insert(0, table_props)
    _set(table_props, 'tblW', {'w': sum(widths), 'type': 'dxa'})
    _set(table_props, 'tblLayout', {'type': 'fixed'})
    grid.clear()
    for width in widths: E.SubElement(grid, W + 'gridCol').set(W + 'w', str(width))
    headers = props.get('header_rows', 1)
    rows = table.findall(W + 'tr')
    if headers < 0 or headers >= len(rows): raise WordError('INVALID_HEADER_ROWS')
    if props.get('three_line'):
        borders = _set(table_props, 'tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            _set(borders, side, {'val': 'single' if side in ('top', 'bottom') else 'nil', 'sz': 8})
    for index, row in enumerate(rows):
        row_props = row.find(W + 'trPr')
        if row_props is None: row_props = E.Element(W + 'trPr'); row.insert(0, row_props)
        _set(row_props, 'cantSplit')
        if index < headers: _set(row_props, 'tblHeader')
        position = 0
        for cell in row.findall(W + 'tc'):
            cell_props = cell.find(W + 'tcPr')
            if cell_props is None: cell_props = E.Element(W + 'tcPr'); cell.insert(0, cell_props)
            span = cell_props.find(W + 'gridSpan')
            count = int(span.get(W + 'val')) if span is not None else 1
            _set(cell_props, 'tcW', {'w': sum(widths[position:position+count]), 'type': 'dxa'})
            position += count
            if props.get('three_line'):
                borders = _set(cell_props, 'tcBorders')
                for side in ('top', 'left', 'bottom', 'right'):
                    _set(borders, side, {'val': 'single' if side == 'bottom' and index == headers - 1 else 'nil', 'sz': 4})
    from .ooxml import order_properties
    order_properties(table)
    if props.get('split_rows'): return split(table, props, headers)
    return {'widths_twips': widths, 'rows': len(rows), 'header_rows': headers, 'three_line': props.get('three_line', False)}


def split(table, props, headers):
    """Break at verified row boundaries; vertical spans crossing a boundary fail."""
    rows = table.findall(W + 'tr')
    boundaries = sorted(props['split_rows'])
    if len(set(boundaries)) != len(boundaries) or any(i <= headers or i >= len(rows) for i in boundaries):
        raise WordError('INVALID_TABLE_SPLIT')
    for index in boundaries:
        for cell in rows[index].findall(W + 'tc'):
            mark = cell.find('w:tcPr/w:vMerge', namespaces=NS)
            if mark is not None and mark.get(W + 'val', 'continue') == 'continue': raise WordError('TABLE_SPLIT_CROSSES_MERGE')
    parts = []
    start = headers
    for stop in [*boundaries, len(rows)]:
        fragment = deepcopy(table)
        for old in fragment.findall(W + 'tr'): fragment.remove(old)
        fragment.extend(deepcopy(row) for row in rows[:headers] + rows[start:stop])
        for node in fragment.iter():
            if ID in node.attrib: del node.attrib[ID]
        parts.append(fragment)
        start = stop
    cursor = table
    position = props.get('caption_position', 'below')
    if not props.get('title') or not props.get('number'): raise WordError('CONTINUATION_CAPTION_REQUIRED')
    for index, fragment in enumerate(parts):
        title = caption('Table', props['title'], props['number'], continuation=index > 0, position=position)
        nodes = (title, fragment) if position == 'above' else (fragment, title)
        for node in nodes: cursor.addnext(node); cursor = node
        if index < len(parts) - 1:
            page = E.Element(W + 'p')
            E.SubElement(E.SubElement(page, W + 'r'), W + 'br').set(W + 'type', 'column')
            cursor.addnext(page); cursor = page
    table.getparent().remove(table)
    return {'segments': len(parts), 'split_rows': boundaries, 'captions': len(parts), 'caption_position': position}


def merge(table, props):
    allowed = {'operation', 'row_start', 'row_end', 'column_start', 'column_end'}
    if set(props) - allowed: raise WordError('MERGE_PROPERTY_UNSUPPORTED')
    rows = table.findall(W + 'tr')
    r0, r1, c0, c1 = (props[k] for k in ('row_start', 'row_end', 'column_start', 'column_end'))
    if not (0 <= r0 <= r1 < len(rows)) or c0 < 0 or c1 < c0: raise WordError('INVALID_TABLE_MERGE')
    for row in rows[r0:r1+1]:
        cells = row.findall(W + 'tc')
        if c1 >= len(cells) or any(cell.xpath('.//w:vMerge | .//w:gridSpan', namespaces=NS) for cell in cells[c0:c1+1]):
            raise WordError('MERGE_INTERSECTS_EXISTING_MERGE')
    for index, row in enumerate(rows[r0:r1+1]):
        cells = row.findall(W + 'tc')
        first = cells[c0]
        tcpr = first.find(W + 'tcPr')
        if tcpr is None: tcpr = E.Element(W + 'tcPr'); first.insert(0, tcpr)
        if c1 > c0:
            _set(tcpr, 'gridSpan', {'val': c1 - c0 + 1})
            for cell in cells[c0+1:c1+1]:
                for paragraph in cell.findall(W + 'p'): first.append(deepcopy(paragraph))
                row.remove(cell)
        if r1 > r0:
            _set(tcpr, 'vMerge', {'val': 'restart' if index == 0 else 'continue'})
    return {'merged': [r0, r1, c0, c1]}
