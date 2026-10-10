"""Physical constraints belong to regions, never to journal identifiers."""
from dataclasses import dataclass
from lxml import etree as E
from .package import W, NS
from .runtime import require_actions, WordError


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

    @classmethod
    def resolve(cls, package, item):
        require_actions()
        root = package.xml("word/document.xml")
        sections = list(root.iter(W + "sectPr"))
        element = item["element"]
        if element.tag in (W + 'body', W + 'document'): section = sections[-1] if sections else None
        elif item["part"] == "word/document.xml":
            ordered = list(root.iter())
            position = ordered.index(element)
            section = next((s for s in sections if ordered.index(s) >= position), sections[-1] if sections else None)
        else: section = sections[-1] if sections else None
        if section is None: raise WordError("SECTION_GEOMETRY_MISSING")
        pg = section.find(W + "pgSz")
        margin = section.find(W + "pgMar")
        cols = section.find(W + "cols")
        def attr(node, key, default): return int(node.get(W + key, default)) if node is not None else int(default)
        width = attr(pg, "w", 12240) - attr(margin, "left", 1440) - attr(margin, "right", 1440) - attr(margin, "gutter", 0)
        height = attr(pg, "h", 15840) - attr(margin, "top", 1440) - attr(margin, "bottom", 1440)
        count, gap = attr(cols, "num", 1), attr(cols, "space", 720)
        explicit = cols.findall(W + "col") if cols is not None else []
        widths = tuple(attr(c, "w", 0) for c in explicit) if explicit else tuple((width - (count - 1) * gap) // count for _ in range(count))
        if min(widths, default=0) <= 0: raise WordError("INVALID_REGION_GEOMETRY")
        available = min(widths)
        cell = next((a for a in element.iterancestors() if a.tag == W + 'tc'), None)
        if element.tag == W + 'tc': cell = element
        if cell is not None:
            cell_width = cell.find('w:tcPr/w:tcW', namespaces=NS)
            if cell_width is not None and cell_width.get(W + 'type', 'dxa') == 'dxa':
                available = min(available, int(cell_width.get(W + 'w')))
            table = next((a for a in cell.iterancestors() if a.tag == W + 'tbl'), None)
            for side in ('left', 'right'):
                margin = cell.find('w:tcPr/w:tcMar/w:' + side, namespaces=NS)
                if margin is None and table is not None: margin = table.find('w:tblPr/w:tblCellMar/w:' + side, namespaces=NS)
                available -= int(margin.get(W + 'w', '0')) if margin is not None else 108
        if available <= 0: raise WordError('INVALID_OBJECT_GEOMETRY')
        paragraph = element if element.tag == W + 'p' else next((a for a in element.iterancestors() if a.tag == W + 'p'), None)
        style = paragraph.find('w:pPr/w:pStyle', namespaces=NS) if paragraph is not None else None
        style_id = style.get(W + 'val') if style is not None else 'Normal'
        fonts, pagination = {}, {}
        if 'word/styles.xml' in package.parts:
            styles = package.xml('word/styles.xml')
            rules = styles.xpath('./w:style[@w:styleId=$name]', namespaces=NS, name=style_id)
            properties = rules[0].find('w:rPr/w:rFonts', namespaces=NS) if rules else None
            if properties is not None: fonts = {E.QName(key).localname: value for key, value in properties.attrib.items()}
        if paragraph is not None:
            pagination = {key: paragraph.find('w:pPr/w:' + key, namespaces=NS) is not None for key in ('keepNext', 'keepLines', 'pageBreakBefore', 'widowControl')}
        region = item.get('region')
        if not region:
            slot = next((a for a in element.iterancestors() if a.tag == W + 'sdt'), None)
            tag = slot.find('w:sdtPr/w:tag', namespaces=NS) if slot is not None else None
            if tag is not None and tag.get(W + 'val', '').startswith('region.'): region = tag.get(W + 'val')[7:]
        return cls(sections.index(section) + 1, width, height, count, gap, widths, region, available, style_id, fonts, pagination)
