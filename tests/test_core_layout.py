"""Independent layout contracts and actual compatibility qualification, never paper templates."""
from copy import deepcopy
from pathlib import Path
from io import BytesIO
import hashlib
import json
import pytest
from lxml import etree as E
from fontTools.ttLib import TTFont
from word_module_studio.package import Package, W, M, NS, snapshot
from word_module_studio.context import LayoutContext
from word_module_studio.templates import build, check_fonts
from word_module_studio.runtime import WordError, run, digest, write_json
from word_module_studio.render import render
from test_templates import spec
from test_native_modules import apply, item


def test_effective_style_theme_and_explicit_false(document, tmp_path):
    output = apply(document, tmp_path, 'M19', item(document, 'document'), action='extension',
        props={'operation': 'theme', 'properties': {'theme.name': 'Layout test', 'theme.font.minor.latin': 'Liberation Sans', 'theme.font.minor.cs': 'Noto Sans Arabic', 'theme.color.accent1': '227788'}})
    package = Package(output); styles = package.xml('word/styles.xml')
    base = E.SubElement(styles, W + 'style'); base.set(W + 'type', 'paragraph'); base.set(W + 'styleId', 'LayoutBase')
    E.SubElement(base, W + 'name').set(W + 'val', 'LayoutBase')
    rp = E.SubElement(base, W + 'rPr'); E.SubElement(rp, W + 'rFonts').set(W + 'asciiTheme', 'minorHAnsi')
    pp = E.SubElement(base, W + 'pPr'); E.SubElement(pp, W + 'keepNext')
    leaf = E.SubElement(styles, W + 'style'); leaf.set(W + 'type', 'paragraph'); leaf.set(W + 'styleId', 'LayoutLeaf')
    E.SubElement(leaf, W + 'name').set(W + 'val', 'LayoutLeaf'); E.SubElement(leaf, W + 'basedOn').set(W + 'val', 'LayoutBase')
    target = next(o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == 'first')
    pp = target['element'].find(W + 'pPr')
    if pp is None: pp = E.Element(W + 'pPr'); target['element'].insert(0, pp)
    for n in list(pp): pp.remove(n)
    E.SubElement(pp, W + 'pStyle').set(W + 'val', 'LayoutLeaf'); E.SubElement(pp, W + 'keepNext').set(W + 'val', '0')
    context = LayoutContext.resolve(package, target)
    assert context.fonts['ascii'] == 'Liberation Sans'
    assert not context.pagination['keepNext']
    assert context.effective_format['sources']['font.asciiTheme'] == 'LayoutBase'
    E.SubElement(base, W + 'basedOn').set(W + 'val', 'LayoutLeaf')
    with pytest.raises(WordError, match='STYLE_INHERITANCE_CYCLE'): LayoutContext.resolve(package, target)


def test_header_and_note_ownership(tmp_path):
    policy = spec(3); policy['regions'][0]['header'] = 'First section header'
    policy['regions'][1]['header'] = 'Second section header'
    manifest = build(policy, tmp_path / 'template'); package = Package(manifest['master'])
    header = next(o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == 'First section header')
    context = LayoutContext.resolve(package, header)
    assert context.owning_sections == (1,) and context.container == 'page'
    assert context.available_width_twips == context.width_twips
    sections = list(package.xml('word/document.xml').iter(W + 'sectPr'))
    second = sections[1].find(W + 'headerReference'); sections[1].remove(second)
    assert LayoutContext.resolve(package, header).owning_sections == (1, 2)


def test_native_textbox_content_width(document, tmp_path):
    output = apply(document, tmp_path, 'M13', item(document, 'body'), action='add', kind='textbox',
        props={'text': 'Textbox width', 'width': '4cm', 'height': '2cm'})
    package = Package(output)
    target = next(o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == 'Textbox width' and any(E.QName(a).localname == 'txbxContent' for a in o['element'].iterancestors()))
    context = LayoutContext.resolve(package, target)
    assert context.container == 'textbox' and 1700 < context.available_width_twips < 2400


