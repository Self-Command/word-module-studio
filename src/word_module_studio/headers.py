"""Section-scoped headers/footers and explicit inheritance."""
from lxml import etree as E
from .package import W, NS
from .runtime import WordError


def apply(package, target, props):
    allowed = {'operation', 'kind', 'type', 'text', 'link_previous', 'align'}
    if set(props) - allowed or props.get('operation') != 'scope': raise WordError('HEADER_SCOPE_PROPERTY_UNSUPPORTED')
    section = target['element']
    if section.tag != W + 'sectPr': raise WordError('HEADER_SECTION_REQUIRED')
    kind, scope = props['kind'], props.get('type', 'default')
    if kind not in ('header', 'footer') or scope not in ('default', 'first', 'even'): raise WordError('HEADER_SCOPE_INVALID')
    old = next((n for n in section if n.tag == W + kind + 'Reference' and n.get(W + 'type') == scope), None)
    if old is not None: section.remove(old)
    if props.get('link_previous'):
        if section is list(package.xml('word/document.xml').iter(W + 'sectPr'))[0]: raise WordError('HEADER_FIRST_SECTION_CANNOT_LINK')
        return {'kind': kind, 'type': scope, 'link_previous': True}
    index = 1
    while f'word/{kind}{index}.xml' in package.parts: index += 1
    root = E.Element(W + ('hdr' if kind == 'header' else 'ftr'), nsmap={'w': NS['w']})
    paragraph = E.SubElement(root, W + 'p')
    E.SubElement(E.SubElement(paragraph, W + 'pPr'), W + 'jc').set(W + 'val', props.get('align', 'center'))
    import re
    for piece in re.split(r'(\{\{(?:PAGE|NUMPAGES|SECTIONPAGES)\}\})', props.get('text', '')):
        if piece.startswith('{{'):
            field = E.SubElement(paragraph, W + 'fldSimple'); field.set(W + 'instr', piece[2:-2])
            E.SubElement(E.SubElement(field, W + 'r'), W + 't').text = '1'
        elif piece:
            text = E.SubElement(E.SubElement(paragraph, W + 'r'), W + 't'); text.text = piece
            text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    part = f'word/{kind}{index}.xml'; package.parts[part] = E.tostring(root, xml_declaration=True, encoding='UTF-8')
    rels = package.xml('word/_rels/document.xml.rels'); ids = {n.get('Id') for n in rels}; number = 1
    while 'rId' + str(number) in ids: number += 1
    rel_id = 'rId' + str(number)
    E.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
        Id=rel_id, Type=NS['r'] + '/' + kind, Target=f'{kind}{index}.xml')
    reference = E.SubElement(section, W + kind + 'Reference'); reference.set(W + 'type', scope); reference.set('{' + NS['r'] + '}id', rel_id)
    E.SubElement(package.xml('[Content_Types].xml'), '{http://schemas.openxmlformats.org/package/2006/content-types}Override',
        PartName='/' + part, ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.' + kind + '+xml')
    if scope == 'first' and section.find(W + 'titlePg') is None: E.SubElement(section, W + 'titlePg')
    if scope == 'even':
        settings = package.xml('word/settings.xml')
        if settings.find(W + 'evenAndOddHeaders') is None:
            node = E.Element(W + 'evenAndOddHeaders'); settings.insert(0, node)
    from .ooxml import order_properties
    order_properties(section)
    return {'kind': kind, 'type': scope, 'part': part, 'link_previous': False}
