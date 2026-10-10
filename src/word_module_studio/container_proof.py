"""Map renderer positions and PDF glyphs to declared OOXML containers.

Ambiguous matches stay review candidates. This does not implement pagination.
"""
from collections import defaultdict
import pdfplumber
from .package import Package, W, NS
from .context import LayoutContext
from .runtime import require_actions


def check(source, pdf, layout):
    require_actions()
    package = Package(source)
    paragraphs = defaultdict(list)
    for obj in package.objects():
        if obj['kind'] == 'paragraph' and obj['text'].strip(): paragraphs[obj['text'].strip()].append(obj)
    records, issues = [], []
    with pdfplumber.open(pdf) as document:
        for rendered in layout.get('paragraphs', []):
            text = rendered['text'].strip(); matches = paragraphs.get(text, [])
            if len(matches) != 1: continue
            context = LayoutContext.resolve(package, matches[0])
            page_number = rendered['page']
            if not 1 <= page_number <= len(document.pages): continue
            page = document.pages[page_number - 1]; pg = rendered.get('page_geometry', {})
            left, right = pg.get('left_pt', 0), page.width - pg.get('right_pt', 0)
            columns = pg.get('columns', [])
            total = sum(c['width'] for c in columns)
            ranges, position = [], left
            for column in columns:
                width = (right - left) * column['width'] / total if total else right - left
                ranges.append((position + column['left_pt'], position + width - column['right_pt']))
                position += width
            if not ranges: ranges = [(left, right)]
            x = rendered['x_pt']
            chosen = min(range(len(ranges)), key=lambda i: abs(x - ranges[i][0]))
            lo, hi = ranges[chosen] if context.container == 'column' else (left, right)
            record = {'object_id': matches[0]['id'], 'page': page_number, 'container': context.container,
                'column': chosen + 1, 'bounds_pt': [lo, hi], 'available_width_pt': context.available_width_twips / 20,
                'owning_sections': context.owning_sections, 'renderer_start_pt': x, 'text': text[:100]}
            records.append(record)
            if context.container == 'column' and (x < lo - 5 or x > hi + 5):
                issues.append({'page': page_number, 'code': 'CONTAINER_START_OUTSIDE', 'severity': 'review', **record})
            # Only a unique full first line can prove a glyph span. Wrapped continuations
            # and mathematically overlapping glyphs must be read on the page.
            prefix = text.split('\n')[0][:32]
            lines = page.extract_text_lines()
            hits = [line for line in lines if prefix and prefix in line['text']]
            if len(hits) == 1 and context.container == 'column':
                hit = hits[0]
                if hit['x0'] < lo - 5 or hit['x1'] > hi + 5:
                    issues.append({'page': page_number, 'code': 'COLUMN_GLYPH_SPAN_REVIEW', 'severity': 'review',
                        'object_id': matches[0]['id'], 'bounds_pt': [lo, hi], 'glyph_span_pt': [hit['x0'], hit['x1']]})
        for frame in layout.get('frames', []):
            if frame['width_pt'] <= frame['left_inset_pt'] + frame['right_inset_pt']:
                issues.append({'page': frame['page'], 'code': 'TEXT_FRAME_NO_CONTENT_WIDTH', 'severity': 'error', 'name': frame['name']})
        for shape in layout.get('shapes', []):
            number = shape.get('page')
            if number and 1 <= number <= len(document.pages):
                page = document.pages[number - 1]
                if shape['width_pt'] > page.width + 1 or shape['height_pt'] > page.height + 1:
                    issues.append({'page': number, 'code': 'OBJECT_EXCEEDS_PAGE', 'severity': 'error', 'index': shape['index']})
    return {'paragraphs': records, 'frames': layout.get('frames', []), 'shapes': layout.get('shapes', []),
        'issues': issues, 'unmatched_paragraphs_require_visual_review': True,
        'basis': 'LibreOffice native object sizes and view cursor positions; PDF glyph spans; OOXML container ownership'}
