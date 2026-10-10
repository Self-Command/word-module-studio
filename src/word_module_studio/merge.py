"""docxcompose adapter with explicit region policy and auxiliary-part guards."""
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docxcompose.composer import Composer
from .runtime import require_actions, WordError, run, write_json, digest
from .package import Package, W, NS, ID
from .verify import relationships


class RegionComposer(Composer):
    def __init__(self, document):
        super().__init__(document, preserve_styles=True)
        self.region_relations = {}

    def remove_header_and_footer_references(self, source, element):
        # Upstream intentionally drops these. Source-regions mode imports them.
        for node in element.iter():
            if node.tag not in (W + 'headerReference', W + 'footerReference'): continue
            old = node.get('{' + NS['r'] + '}id')
            key = (id(source.part), old)
            if key not in self.region_relations:
                self.region_relations[key] = self.add_relationship(source.part, self.doc.part, source.part.rels[old]).rId
            node.set('{' + NS['r'] + '}id', self.region_relations[key])

    def fix_section_types(self, source):
        pass  # Explicit section carriers below own transitions.

    def fix_header_and_footers(self, source):
        pass  # Never overwrite source region headers with the master's headers.


def merge(master, additions, output, *, header_policy):
    require_actions()
    if header_policy not in ('master', 'source_regions'): raise WordError('MERGE_HEADER_POLICY_REQUIRED')
    destination = Document(master)
    composer = Composer(destination, preserve_styles=True) if header_policy == 'master' else RegionComposer(destination)
    before_text = []
    for source_path in additions:
        package = Package(source_path)
        # These require joint ID/anchor remapping, not a silent upstream drop.
        if any(n in package.parts for n in ('word/endnotes.xml', 'word/comments.xml')):
            raise WordError('MERGE_AUXILIARY_PART_NOT_READY', str(source_path))
        source = Document(source_path)
        for element in source.element.iter():
            for attribute in list(element.attrib):
                if attribute.startswith('{' + NS['wms'] + '}'): del element.attrib[attribute]
        before_text.append(''.join(source.element.body.xpath('.//w:t/text()')))
        if header_policy == 'source_regions':
            previous = destination.element.body.find(W + 'sectPr')
            boundary = OxmlElement('w:p'); ppr = OxmlElement('w:pPr')
            ppr.append(deepcopy(previous)); boundary.append(ppr)
            destination.element.body.insert(composer.append_index(), boundary)
            tail = deepcopy(source.element.body.find(W + 'sectPr'))
            marker = OxmlElement('w:p'); ppr = OxmlElement('w:pPr'); ppr.append(tail); marker.append(ppr)
            source.element.body.insert(len(source.element.body) - 1, marker)
            composer.append(source, remove_property_fields=False)
            inserted = destination.element.body[-2]
            if inserted.tag != W + 'p' or inserted.find('w:pPr/w:sectPr', namespaces=NS) is None:
                raise WordError('MERGE_SECTION_CARRIER_MISSING')
            incoming = inserted.find('w:pPr/w:sectPr', namespaces=NS)
            destination.element.body.replace(previous, deepcopy(incoming))
            destination.element.body.remove(inserted)
        else: composer.append(source, remove_property_fields=False)
    composer.save(output)
    result = Package(output)
    joined = ''.join(result.xml('word/document.xml').xpath('//w:t/text()', namespaces=NS))
    if any(text not in joined for text in before_text): raise WordError('MERGE_CONTENT_CHANGED')
    relationships(output)
    run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', output])
    report = {'module': 'M17', 'header_policy': header_policy, 'inputs': [digest(master), *[digest(p) for p in additions]], 'output_sha256': digest(output)}
    write_json(Path(output).with_suffix('.merge.json'), report)
    return report


def extract(source, object_ids, output):
    require_actions()
    package = Package(source)
    body = package.xml('word/document.xml').find(W + 'body')
    selected = [package.locate(identifier)['element'] for identifier in object_ids]
    carriers = []
    for node in selected:
        while node.getparent() is not None and node.getparent() is not body: node = node.getparent()
        if node.getparent() is not body: raise WordError('EXTRACT_BODY_OBJECT_REQUIRED')
        if node not in carriers: carriers.append(node)
    original = list(body)
    selected_indexes = [original.index(node) for node in carriers]
    if selected_indexes != sorted(selected_indexes): raise WordError('EXTRACT_ORDER_INVALID')
    for node in list(body):
        if node not in carriers and node.tag != W + 'sectPr': body.remove(node)
    package.save(output)
    relationships(output)
    run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', output])
    return {'module': 'M17', 'objects': object_ids, 'output_sha256': digest(output)}
