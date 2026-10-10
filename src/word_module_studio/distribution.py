"""Allowlisted, reproducible skill distributions; never collect workspace inputs."""
import json
import os
from pathlib import Path
import shutil
import zipfile
from .runtime import require_actions, WordError, digest, write_json
from . import __version__

ROOT = Path(__file__).resolve().parents[2]
CORE = ('src', 'schemas', 'sdk', 'ci', 'consumers', 'third_party', 'docs', 'examples', '.github/workflows',
        'pyproject.toml', 'requirements.lock', 'requirements-resolved.lock', 'pins.json', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md', 'README.zh-CN.md')


def build_package(folder):
    require_actions()
    folder = Path(folder).resolve(); folder.mkdir(parents=True, exist_ok=True)
    stage = folder / 'package' / 'word-module-studio'
    if stage.exists(): raise WordError('PACKAGE_OUTPUT_ALREADY_EXISTS')
    shutil.copytree(ROOT / 'skills/word-module-studio', stage)
    core = stage / 'core'; core.mkdir()
    for name in CORE:
        source, target = ROOT / name, core / name
        if not source.exists(): raise WordError('PACKAGE_RESOURCE_MISSING', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'bin', 'obj', '*.egg-info'))
        else: shutil.copyfile(source, target)
    files = {str(p.relative_to(stage)).replace('\\', '/'): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    manifest = {'schema_version': 1, 'version': __version__, 'engine_commit': os.environ.get('GITHUB_SHA'),
        'run_id': os.environ['GITHUB_RUN_ID'], 'release_status': 'candidate', 'files': files}
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
