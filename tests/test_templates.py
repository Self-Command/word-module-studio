from copy import deepcopy
import json
import pytest
from word_module_studio.templates import build, check_identity
from word_module_studio.engine import execute
from word_module_studio.package import snapshot, Package, W
from word_module_studio.context import LayoutContext
from word_module_studio.runtime import WordError, digest


def spec(columns=2):
    return {'schema_version': 1, 'id': 'test', 'version': '1.0.0',
        'fonts': {'latin': 'Liberation Serif', 'cjk': 'Noto Serif CJK SC', 'math': 'TeX Gyre Pagella Math'},
        'regions': [{'id': 'front', 'page': {'width_twips': 11906, 'height_twips': 16838, 'margins_twips': [1247] * 4}, 'columns': 1, 'gap_twips': 340, 'break': 'continuous'},
                    {'id': 'body', 'page': {'width_twips': 11906, 'height_twips': 16838, 'margins_twips': [1247] * 4}, 'columns': columns, 'gap_twips': 340}],
        'styles': {'Normal': {'size_pt': 10}, 'Heading1': {'size_pt': 12, 'bold': True}, 'Caption': {'size_pt': 9}},
        'captions': {'figure': 'above', 'table': 'below'}}


@pytest.mark.parametrize('columns', [1, 2, 3])
def test_region_specific_context(tmp_path, columns):
    manifest = build(spec(columns), tmp_path / str(columns))
    package = Package(manifest['master'])
    paragraphs = [o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == '{{body}}']
    context = LayoutContext.resolve(package, paragraphs[0])
    assert context.columns == columns
    front = next(o for o in package.objects() if o['kind'] == 'paragraph' and o['text'] == '{{front}}')
    assert LayoutContext.resolve(package, front).columns == 1


def test_template_identity_cannot_reuse_version(tmp_path):
    manifest = build(spec(), tmp_path / 'master')
    check_identity(manifest)
    changed = spec(); changed['regions'][1]['columns'] = 1
    with pytest.raises(WordError, match='TEMPLATE_VERSION_REUSE'): build(changed, tmp_path / 'master')


@pytest.mark.parametrize('module,props', [('M05', {'columns': 1}), ('M02', {'size': 28}), ('M02', {'font': 'Other font'})])
def test_locked_template_rejects_injections(tmp_path, module, props):
    manifest = build(spec(), tmp_path / 'master')
    source = manifest['master']
    item = next(o for o in snapshot(source)['objects'] if o['kind'] == 'paragraph' and o['text'] == '{{body}}')
    batch = {'schema_version': 1, 'input_sha256': digest(source), 'mode': 'locked_template',
        'operations': [{'id': 'inject', 'module': module, 'action': 'set', 'target': item['id'], 'props': props}]}
    with pytest.raises(WordError, match='TEMPLATE_LAYOUT_LOCKED'): execute(batch, source, tmp_path / 'output.docx', template=manifest)
    assert not (tmp_path / 'output.docx').exists()


def test_missing_font_is_explicit(tmp_path):
    changed = spec(); changed['fonts']['latin'] = 'WordStudioNonexistentFont'
    with pytest.raises(WordError, match='FONT_MISSING'): build(changed, tmp_path / 'master')
