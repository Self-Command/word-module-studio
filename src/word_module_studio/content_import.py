"""MIT migration of content-only resource and list import from reference-paper-studio."""
from copy import deepcopy
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from .package import W, NS
from .runtime import WordError as StudioError
R = '{' + NS['r'] + '}'


def set_child(parent, tag, attributes):
    node = parent.find(W + tag)
    if node is None: node = OxmlElement('w:' + tag); parent.append(node)
    for key, value in attributes.items(): node.set(W + key.split(':')[-1], value)
    return node

def import_resources(source, target, elements):
    """Only images and hyperlinks enter the mother; no styles/themes/headers."""
    mapping = {}
    for element in elements:
        for node in element.iter():
            for key, identifier in list(node.attrib.items()):
                if not key.startswith(R): continue
                if identifier not in mapping:
                    relation = source.part.rels[identifier]
                    if relation.reltype == RT.IMAGE and not relation.is_external:
                        # Pandoc already packaged the image. Copy its original bytes
                        # and MIME type without re-decoding it with the narrower
                        # python-docx image-header detector. Drawing extent stays
                        # in the checked content XML and is capped below.
                        from docx.parts.image import ImagePart
                        from docx.opc.packuri import PackURI
                        incoming=relation.target_part
                        collection=target.part.package.image_parts
                        matched=next((part for part in collection if part.blob==incoming.blob and part.content_type==incoming.content_type),None)
                        if matched is None:
                            names={str(part.partname) for part in target.part.package.parts}
                            index=1
                            while "/word/media/rps-image"+str(index)+"."+incoming.partname.ext in names:index+=1
                            partname=PackURI("/word/media/rps-image"+str(index)+"."+incoming.partname.ext)
                            matched=ImagePart(partname,incoming.content_type,incoming.blob)
                            collection.append(matched)
                        mapping[identifier]=target.part.relate_to(matched,RT.IMAGE)
                    elif relation.reltype == RT.HYPERLINK and relation.is_external:
                        mapping[identifier] = target.part.relate_to(relation.target_ref, RT.HYPERLINK, is_external=True)
                    else: raise StudioError("UNSUPPORTED_CONTENT_RELATION: "+relation.reltype)
                node.set(key, mapping[identifier])


def import_lists(source, target, elements):
    """Copy list semantics and restart values, replacing every indent/font."""
    numbering = target.part.numbering_part.element
    originals = source.part.numbering_part.element
    mapping = {}
    for element in elements:
        for reference in element.iter(W+"numId"):
            old = reference.get(W+"val")
            if old not in mapping:
                num = next((n for n in originals.findall(W+"num") if n.get(W+"numId") == old), None)
                if num is None: raise StudioError("INVALID_LIST_NUMBERING")
                abstract_id = num.find(W+"abstractNumId").get(W+"val")
                abstract = next(n for n in originals.findall(W+"abstractNum") if n.get(W+"abstractNumId") == abstract_id)
                aid = max([int(n.get(W+"abstractNumId")) for n in numbering.findall(W+"abstractNum")]+[0])+1
                nid = max([int(n.get(W+"numId")) for n in numbering.findall(W+"num")]+[0])+1
                clean = OxmlElement("w:abstractNum"); clean.set(W+"abstractNumId", str(aid))
                for level in abstract.findall(W+"lvl"):
                    item = OxmlElement("w:lvl"); item.set(W+"ilvl", level.get(W+"ilvl"))
                    for tag in ("start", "numFmt", "lvlText"):
                        value = level.find(W+tag)
                        if value is not None: item.append(deepcopy(value))
                    props = OxmlElement("w:pPr")
                    set_child(props, "ind", {"w:left": str(400*(int(level.get(W+"ilvl"))+1)), "w:hanging": "400"})
                    item.append(props); clean.append(item)
                first_number = numbering.find(W + 'num')
                if first_number is None: numbering.append(clean)
                else: first_number.addprevious(clean)
                copy = deepcopy(num); copy.set(W+"numId", str(nid)); copy.find(W+"abstractNumId").set(W+"val", str(aid))
                for child in list(copy):
                    if child.tag not in {W+"abstractNumId", W+"lvlOverride"}: copy.remove(child)
                numbering.append(copy); mapping[old] = str(nid)
            reference.set(W+"val", mapping[old])



