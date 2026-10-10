from copy import deepcopy
from pathlib import Path
import json
import pytest
from lxml import etree as E
from word_module_studio.package import Package, snapshot, NS, W, M
from word_module_studio.engine import execute
from word_module_studio.runtime import digest, WordError
from word_module_studio.backend import OfficeBackend
from test_native_modules import apply, item


def test_native_range_keeps_outside_text_and_format(document, tmp_path):
    api = OfficeBackend(); api.edit(document, '/body/p[1]', 'set', 'paragraph', {'text': 'alpha beta gamma', 'italic': True})
    output = apply(document, tmp_path, 'M02', item(document, 'paragraph', 'alpha beta gamma'), action='extension',
        props={'operation': 'range', 'start': 6, 'end': 10, 'text': 'DELTA', 'format': {'bold': True, 'language': 'en-US'}})
    p = item(output, 'paragraph', 'alpha DELTA gamma')
    root = Package(output).locate(p['id'])['element']
    runs = root.findall(W + 'r')
    assert len(runs) == 3
    assert all(r.find('w:rPr/w:i', namespaces=NS) is not None for r in runs)
    assert runs[1].find('w:rPr/w:b', namespaces=NS) is not None
    assert runs[0].find('w:rPr/w:b', namespaces=NS) is None


def test_multilevel_numbering_restart_and_continue(document, tmp_path):
    output = apply(document, tmp_path, 'M04', item(document, 'paragraph', 'first'), action='extension',
        props={'operation': 'list', 'start': 4, 'levels': [{'format': 'decimal', 'text': '%1.'}, {'format': 'lowerLetter', 'text': '%1.%2)'}], 'heading_styles': ['Heading1', 'Heading2']})
    package = Package(output); identifier = int(package.xml('word/document.xml').find('.//' + W + 'numId').get(W + 'val'))
    output = apply(output, tmp_path, 'M04', item(output, 'paragraph', 'second'), action='extension',
        props={'operation': 'list', 'continue_num_id': identifier, 'level': 1}, name='continued')
    package = Package(output)
    assert len(package.xml('word/document.xml').xpath('//w:numId[@w:val="' + str(identifier) + '"]', namespaces=NS)) == 2
    assert package.xml('word/numbering.xml').xpath('//w:start[@w:val="4"]', namespaces=NS)


@pytest.mark.parametrize('scope', ['first', 'even', 'default'])
def test_header_scopes_native_fields(document, tmp_path, scope):
    output = apply(document, tmp_path, 'M06', item(document, 'section'), action='extension',
        props={'operation': 'scope', 'kind': 'footer', 'type': scope, 'text': 'Page {{PAGE}} of {{NUMPAGES}}'})
    package = Package(output)
    assert package.xml('word/document.xml').xpath('//w:footerReference[@w:type="' + scope + '"]', namespaces=NS)
    text = ''.join(package.parts[n].decode() for n in package.parts if n.startswith('word/footer') and n.endswith('.xml'))
    assert 'PAGE' in text and 'NUMPAGES' in text


def test_picture_anchor_crop_and_alt(document, tmp_path):
    image = Path('fixtures/upstream/word/pictures-logo.png').resolve()
    output = apply(document, tmp_path, 'M11', item(document, 'paragraph', 'second'), action='add', kind='picture',
        props={'path': str(image), 'width': '3cm', 'height': '1.5cm', 'anchor': True, 'wrap': 'square', 'crop': '10,5,10,5',
            'hRelative': 'column', 'vRelative': 'paragraph', 'hPosition': '0cm', 'vPosition': '0cm', 'alt': 'Accessible logo'})
    root = Package(output).xml('word/document.xml')
    assert root.xpath('//*[local-name()="anchor"]')
    assert root.xpath('//*[local-name()="srcRect"][@l="10000"][@t="5000"]')
    assert root.xpath('//*[local-name()="docPr"][@descr="Accessible logo" or @title="Accessible logo"]')


@pytest.mark.parametrize('control_type,extra', [('text', {}), ('richtext', {}), ('date', {'format': 'yyyy-MM-dd'}),
    ('checkbox', {'checked': True}), ('dropdown', {'items': 'Draft|DRAFT,Final|FINAL'}), ('combobox', {'items': 'One,Two'}), ('picture', {})])
