import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pytest
import yaml
from word_module_studio.distribution import build_package
from word_module_studio.runtime import WordError, digest
import word_module_studio.distribution as distribution


def test_install_upgrade_and_rollback_only_allowlisted_resources(tmp_path):
    report = build_package(tmp_path / 'dist')
    archive = tmp_path / 'dist' / report['archive']
    with zipfile.ZipFile(archive) as package:
        assert all('/fixtures/' not in n and '/tests/' not in n and '/.downloads/' not in n and '/consumers/' not in n for n in package.namelist())
        package.extractall(tmp_path / 'skills')
    installed = tmp_path / 'skills/word-module-studio'
    manifest = json.loads((installed / 'package-manifest.json').read_text())
    for name, sha in manifest['files'].items(): assert digest(installed / name) == sha
    skill = (installed / 'SKILL.md').read_text()
    frontmatter = yaml.safe_load(skill.split('---', 2)[1])
    assert frontmatter['name'] == 'word-module-studio' and frontmatter['description']
    assert (installed / 'core/ci/task.py').is_file()
    assert (installed / 'core/docs/module-coverage.json').is_file()
    cli = subprocess.run([sys.executable, installed / 'core/src/word_module_studio/client.py', '--help'], capture_output=True, text=True)
    assert cli.returncode == 0 and 'submit' in cli.stdout and 'fetch' in cli.stdout
    # Upgrade moves the verified old package aside; rollback restores its exact bytes.
    backup = tmp_path / 'skills/word-module-studio.previous'
    installed.rename(backup)
    shutil.copytree(backup, installed)
    (installed / 'SKILL.md').write_text('candidate upgrade')
    shutil.rmtree(installed); backup.rename(installed)
    assert digest(installed / 'SKILL.md') == manifest['files']['SKILL.md']
    with pytest.raises(WordError, match='PACKAGE_OUTPUT_ALREADY_EXISTS'): build_package(tmp_path / 'dist')


def test_unlisted_files_cannot_enter_the_installation(tmp_path, monkeypatch):
    original = distribution.ROOT
    inventory = json.loads((original / 'publication-manifest.json').read_text())
    source = tmp_path / 'source'
    for name in inventory['repository_files']:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, target)
    unlisted = ['src/word_module_studio/private-draft.txt', 'docs/private-document.docx',
                'skills/word-module-studio/notes.txt', 'fixtures/model/input.md']
    for name in unlisted:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('unlisted user input')
    monkeypatch.setattr(distribution, 'ROOT', source)
    report = build_package(tmp_path / 'dist')
    with zipfile.ZipFile(tmp_path / 'dist' / report['archive']) as package:
        expected = {'word-module-studio/package-manifest.json'}
        expected.update('word-module-studio/' + name.removeprefix('skills/word-module-studio/') for name in inventory['skill_files'])
        expected.update('word-module-studio/core/' + name for name in inventory['core_files'])
        assert set(package.namelist()) == expected
        assert all('unlisted user input' not in package.read(name).decode('utf-8', errors='ignore') for name in package.namelist())
    (source / 'src/word_module_studio/text.py').unlink()
    with pytest.raises(WordError, match='PACKAGE_RESOURCE_MISSING'):
        build_package(tmp_path / 'missing-resource')
