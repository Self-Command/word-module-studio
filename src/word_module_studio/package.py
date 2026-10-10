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


class Package:
    def __init__(self, path):
        require_actions()
        self.path = Path(path)
        with ZipFile(path) as z:
            if len(set(z.namelist())) != len(z.namelist()): raise WordError("DUPLICATE_PACKAGE_PART")
            self.parts = {n: z.read(n) for n in z.namelist()}
        self.roots = {}

    def xml(self, part):
        if part not in self.roots:
            parser = E.XMLParser(resolve_entities=False, no_network=True)
            self.roots[part] = E.fromstring(self.parts[part], parser)
        return self.roots[part]

    def save(self, path=None):
        require_actions()
        for name, root in self.roots.items():
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
                if local not in KINDS: continue
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
        return f"/{local}[@{attribute}={element.get(W + 'id')}]"
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
    objects = [{k: v for k, v in o.items() if k != "element"} for o in package.objects()]
    known = {o["part"] for o in objects}
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
                "math": [E.tostring(m, method="c14n").decode() for m in root.iter(M + "oMath")],
                "tables": [["".join(c.xpath(".//w:t/text()", namespaces=NS)) for c in row.findall(W + "tc")]
                           for table in root.iter(W + "tbl") for row in table.findall(W + "tr")]
            }
    return result