def test_native_control_variants(document, tmp_path, control_type, extra):
    output = apply(document, tmp_path, 'M16', item(document, 'body'), action='add', kind='sdt', props={'type': control_type, 'tag': 'sample', **extra})
    root = Package(output).xml('word/document.xml')
    local = {'richtext': 'richText', 'dropdown': 'dropDownList', 'combobox': 'comboBox'}.get(control_type, control_type)
    assert root.xpath('//*[local-name()="' + local + '"]')


def test_native_repeat_block_and_split_token(document, tmp_path):
    output = apply(document, tmp_path, 'M16', item(document, 'body'), action='extension',
        props={'operation': 'repeat_create', 'tag': 'records', 'text': 'Item {{item.name}}'})
    package = Package(output)
    paragraph = next(p for p in package.xml('word/document.xml').iter(W + 'p') if '{{item.name}}' in ''.join(p.xpath('.//w:t/text()', namespaces=NS)))
    run = paragraph.find(W + 'r'); run.find(W + 't').text = 'Item {{item.'
    clone = deepcopy(run)
    from word_module_studio.package import ID
    if ID in clone.attrib: del clone.attrib[ID]
    clone.find(W + 't').text = 'name}}'; paragraph.append(clone); package.save()
    output = apply(output, tmp_path, 'M16', item(output, 'document'), action='extension',
        props={'operation': 'fill', 'data': {'records': [{'name': 'Ada'}, {'name': 'Lin'}]}}, name='fill')
    root = Package(output).xml('word/document.xml')
    text = ''.join(root.xpath('//w:t/text()', namespaces=NS))
    assert 'Item Ada' in text and 'Item Lin' in text and '{{' not in text
    assert len(root.xpath('//*[local-name()="repeatingSectionItem"]')) == 2


def test_comment_reply_and_resolution(document, tmp_path):
    output = apply(document, tmp_path, 'M15', item(document, 'paragraph', 'first'), action='add', kind='comment', props={'text': 'Parent', 'author': 'Reviewer'})
    comment = item(output, 'comment', 'Parent'); number = Package(output).locate(comment['id'])['element'].get(W + 'id')
    output = apply(output, tmp_path, 'M15', item(output, 'paragraph', 'first'), action='add', kind='comment',
        props={'text': 'Reply', 'author': 'Editor', 'parentId': int(number)}, name='reply')
    output = apply(output, tmp_path, 'M15', item(output, 'comment', 'Parent'), props={'done': True}, name='resolve')
    xml = Package(output).parts['word/commentsExtended.xml'].decode()
    assert 'paraIdParent' in xml and ('done="1"' in xml or 'done="true"' in xml)


@pytest.mark.parametrize('kind,decision,remaining', [('ins', 'accept', True), ('ins', 'reject', False), ('del', 'accept', False), ('del', 'reject', True)])
def test_accept_reject_native_revisions(document, tmp_path, kind, decision, remaining):
    output = apply(document, tmp_path, 'M15', item(document, 'run', 'second'), props={'revision.type': kind, 'revision.author': 'Editor'})
    output = apply(output, tmp_path, 'M15', item(output, 'revision'), props={'revision.action': decision}, name='decide')
    root = Package(output).xml('word/document.xml')
    assert bool('second' in ''.join(root.xpath('//w:t/text()', namespaces=NS))) == remaining
    assert not list(root.iter(W + kind))


def test_editable_group_and_textbox_transform(document, tmp_path):
    output = apply(document, tmp_path, 'M13', item(document, 'body'), action='add', kind='shape',
        props={'geometry': 'rect', 'width': '2cm', 'height': '1cm', 'anchor.x': '0cm', 'anchor.y': '0cm'})
    first = item(output, 'shape')
    output = apply(output, tmp_path, 'M13', item(output, 'body'), action='add', kind='textbox',
        props={'text': 'Editable label', 'width': '2cm', 'height': '1cm', 'anchor.x': '3cm', 'anchor.y': '0cm'}, name='textbox')
    second = item(output, 'textbox')
    output = apply(output, tmp_path, 'M13', second, action='extension',
        props={'operation': 'format', 'rotation_degrees': 10, 'text': 'New label', 'text_effect': 'textArchUp'}, name='effect')
    output = apply(output, tmp_path, 'M13', item(output, 'body'), action='extension',
        props={'operation': 'group', 'objects': [first['id'], second['id']], 'name': 'Native group'}, name='group')
    root = Package(output).xml('word/document.xml')
    assert len(root.xpath('//*[local-name()="wgp"]/*[local-name()="wsp"]')) == 2
    assert 'New label' in ''.join(root.xpath('//w:t/text()', namespaces=NS))
