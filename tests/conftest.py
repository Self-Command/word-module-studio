import os
import pytest

if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'):
    raise RuntimeError('CLOUD_ONLY: tests require GitHub Actions')


@pytest.fixture
def document(tmp_path):
    from word_module_studio.backend import OfficeBackend
    backend = OfficeBackend()
    file = tmp_path / 'source.docx'
    backend.invoke('create', file)
    backend.edit(file, '/body', 'add', 'paragraph', {'text': 'first'})
    backend.edit(file, '/body', 'add', 'paragraph', {'text': 'second'})
    return file
