"""Refresh only native field results; the renderer never replaces the source package."""
from copy import deepcopy
from collections import defaultdict
import json
from pathlib import Path
import posixpath
import re
import shutil
import tempfile
from lxml import etree as E
from .package import Package, W, M, NS
from .runtime import require_actions, WordError, digest, run, write_json

SUPPORTED = {'PAGE', 'NUMPAGES', 'SECTION', 'SECTIONPAGES', 'SEQ', 'REF', 'PAGEREF', 'NOTEREF', 'TOC', 'INDEX', 'TOA', 'STYLEREF', 'DOCPROPERTY', 'DATE', 'TIME', 'AUTHOR', 'TITLE', 'FILENAME'}


def fields(root):
    """Top-level complex or simple fields; nested result fields travel with their parent."""
    stack, records = [], []
    for node in root.iter():
        if node.tag == W + 'fldSimple' and not stack:
            records.append({'simple': node, 'instruction': node.get(W + 'instr', '')})
        elif node.tag == W + 'fldChar':
            kind = node.get(W + 'fldCharType')
            if kind == 'begin': stack.append({'begin': node, 'instruction': '', 'separator': None})
            elif kind == 'separate' and stack: stack[-1]['separator'] = node
            elif kind == 'end':
                if not stack: raise WordError('FIELD_BOUNDARY_UNBALANCED')
                record = stack.pop(); record['end'] = node
                if not stack: records.append(record)
        elif node.tag == W + 'instrText' and stack and stack[-1]['separator'] is None:
            stack[-1]['instruction'] += node.text or ''
    if stack: raise WordError('FIELD_BOUNDARY_UNBALANCED')
    return records


def normalized(instruction):
    return re.sub(r'\s+', ' ', re.sub(r'\\\*\s+MERGEFORMAT', '', instruction, flags=re.I)).strip().upper()


def common(left, right):
    parents = [left, *left.iterancestors()]
    return next(n for n in [right, *right.iterancestors()] if n in parents)


def result_nodes(record):
    if 'simple' in record: return [deepcopy(n) for n in record['simple']]
    if record['separator'] is None: return []
    separator, end = record['separator'].getparent(), record['end'].getparent()
    container = common(separator, end)
    ordered = list(container.iter()); positions = {n: i for i, n in enumerate(ordered)}
    low, high = max(positions[n] for n in separator.iter()) + 1, positions[end]
    def prune(node):
        first, last = positions[node], max(positions[n] for n in node.iter())
        if first >= low and last < high: return deepcopy(node)
        if last < low or first >= high: return None
        clone = deepcopy(node)
        for child in list(clone): clone.remove(child)
        kept = [value for child in node if (value := prune(child)) is not None]
        if not kept: return None
        clone.extend(kept)
        prop = 'pPr' if node.tag == W + 'p' else 'rPr' if node.tag == W + 'r' else None
        if prop and clone.find(W + prop) is None and node.find(W + prop) is not None:
            clone.insert(0, deepcopy(node.find(W + prop)))
        return clone
    return [value for node in container if (value := prune(node)) is not None]


def replace_result(record, nodes):
    if 'simple' in record:
        field = record['simple']
        for child in list(field): field.remove(child)
        field.extend(nodes); field.set(W + 'dirty', 'false'); return
    end_run = record['end'].getparent()
    if record['separator'] is None:
        separator = E.Element(W + 'r'); record['separator'] = E.SubElement(separator, W + 'fldChar')
        record['separator'].set(W + 'fldCharType', 'separate'); end_run.addprevious(separator)
    start_run = record['separator'].getparent()
    if start_run.getparent() is end_run.getparent():
        parent = start_run.getparent(); children = list(parent)
        for node in children[children.index(start_run) + 1:children.index(end_run)]: parent.remove(node)
        position = list(parent).index(end_run)
        for node in nodes:
            values = [n for n in node if n.tag != W + 'pPr'] if node.tag == W + 'p' else [node]
            for value in values: parent.insert(position, value); position += 1
    else:
        start, end = start_run.getparent(), end_run.getparent()
        if start.tag != W + 'p' or end.tag != W + 'p' or start.getparent() is not end.getparent(): raise WordError('FIELD_CACHE_BOUNDARY_UNSUPPORTED')
        parent = start.getparent(); blocks = list(parent)
        for node in list(start)[list(start).index(start_run) + 1:]: start.remove(node)
        for node in list(end)[:list(end).index(end_run)]:
            if node.tag != W + 'pPr': end.remove(node)
        for node in blocks[blocks.index(start) + 1:blocks.index(end)]: parent.remove(node)
        for index, node in enumerate(nodes):
            if index == 0 and node.tag == W + 'p': start.extend(n for n in list(node) if n.tag != W + 'pPr')
            else: end.addprevious(node if node.tag == W + 'p' else _paragraph(node))
    record['begin'].set(W + 'dirty', 'false')