def test_native_frame_and_original_preserved(document, tmp_path):
    before = digest(document)
    output = apply(document, tmp_path, 'M03', item(document, 'paragraph', 'first'), action='extension',
        props={'operation': 'frame', 'attributes': {'dropCap': 'drop', 'lines': 3, 'hSpace': 120, 'wrap': 'around'}})
    node = Package(output).xml('word/document.xml').find('.//' + W + 'framePr')
    assert node.get(W + 'dropCap') == 'drop' and node.get(W + 'lines') == '3'
    assert digest(document) == before


def test_font_is_really_embedded_and_reversible(document, tmp_path):
    font = check_fonts({'latin': 'Liberation Serif'})['latin']
    output = apply(document, tmp_path, 'M19', item(document, 'document'), action='extension', props={
        'operation': 'embed_fonts', 'fonts': [{**{k: font[k] for k in ('family', 'file', 'index')}, 'redistributable': True}]})
    package = Package(output); table = package.xml('word/fontTable.xml')
    ref = table.find('.//' + W + 'embedRegular'); assert ref is not None
    rel = next(n for n in package.xml('word/_rels/fontTable.xml.rels') if n.get('Id') == ref.get('{' + NS['r'] + '}id'))
    import posixpath
    target = rel.get('Target')
    data = bytearray(package.parts[posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('word', target))])
    mask = bytes.fromhex(ref.get(W + 'fontKey').strip('{}').replace('-', ''))[::-1]
    for index in range(32): data[index] ^= mask[index % 16]
    decoded = TTFont(BytesIO(data)); assert decoded['name'].getDebugName(1) == 'Liberation Serif'; decoded.close()
    report = json.loads(output.with_suffix('.operations.json').read_text())
    assert hashlib.sha256(data).hexdigest() == report['operations'][0]['result']['sources'][0]['embedded_sha256']


def test_restricted_font_and_missing_declaration_are_rejected(document, tmp_path):
    font = check_fonts({'latin': 'Liberation Serif'})['latin']; restricted = tmp_path / 'restricted.ttf'
    with TTFont(font['file']) as value: value['OS/2'].fsType = 2; value.save(restricted)
    for path, declared, error in ((restricted, True, 'FONT_EMBEDDING_RESTRICTED'), (Path(font['file']), False, 'FONT_DISTRIBUTION_DECLARATION_REQUIRED')):
        with pytest.raises(WordError, match=error):
            apply(document, tmp_path, 'M19', item(document, 'document'), action='extension', props={
                'operation': 'embed_fonts', 'fonts': [{'family': 'Liberation Serif', 'file': str(path), 'redistributable': declared}]})


def test_composable_typography_theme_table_and_math_settings(tmp_path):
    from word_module_studio.compose import compose
    policy = spec(2); policy['regions'] = [policy['regions'][1]]
    policy.update(typography={'docGrid.type': 'lines', 'docGrid.linePitch': 300, 'kinsoku': True, 'autoHyphenation': True},
        theme={'theme.color.accent1': '227788', 'theme.font.minor.latin': 'Liberation Serif'},
        table_policy={'layout': 'autofit', 'preferred_width_pct': 90},
        equations={'long_formula': 'practical', 'operator_position': 'before', 'continuation_indent_twips': 300})
    policy['styles']['Normal']['native'] = {'widowControl': True, 'kinsoku': True, 'keepLines': False}
    policy['regions'][0]['native'] = {'vAlign': 'top', 'marginHeader': 500}
    manifest = build(policy, tmp_path / 'template')
    markdown = tmp_path / 'generic.md'; markdown.write_text('# Layout core\n\n中文排版测试 Paragraph wrapping.\n\n| Name | Value |\n|---|---|\n| retained | 123 |', encoding='utf-8')
    output = tmp_path / 'generic.docx'; compose(markdown, manifest, output)
    package = Package(output)
    assert package.xml('word/document.xml').find('.//' + W + 'docGrid').get(W + 'linePitch') == '300'
    assert package.xml('word/document.xml').find('.//' + W + 'tblLayout').get(W + 'type') == 'autofit'
    assert package.xml('word/settings.xml').find('.//' + M + 'wrapIndent').get(M + 'val') == '300'
    report = render(output, tmp_path / 'proof'); assert report['automatic_pass'], report['issues']


