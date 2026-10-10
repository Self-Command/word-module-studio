"""OOXML ownership and effective format; renderers perform actual layout."""
from dataclasses import dataclass
import posixpath
from lxml import etree as E
from .package import W, NS
from .runtime import require_execution, WordError

R = '{' + NS['r'] + '}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def effective_format(package, element):
    paragraph = element if element.tag == W + 'p' else next((a for a in element.iterancestors() if a.tag == W + 'p'), None)
    styles = package.xml('word/styles.xml') if 'word/styles.xml' in package.parts else None
    definitions = {s.get(W + 'styleId'): s for s in styles.findall(W + 'style')} if styles is not None else {}
    props = paragraph.find(W + 'pPr') if paragraph is not None else None
    named = props.find(W + 'pStyle') if props is not None else None
    default = next((s.get(W + 'styleId') for s in definitions.values() if s.get(W + 'type') == 'paragraph' and s.get(W + 'default') == '1'), 'Normal')
    style_id = named.get(W + 'val') if named is not None else default
    fonts, run, para, sources = {}, {}, {}, {}
    def merge(node, category, source):
        if node is None: return
        for child in node:
            key = E.QName(child).localname
            if key == 'rFonts':
                for role, value in child.attrib.items():
                    role = E.QName(role).localname
                    fonts[role] = value; sources['font.' + role] = source
                    fonts.pop(role[:-5] if role.endswith('Theme') else role + 'Theme', None)
            else:
                category[key] = dict(child.attrib) or {W + 'val': '1'}; sources[key] = source
    def style(name, visiting=None):
        visiting = set(visiting or ())
        if name in visiting: raise WordError('STYLE_INHERITANCE_CYCLE', name)
        node = definitions.get(name)
        if node is None: return
        visiting.add(name)
        parent = node.find(W + 'basedOn')
        if parent is not None: style(parent.get(W + 'val'), visiting)
        merge(node.find(W + 'rPr'), run, name); merge(node.find(W + 'pPr'), para, name)
    if styles is not None:
        merge(styles.find('w:docDefaults/w:rPrDefault/w:rPr', namespaces=NS), run, 'docDefaults')
        merge(styles.find('w:docDefaults/w:pPrDefault/w:pPr', namespaces=NS), para, 'docDefaults')
    style(style_id)
    if element.tag == W + 'r':
        direct = element.find(W + 'rPr')
        rstyle = direct.find(W + 'rStyle') if direct is not None else None
        if rstyle is not None: style(rstyle.get(W + 'val'))
        merge(direct, run, 'direct')
    merge(props, para, 'direct')
    theme = package.xml('word/theme/theme1.xml') if 'word/theme/theme1.xml' in package.parts else None
    language = run.get('lang', {}).get(W + 'eastAsia', run.get('lang', {}).get(W + 'val', ''))
    script = 'Jpan' if language.startswith('ja') else 'Hang' if language.startswith('ko') else 'Hant' if language in ('zh-TW', 'zh-HK') else 'Hans'
    for role in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        token = fonts.get(role + 'Theme')
        if not token or theme is None: continue
        group = 'majorFont' if token.startswith('major') else 'minorFont'
        family = 'ea' if role == 'eastAsia' else 'cs' if role == 'cs' else 'latin'
        node = theme.find('.//' + A + group + '/' + A + family)
        face = node.get('typeface') if node is not None else None
        if not face and family == 'ea':
            node = theme.find('.//' + A + group + '/' + A + "font[@script='" + script + "']")
            face = node.get('typeface') if node is not None else None
        if face: fonts[role] = face
    pagination = {key: para.get(key, {}).get(W + 'val', '0').lower() not in ('0', 'false', 'off') for key in ('keepNext', 'keepLines', 'pageBreakBefore', 'widowControl')}
    return style_id, fonts, pagination, {'run': run, 'paragraph': para, 'sources': sources}


def owning_sections(package, item):
    root = package.xml('word/document.xml'); sections = list(root.iter(W + 'sectPr'))
    element, part = item['element'], item['part']; ordered = list(root.iter())
    def owner(node):
        position = ordered.index(node)
        return next((i for i, s in enumerate(sections) if ordered.index(s) >= position), len(sections) - 1)
    if part == 'word/document.xml': return [len(sections) - 1] if element.tag in (W + 'body', W + 'document') else [owner(element)]
    if part.startswith(('word/header', 'word/footer')):
        rels = package.xml('word/_rels/document.xml.rels')
        ids = {r.get('Id') for r in rels if posixpath.normpath(r.get('Target', '').lstrip('/') if r.get('Target', '').startswith('/') else posixpath.join('word', r.get('Target', ''))) == part}
        tag = 'headerReference' if '/header' in part else 'footerReference'
        links, owners = {}, []
        for i, section in enumerate(sections):
            for ref in section.findall(W + tag): links[ref.get(W + 'type', 'default')] = ref.get(R + 'id')
            if any(value in ids for value in links.values()): owners.append(i)
        if owners: return owners
    for kind in ('footnote', 'endnote', 'comment'):
        note = element if element.tag == W + kind else next((a for a in element.iterancestors() if a.tag == W + kind), None)
        if note is not None:
            refs = [n for n in root.iter(W + kind + 'Reference') if n.get(W + 'id') == note.get(W + 'id')]
            if refs: return sorted({owner(n) for n in refs})
    raise WordError('LAYOUT_OWNERSHIP_UNRESOLVED', part)