def _paragraph(node):
    result = E.Element(W + 'p'); result.append(node); return result


def parts(package):
    return [p for p in package.parts if p.startswith(('word/document', 'word/header', 'word/footer', 'word/footnotes', 'word/endnotes')) and p.endswith('.xml')]


def scope(package, part):
    if part.startswith(('word/header', 'word/footer')):
        links = {r.get('Id'): posixpath.normpath(r.get('Target', '').lstrip('/') if r.get('Target', '').startswith('/') else posixpath.join('word', r.get('Target', ''))) for r in package.xml('word/_rels/document.xml.rels')}
        tag = 'headerReference' if '/header' in part else 'footerReference'
        return tag + ':' + ','.join(str(i) + '/' + r.get(W + 'type', 'default') for i, s in enumerate(package.xml('word/document.xml').iter(W + 'sectPr')) for r in s.findall(W + tag) if links.get(r.get('{' + NS['r'] + '}id')) == part)
    return part


def without_cache(package):
    result = {}
    from .migration.math_layout import tree
    for part in parts(package):
        root = deepcopy(package.xml(part))
        for record in reversed(fields(root)): replace_result(record, [])
        for node in root.iter():
            for key in list(node.attrib):
                if key.startswith('{' + NS['wms'] + '}'): del node.attrib[key]
        result[part] = {'text': list(root.xpath('//w:t/text()', namespaces=NS)), 'math': [tree(m) for m in root.iter(M + 'oMath')]}
    return result


def cached_run_ids(package):
    from .package import ID
    return {node.get(ID) for part in parts(package) for record in fields(package.xml(part)) for value in result_nodes(record) for node in value.iter(W + 'r') if node.get(ID)}


