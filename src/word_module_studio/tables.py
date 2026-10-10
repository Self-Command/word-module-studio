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
    if operation == 'paginate': return paginate(package, target, props)
    if operation == 'merge': return merge(table, props)
    allowed = {'operation', 'widths_twips', 'three_line', 'header_rows', 'split_rows', 'title', 'number', 'caption_position'}
    if set(props) - allowed: raise WordError('TABLE_PROPERTY_UNSUPPORTED')
    context = LayoutContext.resolve(package, target)
    budget = context.available_width_twips
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
    if headers < 0 or headers > len(rows): raise WordError('INVALID_HEADER_ROWS')
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
                    outer = side == 'top' and index == 0 or side == 'bottom' and index == len(rows) - 1
                    header_line = side == 'bottom' and index == headers - 1
                    _set(borders, side, {'val': 'single' if outer or header_line else 'nil', 'sz': 8 if outer else 4})
    from .ooxml import order_properties
    order_properties(table)
    if props.get('split_rows'): return split(table, props, headers)
    if props.get('title'):
        if not props.get('number'): raise WordError('CAPTION_NUMBER_REQUIRED')
        title = caption('Table', props['title'], props['number'], position=props.get('caption_position', 'below'))
        if props.get('caption_position', 'below') == 'above': table.addprevious(title)
        else: table.addnext(title)
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
        if props.get('three_line'):
            selected = fragment.findall(W + 'tr')
            for row, side in ((selected[0], 'top'), (selected[-1], 'bottom')):
                for cell in row.findall(W + 'tc'):
                    borders = cell.find('w:tcPr/w:tcBorders', namespaces=NS)
                    if borders is not None: _set(borders, side, {'val': 'single', 'sz': 8})
        for node in fragment.iter():
            if ID in node.attrib: del node.attrib[ID]
        from .ooxml import order_properties
        order_properties(fragment)
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


def paginate(package, target, props):
    """Derive safe continuation boundaries from actual cloud pagination."""
    import json
    import tempfile
    from pathlib import Path
    from .render import render
    allowed = {'operation', 'title', 'number', 'header_rows', 'caption_position', 'widths_twips', 'three_line'}
    if set(props) - allowed: raise WordError('PAGINATION_PROPERTY_UNSUPPORTED')
    if not props.get('title') or not props.get('number'): raise WordError('CONTINUATION_CAPTION_REQUIRED')
    table = target['element']
    if table.xpath('.//w:vMerge', namespaces=NS): raise WordError('TABLE_PAGINATION_MERGED_ROWS_REQUIRE_EXPLICIT_SPLIT')
    headers = props.get('header_rows', 1)
    formatting = {k: v for k, v in props.items() if k not in ('operation', 'title', 'number', 'caption_position')}
    apply(package, target, {'operation': 'format', **formatting})
    # Add a real first caption so its height participates in boundary discovery.
    original_caption = caption('Table', props['title'], props['number'], position=props.get('caption_position', 'below'))
    if props.get('caption_position', 'below') == 'above': table.addprevious(original_caption)
    else: table.addnext(original_caption)
    package.save()
    native_tables = list(package.xml('word/document.xml').iter(W + 'tbl'))
    ordinal = native_tables.index(table)
    with tempfile.TemporaryDirectory(dir=package.path.parent) as temporary:
        folder = Path(temporary)
        render(package.path, folder)
        layout = json.loads((folder / (package.path.stem + '.layout.json')).read_text())
    if ordinal >= len(layout['tables']): raise WordError('TABLE_PAGINATION_MAPPING_FAILED')
    rows = layout['tables'][ordinal]['rows']
    if len(rows) != len(table.findall(W + 'tr')) or any('diagnostic' in row for row in rows): raise WordError('TABLE_PAGINATION_MAPPING_FAILED')
    boundaries = []
    for index in range(max(headers, 1), len(rows)):
        previous, current = rows[index - 1], rows[index]
        if current['page'] != previous['page'] or abs(current['x_pt'] - previous['x_pt']) > 12:
            if index <= headers: raise WordError('TABLE_HEADER_CANNOT_FIT')
            boundaries.append(index)
    original_caption.getparent().remove(original_caption)
    if not boundaries:
        return apply(package, target, {**props, 'operation': 'format'})
    parent = table.getparent()
    previous, following = table.getprevious(), table.getnext()
    prototype = deepcopy(table)
    original_stops = [headers, *boundaries, len(rows)]
    capacities = [stop - start for start, stop in zip(original_stops, original_stops[1:])]
    attempts = []
    for reserve in range(1, 4):
        if reserve > 1:
            start = list(parent).index(previous) + 1 if previous is not None else 0
            end = list(parent).index(following) if following is not None else len(parent)
            for node in list(parent)[start:end]: parent.remove(node)
            table = deepcopy(prototype); parent.insert(start, table)
        # Every fragment needs room for its own caption and repeated header.
        continuation_capacity = max(capacities[1:-1] or capacities[:1]) - reserve
        if continuation_capacity <= 0: raise WordError('TABLE_ROW_AND_CAPTION_CANNOT_FIT')
        first_capacity = capacities[0] - reserve
        if first_capacity <= 0: raise WordError('TABLE_ROW_AND_CAPTION_CANNOT_FIT')
        trial = []; stop = headers + first_capacity
        while stop < len(rows):
            trial.append(stop); stop += continuation_capacity
        result = split(table, {**props, 'split_rows': trial}, headers)
        package.save()
        with tempfile.TemporaryDirectory(dir=package.path.parent) as temporary:
            folder = Path(temporary)
            proof = render(package.path, folder)
            final_layout = json.loads((folder / (package.path.stem + '.layout.json')).read_text())
        fragments = final_layout['tables'][ordinal:ordinal + result['segments']]
        captions = [p for p in final_layout['paragraphs'] if p['text'].startswith('Table ') and props['title'] in p['text']]
        valid = len(fragments) == result['segments'] and len(captions) == result['segments']
        for fragment, title in zip(fragments, captions):
            placed = fragment['rows']
            if not placed or any('diagnostic' in row for row in placed): valid = False; continue
            first, last = placed[0], placed[-1]
            if any(row['page'] != first['page'] or abs(row['x_pt'] - first['x_pt']) > 12 for row in placed): valid = False
            if title['page'] != last['page'] or not first['x_pt'] - 12 <= title['x_pt'] <= first['x_pt'] + LayoutContext.resolve(package, {'element': parent, 'part': 'word/document.xml'}).available_width_twips / 20 + 12: valid = False
        attempts.append({'reserved_rows': reserve, 'split_rows': trial, 'segments': result['segments'], 'single_column_fragments_and_attached_captions': valid, 'automatic_pass': proof['automatic_pass']})
        if valid and proof['automatic_pass']:
            return {**result, 'boundary_source': 'LibreOffice native row positions', 'initial_row_positions': rows, 'convergence': attempts}
    raise WordError('TABLE_PAGINATION_NOT_CONVERGED', str(attempts))
