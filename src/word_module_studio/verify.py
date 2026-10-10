"""Relationship integrity and declared semantic changes, not mathematical proof."""
import posixpath
import re
from .package import Package, NS, W, M, semantic
from .runtime import require_execution, WordError


def relationships(path):
    require_execution()
    package = Package(path)
    checked = []
    for part in package.parts:
        if not part.endswith('.rels'): continue
        base = '' if part == '_rels/.rels' else posixpath.dirname(posixpath.dirname(part))
        root = package.xml(part)
        ids = []
        for relationship in root:
            ids.append(relationship.get('Id'))
            if relationship.get('TargetMode') == 'External': continue
            target = relationship.get('Target', '').split('#')[0]
            resolved = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(base, target))
            if resolved not in package.parts: raise WordError('BROKEN_RELATIONSHIP', part + ': ' + resolved)
            checked.append(resolved)
        if len(ids) != len(set(ids)): raise WordError('DUPLICATE_RELATIONSHIP_ID', part)
    document = package.xml('word/document.xml')
    bookmarks = {node.get(W + 'name') for node in document.iter(W + 'bookmarkStart')}
    for link in document.iter(W + 'hyperlink'):
        anchor = link.get(W + 'anchor')
        if anchor and anchor not in bookmarks: raise WordError('BROKEN_HYPERLINK_REFERENCE', anchor)
    instructions = [node.text or '' for node in document.iter(W + 'instrText')]
    instructions += [node.get(W + 'instr', '') for node in document.iter(W + 'fldSimple')]
    for instruction in instructions:
        match = re.search(r'\b(?:REF|PAGEREF)\s+([A-Za-z_][A-Za-z0-9_]*)', instruction, re.I)
        if match and match[1] not in bookmarks: raise WordError('BROKEN_REFERENCE', match[1])
    return {'relationships_checked': len(checked), 'bookmarks': len(bookmarks), 'fields': len(instructions)}


def preservation(before, after, operations):
    require_execution()
    initial, final = semantic(before), semantic(after)
    from .package import ID
    old_package, new_package = Package(before), Package(after)
    old_objects = old_package.objects(); new_objects = {o['id']: o for o in new_package.objects()}
    authorized = set()
    for operation in operations:
        if operation['module'] == 'M08' and operation.get('props', {}).get('operation') == 'refresh_fields':
            from .field_cache import cached_run_ids
            authorized.update(cached_run_ids(old_package))
        props = operation.get('props', {})
        drop_cap = operation['action'] == 'extension' and operation['module'] in ('M03', 'M13') and props.get('operation') == 'frame' and props.get('attributes', {}).get('dropCap') in ('drop', 'margin')
        changes_content = drop_cap or operation['action'] == 'remove' or operation['action'] == 'extension' and operation['module'] in ('M02', 'M10', 'M13', 'M16') or any(
            key in props for key in ('text', 'find', 'replace', 'data', 'formula', 'revision.type', 'revision.action'))
        if not changes_content: continue
        target = old_package.locate(operation['target'])
        nodes = set(target['element'].iter())
        authorized.update(o['id'] for o in old_objects if o['element'] in nodes)
        if operation['module'] == 'M13' and props.get('operation') == 'group':
            for identifier in props.get('objects', []):
                host = old_package.locate(identifier)['element']
                authorized.update(o['id'] for o in old_objects if o['element'] in set(host.iter()))
    untouched_runs = 0
    for old in old_objects:
        if old['kind'] != 'run' or old['id'] in authorized: continue
        new = new_objects.get(old['id'])
        if new is None or new['text'] != old['text']: raise WordError('UNDECLARED_RUN_CONTENT_CHANGE', old['id'])
        untouched_runs += 1
    text_changes = any(o['action'] in ('add', 'remove', 'extension') or any(k in o.get('props', {}) for k in ('text', 'data', 'formula', 'revision.type', 'revision.action')) for o in operations)
    if not text_changes:
        for part in initial:
            if part in final and initial[part] != final[part]: raise WordError('UNDECLARED_CONTENT_CHANGE', part)
    # Math unrelated to a math operation must remain structurally exact.
    if not any(o['module'] == 'M09' or o['action'] == 'remove' for o in operations):
        initial_math = [m for v in initial.values() for m in v['math']]
        final_math = [m for v in final.values() for m in v['math']]
        if initial_math != final_math: raise WordError('UNDECLARED_MATH_CHANGE')
    return {'format_only_exact': not text_changes, 'untouched_runs_verified': untouched_runs,
        'mathematical_objects_before': sum(len(v['math']) for v in initial.values()),
        'mathematical_objects_after': sum(len(v['math']) for v in final.values())}
