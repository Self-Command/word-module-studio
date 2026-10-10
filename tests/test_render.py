import json
from pathlib import Path
import pytest
import pdfplumber
from word_module_studio.templates import build
from word_module_studio.compose import compose
from word_module_studio.render import render, receipt
from word_module_studio.runtime import WordError
from test_templates import spec


@pytest.mark.parametrize('columns,landscape,sans', [(1, False, False), (2, False, False), (3, False, False), (2, True, True)])
def test_real_cloud_pagination(tmp_path, columns, landscape, sans):
    policy = spec(columns)
    if landscape:
        for region in policy['regions']: region['page']['width_twips'], region['page']['height_twips'] = 16838, 11906
    if sans: policy['fonts'].update(latin='Liberation Sans', cjk='Noto Sans CJK SC')
    policy['regions'][0]['footer'] = 'Page {{PAGE}} of {{NUMPAGES}}'
    template = build(policy, tmp_path / 'template')
    markdown = tmp_path / 'source.md'
    paragraphs = ['# Reusable modules\n\n中文内容与原生公式。']
    prose = 'A shared operation obtains the width of its own region and retains the semantic content of the input. '
    for index in range(12): paragraphs.append('COLCHECK' + str(index) + ' ' + prose * 14)
    paragraphs += [r'$$x=\frac{1+y^2}{1+z}\tag{E1}$$',
        r'$$f(x)=\begin{cases}x^2&x\geq0\\-x&x<0\end{cases}\tag{E2}$$',
        '| Category | Value |\n|---|---|\n| Observed | 123 |\n| Estimated | 122 |\n\nTable: Observations']
    markdown.write_text('\n\n'.join(paragraphs), encoding='utf-8')
    output = tmp_path / 'result.docx'
    compose(markdown, template, output, data={'front': 'Module composition proof'})
    proof = tmp_path / 'proof'; report = render(output, proof)
    assert len(report['pages']) >= 2
    assert report['automatic_pass'], report['issues']
    assert any('TeXGyrePagellaMath' in name.replace('-', '') for name in report['actual_fonts']), report['actual_fonts']
    with pdfplumber.open(proof / 'result.pdf') as pdf:
        text = ''.join(p.extract_text() or '' for p in pdf.pages)
        assert all('COLCHECK' + str(index) in text for index in range(12))
        assert '123' in text and '122' in text and '(E1)' in text and '(E2)' in text
        assert all(p.width > p.height for p in pdf.pages) if landscape else all(p.width < p.height for p in pdf.pages)
    layout = json.loads((proof / 'result.layout.json').read_text())
    starts = [p['x_pt'] for p in layout['paragraphs'] if p['text'].startswith('COLCHECK')]
    if columns > 1:
        assert max(starts) - min(starts) > 70, 'Columns must affect actual pagination, not only w:cols'
    with pytest.raises(WordError, match='VISUAL_RECEIPT_IDENTITY_MISMATCH'):
        receipt(proof, {'run_id': 'wrong'})
