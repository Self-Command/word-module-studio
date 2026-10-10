"""Lossless ZIP parts and stable, markup-compatible object identities."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from .runtime import require_actions, WordError, digest

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
      "wms": "urn:word-module-studio:objects:v1"}
W = "{" + NS["w"] + "}"
M = "{" + NS["m"] + "}"
ID = "{" + NS["wms"] + "}id"
KINDS = {"document": "document", "body": "body", "p": "paragraph", "r": "run",
         "tbl": "table", "tr": "table-row", "tc": "table-cell", "sectPr": "section",
         "hdr": "header", "ftr": "footer", "sdt": "sdt", "footnote": "footnote",
         "endnote": "endnote", "comment": "comment", "style": "style", "styles": "styles",
         "numbering": "numbering", "abstractNum": "abstractNum", "num": "num",
         "oMath": "equation", "oMathPara": "equation", "bookmarkStart": "bookmark",
         "hyperlink": "hyperlink", "fldSimple": "field"}
KINDS.update({name: 'revision' for name in ('ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange', 'tblPrChange', 'trPrChange', 'tcPrChange', 'sectPrChange')})


class Package:
    def __init__(self, path):
        require_actions()
        self.path = Path(path)
        with ZipFile(path) as z:
            if len(set(z.namelist())) != len(z.namelist()): raise WordError("DUPLICATE_PACKAGE_PART")
            self.parts = {n: z.read(n) for n in z.namelist()}
        self.roots = {}
        self.original_trees = {}

    def xml(self, part):
        if part not in self.roots:
            parser = E.XMLParser(resolve_entities=False, no_network=True)
            self.roots[part] = E.fromstring(self.parts[part], parser)
            self.original_trees[part] = E.tostring(self.roots[part], method='c14n')
        return self.roots[part]

    def save(self, path=None):
        require_actions()
        for name, root in self.roots.items():
            if E.tostring(root, method='c14n') != self.original_trees[name]:
                self.parts[name] = E.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        target = Path(path or self.path)
        with ZipFile(target, "w", ZIP_DEFLATED) as z:
            for name, data in self.parts.items(): z.writestr(name, data)

    def objects(self, stamp=False):
        require_actions()
        objects = []
        used = {node.get(ID) for part in self.parts if part.startswith('word/') and part.endswith('.xml')
                for node in self.xml(part).iter() if node.get(ID)}
        for part in sorted(self.parts):
            if not part.startswith("word/") or not part.endswith(".xml"): continue
            root = self.xml(part)
            if not any(E.QName(e).namespace in (NS['w'], NS['m']) and E.QName(e).localname in KINDS for e in root.iter()):
                continue
            if stamp:
                namespaces = dict(root.nsmap)
                namespaces.update(wms=NS["wms"], mc=NS["mc"])
                rebuilt = E.Element(root.tag, nsmap=namespaces)
                rebuilt.attrib.update(root.attrib)
                rebuilt.text, rebuilt.tail = root.text, root.tail
                rebuilt.extend(list(root))
                ignore = set(rebuilt.get("{" + NS["mc"] + "}Ignorable", "").split())
                rebuilt.set("{" + NS["mc"] + "}Ignorable", " ".join(sorted(ignore | {"wms"})))
                root = self.roots[part] = rebuilt
            sections = list(root.iter(W + "sectPr"))
            for element in root.iter():
                local = E.QName(element).localname
                if local not in KINDS or E.QName(element).namespace not in (NS['w'], NS['m']): continue
                xpath = element.getroottree().getpath(element)
                object_id = element.get(ID) or "o_" + hashlib.sha256((part + ":" + xpath).encode()).hexdigest()[:20]
                if not element.get(ID):
                    seed, suffix = object_id, 0
                    while object_id in used:
                        suffix += 1
                        object_id = seed + '_' + str(suffix)
                    used.add(object_id)
                if stamp: element.set(ID, object_id)
                objects.append({"id": object_id, "part": part, "xpath": xpath, "kind": KINDS[local],
                    "path": native_path(element, part, sections),
                    "text": "".join(element.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS)),
                    "region": element.get("{" + NS["wms"] + "}region"),
                    "element": element})
        if len({o["id"] for o in objects}) != len(objects): raise WordError("DUPLICATE_OBJECT_ID")
        # Composite fields and drawings use their host's identity, not current indexes.
        counters = {'field': 0, 'chart': 0, 'shape': 0, 'textbox': 0}
        extra = []
        for item in objects:
            element = item['element']
            if item['kind'] == 'run':
                begin = element.find(W + 'fldChar')
                if begin is not None and begin.get(W + 'fldCharType') == 'begin':
                    counters['field'] += 1
                    extra.append({**item, 'id': item['id'] + ':field', 'kind': 'field', 'path': f"/field[{counters['field']}]"})
                drawing = element.find(W + 'drawing')
                if drawing is None: continue
                xml = E.tostring(drawing).decode()
                kind = 'chart' if 'http://schemas.openxmlformats.org/drawingml/2006/chart' in xml else 'textbox' if 'txbxContent' in xml else 'shape' if ':wsp' in xml else 'picture'
                if kind in counters:
                    counters[kind] += 1
                    path = f"/chart[{counters[kind]}]" if kind == 'chart' else f"/body/{kind}[{counters[kind]}]"
                else: path = item['path']
                extra.append({**item, 'id': item['id'] + ':' + kind, 'kind': kind, 'path': path})
        objects.extend(extra)
        return objects

    def locate(self, object_id):
        matches = [o for o in self.objects() if o["id"] == object_id]
        if len(matches) != 1: raise WordError("OBJECT_NOT_FOUND", object_id)
        return matches[0]


def native_path(element, part, sections):
    local = E.QName(element).localname
    if local == "document": return "/"
    if local == "sectPr": return f"/section[{sections.index(element) + 1}]"
    if local == "style": return "/styles/" + element.get(W + "styleId", "")
    if local in ("footnote", "endnote", "comment"):
        attribute = {"footnote": "footnoteId", "endnote": "endnoteId", "comment": "commentId"}[local]
        return f"/{'comments/' if local == 'comment' else ''}{local}[@{attribute}={element.get(W + 'id')}]"
    if local in ('ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange', 'tblPrChange', 'trPrChange', 'tcPrChange', 'sectPrChange'):
        return f"/revision[@id={element.get(W + 'id')}]"
    if local in ("hdr", "ftr"):
        prefix = "header" if local == "hdr" else "footer"
        index = re.search(r"(\d+)\.xml$", part)
        return f"/{prefix}[{index.group(1) if index else '1'}]"
    if element.getparent() is None: return "/" + local
    parent = native_path(element.getparent(), part, sections)
    same = [c for c in element.getparent() if c.tag == element.tag]
    if local == "body": return "/body"
    return parent.rstrip("/") + f"/{local}[{same.index(element) + 1}]"


def snapshot(path):
    require_actions()
    package = Package(path)
    from dataclasses import asdict
    from .context import LayoutContext
    objects = []
    for item in package.objects():
        record = {k: v for k, v in item.items() if k != 'element'}
        if item['part'] == 'word/document.xml' and item['kind'] in ('paragraph', 'table', 'equation', 'picture', 'chart', 'shape', 'textbox', 'sdt'):
            context = LayoutContext.resolve(package, item)
            record.update(layout_context=asdict(context), style=context.style_id, region=context.region)
        objects.append(record)
    known = {o["part"] for o in objects} | {'word/settings.xml', 'word/fontTable.xml', 'word/webSettings.xml'}
    return {"schema_version": 1, "sha256": digest(path), "objects": objects,
            "parts": {n: hashlib.sha256(v).hexdigest() for n, v in package.parts.items()},
            "unknown_parts": sorted(n for n in package.parts if n.startswith("word/") and n not in known and not n.endswith(".rels"))}


def semantic(path):
    require_actions()
    package = Package(path)
    result = {}
    for part in package.parts:
        if part.startswith("word/") and part.endswith(".xml"):
            root = deepcopy(package.xml(part))
            for element in root.iter():
                for attribute in list(element.attrib):
                    if attribute.startswith("{" + NS["wms"] + "}"): del element.attrib[attribute]
            result[part] = {
                "text": root.xpath("//w:t/text() | //w:delText/text()", namespaces=NS),
                "math": [_math_tree(m) for m in root.iter(M + "oMath")],
                "tables": [["".join(c.xpath(".//w:t/text()", namespaces=NS)) for c in row.findall(W + "tc")]
                           for table in root.iter(W + "tbl") for row in table.findall(W + "tr")]
            }
    return result


def _math_tree(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text or '',
            tuple(_math_tree(child) for child in node if child.tag != W + 'rPr'))
