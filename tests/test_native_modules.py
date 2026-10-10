from copy import deepcopy
import json
from pathlib import Path
import pytest
from lxml import etree as E
from word_module_studio.backend import OfficeBackend
from word_module_studio.package import Package, snapshot, NS, W, M, semantic
from word_module_studio.engine import execute
from word_module_studio.runtime import digest, WordError, run


def apply(file, tmp_path, module, target, *, action='set', kind=None, props=None, name='result'):
    operation = {'id': name, 'module': module, 'action': action, 'target': target['id'], 'props': props or {}}
    if kind: operation['kind'] = kind
    request = {'schema_version': 1, 'input_sha256': digest(file), 'mode': 'free_edit', 'operations': [operation]}
    output = tmp_path / (name + '.docx')
    execute(request, file, output)
    return output


def item(file, kind, text=None):
    return next(o for o in snapshot(file)['objects'] if o['kind'] == kind and (text is None or o['text'] == text))


@pytest.mark.parametrize('module,props,path,expected', [
    ('M02', {'bold': True, 'italic': True, 'color': 'A00000'}, '//w:b', None),
    ('M03', {'align': 'center', 'keepNext': True}, '//w:jc', 'center'),
    ('M04', {'listStyle': 'ordered'}, '//w:numPr', None),
])
def test_basic_formatting(document, tmp_path, module, props, path, expected):
    output = apply(document, tmp_path, module, item(document, 'paragraph', 'first'), props=props)
    matches = Package(output).xml('word/document.xml').xpath(path, namespaces=NS)
    assert matches
    if expected is not None: assert matches[0].get(W + 'val') == expected
    assert 'first' in item(output, 'paragraph', 'first')['text']


def test_section_unequal_columns_and_page_number(document, tmp_path):
    section = item(document, 'section')
    output = apply(document, tmp_path, 'M05', section, props={'columns': 2, 'pageStart': 3, 'pageNumFmt': 'lowerRoman'})
    output = apply(output, tmp_path, 'M05', item(output, 'section'), action='extension',
        props={'operation': 'unequal_columns', 'widths_twips': [3500, 4200], 'gap_twips': 500}, name='unequal')
    root = Package(output).xml('word/document.xml')
    assert root.xpath('//w:cols[@w:equalWidth="0" or @w:equalWidth="false"]/w:col[@w:w="3500"]', namespaces=NS)
    assert root.xpath('//w:pgNumType[@w:start="3"][@w:fmt="lowerRoman"]', namespaces=NS)


def test_header_footer_native_fields(document, tmp_path):
    root = item(document, 'document')
    output = apply(document, tmp_path, 'M06', root, action='add', kind='footer', props={'field': 'page', 'align': 'center', 'type': 'default'})
    package = Package(output)
    footer = next(n for n in package.parts if n.startswith('word/footer') and n.endswith('.xml'))
    assert 'PAGE' in ''.join(package.xml(footer).xpath('//w:instrText/text()', namespaces=NS)).upper()


def test_bookmark_and_reference(document, tmp_path):
    output = apply(document, tmp_path, 'M07', item(document, 'paragraph', 'first'), action='add', kind='bookmark', props={'name': 'FirstSection'})
    output = apply(output, tmp_path, 'M07', item(output, 'paragraph', 'second'), action='add', kind='field', props={'fieldType': 'ref', 'name': 'FirstSection'}, name='reference')
    root = Package(output).xml('word/document.xml')
    assert root.xpath('//w:bookmarkStart[@w:name="FirstSection"]', namespaces=NS)
    assert 'REF FirstSection' in ''.join(root.xpath('//w:instrText/text()', namespaces=NS))


def test_toc_is_native_field(document, tmp_path):
    output = apply(document, tmp_path, 'M08', item(document, 'body'), action='add', kind='toc', props={'levels': '1-3', 'title': 'Contents'})
    instructions = ''.join(Package(output).xml('word/document.xml').xpath('//w:instrText/text()', namespaces=NS))
    assert 'TOC' in instructions


@pytest.mark.parametrize('formula', [r'\frac{x^{2}}{1+y}+\sum_{i=1}^{n}i',
    r'f(x)=\begin{cases}x^2 & x\geq 0\\-x & x<0\end{cases}',
    r'A=\begin{pmatrix}1&2\\3&4\end{pmatrix}',
    r'\begin{aligned}x+y&=1\\x-y&=0\end{aligned}',
    r'\int_0^1 x^{2}\,dx=\frac13'])
def test_math_native_recovery(document, tmp_path, formula):
    output = apply(document, tmp_path, 'M09', item(document, 'body'), action='extension',
        props={'formula': formula, 'mode': 'display', 'number': 'M1', 'size_pt': 10})
    root = Package(output).xml('word/document.xml')
    assert list(root.iter(M + 'oMath'))
    assert '(M1)' in ''.join(root.xpath('//w:t/text()', namespaces=NS))
    report = json.loads(output.with_suffix('.operations.json').read_text())
    assert report['operations'][0]['result']['original_math']


