"""Content control bindings and repeat/condition fill from structured data."""
from copy import deepcopy
import json
import uuid
from lxml import etree as E
from jinja2 import Environment, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from .package import W, NS, ID
from .runtime import require_execution, WordError


def apply(package, target, props):
    require_execution()
    if props.get('operation') == 'bind': return bind(package, target, props)
    if props.get('operation') == 'repeat_create': return repeat_create(package, target, props)
    if props.get('operation') != 'fill': raise WordError('CONTROL_OPERATION_UNSUPPORTED')
    if set(props) - {'operation', 'data'}: raise WordError('CONTROL_PROPERTY_UNSUPPORTED')
    data = props['data']
    if not isinstance(data, dict): raise WordError('CONTROL_DATA_REQUIRED')
    def semantic_value(value):
        if isinstance(value, (list, tuple)):
            if any(isinstance(item, (dict, list, tuple)) for item in value): raise WordError('CONTROL_STRUCTURED_VALUE_NEEDS_REPEAT')
            return '; '.join(str(item) for item in value)
        if isinstance(value, dict): raise WordError('CONTROL_STRUCTURED_VALUE_NEEDS_REPEAT')
        return value
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, finalize=semantic_value)
    root = target['element']
    count = 0
    for control in list(root.iter(W + 'sdt')):
        tag = control.find('w:sdtPr/w:tag', namespaces=NS)
        content = control.find(W + 'sdtContent')
        if tag is None or content is None: continue
        name = tag.get(W + 'val', '')
        if name.startswith('if.'):
            value = _lookup(data, name[3:])
            if not isinstance(value, bool): raise WordError('CONTROL_CONDITION_NOT_BOOLEAN', name)
            if not value:
                control.getparent().remove(control); count += 1; continue
        elif name.startswith('repeat.'):
            values = _lookup(data, name[7:])
            if not isinstance(values, list): raise WordError('CONTROL_REPEAT_NOT_LIST', name)
            prototypes = list(content)
            for child in prototypes: content.remove(child)
            for index, value in enumerate(values):
                for prototype in prototypes:
                    instance = deepcopy(prototype)
                    for node in instance.iter():
                        if ID in node.attrib: del node.attrib[ID]
                    _render(instance, environment, {**data, 'item': value, 'index': index})
                    for nested in instance.iter(W + 'sdtPr'):
                        control_id = nested.find(W + 'id')
                        if control_id is not None: control_id.set(W + 'val', str(100000 + index * 100 + len(content)))
                    content.append(instance)
            count += 1
        else:
            _render(content, environment, data); count += 1
    _render(root, environment, data)
    return {'filled_controls': count}


def _render(root, environment, data):
    # Word routinely splits a variable over runs during ordinary editing.
    for paragraph in root.iter(W + 'p'):
        texts = list(paragraph.iter(W + 't'))
        joined = ''.join(t.text or '' for t in texts)
        if '{%' in joined: raise WordError('TEMPLATE_CONTROL_TAG_IN_TEXT', 'Use native if./repeat. controls')
        if '{{' not in joined: continue
        import re
        for match in reversed(list(re.finditer(r'\{\{.*?\}\}', joined))):
            replacement = environment.from_string(match[0]).render(data)
            offset = 0; affected = []
            for node in texts:
                end = offset + len(node.text or '')
                if end > match.start() and offset < match.end(): affected.append((node, offset, end))
                offset = end
            if not affected: raise WordError('CONTROL_TOKEN_RANGE_INVALID')
            first, start, _ = affected[0]; last, last_start, _ = affected[-1]
            prefix = (first.text or '')[:match.start() - start]
            suffix = (last.text or '')[match.end() - last_start:]
            first.text = prefix + replacement + (suffix if first is last else '')
            for node, _, _ in affected[1:]: node.text = suffix if node is last else ''
        if '{{' in ''.join(t.text or '' for t in texts): raise WordError('CONTROL_TOKEN_UNRESOLVED')