def test_qualify_renderer_native_math_breaks(document, tmp_path):
    # A capability probe records true compatibility rather than calling unsupported output a pass.
    from word_module_studio.math import convert
    formula = convert('a+b+c+d+e+f+g+h+i+j+k+l+m+n+p+q+r+s+t+u+v+w+x+y+z')
    runs = list(formula.findall(M + 'r'))
    operators = [r for r in runs if (r.findtext(M + 't') or '').startswith('+')]
    if not operators: operators = [r for r in runs if '+' in (r.findtext(M + 't') or '')]
    if operators:
        target = operators[len(operators) // 2]
        properties = target.find(M + 'rPr')
        if properties is None: properties = E.Element(M + 'rPr'); target.insert(0, properties)
        E.SubElement(properties, M + 'brk')
    package = Package(document); body = package.xml('word/document.xml').find(W + 'body')
    p = E.Element(W + 'p'); display = E.SubElement(p, M + 'oMathPara'); display.append(formula); body.insert(0, p)
    output = tmp_path / 'native-break-probe.docx'; package.save(output)
    report = render(output, tmp_path / 'proof')
    import pdfplumber
    with pdfplumber.open(tmp_path / 'proof/native-break-probe.pdf') as pdf:
        page = pdf.pages[0]
        ys = sorted({round(c['top'] / 3) * 3 for c in page.chars if c['text'] == '+'})
    write_json(tmp_path / 'native-break-qualification.json', {'renderer': report['renderer'], 'operator_runs': len(operators),
        'native_manual_break_visible': len(ys) >= 2, 'operator_line_positions': ys, 'source_sha256': digest(output)})
    assert operators, 'Probe must place a real native operator break'


def test_practical_math_preserves_author_alignment(document, tmp_path):
    from word_module_studio.migration.semantic_import import normalize_aligned
    formula = r'\begin{aligned}x+y&=1\\x-y&=0\end{aligned}'
    assert normalize_aligned(formula) == formula
    output = apply(document, tmp_path, 'M09', item(document, 'body'), action='extension',
        props={'formula': formula, 'number': 'A1', 'policy': 'practical'})
    root = Package(output).xml('word/document.xml')
    assert ''.join(root.xpath('//m:t/text()', namespaces=NS)).count('=') == 2
    assert root.find('.//' + M + 'm') is not None or root.find('.//' + M + 'eqArr') is not None
    report = render(output, tmp_path / 'alignment-proof'); assert report['automatic_pass'], report['issues']


def test_practical_math_never_splits_nested_atoms(document, tmp_path):
    from word_module_studio.math import convert
    numerator = '+'.join('x_{' + str(i) + '}' for i in range(35))
    formula = r'\frac{' + numerator + '}{1+x^2}'
    expected = convert(formula).find(M + 'f')
    output = apply(document, tmp_path, 'M09', item(document, 'body'), action='extension',
        props={'formula': formula, 'number': 'F1', 'policy': 'practical'})
    actual = Package(output).xml('word/document.xml').find('.//' + M + 'f')
    from word_module_studio.migration.math_layout import tree
    assert tree(actual) == tree(expected)
    assert actual.find('.//' + M + 'eqArr') is None
    report = json.loads(output.with_suffix('.operations.json').read_text())['operations'][0]['result']
    assert report['layout_status'] == 'needs_minor_adjustment' and report['manual_adjustments']


def test_field_cache_refresh_changes_only_results(document, tmp_path):
    from word_module_studio.field_cache import refresh, fields, without_cache
    package = Package(document); body = package.xml('word/document.xml').find(W + 'body')
    p = E.Element(W + 'p'); field = E.SubElement(p, W + 'fldSimple'); field.set(W + 'instr', ' NUMPAGES ')
    E.SubElement(E.SubElement(field, W + 'r'), W + 't').text = '999'; body.insert(0, p)
    package.save(); before = digest(document); baseline = without_cache(Package(document))
    output = tmp_path / 'cached.docx'; result = refresh(document, output, tmp_path / 'cache-proof')
    assert result['fields_updated'][0]['result_text'] == '1'
    assert without_cache(Package(output)) == baseline and digest(document) == before
    assert result['cache_convergence_passes'] == 2
