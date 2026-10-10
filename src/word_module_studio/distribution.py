"""Allowlisted, reproducible skill distributions; never collect workspace inputs."""
import json
import os
from pathlib import Path
import shutil
import zipfile
from .runtime import require_actions, WordError, digest, write_json
from . import __version__

ROOT = Path(__file__).resolve().parents[2]

def publication_manifest():
    """An explicit inventory prevents directory copies from collecting new inputs."""
    require_actions()
    inventory = json.loads((ROOT / 'publication-manifest.json').read_text(encoding='utf-8-sig'))
    if inventory.get('schema_version') != 1: raise WordError('PUBLICATION_MANIFEST_INVALID')
    for group in ('repository_files', 'skill_files', 'core_files'):
        names = inventory.get(group)
        if not isinstance(names, list) or not names or len(names) != len(set(names)):
            raise WordError('PUBLICATION_MANIFEST_INVALID', group)
        for name in names:
            if not isinstance(name, str): raise WordError('PUBLICATION_PATH_INVALID', str(name))
            path = Path(name)
            if '\\' in name or path.is_absolute() or '..' in path.parts:
                raise WordError('PUBLICATION_PATH_INVALID', str(name))
            source = ROOT / path
            if source.is_symlink() or not source.resolve().is_relative_to(ROOT.resolve()) or not source.is_file():
                raise WordError('PACKAGE_RESOURCE_MISSING', name)
    approved = set(inventory['repository_files'])
    if not set(inventory['skill_files'] + inventory['core_files']) <= approved:
        raise WordError('PUBLICATION_RESOURCE_NOT_APPROVED')
    if any(not name.startswith('skills/word-module-studio/') for name in inventory['skill_files']):
        raise WordError('PUBLICATION_SKILL_PATH_INVALID')
    return inventory


def build_package(folder, *, acceptance=None):
    require_actions()
    folder = Path(folder).resolve(); folder.mkdir(parents=True, exist_ok=True)
    stage = folder / 'package' / 'word-module-studio'
    if stage.exists(): raise WordError('PACKAGE_OUTPUT_ALREADY_EXISTS')
    inventory = publication_manifest()
    prefix = 'skills/word-module-studio/'
    for group in ('skill_files', 'core_files'):
        for name in inventory[group]:
            relative = name[len(prefix):] if group == 'skill_files' else 'core/' + name
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
    files = {str(p.relative_to(stage)).replace('\\', '/'): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    manifest = {'schema_version': 1, 'version': __version__, 'engine_commit': os.environ.get('GITHUB_SHA'),
        'run_id': os.environ['GITHUB_RUN_ID'], 'release_status': 'core-layout-accepted' if acceptance else 'candidate', 'files': files}
    if acceptance:
        if not acceptance.get('delivery_accepted') or not acceptance.get('proofs'): raise WordError('CORE_ACCEPTANCE_REQUIRED')
        manifest['acceptance'] = acceptance
    write_json(stage / 'package-manifest.json', manifest)
    archive = folder / ('word-module-studio-' + __version__ + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(stage.rglob('*')):
            if not path.is_file(): continue
            info = zipfile.ZipInfo('word-module-studio/' + str(path.relative_to(stage)).replace('\\', '/'), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes())
    result = {**manifest, 'archive': archive.name, 'archive_sha256': digest(archive), 'private_inputs_included': False}
    write_json(folder / 'distribution-report.json', result)
    return result
