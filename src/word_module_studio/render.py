"""Actual pagination, field refresh, page proofs and explicit visual receipts."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import pdfplumber
from .runtime import require_actions, WordError, run, write_json, digest
from .package import Package, NS, W, semantic

ROOT = Path(__file__).resolve().parents[2]


def render(source, folder):
    require_actions()
    source, folder = Path(source).resolve(), Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / (source.stem + '.pdf')
    fingerprints = []
    with tempfile.TemporaryDirectory() as temporary:
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0)); port = connection.getsockname()[1]
        profile = Path(temporary) / 'profile'
        process = subprocess.Popen(['libreoffice', '-env:UserInstallation=' + profile.as_uri(), '--headless', '--norestore', '--nodefault',
            f'--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            run(['/usr/bin/python3', ROOT / 'ci/uno_refresh.py', source, pdf, port], timeout=120)
        finally:
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        if not pdf.is_file(): raise WordError('RENDER_OUTPUT_MISSING')
        # Refresh the same in-memory document. Re-importing a refreshed DOCX
        # would repeatedly round-trip OMML and measure converter drift instead
        # of field/page-cache convergence.
        for attempt in range(3):
            pass_file = pdf.with_name(pdf.stem + '.pass-' + str(attempt) + '.pdf')
            with pdfplumber.open(pass_file) as document:
                signature = [(page.width, page.height, [(c['text'], round(c['x0'], 2), round(c['top'], 2)) for c in page.chars]) for page in document.pages]
            fingerprints.append(hashlib.sha256(json.dumps(signature, ensure_ascii=False).encode()).hexdigest())
        if fingerprints[-1] != fingerprints[-2]: raise WordError('FIELD_PAGINATION_NOT_CONVERGED')
    run(['pdftoppm', '-png', '-r', '110', pdf, folder / 'page'], timeout=180)
    pages = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.rsplit('-', 1)[-1]))
    if not pages: raise WordError('PAGE_PREVIEWS_MISSING')
    issues = geometry(pdf)
    report = {'schema_version': 1, 'build_success': True, 'automatic_pass': not any(i['severity'] == 'error' for i in issues),
        'visual_review_complete': False, 'delivery_accepted': False, 'renderer': 'LibreOffice 26.8.1 compatibility proof; not Microsoft Word native rendering',
        'run_id': os.environ['GITHUB_RUN_ID'], 'input_sha256': digest(source), 'output_sha256': digest(pdf),
        'pages': [{'file': p.name, 'sha256': digest(p)} for p in pages], 'convergence': fingerprints,
        'issues': issues, 'actual_fonts': pdf_fonts(pdf),
        'math_font_application': json.loads(pdf.with_suffix('.layout.json').read_text()).get('formula_fonts', [])}
    write_json(folder / 'render-report.json', report)
    return report


def geometry(pdf):
    require_actions()
    issues = []
    with pdfplumber.open(pdf) as document:
        for index, page in enumerate(document.pages, 1):
            if not page.chars and not page.images and not page.rects and not page.curves:
                issues.append({'page': index, 'code': 'BLANK_PAGE', 'severity': 'error'})
            for glyph in page.chars:
                if glyph['x0'] < -1 or glyph['x1'] > page.width + 1 or glyph['top'] < -1 or glyph['bottom'] > page.height + 1:
                    issues.append({'page': index, 'code': 'PAGE_CLIPPING', 'severity': 'error', 'text': glyph['text']})
            if page.chars:
                last = max(c['bottom'] for c in page.chars)
                if last < page.height * .35 and index < len(document.pages):
                    issues.append({'page': index, 'code': 'LARGE_WHITESPACE_REVIEW', 'severity': 'review'})
            # Same-position characters are candidates, not assumed errors: accents/math may overlap intentionally.
            positions = {}
            for glyph in page.chars:
                key = (round(glyph['x0'], 1), round(glyph['top'], 1))
                if key in positions and glyph['text'] != positions[key] and not glyph['text'].isspace():
                    issues.append({'page': index, 'code': 'OVERLAP_CANDIDATE', 'severity': 'review', 'text': positions[key] + glyph['text']})
                positions[key] = glyph['text']
    return issues


def pdf_fonts(pdf):
    require_actions()
    with pdfplumber.open(pdf) as document:
        return sorted({c['fontname'] for page in document.pages for c in page.chars})


def receipt(proof_folder, value):
    require_actions()
    proof_folder = Path(proof_folder)
    report = json.loads((proof_folder / 'render-report.json').read_text())
    if value.get('run_id') != report['run_id'] or value.get('output_sha256') != report['output_sha256']:
        raise WordError('VISUAL_RECEIPT_IDENTITY_MISMATCH')
    if value.get('pages') != report['pages']: raise WordError('VISUAL_RECEIPT_PAGE_MISMATCH')
    for page in report['pages']:
        if digest(proof_folder / page['file']) != page['sha256']: raise WordError('VISUAL_RECEIPT_PAGE_CHANGED')
    if not value.get('reviewer') or len(value.get('checklist', [])) != 21:
        raise WordError('VISUAL_RECEIPT_INCOMPLETE')
    if any(item.get('result') not in ('pass', 'fail', 'not-applicable') for item in value['checklist']):
        raise WordError('VISUAL_RECEIPT_INVALID_RESULT')
    if {item.get('id') for item in value['checklist']} != {f'V{i:02}' for i in range(1, 22)}:
        raise WordError('VISUAL_RECEIPT_CHECKLIST_MISMATCH')
    reviews = value.get('page_reviews', [])
    if {p.get('page') for p in reviews} != set(range(1, len(report['pages']) + 1)) or len(reviews) != len(report['pages']):
        raise WordError('VISUAL_RECEIPT_PAGE_REVIEWS_INCOMPLETE')
    if any(p.get('status') not in ('pass', 'fail') or not p.get('observations') for p in reviews):
        raise WordError('VISUAL_RECEIPT_PAGE_REVIEWS_INCOMPLETE')
    report['visual_review_complete'] = True
    report['visual_issues_found'] = bool(value.get('findings')) or any(item['result'] == 'fail' for item in value['checklist'])
    report['delivery_accepted'] = report['automatic_pass'] and not report['visual_issues_found']
    report['reviewer'] = value['reviewer']
    report['findings'] = value.get('findings', [])
    report['page_reviews'] = reviews
    write_json(proof_folder / 'visual-report.json', report)
    return report
