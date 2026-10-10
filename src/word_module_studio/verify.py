"""Relationship integrity and declared semantic changes, not mathematical proof."""
import posixpath
import re
from .package import Package, NS, W, M, semantic
from .runtime import require_actions, WordError


def relationships(path):
    require_actions()
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
    instructions = [node.text or '' for node in document.iter(W + 'instrText')]
    instructions += [node.get(W + 'instr', '') for node in document.iter(W + 'fldSimple')]
    for instruction in instructions:
        match = re.search(r'\b(?:REF|PAGEREF)\s+([A-Za-z_][A-Za-z0-9_]*)', instruction, re.I)
        if match and match[1] not in bookmarks: raise WordError('BROKEN_REFERENCE', match[1])
    return {'relationships_checked': len(checked), 'bookmarks': len(bookmarks), 'fields': len(instructions)}


def preservation(before, after, operations):
    require_actions()
    initial, final = semantic(before), semantic(after)
    text_changes = any(o['action'] in ('add', 'remove', 'extension') or any(k in o.get('props', {}) for k in ('text', 'data', 'formula', 'revision.type', 'revision.action')) for o in operations)
    if not text_changes:
        for part in initial:
            if part in final and initial[part] != final[part]: raise WordError('UNDECLARED_CONTENT_CHANGE', part)
    # Math unrelated to a math operation must remain structurally exact.
    if not any(o['module'] == 'M09' or o['action'] == 'remove' for o in operations):
        initial_math = [m for v in initial.values() for m in v['math']]
        final_math = [m for v in final.values() for m in v['math']]
        if initial_math != final_math: raise WordError('UNDECLARED_MATH_CHANGE')
    return {'format_only_exact': not text_changes, 'mathematical_objects_before': sum(len(v['math']) for v in initial.values()),
        'mathematical_objects_after': sum(len(v['math']) for v in final.values())}
