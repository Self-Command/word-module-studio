import os
from copy import deepcopy
import pytest
from word_module_studio.package import snapshot, Package, W
from word_module_studio.engine import execute
from word_module_studio.runtime import WordError, digest, require_actions


def batch(file, operations):
    return {'schema_version': 1, 'input_sha256': digest(file), 'mode': 'free_edit', 'operations': operations}


def test_stable_target_and_original_preserved(document, tmp_path):
    original = digest(document)
    snap = snapshot(document)
    body = next(o for o in snap['objects'] if o['kind'] == 'body')
    second = next(o for o in snap['objects'] if o['kind'] == 'paragraph' and o['text'] == 'second')
    operations = [{'id': 'add', 'module': 'M02', 'action': 'add', 'target': body['id'], 'kind': 'paragraph', 'props': {'text': 'third'}},
                  {'id': 'update', 'module': 'M02', 'action': 'set', 'target': second['id'], 'props': {'text': 'changed'}}]
    output = tmp_path / 'result.docx'
    report = execute(batch(document, operations), document, output)
    assert report['automatic_pass'] and not report['visual_review_complete']
    assert digest(document) == original
    updated = next(o for o in snapshot(output)['objects'] if o['id'] == second['id'])
    assert updated['text'] == 'changed'
    assert 'third' in [o['text'] for o in snapshot(output)['objects'] if o['kind'] == 'paragraph']


def test_failed_batch_rolls_back(document, tmp_path):
    p = next(o for o in snapshot(document)['objects'] if o['kind'] == 'paragraph' and o['text'] == 'first')
    operations = [{'id': 'valid', 'module': 'M02', 'action': 'set', 'target': p['id'], 'props': {'text': 'modified'}},
                  {'id': 'invalid', 'module': 'M02', 'action': 'set', 'target': p['id'], 'props': {'madeUpProperty': 'invalid'}}]
    original = digest(document)
    output = tmp_path / 'result.docx'
    with pytest.raises(WordError, match='UNSUPPORTED_PROPERTY'): execute(batch(document, operations), document, output)
    assert digest(document) == original and not output.exists()


def test_stale_input_rejected(document, tmp_path):
    item = next(o for o in snapshot(document)['objects'] if o['kind'] == 'body')
    request = batch(document, [{'id': 'read', 'module': 'M01', 'action': 'get', 'target': item['id']}])
    request['input_sha256'] = '0' * 64
    with pytest.raises(WordError, match='STALE_INPUT'): execute(request, document, tmp_path / 'result.docx')


def test_document_apis_work_without_actions(monkeypatch, document, tmp_path):
    monkeypatch.delenv('GITHUB_ACTIONS')
    monkeypatch.delenv('GITHUB_RUN_ID')
    snap = snapshot(document)
    request = batch(document, [{'id': 'read', 'module': 'M01', 'action': 'get', 'target': snap['objects'][0]['id']}])
    report = execute(request, document, tmp_path / 'local.docx')
    assert report['automatic_pass'] and (tmp_path / 'local.docx').is_file()


def test_contract_rejects_layout_profile(document, tmp_path):
    snap = snapshot(document)
    request = batch(document, [{'id': 'read', 'module': 'M01', 'action': 'get', 'target': snap['objects'][0]['id']}])
    request['profile'] = {'columns': 1}
    with pytest.raises(WordError, match='CONTRACT_INVALID'): execute(request, document, tmp_path / 'result.docx')
