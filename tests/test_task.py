import importlib.util
import json
from pathlib import Path
import pytest
from word_module_studio.runtime import digest, WordError


def runner():
    spec = importlib.util.spec_from_file_location('task_runner', Path('ci/task.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.execute_task


def test_explicit_file_task_and_stale_input(document, tmp_path):
    task_id, commit = 'task-' + '1' * 16, 'a' * 40
    manifest = {'schema_version': 1, 'stage': 'inspect', 'task_id': task_id, 'engine_commit': commit,
        'files': [{'path': document.name, 'role': 'document', 'sha256': digest(document)}]}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    result = runner()(tmp_path, tmp_path / 'result', task_id=task_id, engine_commit=commit)
    assert result['result']['snapshot']['sha256'] == digest(document)
    manifest['files'][0]['sha256'] = '0' * 64; (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(WordError, match='INPUT_FINGERPRINT_CHANGED'):
        runner()(tmp_path, tmp_path / 'stale', task_id=task_id, engine_commit=commit)
