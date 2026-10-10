"""Native auxiliary parts imported through docxcompose's relationship copier."""
from copy import deepcopy
import re
from lxml import etree as E
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from docx.oxml import parse_xml
from docx.opc.oxml import serialize_part_xml
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from .package import W, NS
from .runtime import WordError

REL = NS['r'] + '/'
TYPES = {
    'footnote': (RT.FOOTNOTES, 'footnotes', 'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml'),
    'endnote': (RT.ENDNOTES, 'endnotes', 'application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml'),
    'comment': (RT.COMMENTS, 'comments', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml'),
}


def save_root(part, root):
    if hasattr(part, '_element'): part._element = root
    else: part._blob = serialize_part_xml(root)


def auxiliary(composer, source, element):
    """Remap every range/reference to one imported native note/comment."""
    if not hasattr(composer, '_aux_maps'): composer._aux_maps = {}
    for kind, (reltype, plural, content_type) in TYPES.items():
        tags = [W + kind + 'Reference'] if kind != 'comment' else [W + n for n in ('commentRangeStart', 'commentRangeEnd', 'commentReference')]
        refs = [node for node in element.iter() if node.tag in tags]
        if not refs: continue
        src = source.part.rels.part_with_reltype(reltype)
        source_root = parse_xml(src.blob)
        try: dst = composer.doc.part.rels.part_with_reltype(reltype)
        except KeyError:
            root = E.Element(W + plural, nsmap={'w': NS['w']})
            # Separator records are required for native notes, and are copied once.
            if kind != 'comment':
                root.extend(deepcopy(n) for n in source_root if int(n.get(W + 'id', '0')) <= 0)
            dst = Part(PackURI('/word/' + plural + '.xml'), content_type, E.tostring(root), composer.pkg)
            composer.doc.part.relate_to(dst, reltype)
        root = parse_xml(dst.blob)
        mapping = composer._aux_maps.setdefault((id(source.part), kind), {})
        next_id = max([int(n.get(W + 'id', '0')) for n in root] + [0]) + 1
        for ref in refs:
            old = ref.get(W + 'id')
            if old not in mapping:
                matches = [n for n in source_root if n.get(W + 'id') == old]
                if len(matches) != 1: raise WordError('MERGE_AUXILIARY_REFERENCE_INVALID', kind + '/' + str(old))
                imported = deepcopy(matches[0]); imported.set(W + 'id', str(next_id))
                mapping[old] = str(next_id); next_id += 1
                composer.add_styles(source, imported)
                composer.add_numberings(source, imported)
                for node in imported.iter():
                    for attribute in ('id', 'embed', 'link'):
                        key = '{' + NS['r'] + '}' + attribute
                        old_rel = node.get(key)
                        if old_rel:
                            if old_rel not in src.rels: raise WordError('MERGE_AUXILIARY_RELATIONSHIP_INVALID', old_rel)
                            node.set(key, composer.add_relationship(src, dst, src.rels[old_rel]).rId)
                root.append(imported)
            ref.set(W + 'id', mapping[old])
        save_root(dst, root)


def prepare_identifiers(destination, source, prefix):
    """Names are referenced by REF fields, so ID renumbering alone is insufficient."""
    used = {n.get(W + 'name') for n in destination.element.iter(W + 'bookmarkStart')}
    names = {}
    for node in source.element.iter(W + 'bookmarkStart'):
        name = node.get(W + 'name')
        if name in used:
            candidate = (prefix + '_' + name)[:40]
            suffix = 0
            while candidate in used:
                suffix += 1; candidate = (prefix + '_' + name)[:32] + '_' + str(suffix)
            names[name] = candidate; node.set(W + 'name', candidate); name = candidate
        used.add(name)
    for node in source.element.iter():
        if node.tag == W + 'hyperlink' and node.get(W + 'anchor') in names: node.set(W + 'anchor', names[node.get(W + 'anchor')])
        if node.tag in (W + 'instrText', W + 'fldSimple'):
            key = W + 'instr' if node.tag == W + 'fldSimple' else None
            text = node.get(key, '') if key else node.text or ''
            for old, new in names.items(): text = re.sub(r'(\b(?:REF|PAGEREF)\s+)' + re.escape(old) + r'\b', lambda m: m[1] + new, text)
            if key: node.set(key, text)
            else: node.text = text
    # Comment thread paragraph/durable identifiers are package-wide hexadecimal IDs.
    para_namespaces = ('http://schemas.microsoft.com/office/word/2010/wordml',
        'http://schemas.microsoft.com/office/word/2012/wordml',
        'http://schemas.microsoft.com/office/word/2016/wordml/cid',
        'http://schemas.microsoft.com/office/word/2018/wordml/cex')
    identifier_map = {}
    related = []
    for rel in source.part.rels.values():
        if rel.is_external: continue
        part = rel.target_part
        if 'comments' in str(part.partname) or str(part.partname).endswith('/people.xml'):
            root = parse_xml(part.blob); related.append((part, root))
            for node in root.iter():
                for key, value in node.attrib.items():
                    q = E.QName(key)
                    if q.namespace in para_namespaces and q.localname in ('paraId', 'durableId'):
                        import hashlib
                        number = int(hashlib.sha256((prefix + value).encode()).hexdigest()[:8], 16) & 0x7fffffff
                        identifier_map.setdefault(value, f'{number or 1:08X}')
    for part, root in related:
        for node in root.iter():
            for key, value in list(node.attrib.items()):
                if E.QName(key).namespace in para_namespaces and value in identifier_map: node.set(key, identifier_map[value])
        save_root(part, root)


def metadata(composer, source):
    """Import native comment replies/status metadata and custom XML bindings."""
    for rel in source.part.rels.values():
        if rel.is_external: continue
        name = str(rel.target_part.partname)
        if ('comments' in name and not name.endswith('/comments.xml')) or name.endswith('/people.xml'):
            try: destination = composer.doc.part.rels.part_with_reltype(rel.reltype)
            except KeyError:
                composer.add_relationship(source.part, composer.doc.part, rel); continue
            root, incoming = parse_xml(destination.blob), parse_xml(rel.target_part.blob)
            root.extend(deepcopy(n) for n in incoming)
            save_root(destination, root)
        elif rel.reltype == RT.CUSTOM_XML:
            composer.add_relationship(source.part, composer.doc.part, rel)
