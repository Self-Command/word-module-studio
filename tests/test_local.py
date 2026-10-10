"""Real local CLI processes have neither Actions variables nor GitHub credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import pytest
from word_module_studio.runtime import digest, WordError
from word_module_studio.local import execute_local

CLIENT = Path('src/word_module_studio/client.py').resolve()


def local_process(*args, cwd):
    env = {key: value for key, value in os.environ.items() if not key.startswith(('GITHUB_', 'GH_'))}
    return subprocess.run([sys.executable, CLIENT, *args], cwd=cwd, env=env, text=True,
        encoding='utf-8', capture_output=True, timeout=180)


def test_local_cli_inspect_edit_and_real_proof_outside_engine(document):
    with tempfile.TemporaryDirectory(prefix='word local ') as temporary:
        root = Path(temporary); source = root / 'input with spaces.docx'; shutil.copyfile(document, source)
        original = digest(source)
        manifest = root / 'task.json'
        manifest.write_text(json.dumps({'schema_version': 1, 'stage': 'inspect',
            'files': [{'path': source.name, 'role': 'document'}]}))
        inspected = local_process('run', '--manifest', manifest, '--output', root / 'inspection', cwd=root)
        assert inspected.returncode == 0, inspected.stderr
        report = json.loads(inspected.stdout)
        assert report['execution'] == 'local' and report['run_id'].startswith('local-')
        assert report['result']['snapshot']['sha256'] == original
        target = next(item for item in report['result']['snapshot']['objects'] if item['kind'] == 'paragraph' and item['text'] == 'first')
        (root / 'batch.json').write_text(json.dumps({'schema_version': 1, 'input_sha256': original, 'mode': 'free_edit',
            'operations': [{'id': 'title', 'module': 'M02', 'action': 'set', 'target': target['id'], 'props': {'text': 'Edited locally'}}]}))
        manifest.write_text(json.dumps({'schema_version': 1, 'stage': 'edit', 'files': [
            {'path': source.name, 'role': 'document'}, {'path': 'batch.json', 'role': 'batch'}]}))
        edited = local_process('run', '--manifest', manifest, '--output', root / 'edited', cwd=root)
        assert edited.returncode == 0, edited.stderr
        result = json.loads(edited.stdout)
        assert result['result']['automatic_pass'] and digest(source) == original
        assert result['result']['proof']['execution'] == 'local'
        assert result['result']['proof']['run_id'] == result['run_id']
        assert not result['result']['proof']['delivery_accepted']
        assert (root / 'edited/document.docx').is_file() and list((root / 'edited/proof').glob('page-*.png'))
        from word_module_studio.package import snapshot
        assert 'Edited locally' in [item['text'] for item in snapshot(root / 'edited/document.docx')['objects'] if item['kind'] == 'paragraph']
        assert len(result['engine_fingerprint']) == 64


def test_local_manifest_fingerprint_and_path_checks_precede_output(document, tmp_path):
    request = {'schema_version': 1, 'stage': 'inspect', 'files': [
        {'path': document.name, 'role': 'document', 'sha256': '0' * 64}]}
    manifest = tmp_path / 'task.json'; manifest.write_text(json.dumps(request))
    with pytest.raises(WordError, match='INPUT_FINGERPRINT_CHANGED'): execute_local(manifest, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
    request['files'][0]['path'] = '../outside.docx'; manifest.write_text(json.dumps(request))
    with pytest.raises(WordError, match='PATH_ESCAPE'): execute_local(manifest, tmp_path / 'output')


def test_local_doctor_reports_missing_tools_without_upload_or_install(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith(('GITHUB_', 'GH_'))}
    env['WMS_OFFICECLI'] = str(tmp_path / 'not-installed')
    process = subprocess.run([sys.executable, CLIENT, 'doctor'], cwd=tmp_path, env=env,
        text=True, encoding='utf-8', capture_output=True, timeout=90)
    assert process.returncode == 2
    result = json.loads(process.stdout)
    assert not result['ready'] and not next(item for item in result['checks'] if item['name'] == 'officecli')['available']
