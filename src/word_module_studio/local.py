"""Explicit local tasks: no account, repository, upload or Actions variables."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import uuid
from . import __version__
from .runtime import ROOT, WordError, confined, digest, execution_scope, run, sdk_path, tool, uno_python, write_json


def doctor(profile='full'):
    modules = ['lxml', 'jsonschema'] if profile == 'inspect' else ['lxml', 'jsonschema', 'pdfplumber', 'yaml', 'fontTools', 'PIL', 'docx', 'docxtpl', 'docxcompose']
    checks = [{'name': name, 'available': importlib.util.find_spec(name) is not None} for name in modules]
    if profile == 'full':
        for name in ('officecli', 'dotnet', 'pandoc', 'libreoffice', 'pdftoppm', 'pdffonts', 'fc-match'):
            try: checks.append({'name': name, 'available': True, 'path': tool(name)})
            except WordError as exc: checks.append({'name': name, 'available': False, 'error': str(exc)})
        try: checks.append({'name': 'WordSdk.dll', 'available': True, 'path': sdk_path()})
        except WordError as exc: checks.append({'name': 'WordSdk.dll', 'available': False, 'error': str(exc)})
        try:
            executable = uno_python(); run([executable, '-c', 'import uno'])
            checks.append({'name': 'UNO Python', 'available': True, 'path': executable})
        except WordError as exc: checks.append({'name': 'UNO Python', 'available': False, 'error': str(exc)})
    return {'execution': 'local', 'profile': profile, 'ready': all(check['available'] for check in checks), 'checks': checks}


def _fingerprint():
    files = sorted([*ROOT.glob('src/**/*.py'), *ROOT.glob('schemas/*.json'), *ROOT.glob('sdk/*.cs'), ROOT / 'pins.json'])
    return hashlib.sha256('\n'.join(str(path.relative_to(ROOT)) + ':' + digest(path) for path in files).encode()).hexdigest()


def execute_local(manifest_file, folder):
    from .contracts import validate
    from .tasks import execute_task
    manifest_file, folder = Path(manifest_file).resolve(), Path(folder).resolve()
    manifest = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    task_id = 'task-' + uuid.uuid4().hex[:16]
    manifest['task_id'] = task_id
    # A local user need not pin or possess a Git commit. Source fingerprints still identify the runtime.
    manifest.pop('engine_commit', None)
    paths, seen = [], set()
    for entry in manifest['files']:
        source = confined(manifest_file.parent, entry['path'])
        if source == manifest_file or source.relative_to(manifest_file.parent).as_posix().casefold() == 'manifest.json':
            raise WordError('INPUT_PATH_RESERVED', entry['path'])
        if source in seen: raise WordError('DUPLICATE_TASK_FILE', entry['path'])
        seen.add(source)
        if not source.is_file(): raise WordError('TASK_INPUT_MISSING', entry['path'])
        actual = digest(source)
        if entry.get('sha256') and entry['sha256'] != actual: raise WordError('INPUT_FINGERPRINT_CHANGED', entry['path'])
        entry['sha256'] = actual
        paths.append((entry, source))
    validate('task', manifest)
    if folder.exists() and any(folder.iterdir()): raise WordError('TASK_OUTPUT_NOT_EMPTY', str(folder))
    folder.mkdir(parents=True, exist_ok=True)
    staged = folder / '.inputs'; staged.mkdir()
    for entry, source in paths:
        target = confined(staged, entry['path']); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    write_json(staged / 'manifest.json', manifest)
    with execution_scope('local', output_root=folder):
        try:
            report = execute_task(staged, folder, task_id=task_id)
            report['engine_version'], report['engine_fingerprint'] = __version__, _fingerprint()
            write_json(folder / 'task-report.json', report)
            return report
        except Exception as exc:
            write_json(folder / 'task-failure.json', {'execution': 'local', 'automatic_pass': False,
                'visual_review_complete': False, 'delivery_accepted': False, 'error': str(exc)})
            raise
