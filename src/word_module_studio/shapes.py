"""Native group transforms, connectors, rotation and editable textbox effects."""
from copy import deepcopy
from lxml import etree as E
from .package import W, NS, ID
from .runtime import WordError

A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
WPS = '{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}'
WPG = '{http://schemas.microsoft.com/office/word/2010/wordprocessingGroup}'


def apply(package, target, props):
    operation = props.get('operation')
    if operation == 'group': return group(package, props)
    allowed = {'operation', 'rotation_degrees', 'text', 'text_effect', 'connector_start', 'connector_end'}
    if operation != 'format' or set(props) - allowed: raise WordError('SHAPE_EXTENSION_UNSUPPORTED')
    shape = next(iter(target['element'].iter(WPS + 'wsp')), None)
    if shape is None: raise WordError('NATIVE_SHAPE_REQUIRED')
    transform = shape.find(WPS + 'spPr/' + A + 'xfrm')
    if transform is None: raise WordError('SHAPE_TRANSFORM_MISSING')
    if 'rotation_degrees' in props: transform.set('rot', str(round(props['rotation_degrees'] * 60000)))
    if 'text' in props:
        content = next(iter(shape.iter(W + 'txbxContent')), None)
        if content is None: raise WordError('TEXTBOX_REQUIRED')
        content.clear(); E.SubElement(E.SubElement(E.SubElement(content, W + 'p'), W + 'r'), W + 't').text = props['text']
    if 'text_effect' in props:
        if props['text_effect'] not in ('textPlain', 'textArchUp', 'textArchDown', 'textCircle', 'textWave1'): raise WordError('TEXT_EFFECT_INVALID')
        body = shape.find(WPS + 'bodyPr')
        if body is None: raise WordError('TEXTBOX_REQUIRED')
        old = body.find(A + 'prstTxWarp')
        if old is not None: body.remove(old)
        warp = E.Element(A + 'prstTxWarp', prst=props['text_effect']); E.SubElement(warp, A + 'avLst'); body.insert(0, warp)
    if 'connector_start' in props or 'connector_end' in props:
        old = shape.find(WPS + 'cNvSpPr')
        if old is not None: shape.remove(old)
        props_node = shape.find(WPS + 'cNvCnPr')
        if props_node is None: props_node = E.Element(WPS + 'cNvCnPr'); shape.insert(1 if shape.find(WPS + 'cNvPr') is not None else 0, props_node)
        for key, tag in (('connector_start', 'stCxn'), ('connector_end', 'endCxn')):
            if key in props:
                other = package.locate(props[key])['element']
                candidate = next(iter(other.iter(WPS + 'cNvPr')), None)
                if candidate is None: raise WordError('CONNECTOR_TARGET_MUST_BE_GROUP_MEMBER')
                E.SubElement(props_node, A + tag, id=candidate.get('id'), idx='0')
    return {'operation': operation, 'properties': {k: v for k, v in props.items() if k != 'operation'}}


def group(package, props):
    if set(props) - {'operation', 'objects', 'name'}: raise WordError('GROUP_PROPERTY_UNSUPPORTED')
    items = [package.locate(identifier) for identifier in props['objects']]
    if len(items) < 2 or len(set(props['objects'])) != len(items): raise WordError('GROUP_OBJECTS_INVALID')
    if any(item['part'] != 'word/document.xml' for item in items): raise WordError('GROUP_PART_MISMATCH')
    drawings = [item['element'].find(W + 'drawing') for item in items]
    if any(d is None for d in drawings): raise WordError('GROUP_DRAWING_REQUIRED')
    frames = [next(iter(d), None) for d in drawings]
    shapes = [next(iter(d.iter(WPS + 'wsp')), None) for d in drawings]
    if any(s is None for s in shapes): raise WordError('GROUP_SHAPE_REQUIRED')
    coordinates = []
    for frame in frames:
        extent = frame.find(WP + 'extent')
        if extent is None: raise WordError('GROUP_EXTENT_MISSING')
        def offset(axis):
            position = frame.find(WP + 'position' + axis)
            if position is None: return 0
            value = position.find(WP + 'posOffset')
            if value is None: raise WordError('GROUP_EXPLICIT_POSITIONS_REQUIRED')
            return int(value.text)
        coordinates.append((offset('H'), offset('V'), int(extent.get('cx')), int(extent.get('cy'))))
    left, top = min(c[0] for c in coordinates), min(c[1] for c in coordinates)
    width, height = max(c[0] + c[2] for c in coordinates) - left, max(c[1] + c[3] for c in coordinates) - top
    group_node = E.Element(WPG + 'wgp', nsmap={'wpg': WPG[1:-1]})
    E.SubElement(group_node, WPG + 'cNvGrpSpPr')
    xfrm = E.SubElement(E.SubElement(group_node, WPG + 'grpSpPr'), A + 'xfrm')
    for tag, attributes in (('off', {'x': '0', 'y': '0'}), ('ext', {'cx': str(width), 'cy': str(height)}),
        ('chOff', {'x': '0', 'y': '0'}), ('chExt', {'cx': str(width), 'cy': str(height)})):
        E.SubElement(xfrm, A + tag, **attributes)
    for index, (shape, coords) in enumerate(zip(shapes, coordinates), 1):
        imported = deepcopy(shape)
        nonvisual = imported.find(WPS + 'cNvPr')
        if nonvisual is None: nonvisual = E.Element(WPS + 'cNvPr'); imported.insert(0, nonvisual)
        nonvisual.set('id', str(index)); nonvisual.set('name', 'Group member ' + str(index))
        transform = imported.find(WPS + 'spPr/' + A + 'xfrm')
        offset = transform.find(A + 'off')
        if offset is None: offset = E.Element(A + 'off'); transform.insert(0, offset)
        offset.set('x', str(coords[0] - left)); offset.set('y', str(coords[1] - top))
        group_node.append(imported)
    first = drawings[0]; graphic = next(iter(first.iter(A + 'graphicData')), None)
    if graphic is None: raise WordError('GROUP_GRAPHIC_DATA_MISSING')
    graphic.clear(); graphic.set('uri', WPG[1:-1]); graphic.append(group_node)
    extent = frames[0].find(WP + 'extent'); extent.set('cx', str(width)); extent.set('cy', str(height))
    for axis, value in (('H', left), ('V', top)):
        position = frames[0].find(WP + 'position' + axis)
        if position is not None: position.find(WP + 'posOffset').text = str(value)
    name = frames[0].find(WP + 'docPr')
    if name is not None: name.set('name', props.get('name', 'Native shape group'))
    for item in items[1:]:
        run = item['element']; run.getparent().remove(run)
    return {'members': props['objects'], 'width_emu': width, 'height_emu': height}