def transplant(source, refreshed):
    baseline = without_cache(source)
    candidates = defaultdict(list)
    for part in parts(refreshed):
        for record in fields(refreshed.xml(part)):
            candidates[(scope(refreshed, part), normalized(record['instruction']))].append((part, record))
    used, updated = defaultdict(int), []
    styles = {s.get(W + 'styleId') for s in source.xml('word/styles.xml').findall(W + 'style')}
    original = source.xml('word/document.xml')
    names = {n.get(W + 'name') for n in original.iter(W + 'bookmarkStart')}
    next_bookmark = max([int(n.get(W + 'id', '0')) for n in original.iter(W + 'bookmarkStart')] + [0]) + 1
    for part in parts(source):
        for record in fields(source.xml(part)):
            code = normalized(record['instruction']); kind = code.split(' ', 1)[0]
            if kind not in SUPPORTED: continue
            key = scope(source, part), code; index = used[key]; used[key] += 1
            if index >= len(candidates[key]): raise WordError('FIELD_CACHE_MATCH_MISSING', part + ': ' + code)
            candidate_part, candidate = candidates[key][index]
            nodes = result_nodes(candidate)
            for value in nodes:
                for node in value.iter():
                    for attribute in list(node.attrib):
                        if attribute.startswith('{' + NS['wms'] + '}'): del node.attrib[attribute]
                    if node.tag in (W + 'pStyle', W + 'rStyle') and node.get(W + 'val') not in styles:
                        if node.tag == W + 'pStyle': node.set(W + 'val', 'Normal')
                        else: node.getparent().remove(node)
                    anchor = node.get(W + 'anchor')
                    if anchor and anchor not in names:
                        markers = refreshed.xml('word/document.xml').xpath('//w:bookmarkStart[@w:name=$name]', namespaces=NS, name=anchor)
                        paragraphs = [a for a in markers[0].iterancestors() if a.tag == W + 'p'] if markers else []
                        text = ''.join(paragraphs[0].xpath('.//w:t/text()', namespaces=NS)) if paragraphs else ''
                        targets = [p for p in original.iter(W + 'p') if ''.join(p.xpath('.//w:t/text()', namespaces=NS)) == text] if text else []
                        if len(targets) != 1: raise WordError('FIELD_CACHE_ANCHOR_UNRESOLVED', anchor)
                        start = E.Element(W + 'bookmarkStart'); start.set(W + 'id', str(next_bookmark)); start.set(W + 'name', anchor)
                        end = E.Element(W + 'bookmarkEnd'); end.set(W + 'id', str(next_bookmark)); next_bookmark += 1
                        position = 1 if targets[0].find(W + 'pPr') is not None else 0
                        targets[0].insert(position, start); targets[0].append(end); names.add(anchor)
                    relation_id = node.get('{' + NS['r'] + '}id')
                    if relation_id:
                        relationship_part = posixpath.dirname(candidate_part) + '/_rels/' + posixpath.basename(candidate_part) + '.rels'
                        matches = [r for r in refreshed.xml(relationship_part) if r.get('Id') == relation_id]
                        if len(matches) != 1 or matches[0].get('TargetMode') != 'External' or not matches[0].get('Type', '').endswith('/hyperlink'): raise WordError('FIELD_CACHE_RELATIONSHIP_UNSUPPORTED')
                        destination = posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'
                        root = source.xml(destination)
                        identifiers = {r.get('Id') for r in root}; serial = 1
                        while 'rIdWMSCache' + str(serial) in identifiers: serial += 1
                        imported = deepcopy(matches[0]); imported.set('Id', 'rIdWMSCache' + str(serial)); root.append(imported)
                        node.set('{' + NS['r'] + '}id', imported.get('Id'))
            replace_result(record, nodes)
            updated.append({'part': part, 'instruction': record['instruction'], 'result_text': ''.join(t.text or '' for value in nodes for t in value.iter(W + 't'))})
    if without_cache(source) != baseline: raise WordError('FIELD_REFRESH_CHANGED_SOURCE_CONTENT')
    return updated


def refresh(source, output, folder):
    require_actions()
    from .render import render
    from .verify import relationships
    source, output, folder = Path(source), Path(output), Path(folder)
    output.parent.mkdir(parents=True, exist_ok=True); folder.mkdir(parents=True, exist_ok=True)
    original = Package(source); baseline = without_cache(original); histories, records = [], []
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary) / 'cache-work.docx'; shutil.copyfile(source, work)
        for attempt in range(3):
            proof = folder / ('pass-' + str(attempt + 1)); report = render(work, proof)
            package = Package(work)
            records = transplant(package, Package(proof / 'cache-work.refreshed.docx'))
            package.save()
            signature = [(r['part'], normalized(r['instruction']), r['result_text']) for r in records]
            histories.append(signature)
            if len(histories) > 1 and histories[-1] == histories[-2]: break
        else: raise WordError('FIELD_PAGINATION_NOT_CONVERGED')
        final = Package(work)
        if without_cache(final) != baseline: raise WordError('FIELD_REFRESH_CHANGED_SOURCE_CONTENT')
        touched = set(parts(final)) | {p for p in final.parts if p.endswith('.rels') and final.parts[p] != original.parts.get(p)}
        for part, data in original.parts.items():
            if part not in touched and final.parts.get(part) != data: raise WordError('FIELD_REFRESH_CHANGED_UNRELATED_PART', part)
        integrity = relationships(work)
        sdk = json.loads(run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', work]))
        shutil.copyfile(work, output)
    final_proof = render(output, folder / 'final')
    result = {'schema_version': 1, 'automatic_pass': final_proof['automatic_pass'], 'visual_review_complete': False,
        'delivery_accepted': False, 'source_sha256': digest(source), 'output_sha256': digest(output),
        'fields_updated': records, 'cache_convergence_passes': len(histories), 'relationships': integrity, 'sdk': sdk, 'proof': final_proof}
    write_json(output.with_suffix('.fields.json'), result); return result
