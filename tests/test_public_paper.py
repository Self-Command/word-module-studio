import json
from pathlib import Path
import pdfplumber
from word_module_studio.templates import build
from word_module_studio.compose import compose
from word_module_studio.render import render
from word_module_studio.package import Package, NS
from word_module_studio.runtime import digest, write_json
from test_templates import spec


def test_unmodified_licensed_public_markdown_first_use(tmp_path):
    folder = Path('fixtures/public-paper')
    source = folder / 'paper.md'
    inputs = {p.name: digest(p) for p in folder.iterdir() if p.suffix in ('.md', '.bib', '.png')}
    policy = spec(2); policy['id'] = 'public-complex-first-use'
    policy['regions'] = [policy['regions'][1]]
    manifest = build(policy, tmp_path / 'template')
    # Standard content pipeline; no source edits or fixture-specific layout branch.
    output = tmp_path / 'first.docx'
    try:
        result = compose(source, manifest, output, resources=[*folder.glob('*.png'), folder / 'paper.bib'])
        proof = render(output, tmp_path / 'proof')
        assert result['display_equations'] >= 1
        assert proof['automatic_pass'], proof['issues']
        package = Package(output)
        assert len(package.xml('word/document.xml').xpath('//*[local-name()="pic"]')) == 4
        with pdfplumber.open(tmp_path / 'proof/first.pdf') as pdf:
            text = ''.join(p.extract_text() or '' for p in pdf.pages)
            assert 'PyKoopman' in text and 'References' in text and 'Schmid' in text
    finally:
        write_json(tmp_path / 'first-use-inputs.json', {'sources': inputs, 'source_sha256': digest(source),
            'source_unchanged': all(digest(folder / name) == sha for name, sha in inputs.items()),
            'first_docx_retained': output.exists(), 'source_license': 'CC-BY-4.0'})
    assert all(digest(folder / name) == sha for name, sha in inputs.items())
