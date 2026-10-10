"""Explicit module extensions; raw HTML, raw OOXML and arbitrary code are absent."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from lxml import etree as E
from .package import W, NS, ID
from .runtime import require_actions, WordError, run


def apply(package, target, module, props):
    require_actions()
    if module == 'M09':
        from .math import apply as math_apply
        return math_apply(package, target, props)
    operation = props.get('operation')
    if module == 'M05' and operation == 'unequal_columns':
        package.save()
        result = _sdk(package.path, target['id'], module, props)
        refreshed = type(package)(package.path)
        package.parts, package.roots, package.original_trees = refreshed.parts, refreshed.roots, refreshed.original_trees
        return result
    if module == 'M14' and operation == 'convert_notes':
        package.save()
        result = _sdk(package.path, target['id'], module, props)
        refreshed = type(package)(package.path)
        package.parts, package.roots, package.original_trees = refreshed.parts, refreshed.roots, refreshed.original_trees
        return result
    if module == 'M10':
        from .tables import apply as tables_apply
        return tables_apply(package, target, props)
    if module == 'M16':
        from .controls import apply as controls_apply
        return controls_apply(package, target, props)
    if module == 'M07' and operation == 'caption':
        from .captions import apply as caption_apply
        return caption_apply(package, target, props)
    raise WordError('EXTENSION_UNSUPPORTED', f'{module}/{operation}')


def _sdk(path, target, module, props):
    with tempfile.TemporaryDirectory() as temporary:
        request = Path(temporary) / 'request.json'
        request.write_text(json.dumps({'target': target, 'module': module, 'props': props}))
        return json.loads(run(['dotnet', '.tools/sdk/WordSdk.dll', 'apply', path, request]))
