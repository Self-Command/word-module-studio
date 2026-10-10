"""Semantic labelled-object references become native numbered REF fields."""
from copy import deepcopy
from lxml import etree as E
from .package import W, NS
from .runtime import WordError


def prepare(ast, equations):
    objects, labels = [], {}
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values(): yield from walk(child)
        elif isinstance(value, list):
            for child in value: yield from walk(child)
    def register(label, sequence, number):
        if not label: return
        record = {'label': label, 'sequence': sequence, 'number': str(number),
            'bookmark': 'wms_' + sequence.lower() + '_' + str(len(objects) + 1)}
        if label in labels:
            if labels[label]['sequence'] != sequence or labels[label]['number'] != str(number): raise WordError('DUPLICATE_OBJECT_LABEL', label)
            return
        labels[label] = record; objects.append(record)
    counts = {'Figure': 0, 'Table': 0}
    for node in walk(ast.get('blocks', [])):
        if node.get('t') not in ('Image', 'Table'): continue
        sequence = 'Figure' if node['t'] == 'Image' else 'Table'; counts[sequence] += 1
        register(node['c'][0][0], sequence, counts[sequence])
        # TeX labels are semantic empty spans in the caption, not raw XML.
        caption = node['c'][1]
        for span in walk(caption):
            if span.get('t') == 'Span' and not span['c'][1]: register(span['c'][0][0], sequence, counts[sequence])
    for index, equation in enumerate(equations, 1):
        for label in equation.get('labels', []): register(label, 'Equation', equation['number'] or index)
    references = []
    for node in walk(ast):
        if node.get('t') != 'Link' or not node['c'][2][0].startswith('#'): continue
        target = node['c'][2][0][1:]
        explicitly_numbered = any(key == 'wms-ref' for key, _ in node['c'][0][2])
        if target not in labels:
            if explicitly_numbered: raise WordError('BROKEN_REFERENCE', target)
            continue
        record = labels[target]
        marker = '__WMS_REFERENCE_' + str(len(references)) + '__'
        node['c'][1] = [{'t': 'Str', 'c': marker}]; node['c'][0][2] = []
        references.append({**record, 'marker': marker})
    return {'objects': objects, 'references': references}


def bookmark(package, parent, node, name):
    document = package.xml('word/document.xml')
    if any(n.get(W + 'name') == name for n in document.iter(W + 'bookmarkStart')): raise WordError('DUPLICATE_BOOKMARK', name)
    identifier = max([int(n.get(W + 'id')) for n in document.iter(W + 'bookmarkStart')] + [0]) + 1
    start, end = E.Element(W + 'bookmarkStart'), E.Element(W + 'bookmarkEnd')
    start.set(W + 'id', str(identifier)); start.set(W + 'name', name); end.set(W + 'id', str(identifier))
    node.addprevious(start); node.addnext(end)


def finish(package, ledger):
    document = package.xml('word/document.xml')
    for record in ledger['objects']:
        if record['sequence'] == 'Equation': continue  # M09 owns its number bookmark.
        fields = [f for f in document.iter(W + 'fldSimple') if f.get(W + 'instr', '').strip().startswith('SEQ ' + record['sequence'] + ' ')]
        index = int(record['number']) - 1
        if index >= len(fields): raise WordError('REFERENCE_CAPTION_TARGET_MISSING', record['label'])
        bookmark(package, fields[index].getparent(), fields[index], record['bookmark'])
    for record in ledger['references']:
        hosts = [n for n in document.iter(W + 'hyperlink') if ''.join(n.xpath('.//w:t/text()', namespaces=NS)) == record['marker']]
        if len(hosts) != 1: raise WordError('REFERENCE_MARKER_MISSING', record['label'])
        field = E.Element(W + 'fldSimple'); field.set(W + 'instr', ' REF ' + record['bookmark'] + ' \\h ')
        E.SubElement(E.SubElement(field, W + 'r'), W + 't').text = record['number']
        hosts[0].getparent().replace(hosts[0], field)
    return ledger
