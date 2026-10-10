from pathlib import Path
import pytest
from word_module_studio.compose import compose
from word_module_studio.templates import build
from word_module_studio.package import Package, W, M, NS
from word_module_studio.runtime import WordError
from test_templates import spec


@pytest.mark.parametrize('columns', [1, 2, 3])
def test_markdown_into_registered_regions(tmp_path, columns):
    template = build(spec(columns), tmp_path / 'template')
    source = tmp_path / 'content.md'
    image = Path('fixtures/upstream/word/pictures-logo.png').resolve()
    source.write_text('# A reusable model\n\nA **bold** result with $x^2$ and a note.[^a]\n\n'
        '$$\\frac{x}{1+y}=z\\tag{M1}$$\n\n'
        '$$A=\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}\\tag{M2}$$\n\n'
        '| Parameter | Value |\n|---|---|\n| Count | 12 |\n\nTable: Measured parameters\n\n'
        f'![A retained image]({image})\n\n[^a]: A native source note.\n', encoding='utf-8')
    output = tmp_path / 'model.docx'
    report = compose(source, template, output, resources=[image], data={'front': 'A reusable model'})
    assert report['display_equations'] == 2
    package = Package(output); root = package.xml('word/document.xml')
    assert len(list(root.iter(M + 'oMath'))) == 3
    assert '(M1)' in ''.join(root.xpath('//w:t/text()', namespaces=NS))
    assert 'A native source note.' in ''.join(package.xml('word/footnotes.xml').xpath('//w:t/text()', namespaces=NS))
    captions = root.xpath('//w:p[w:pPr/w:pStyle[@w:val="Caption"]]', namespaces=NS)
    table_caption = next(p for p in captions if 'Measured parameters' in ''.join(p.xpath('.//w:t/text()', namespaces=NS)))
    assert table_caption.getprevious().tag == W + 'tbl'


def test_markdown_injection_and_missing_images_fail(tmp_path):
    template = build(spec(), tmp_path / 'template'); source = tmp_path / 'bad.md'
    source.write_text('![missing](absent.png)', encoding='utf-8')
    with pytest.raises(WordError, match='IMAGE_RESOURCE_MISSING'): compose(source, template, tmp_path / 'bad.docx')
    source.write_text('![layout](absent.png){width=200mm}', encoding='utf-8')
    with pytest.raises(WordError): compose(source, template, tmp_path / 'bad.docx')
def test_legacy_fill_escapes_semantic_data_and_preserves_registered_geometry(tmp_path):
    from word_module_studio.legacy import fill
    from word_module_studio.templates import build
    from word_module_studio.package import Package, NS
    from test_templates import spec
    manifest = build(spec(2), tmp_path / 'legacy-master')
    output = tmp_path / 'legacy.docx'
    fill(manifest, output, {'front': 'Ada & <review>', 'body': 'Retained body'})
    text = ''.join(Package(output).xml('word/document.xml').xpath('//w:t/text()', namespaces=NS))
    assert 'Ada & <review>' in text and 'Retained body' in text

def test_caption_math_and_numbered_source_references_survive(tmp_path):
    from word_module_studio.runtime import digest
    template = build(spec(2), tmp_path / 'reference-template')
    source = tmp_path / 'reference.md'
    image = Path('fixtures/upstream/word/pictures-logo.png').resolve()
    source.write_text('See figure \\ref{fig:sample} and equation \\ref{eq:sample}.\n\n'
        f'![Native $x^2$ caption.\\label{{fig:sample}}]({image})\n\n'
        '$$x=1\\tag{Q1}\\label{eq:sample}$$', encoding='utf-8')
    original = digest(source); output = tmp_path / 'references.docx'
    report = compose(source, template, output, resources=[image])
    root = Package(output).xml('word/document.xml')
    assert len(list(root.iter(M + 'oMath'))) == 2
    assert len(root.xpath('//w:fldSimple[contains(@w:instr," REF wms_")]', namespaces=NS)) == 2
    assert digest(source) == original and report['inline_math_preserved'] == 1

