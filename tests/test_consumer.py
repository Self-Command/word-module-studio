import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from consumers.reference_paper import export, template_spec
from word_module_studio.templates import build
from word_module_studio.package import Package, NS, W
from word_module_studio.runtime import run
from word_module_studio.compose import compose
from word_module_studio.render import render

FONTS = {'latin': 'Liberation Serif', 'cjk': 'Noto Serif CJK SC', 'math': 'TeX Gyre Pagella Math'}


@pytest.mark.parametrize('definition', sorted(Path('fixtures/consumer-policies').glob('*.json')), ids=lambda p: p.stem)
def test_nine_consumer_policies_are_only_compositions(tmp_path, definition):
    value = json.loads(definition.read_text(encoding='utf-8-sig'))
    # This tests the personal review layout, preserving the consumer's pending official/MD approvals.
    for variant in ('front', 'end'):
        spec = template_spec(value, value['policy'], FONTS, variant=variant)
        manifest = build(spec, tmp_path / variant)
        run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', manifest['master']])
        assert manifest['spec']['id'] == value['id']
        assert manifest['spec']['regions'][1]['columns'] == value['policy']['body_columns']
        source = tmp_path / ('source-' + variant + '.md')
        source.write_text('# Composed policy\n\n中文角色与英文内容 123。\n\n'
            '$$x=\\frac{1+y}{1+z}\\tag{E1}$$\n\n'
            '| Key | Value |\n|---|---|\n| Retained | 123 |\n\nTable: Values', encoding='utf-8')
        output = tmp_path / (variant + '.docx')
        compose(source, manifest, output, region='body', data={'title_zh': '组合校样', 'title_en': 'Composition proof'})
        proof = render(output, tmp_path / ('proof-' + variant))
        assert proof['automatic_pass'], proof['issues']


def test_original_model_thirty_formula_identity_and_text(tmp_path):
    definition = json.loads(Path('fixtures/consumer-policies/general-modeling.json').read_text())
    definition['id'] = 'model-regression'; definition['policy']['body_columns'] = 2
    output = tmp_path / 'model.docx'
    report = export('fixtures/model/model.md', definition, FONTS, output,
        metadata=json.loads(Path('fixtures/model/metadata.json').read_text()))
    assert report['display_equations'] == 30
    assert {e['number'] for e in report['equations']} == {'M' + str(i) for i in range(1, 31)}
    assert all(e['original_math'] for e in report['equations'])
    text = ''.join(Package(output).xml('word/document.xml').xpath('//w:t/text()', namespaces=NS))
    assert all('(M' + str(i) + ')' in text for i in range(1, 31))
    proof = render(output, tmp_path / 'proof')
    assert proof['automatic_pass'], proof['issues']
    import pdfplumber
    with pdfplumber.open(tmp_path / 'proof/model.pdf') as pdf:
        text = ''.join(p.extract_text() or '' for p in pdf.pages)
        assert all('(M' + str(i) + ')' in text for i in range(1, 31))
