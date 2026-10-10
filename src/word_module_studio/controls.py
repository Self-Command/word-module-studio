"""Content control bindings and repeat/condition fill from structured data."""
from copy import deepcopy
import json
import uuid
from lxml import etree as E
from jinja2 import Environment, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from .package import W, NS, ID
from .runtime import require_actions, WordError


def apply(package, target, props):
    require_actions()
    if props.get('operation') == 'bind': return bind(package, target, props)
    if props.get('operation') != 'fill': raise WordError('CONTROL_OPERATION_UNSUPPORTED')
    if set(props) - {'operation', 'data'}: raise WordError('CONTROL_PROPERTY_UNSUPPORTED')
    data = props['data']
    if not isinstance(data, dict): raise WordError('CONTROL_DATA_REQUIRED')
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
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
                    content.append(instance)
            count += 1
        else:
            _render(content, environment, data); count += 1
    _render(root, environment, data)
    return {'filled_controls': count}


def _render(root, environment, data):
    for text in root.iter(W + 't'):
        if '{{' in (text.text or '') or '{%' in (text.text or ''):
            if '{%' in text.text: raise WordError('TEMPLATE_CONTROL_TAG_IN_TEXT', 'Use native if./repeat. controls')
            text.text = environment.from_string(text.text).render(data)


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
