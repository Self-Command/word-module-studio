"""Structural accessibility evidence; does not claim assistive-tool certification."""
from .package import Package, W, NS
from .runtime import require_execution


def inspect(path):
    require_execution(); package = Package(path); issues = []
    root = package.xml('word/document.xml')
    for node in root.xpath('//*[local-name()="docPr"]'):
        if not (node.get('descr') or node.get('title')): issues.append({'code': 'IMAGE_ALT_MISSING', 'object': node.get('id')})
    level = 0
    for paragraph in root.iter(W + 'p'):
        pstyle = paragraph.find('w:pPr/w:pStyle', namespaces=NS)
        if pstyle is None: continue
        name = pstyle.get(W + 'val', '')
        if name.startswith('Heading') and name[7:].isdigit():
            current = int(name[7:])
            if current > level + 1: issues.append({'code': 'HEADING_LEVEL_SKIPPED', 'style': name})
            level = current
    for table in root.iter(W + 'tbl'):
        first = table.find(W + 'tr')
        equation = table.find('w:tblPr/w:tblCaption', namespaces=NS)
        is_equation = equation is not None and equation.get(W + 'val') == 'word-module-studio-equation-layout'
        if first is not None and not is_equation and first.find('w:trPr/w:tblHeader', namespaces=NS) is None:
            issues.append({'code': 'TABLE_HEADER_SEMANTICS_MISSING'})
    defaults = package.xml('word/styles.xml').find('w:docDefaults/w:rPrDefault/w:rPr/w:lang', namespaces=NS)
    return {'module': 'M18', 'issues': issues, 'default_language': defaults.get(W + 'val') if defaults is not None else None,
        'automatic_structural_pass': not issues, 'scope': 'Native document structure; manual accessibility review remains separate'}