def test_table_three_line_continuation_titles(document, tmp_path):
    output = apply(document, tmp_path, 'M10', item(document, 'body'), action='add', kind='table', props={'rows': 8, 'cols': 2})
    output = apply(output, tmp_path, 'M10', item(output, 'table'), action='extension',
        props={'operation': 'format', 'three_line': True, 'header_rows': 1, 'split_rows': [4], 'title': 'Measured values', 'number': 1, 'caption_position': 'below'}, name='continuation')
    root = Package(output).xml('word/document.xml')
    assert len(root.findall('.//' + W + 'tbl')) == 2
    captions = root.xpath('//w:p[w:pPr/w:pStyle[@w:val="Caption"]]', namespaces=NS)
    assert len(captions) == 2 and all('Measured values' in ''.join(c.xpath('.//w:t/text()', namespaces=NS)) for c in captions)
    assert all(c.getprevious().tag == W + 'tbl' for c in captions)
    assert not root.xpath('//w:tbl//w:left[@w:val="single"] | //w:tbl//w:right[@w:val="single"]', namespaces=NS)


def test_picture_native_resource(document, tmp_path):
    image = Path('fixtures/upstream/word/pictures-logo.png').resolve()
    output = apply(document, tmp_path, 'M11', item(document, 'paragraph', 'second'), action='add', kind='picture',
        props={'path': str(image), 'width': '3cm', 'alt': 'Qualification logo'})
    package = Package(output)
    assert any(node.get('Type', '').endswith('/image') for name in package.parts if name.endswith('.rels') for node in package.xml(name))
    assert 'Qualification logo' in E.tostring(package.xml('word/document.xml')).decode()


@pytest.mark.parametrize('chart_type', ['column', 'bar', 'line', 'pie', 'area', 'scatter'])
def test_editable_chart(document, tmp_path, chart_type):
    output = apply(document, tmp_path, 'M12', item(document, 'paragraph', 'second'), action='add', kind='chart',
        props={'chartType': chart_type, 'data': 'Series:1,3,2', 'categories': 'A,B,C', 'title': 'Editable chart', 'width': '7cm', 'height': '5cm'})
    package = Package(output)
    assert any(n.startswith('word/charts/') and n.endswith('.xml') for n in package.parts)
    chart_name = next(n for n in package.parts if n.startswith('word/charts/') and n.endswith('.xml'))
    c = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart', 'r': NS['r']}
    chart = package.xml(chart_name)
    assert chart.xpath('//c:externalData[@r:id]', namespaces=c), 'Chart must link editable data'
    assert len(chart.xpath('//c:f/text()', namespaces=c)) >= 3
    rel_name = str(Path(chart_name).parent / '_rels' / (Path(chart_name).name + '.rels'))
    assert any(node.get('Type', '').endswith('/package') for node in package.xml(rel_name)), 'Chart data must be editable'


def test_native_shape(document, tmp_path):
    output = apply(document, tmp_path, 'M13', item(document, 'body'), action='add', kind='shape', props={'geometry': 'ellipse', 'width': '3cm', 'height': '1cm', 'fill': '88AAEE'})
    xml = E.tostring(Package(output).xml('word/document.xml')).decode()
    assert 'ellipse' in xml


def test_note_conversion_preserves_text(document, tmp_path):
    output = apply(document, tmp_path, 'M14', item(document, 'paragraph', 'first'), action='add', kind='footnote', props={'text': 'Real native note'})
    package = Package(output)
    assert 'word/footnotes.xml' in package.parts
    output = apply(output, tmp_path, 'M14', item(output, 'body'), action='extension', props={'operation': 'convert_notes', 'to': 'endnote'}, name='convert')
    package = Package(output)
    assert 'Real native note' in ''.join(package.xml('word/endnotes.xml').xpath('//w:t/text()', namespaces=NS))
    assert 'word/footnotes.xml' not in package.parts
    assert list(package.xml('word/document.xml').iter(W + 'endnoteReference'))


def test_comment_and_tracked_insert(document, tmp_path):
    output = apply(document, tmp_path, 'M15', item(document, 'paragraph', 'first'), action='add', kind='comment', props={'text': 'Review this paragraph', 'author': 'Reviewer'})
    run_target = next(o for o in snapshot(output)['objects'] if o['kind'] == 'run' and o['text'] == 'second')
    output = apply(output, tmp_path, 'M15', run_target, props={'revision.type': 'ins', 'revision.author': 'Editor'}, name='revision')
    package = Package(output)
    assert 'Review this paragraph' in ''.join(package.xml('word/comments.xml').xpath('//w:t/text()', namespaces=NS))
    assert package.xml('word/document.xml').xpath('//w:ins[@w:author="Editor"]', namespaces=NS)


def test_content_control_binding(document, tmp_path):
    output = apply(document, tmp_path, 'M16', item(document, 'body'), action='add', kind='sdt', props={'type': 'text', 'tag': 'customer', 'alias': 'Customer'})
    output = apply(output, tmp_path, 'M16', item(output, 'sdt'), action='extension', props={'operation': 'bind', 'key': 'customer', 'value': 'Ada'}, name='bind')
    package = Package(output)
    assert any(n.startswith('customXml/item') for n in package.parts)
    assert package.xml('word/document.xml').xpath('//w:dataBinding[@w:xpath="/data/customer"]', namespaces=NS)


def test_metadata(document, tmp_path):
    output = apply(document, tmp_path, 'M18', item(document, 'document'), props={'title': 'Public module test', 'author': 'Self-Command'})
    xml = Package(output).parts['docProps/core.xml'].decode()
    assert 'Public module test' in xml and 'Self-Command' in xml
