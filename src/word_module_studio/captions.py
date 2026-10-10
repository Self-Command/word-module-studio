"""Native SEQ captions with separate Figure/Table sequences and bookmarks."""
import re
from lxml import etree as E
from .package import W, NS
from .runtime import require_actions, WordError


def caption(sequence, title, number, *, prefix=None, continuation=False, bookmark=None, position='below'):
    require_actions()
    if sequence not in ('Figure', 'Table', 'Equation'): raise WordError('INVALID_CAPTION_SEQUENCE')
    if not title.strip(): raise WordError('CAPTION_TITLE_REQUIRED')
    p = E.Element(W + 'p')
    ppr = E.SubElement(p, W + 'pPr')
    E.SubElement(ppr, W + 'pStyle').set(W + 'val', 'Caption')
    E.SubElement(ppr, W + 'keepLines')
    E.SubElement(ppr, W + 'keepNext').set(W + 'val', '1' if position == 'above' else '0')
    if bookmark:
        marker = E.SubElement(p, W + 'bookmarkStart'); marker.set(W + 'id', str(number + {'Figure': 5000, 'Table': 10000, 'Equation': 15000}[sequence])); marker.set(W + 'name', bookmark)
    E.SubElement(E.SubElement(p, W + 'r'), W + 't').text = (prefix or sequence) + ' '
    field = E.SubElement(p, W + 'fldSimple')
    instruction = ' SEQ ' + sequence + (' \\c ' if continuation else ' \\* ARABIC ')
    field.set(W + 'instr', instruction)
    E.SubElement(E.SubElement(field, W + 'r'), W + 't').text = str(number)
    text = E.SubElement(E.SubElement(p, W + 'r'), W + 't')
    text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    text.text = ' ' + title + (' (continued)' if continuation else '')
    if bookmark:
        E.SubElement(p, W + 'bookmarkEnd').set(W + 'id', str(number + {'Figure': 5000, 'Table': 10000, 'Equation': 15000}[sequence]))
    from .ooxml import order_properties
    order_properties(p)
    return p


def apply(package, target, props):
    require_actions()
    allowed = {'operation', 'sequence', 'title', 'number', 'prefix', 'position', 'bookmark', 'continuation'}
    if set(props) - allowed: raise WordError('CAPTION_PROPERTY_UNSUPPORTED')
    p = caption(props['sequence'], props['title'], props['number'], prefix=props.get('prefix'),
        continuation=props.get('continuation', False), bookmark=props.get('bookmark'), position=props.get('position', 'below'))
    if props.get('position', 'below') == 'above': target['element'].addprevious(p)
    else: target['element'].addnext(p)
    return {'sequence': props['sequence'], 'number': props['number'], 'position': props.get('position', 'below')}