def repeat_create(package, target, props):
    if set(props) - {'operation', 'tag', 'text', 'alias'}: raise WordError('REPEAT_PROPERTY_UNSUPPORTED')
    namespace = 'http://schemas.microsoft.com/office/word/2012/wordml'
    control = E.Element(W + 'sdt', nsmap={'w15': namespace})
    settings = E.SubElement(control, W + 'sdtPr')
    E.SubElement(settings, W + 'alias').set(W + 'val', props.get('alias', props['tag']))
    E.SubElement(settings, W + 'id').set(W + 'val', str(1000000 + len(list(package.xml('word/document.xml').iter(W + 'sdt')))))
    E.SubElement(settings, W + 'tag').set(W + 'val', 'repeat.' + props['tag'])
    E.SubElement(settings, '{' + namespace + '}repeatingSection')
    content = E.SubElement(control, W + 'sdtContent')
    item = E.SubElement(content, W + 'sdt'); item_props = E.SubElement(item, W + 'sdtPr')
    E.SubElement(item_props, '{' + namespace + '}repeatingSectionItem')
    paragraph = E.SubElement(E.SubElement(item, W + 'sdtContent'), W + 'p')
    E.SubElement(E.SubElement(paragraph, W + 'r'), W + 't').text = props['text']
    from .math import _append
    _append(target['element'], control)
    from .ooxml import order_properties
    order_properties(control)
    return {'type': 'native-repeating-section', 'tag': props['tag']}


def _lookup(data, key):
    current = data
    for name in key.split('.'):
        if not isinstance(current, dict) or name not in current: raise WordError('CONTROL_VALUE_MISSING', key)
        current = current[name]
    return current


def bind(package, target, props):
    if target['element'].tag != W + 'sdt': raise WordError('CONTENT_CONTROL_REQUIRED')
    if set(props) - {'operation', 'key', 'value'}: raise WordError('BIND_PROPERTY_UNSUPPORTED')
    key = props['key']
    if not key.isidentifier(): raise WordError('BIND_KEY_INVALID', key)
    index = 1
    while f'customXml/item{index}.xml' in package.parts: index += 1
    store_id = '{' + str(uuid.uuid4()).upper() + '}'
    xml = E.Element('data'); E.SubElement(xml, key).text = str(props['value'])
    item = f'customXml/item{index}.xml'
    package.parts[item] = E.tostring(xml, xml_declaration=True, encoding='UTF-8')
    ds = 'http://schemas.openxmlformats.org/officeDocument/2006/customXml'
    properties = E.Element('{' + ds + '}datastoreItem', nsmap={'ds': ds})
    properties.set('{' + ds + '}itemID', store_id)
    E.SubElement(properties, '{' + ds + '}schemaRefs')
    package.parts[f'customXml/itemProps{index}.xml'] = E.tostring(properties, xml_declaration=True, encoding='UTF-8')
    relationships = 'http://schemas.openxmlformats.org/package/2006/relationships'
    rels = E.Element('{' + relationships + '}Relationships')
    E.SubElement(rels, '{' + relationships + '}Relationship', Id='rId1', Type=NS['r'] + '/customXmlProps', Target=f'itemProps{index}.xml')
    package.parts[f'customXml/_rels/item{index}.xml.rels'] = E.tostring(rels, xml_declaration=True, encoding='UTF-8')
    document_rels = package.xml('word/_rels/document.xml.rels')
    ids = {node.get('Id') for node in document_rels}
    identifier = 1
    while 'rId' + str(identifier) in ids: identifier += 1
    E.SubElement(document_rels, '{' + relationships + '}Relationship', Id='rId' + str(identifier), Type=NS['r'] + '/customXml', Target='../' + item)
    types = package.xml('[Content_Types].xml')
    namespace = 'http://schemas.openxmlformats.org/package/2006/content-types'
    E.SubElement(types, '{' + namespace + '}Override', PartName=f'/customXml/itemProps{index}.xml', ContentType='application/vnd.openxmlformats-officedocument.customXmlProperties+xml')
    control_props = target['element'].find(W + 'sdtPr')
    old = control_props.find(W + 'dataBinding')
    if old is not None: control_props.remove(old)
    binding = E.SubElement(control_props, W + 'dataBinding')
    binding.set(W + 'storeItemID', store_id); binding.set(W + 'xpath', '/data/' + key)
    from .ooxml import order_properties
    order_properties(target['element'])
    return {'store_id': store_id, 'item': item, 'xpath': '/data/' + key}
