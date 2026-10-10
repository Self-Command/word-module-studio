import os
import pytest


@pytest.fixture
def document(tmp_path):
    from word_module_studio.backend import OfficeBackend
    backend = OfficeBackend()
    file = tmp_path / 'source.docx'
    backend.invoke('create', file)
    backend.edit(file, '/body', 'add', 'paragraph', {'text': 'first'})
    backend.edit(file, '/body', 'add', 'paragraph', {'text': 'second'})
    return file
