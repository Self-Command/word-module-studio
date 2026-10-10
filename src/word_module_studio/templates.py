"""Immutable masters assembled from page/region/style components."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from lxml import etree as E
from .contracts import validate
from .package import Package, W, NS
from .runtime import require_execution, WordError, digest, write_json, run


def canonical_spec(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def check_fonts(fonts):
    require_execution()
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
    require_execution()
    validate('template-spec', spec)
    if len({r['id'] for r in spec['regions']}) != len(spec['regions']): raise WordError('DUPLICATE_REGION')
    for region in spec['regions']:
        top, right, bottom, left = region['page']['margins_twips']
        width = region['page']['width_twips'] - left - right
        if width <= (region['columns'] - 1) * region['gap_twips'] or region['page']['height_twips'] <= top + bottom:
            raise WordError('INVALID_REGION_GEOMETRY', region['id'])
        if region.get('column_widths_twips') and sum(region['column_widths_twips']) + (region['columns'] - 1) * region['gap_twips'] > width:
            raise WordError('COLUMNS_CANNOT_FIT', region['id'])
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
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    document = Document()
    for name, rule in spec['styles'].items():
        style = next((s for s in document.styles if s.style_id == name or s.name == name), None)
        if style is None: style = document.styles.add_style(name, 1)
        style.font.name = spec['fonts']['latin']
        style.font.size = Pt(rule['size_pt'])
        style.font.color.rgb = RGBColor.from_string(rule.get('color', '000000'))
        style.font.bold, style.font.italic = rule.get('bold', False), rule.get('italic', False)
        fonts_node = style.element.get_or_add_rPr().get_or_add_rFonts()
        fonts_node.set(qn('w:eastAsia'), spec['fonts']['cjk'])
        fonts_node.set(qn('w:cs'), spec['fonts'].get('rtl', spec['fonts']['latin']))
        for key in list(fonts_node.attrib):
            if key.lower().endswith('theme'): del fonts_node.attrib[key]
        pformat = style.paragraph_format
        pformat.space_before = Pt(rule.get('space_before_pt', 0))
        pformat.space_after = Pt(rule.get('space_after_pt', 0))
        pformat.keep_with_next = rule.get('keep_next', False)
        pformat.line_spacing = rule.get('line_spacing', 1.0)
        if 'alignment' in rule: pformat.alignment = {'left': 0, 'center': 1, 'right': 2, 'justify': 3}[rule['alignment']]
        if rule.get('based_on'):
            parent = next((s for s in document.styles if s.style_id == rule['based_on'] or s.name == rule['based_on']), None)
            if parent is None: raise WordError('STYLE_PARENT_MISSING', rule['based_on'])
            style.base_style = parent
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
        for slot in region.get('slots', [{'key': region['id'], 'style': 'Normal'}]):
            if slot['style'] not in spec['styles']: raise WordError('SLOT_STYLE_MISSING', slot['style'])
            p = child(content, 'p')
            child(child(p, 'pPr'), 'pStyle', {'val': slot['style']})
            child(child(p, 'r'), 't').text = '{{' + slot['key'] + '}}'
        if index == len(spec['regions']) - 1: section = child(body, 'sectPr')
        else:
            marker = child(body, 'p')
            ppr = child(marker, 'pPr')
            child(ppr, 'spacing', {'before': 0, 'after': 0, 'line': 20, 'lineRule': 'exact'})
            section = child(ppr, 'sectPr')
        if region.get('break'): child(section, 'type', {'val': region['break']})
        for kind in ('header', 'footer'):
            if kind in region:
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.' + kind + '+xml'
                part = 'word/' + kind + str(index + 1) + '.xml'
                header = E.Element(W + ('hdr' if kind == 'header' else 'ftr'), nsmap={'w': NS['w']})
                paragraph = child(header, 'p'); child(child(paragraph, 'pPr'), 'jc', {'val': 'center'})
                pieces = __import__('re').split(r'(\{\{(?:PAGE|NUMPAGES)\}\})', region[kind])
                for piece in pieces:
                    if piece in ('{{PAGE}}', '{{NUMPAGES}}'):
                        field = child(paragraph, 'fldSimple', {'instr': piece[2:-2]})
                        child(child(field, 'r'), 't').text = '1'
                    elif piece:
                        text = child(child(paragraph, 'r'), 't'); text.text = piece
                        text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                package.parts[part] = E.tostring(header, encoding='UTF-8', xml_declaration=True)
                rels = package.xml('word/_rels/document.xml.rels')
                identifiers = {node.get('Id') for node in rels}; suffix = 1
                while 'rId' + str(suffix) in identifiers: suffix += 1
                relationship = E.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                    Id='rId' + str(suffix), Type=NS['r'] + '/' + kind, Target=kind + str(index + 1) + '.xml')
                reference = E.Element(W + kind + 'Reference'); reference.set(W + 'type', 'default')
                reference.set('{' + NS['r'] + '}id', relationship.get('Id')); section.insert(0, reference)
                E.SubElement(package.xml('[Content_Types].xml'), '{http://schemas.openxmlformats.org/package/2006/content-types}Override',
                    PartName='/' + part, ContentType=content_type)
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
    styles_root = package.xml('word/styles.xml')
    defaults = styles_root.find(W + 'docDefaults')
    if defaults is None: defaults = E.Element(W + 'docDefaults'); styles_root.insert(0, defaults)
    rdefault = defaults.find(W + 'rPrDefault')
    if rdefault is None: rdefault = child(defaults, 'rPrDefault')
    rprops = rdefault.find(W + 'rPr')
    if rprops is None: rprops = child(rdefault, 'rPr')
    old = rprops.find(W + 'rFonts')
    if old is not None: rprops.remove(old)
    child(rprops, 'rFonts', {'ascii': spec['fonts']['latin'], 'hAnsi': spec['fonts']['latin'], 'eastAsia': spec['fonts']['cjk'], 'cs': spec['fonts'].get('rtl', spec['fonts']['latin'])})
    if spec.get('document_language'):
        old = rprops.find(W + 'lang')
        if old is not None: rprops.remove(old)
        child(rprops, 'lang', {'val': spec['document_language']})
    math = settings.find('m:mathPr', namespaces=NS)
    if math is None: math = E.SubElement(settings, '{' + NS['m'] + '}mathPr')
    math_font = math.find('m:mathFont', namespaces=NS)
    if math_font is None: math_font = E.SubElement(math, '{' + NS['m'] + '}mathFont')
    math_font.set('{' + NS['m'] + '}val', spec['fonts']['math'])
    from .ooxml import order_properties
    order_properties(root)
    order_properties(styles_root)
    package.save()
    from .typography import native_properties, apply as typography_apply, DOCUMENT_PROPERTIES, SECTION_PROPERTIES
    if spec.get('typography'):
        if set(spec['typography']) - DOCUMENT_PROPERTIES: raise WordError('TEMPLATE_TYPOGRAPHY_UNSUPPORTED')
        native_properties(package, '/', 'document', spec['typography'])
    for name, rule in spec['styles'].items():
        if rule.get('native'): native_properties(package, '/styles/' + name, 'style', rule['native'])
    for index, region in enumerate(spec['regions'], 1):
        if region.get('native'):
            if set(region['native']) - SECTION_PROPERTIES: raise WordError('TEMPLATE_SECTION_PROPERTY_UNSUPPORTED')
            native_properties(package, '/section[' + str(index) + ']', 'section', region['native'])
    if spec.get('theme'):
        target = next(o for o in package.objects() if o['kind'] == 'document')
        typography_apply(package, target, 'M19', {'operation': 'theme', 'properties': spec['theme']})
    package.objects(stamp=True); package.save()
    for frame in spec.get('frames', []):
        target = next((o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == '{{' + frame['slot'] + '}}'), None)
        if target is None: raise WordError('FRAME_SLOT_MISSING', frame['slot'])
        typography_apply(package, target, 'M03', {'operation': 'frame', 'attributes': frame['attributes']})
    embedding = spec.get('font_embedding', {})
    if embedding.get('enabled'):
        target = next(o for o in package.objects() if o['kind'] == 'document')
        roles = embedding.get('roles', list(fonts))
        typography_apply(package, target, 'M19', {'operation': 'embed_fonts', 'fonts': [
            {**{key: fonts[role][key] for key in ('family', 'file', 'index')}, 'redistributable': embedding['redistributable']} for role in roles]})
    math = package.xml('word/settings.xml').find('m:mathPr', namespaces=NS)
    for name, value in (('brkBin', spec.get('equations', {}).get('operator_position')), ('wrapIndent', spec.get('equations', {}).get('continuation_indent_twips'))):
        if value is not None:
            node = math.find('m:' + name, namespaces=NS)
            if node is None: node = E.SubElement(math, '{' + NS['m'] + '}' + name)
            node.set('{' + NS['m'] + '}val', str(value))
    order_properties(package.xml('word/document.xml')); order_properties(package.xml('word/styles.xml'))
    package.save()
    manifest = {'schema_version': 1, 'id': spec['id'], 'version': spec['version'], 'spec': spec,
        'spec_sha256': identity, 'master': str((folder / 'master.docx').resolve()),
        'master_sha256': digest(folder / 'master.docx'), 'fonts': fonts,
        'state': 'candidate', 'automatic_pass': False, 'visual_review_complete': False}
    write_json(manifest_path, manifest)
    return manifest


def check_identity(manifest):
    require_execution()
    if manifest['id'] != manifest['spec']['id'] or manifest['version'] != manifest['spec']['version']: raise WordError('TEMPLATE_IDENTITY_MISMATCH')
    if canonical_spec(manifest['spec']) != manifest['spec_sha256']: raise WordError('TEMPLATE_SPEC_CHANGED')
    if digest(manifest['master']) != manifest['master_sha256']: raise WordError('TEMPLATE_MASTER_CHANGED')
    current = check_fonts(manifest['spec']['fonts'])
    if {k: v['sha256'] for k, v in current.items()} != {k: v['sha256'] for k, v in manifest['fonts'].items()}:
        raise WordError('TEMPLATE_FONT_CHANGED')


def register(manifest, composition, visual, destination):
    """Register only the exact master used by an accepted composition proof."""
    require_execution(); check_identity(manifest)
    if not composition.get('automatic_pass') or not visual.get('automatic_pass') or not visual.get('visual_review_complete') or not visual.get('delivery_accepted'):
        raise WordError('TEMPLATE_ACCEPTANCE_REQUIRED')
    identity = {key: manifest[key] for key in ('id', 'version', 'spec_sha256', 'master_sha256')}
    if composition.get('template') != identity: raise WordError('TEMPLATE_PROBE_IDENTITY_MISMATCH')
    if composition.get('output_sha256') != visual.get('input_sha256'): raise WordError('TEMPLATE_PROBE_OUTPUT_MISMATCH')
    registered = deepcopy(manifest)
    registered.update(state='registered', automatic_pass=True, visual_review_complete=True,
        acceptance={'run_id': visual['run_id'], 'proof_sha256': visual['output_sha256'], 'reviewer': visual['reviewer'], 'template': identity})
    write_json(destination, registered)
    return registered


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
    require_execution()
    if protected_structure(path) != protected_structure(manifest['master']): raise WordError('TEMPLATE_STRUCTURE_CHANGED')
