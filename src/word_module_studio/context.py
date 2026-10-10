"""Physical constraints belong to regions, never to journal identifiers."""
from dataclasses import dataclass
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
        return cls(sections.index(section) + 1, width, height, count, gap, widths, item.get("region"))
