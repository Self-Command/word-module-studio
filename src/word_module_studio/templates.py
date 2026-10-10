"""Immutable masters assembled from page/region/style components."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from lxml import etree as E
from .contracts import validate
from .package import Package, W, NS
from .runtime import require_actions, WordError, digest, write_json, run


def canonical_spec(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def check_fonts(fonts):
    require_actions()
    found = {}
    for role, family in fonts.items():
        match = run(['fc-match', '-f', '%{family}\n%{file}\n%{index}', family]).splitlines()
        if not match or family.casefold() not in [name.strip().casefold() for name in match[0].split(',')]:
            raise WordError('FONT_MISSING', role + ': ' + family)
        found[role] = {'family': family, 'file': match[1], 'index': int(match[2] or 0), 'sha256': digest(match[1])}
    return found


def child(parent, tag, attrs=None):
    element = E.SubElement(parent, W + tag)
    for key, value in (attrs or {}).items(): element.set(W + key, str(value))
    return element


def build(spec, folder):
    require_actions()
    validate('template-spec', spec)
    if len({r['id'] for r in spec['regions']}) != len(spec['regions']): raise WordError('DUPLICATE_REGION')
    fonts = check_fonts(spec['fonts'])
    folder = Path(folder)
    identity = canonical_spec(spec)
    manifest_path = folder / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest['spec_sha256'] != identity: raise WordError('TEMPLATE_VERSION_REUSE')
        check_identity(manifest)
        return manifest
    folder.mkdir(parents=True, exist_ok=True)
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
    document = Document()
    for name, rule in spec['styles'].items():
        style = document.styles[name] if name in document.styles else document.styles.add_style(name, 1)
        style.font.name = spec['fonts']['latin']
        style.font.size = Pt(rule['size_pt'])
        style.font.bold, style.font.italic = rule.get('bold', False), rule.get('italic', False)
        fonts_node = style.element.get_or_add_rPr().get_or_add_rFonts()
        fonts_node.set(qn('w:eastAsia'), spec['fonts']['cjk'])
        fonts_node.set(qn('w:cs'), spec['fonts'].get('rtl', spec['fonts']['latin']))
        pformat = style.paragraph_format
        pformat.space_before = Pt(rule.get('space_before_pt', 0))
        pformat.space_after = Pt(rule.get('space_after_pt', 0))
        pformat.keep_with_next = rule.get('keep_next', False)
        pformat.line_spacing = rule.get('line_spacing', 1.0)
        if 'alignment' in rule: pformat.alignment = {'left': 0, 'center': 1, 'right': 2, 'justify': 3}[rule['alignment']]
        if rule.get('based_on'): style.base_style = document.styles[rule['based_on']]
    document.save(folder / 'master.docx')
    package = Package(folder / 'master.docx')
    root = package.xml('word/document.xml')
    body = root.find(W + 'body')
    for node in list(body): body.remove(node)
    for index, region in enumerate(spec['regions']):
        control = child(body, 'sdt')
        props = child(control, 'sdtPr')
        child(props, 'id', {'val': index + 1})
        child(props, 'tag', {'val': 'region.' + region['id']})
        child(props, 'alias', {'val': region['id']})
        content = child(control, 'sdtContent')
        p = child(content, 'p')
        child(child(p, 'pPr'), 'pStyle', {'val': 'Normal'})
        child(child(p, 'r'), 't').text = '{{' + region['id'] + '}}'
        if index == len(spec['regions']) - 1: section = child(body, 'sectPr')
        else:
            marker = child(body, 'p')
            ppr = child(marker, 'pPr')
            child(ppr, 'spacing', {'before': 0, 'after': 0, 'line': 20, 'lineRule': 'exact'})
            section = child(ppr, 'sectPr')
        if region.get('break'): child(section, 'type', {'val': region['break']})
        page = region['page']
        child(section, 'pgSz', {'w': page['width_twips'], 'h': page['height_twips'],
            'orient': 'landscape' if page['width_twips'] > page['height_twips'] else 'portrait'})
        top, right, bottom, left = page['margins_twips']
        child(section, 'pgMar', {'top': top, 'right': right, 'bottom': bottom, 'left': left, 'header': 400, 'footer': 400, 'gutter': 0})
        if region.get('page_start') is not None: child(section, 'pgNumType', {'start': region['page_start'], 'fmt': region.get('page_format', 'decimal')})
        cols = child(section, 'cols', {'num': region['columns'], 'space': region['gap_twips']})
        if region.get('column_widths_twips'):
            if len(region['column_widths_twips']) != region['columns']: raise WordError('INVALID_COLUMN_WIDTHS')
            cols.set(W + 'equalWidth', '0')
            for width in region['column_widths_twips']: child(cols, 'col', {'w': width, 'space': region['gap_twips']})
    settings = package.xml('word/settings.xml')
    math = settings.find('m:mathPr', namespaces=NS)
    if math is None: math = E.SubElement(settings, '{' + NS['m'] + '}mathPr')
    math_font = math.find('m:mathFont', namespaces=NS)
    if math_font is None: math_font = E.SubElement(math, '{' + NS['m'] + '}mathFont')
    math_font.set('{' + NS['m'] + '}val', spec['fonts']['math'])
    package.save()
    manifest = {'schema_version': 1, 'id': spec['id'], 'version': spec['version'], 'spec': spec,
        'spec_sha256': identity, 'master': str((folder / 'master.docx').resolve()),
        'master_sha256': digest(folder / 'master.docx'), 'fonts': fonts,
        'state': 'candidate', 'automatic_pass': False, 'visual_review_complete': False}
    write_json(manifest_path, manifest)
    return manifest


def check_identity(manifest):
    require_actions()
    if canonical_spec(manifest['spec']) != manifest['spec_sha256']: raise WordError('TEMPLATE_SPEC_CHANGED')
    if digest(manifest['master']) != manifest['master_sha256']: raise WordError('TEMPLATE_MASTER_CHANGED')
    current = check_fonts(manifest['spec']['fonts'])
    if {k: v['sha256'] for k, v in current.items()} != {k: v['sha256'] for k, v in manifest['fonts'].items()}:
        raise WordError('TEMPLATE_FONT_CHANGED')


def check_operations(operations, manifest):
    allowed = {'text', 'formula', 'data', 'name', 'identifier', 'bookmark', 'alt', 'description'}
    for operation in operations:
        if operation['module'] in ('M05', 'M06', 'M19') or operation['action'] == 'extension':
            raise WordError('TEMPLATE_LAYOUT_LOCKED', operation['id'])
        if set(operation.get('props', {})) - allowed: raise WordError('TEMPLATE_LAYOUT_LOCKED', operation['id'])


def protected_structure(path):
    package = Package(path)
    def cleaned(element):
        element = deepcopy(element)
        for node in element.iter():
            for key in list(node.attrib):
                if key.startswith('{' + NS['wms'] + '}') or key == '{' + NS['mc'] + '}Ignorable': del node.attrib[key]
        E.cleanup_namespaces(element)
        return E.tostring(element, method='c14n')
    sections = [cleaned(s) for s in package.xml('word/document.xml').iter(W + 'sectPr')]
    return sections, cleaned(package.xml('word/styles.xml'))


def verify_locked(path, manifest):
    require_actions()
    if protected_structure(path) != protected_structure(manifest['master']): raise WordError('TEMPLATE_STRUCTURE_CHANGED')
