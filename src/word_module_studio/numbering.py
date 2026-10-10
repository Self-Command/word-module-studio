"""Multi-level definitions, explicit restarts and continuation by instance ID."""
from copy import deepcopy
from lxml import etree as E
from .package import W, NS
from .runtime import WordError


def apply(package, target, props):
    allowed = {'operation', 'levels', 'level', 'start', 'continue_num_id', 'heading_styles'}
    if set(props) - allowed or props.get('operation') != 'list': raise WordError('LIST_PROPERTY_UNSUPPORTED')
    paragraph = target['element']
    if paragraph.tag != W + 'p': raise WordError('LIST_PARAGRAPH_REQUIRED')
    if 'word/numbering.xml' not in package.parts: raise WordError('NUMBERING_PART_MISSING')
    root = package.xml('word/numbering.xml')
    if props.get('continue_num_id') is not None:
        identifier = int(props['continue_num_id'])
        if not any(n.get(W + 'numId') == str(identifier) for n in root.iter(W + 'num')): raise WordError('LIST_INSTANCE_MISSING')
    else:
        levels = props.get('levels', [{'format': 'decimal', 'text': '%1.'}])
        if not 1 <= len(levels) <= 9: raise WordError('LIST_LEVELS_INVALID')
        aid = max([int(n.get(W + 'abstractNumId')) for n in root.iter(W + 'abstractNum')] + [-1]) + 1
        identifier = max([int(n.get(W + 'numId')) for n in root.iter(W + 'num')] + [0]) + 1
        abstract = E.Element(W + 'abstractNum'); abstract.set(W + 'abstractNumId', str(aid))
        E.SubElement(abstract, W + 'multiLevelType').set(W + 'val', 'multilevel' if len(levels) > 1 else 'singleLevel')
        for index, value in enumerate(levels):
            if set(value) - {'format', 'text', 'start', 'indent_twips', 'hanging_twips'}: raise WordError('LIST_LEVEL_PROPERTY_UNSUPPORTED')
            level = E.SubElement(abstract, W + 'lvl'); level.set(W + 'ilvl', str(index))
            E.SubElement(level, W + 'start').set(W + 'val', str(value.get('start', props.get('start', 1))))
            E.SubElement(level, W + 'numFmt').set(W + 'val', value.get('format', 'decimal'))
            styles = props.get('heading_styles', [])
            if index < len(styles): E.SubElement(level, W + 'pStyle').set(W + 'val', styles[index])
            E.SubElement(level, W + 'lvlText').set(W + 'val', value.get('text', '%' + str(index + 1) + '.'))
            E.SubElement(level, W + 'lvlJc').set(W + 'val', 'left')
            indent = E.SubElement(E.SubElement(level, W + 'pPr'), W + 'ind')
            indent.set(W + 'left', str(value.get('indent_twips', (index + 1) * 400)))
            indent.set(W + 'hanging', str(value.get('hanging_twips', 400)))
        before = next(iter(root.iter(W + 'num')), None)
        if before is not None: before.addprevious(abstract)
        else: root.append(abstract)
        num = E.SubElement(root, W + 'num'); num.set(W + 'numId', str(identifier))
        E.SubElement(num, W + 'abstractNumId').set(W + 'val', str(aid))
    ppr = paragraph.find(W + 'pPr')
    if ppr is None: ppr = E.Element(W + 'pPr'); paragraph.insert(0, ppr)
    old = ppr.find(W + 'numPr')
    if old is not None: ppr.remove(old)
    numpr = E.SubElement(ppr, W + 'numPr')
    E.SubElement(numpr, W + 'ilvl').set(W + 'val', str(props.get('level', 0)))
    E.SubElement(numpr, W + 'numId').set(W + 'val', str(identifier))
    from .ooxml import order_properties
    order_properties(ppr)
    return {'num_id': identifier, 'level': props.get('level', 0)}
