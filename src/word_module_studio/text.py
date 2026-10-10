"""Character ranges split native runs and retain formatting outside the range."""
from copy import deepcopy
from lxml import etree as E
from .package import W, NS, ID
from .runtime import WordError


def apply(package, target, props):
    if set(props) - {'operation', 'start', 'end', 'text', 'format'}: raise WordError('TEXT_RANGE_PROPERTY_UNSUPPORTED')
    if props.get('operation') != 'range': raise WordError('TEXT_OPERATION_UNSUPPORTED')
    paragraph = target['element']
    if paragraph.tag != W + 'p': raise WordError('TEXT_RANGE_PARAGRAPH_REQUIRED')
    runs = paragraph.findall(W + 'r')
    unsafe = [child for child in paragraph if child.tag not in (W + 'pPr', W + 'r', W + 'bookmarkStart', W + 'bookmarkEnd')]
    if unsafe or any(c.tag not in (W + 'rPr', W + 't') for r in runs for c in r):
        raise WordError('TEXT_RANGE_CONTAINS_NATIVE_OBJECT', target['id'])
    full = ''.join(t.text or '' for r in runs for t in r.iter(W + 't'))
    start, end = props['start'], props['end']
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(full)): raise WordError('TEXT_RANGE_INVALID')
    formatting = props.get('format', {})
    allowed = {'bold': 'b', 'italic': 'i', 'color': 'color', 'language': 'lang', 'superscript': 'vertAlign', 'subscript': 'vertAlign', 'rtl': 'rtl'}
    if set(formatting) - set(allowed): raise WordError('TEXT_RANGE_FORMAT_UNSUPPORTED')
    def piece(source, text, formatted=False):
        node = deepcopy(source)
        if ID in node.attrib: del node.attrib[ID]
        for child in list(node):
            if child.tag != W + 'rPr': node.remove(child)
        if formatted:
            rpr = node.find(W + 'rPr')
            if rpr is None: rpr = E.Element(W + 'rPr'); node.insert(0, rpr)
            for key, value in formatting.items():
                for child in list(rpr):
                    if child.tag == W + allowed[key]: rpr.remove(child)
                if key in ('bold', 'italic', 'rtl'): attrs = {W + 'val': '1' if value else '0'}
                elif key in ('superscript', 'subscript'): attrs = {W + 'val': key if value else 'baseline'}
                else: attrs = {W + 'val': str(value)}
                E.SubElement(rpr, W + allowed[key], attrs)
        text_node = E.SubElement(node, W + 't'); text_node.text = text
        text_node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        return node
    replacement = props.get('text')
    cursor, inserted = 0, False
    for run in runs:
        text = ''.join(t.text or '' for t in run.iter(W + 't')); stop = cursor + len(text)
        if stop < start or cursor > end: cursor = stop; continue
        a, b = max(0, start - cursor), min(len(text), end - cursor)
        pieces = []
        if a > 0: pieces.append(piece(run, text[:a]))
        if replacement is not None:
            if not inserted:
                if replacement: pieces.append(piece(run, replacement, True))
                inserted = True
        elif b > a: pieces.append(piece(run, text[a:b], True))
        if b < len(text): pieces.append(piece(run, text[b:]))
        for node in pieces: run.addprevious(node)
        paragraph.remove(run); cursor = stop
    if not runs and replacement:
        paragraph.append(piece(E.Element(W + 'r'), replacement, True))
    from .ooxml import order_properties
    order_properties(paragraph)
    return {'range': [start, end], 'before': full, 'after': ''.join(t.text or '' for t in paragraph.iter(W + 't'))}