@dataclass(frozen=True)
class LayoutContext:
    section: int
    width_twips: int
    height_twips: int
    columns: int
    gap_twips: int
    column_widths_twips: tuple
    region: str | None
    available_width_twips: int
    style_id: str | None
    fonts: dict
    pagination: dict
    owning_sections: tuple = ()
    container: str = 'column'
    effective_format: dict | None = None

    @classmethod
    def resolve(cls, package, item):
        require_execution()
        sections = list(package.xml('word/document.xml').iter(W + 'sectPr'))
        if not sections: raise WordError('SECTION_GEOMETRY_MISSING')
        owners = owning_sections(package, item)
        def attr(node, key, default): return int(node.get(W + key, default)) if node is not None else int(default)
        def geometry(i):
            section = sections[i]; pg, margin, cols = (section.find(W + n) for n in ('pgSz', 'pgMar', 'cols'))
            width = attr(pg, 'w', 12240) - attr(margin, 'left', 1440) - attr(margin, 'right', 1440) - attr(margin, 'gutter', 0)
            height = attr(pg, 'h', 15840) - attr(margin, 'top', 1440) - attr(margin, 'bottom', 1440)
            count, gap = attr(cols, 'num', 1), attr(cols, 'space', 720)
            explicit = cols.findall(W + 'col') if cols is not None else []
            widths = tuple(attr(c, 'w', 0) for c in explicit) if explicit else tuple((width - (count - 1) * gap) // count for _ in range(count))
            if min(widths, default=0) <= 0: raise WordError('INVALID_REGION_GEOMETRY')
            return width, height, count, gap, widths
        part, element = item['part'], item['element']; header = part.startswith(('word/header', 'word/footer'))
        selected = min(owners, key=lambda i: geometry(i)[0] if header else min(geometry(i)[4]))
        width, height, count, gap, widths = geometry(selected)
        available = width if header else widths[item['column_index']] if 'column_index' in item else min(widths)
        container = 'page' if header else 'column'; ancestors = [element, *element.iterancestors()]
        box = next((a for a in ancestors if E.QName(a).localname == 'txbxContent'), None)
        if box is not None:
            for host in box.iterancestors():
                extent = next(iter(host.xpath('./a:spPr/a:xfrm/a:ext | ./wps:spPr/a:xfrm/a:ext | ./wp:extent', namespaces={'a': A[1:-1], 'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape', 'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'})), None)
                if extent is not None:
                    available = int(extent.get('cx')) // 635
                    body = next(iter(host.xpath('./*[local-name()="bodyPr"]')), None)
                    available -= sum(int(body.get(k, '91440')) // 635 for k in ('lIns', 'rIns')) if body is not None else 288
                    container = 'textbox'; break
        for cell in reversed([a for a in ancestors if a.tag == W + 'tc']):
            cell_width = cell.find('w:tcPr/w:tcW', namespaces=NS)
            if cell_width is not None:
                value, unit = int(cell_width.get(W + 'w', '0')), cell_width.get(W + 'type', 'dxa')
                if unit == 'dxa': available = min(available, value)
                elif unit == 'pct': available = available * value // 5000
            table = next((a for a in cell.iterancestors() if a.tag == W + 'tbl'), None)
            for side in ('left', 'right'):
                margin = cell.find('w:tcPr/w:tcMar/w:' + side, namespaces=NS)
                if margin is None and table is not None: margin = table.find('w:tblPr/w:tblCellMar/w:' + side, namespaces=NS)
                available -= int(margin.get(W + 'w', '0')) if margin is not None else 108
            container = 'cell'
        style_id, fonts, pagination, effective = effective_format(package, element)
        ind = effective['paragraph'].get('ind', {})
        available -= int(ind.get(W + 'left', ind.get(W + 'start', '0'))) + int(ind.get(W + 'right', ind.get(W + 'end', '0')))
        if available <= 0: raise WordError('INVALID_OBJECT_GEOMETRY')
        region = item.get('region')
        if not region:
            slot = next((a for a in ancestors if a.tag == W + 'sdt'), None)
            tag = slot.find('w:sdtPr/w:tag', namespaces=NS) if slot is not None else None
            if tag is not None and tag.get(W + 'val', '').startswith('region.'): region = tag.get(W + 'val')[7:]
        return cls(selected + 1, width, height, count, gap, widths, region, available, style_id, fonts, pagination,
            tuple(i + 1 for i in owners), container, effective)
