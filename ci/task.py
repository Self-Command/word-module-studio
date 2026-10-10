"""Explicit input files and pinned engine, executed solely in GitHub Actions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from word_module_studio.runtime import require_actions, WordError, digest, write_json, confined
from word_module_studio.contracts import validate
from word_module_studio.package import snapshot


def execute_task(root, folder, *, task_id, engine_commit):
    require_actions()
    root, folder = Path(root).resolve(), Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    task = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
    validate('task', task)
    if task.get('task_id') != task_id or task.get('engine_commit') != engine_commit: raise WordError('TASK_IDENTITY_MISMATCH')
    inputs = {}
    names = set()
    for entry in task['files']:
        path = confined(root, entry['path'])
        if path in names: raise WordError('DUPLICATE_TASK_FILE', entry['path'])
        names.add(path)
        if not path.is_file() or digest(path) != entry['sha256']: raise WordError('INPUT_FINGERPRINT_CHANGED', entry['path'])
        inputs.setdefault(entry['role'], []).append(path)
    def one(role):
        matches = inputs.get(role, [])
        if len(matches) != 1: raise WordError('TASK_ONE_INPUT_REQUIRED', role)
        return matches[0]
    def value(role): return json.loads(one(role).read_text(encoding='utf-8-sig'))
    from word_module_studio.templates import build
    def template():
        if inputs.get('template-manifest'):
            from word_module_studio.templates import check_identity
            manifest = value('template-manifest'); manifest['master'] = str(one('master'))
            check_identity(manifest)
            if stage not in ('template-probe', 'template-register') and manifest.get('state') != 'registered': raise WordError('TEMPLATE_NOT_REGISTERED')
            if not task.get('font_scheme') or task['font_scheme'] != manifest['spec']['fonts']: raise WordError('EXPLICIT_FONT_SCHEME_REQUIRED')
            return manifest
        if stage not in ('template-build', 'template-probe'): raise WordError('TEMPLATE_REGISTERED_MASTER_REQUIRED')
        spec = value('template')
        if not task.get('font_scheme') or task['font_scheme'] != spec['fonts']: raise WordError('EXPLICIT_FONT_SCHEME_REQUIRED')
        return build(spec, folder / 'template')
    # Explicit custom fonts are installed only inside this ephemeral runner.
    if inputs.get('font'):
        from word_module_studio.runtime import run
        destination = Path.home() / '.local/share/fonts/word-module-studio'
        destination.mkdir(parents=True, exist_ok=True)
        for path in inputs['font']: shutil.copyfile(path, destination / (digest(path) + path.suffix))
        run(['fc-cache', '-f', destination])
    output = folder / task.get('output_name', 'document.docx')
    stage = task['stage']
    if stage == 'inspect':
        from word_module_studio.capabilities import catalog
        from word_module_studio.accessibility import inspect
        result = {'snapshot': snapshot(one('document')), 'capabilities': catalog(), 'accessibility': inspect(one('document'))}
    elif stage == 'edit':
        from word_module_studio.engine import execute
        request = value('batch')
        result = execute(request, one('document'), output, template=template() if request['mode'] == 'locked_template' else None)
    elif stage in ('compose', 'template-probe'):
        from word_module_studio.compose import compose
        result = compose(one('markdown'), template(), output, resources=[*inputs.get('image', []), *inputs.get('bibliography', [])], data=value('data') if inputs.get('data') else None)
    elif stage == 'template-build': result = template()
    elif stage == 'template-register':
        from word_module_studio.templates import register
        result = register(template(), value('composition-report'), value('visual-report'), folder / 'registered-manifest.json')
    elif stage == 'render':
        from word_module_studio.render import render
        shutil.copyfile(one('document'), output)
        result = render(output, folder / 'proof')
    elif stage == 'refresh-fields':
        from word_module_studio.field_cache import refresh
        result = refresh(one('document'), output, folder / 'field-proof')
    elif stage == 'verify':
        from word_module_studio.verify import relationships
        from word_module_studio.runtime import run
        result = {'sdk': json.loads(run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', one('document')])),
            'relationships': relationships(one('document')), 'snapshot': snapshot(one('document'))}
        from word_module_studio.accessibility import inspect
        result['accessibility'] = inspect(one('document'))
    elif stage == 'merge':
        from word_module_studio.merge import merge
        documents = inputs.get('document', [])
        if len(documents) < 2: raise WordError('MERGE_INPUTS_REQUIRED')
        result = merge(documents[0], documents[1:], output, header_policy=task.get('header_policy'))
    elif stage == 'extract':
        from word_module_studio.merge import extract
        result = extract(one('document'), value('data')['object_ids'], output)
    elif stage == 'visual-receipt':
        from word_module_studio.render import receipt
        proof = folder / 'proof'; proof.mkdir()
        for path in inputs.get('proof', []): shutil.copyfile(path, proof / path.name)
        result = receipt(proof, value('receipt'))
    elif stage == 'package':
        from word_module_studio.distribution import build_package
        result = build_package(folder)
    else: raise WordError('TASK_STAGE_UNSUPPORTED', stage)
    if stage in ('edit', 'compose', 'template-probe', 'merge', 'extract'):
        from word_module_studio.render import render
        result['proof'] = render(output, folder / 'proof')
        result['automatic_pass'] = result.get('automatic_pass', True) and result['proof']['automatic_pass']
    identity = {'task_id': task_id, 'engine_commit': engine_commit, 'run_id': os.environ['GITHUB_RUN_ID'],
        'input_commit': os.environ.get('WMS_INPUT_COMMIT'), 'stage': stage, 'input_files': task['files'], 'result': result}
    write_json(folder / 'task-report.json', identity)
    return identity


if __name__ == '__main__':
    require_actions()
    folder = Path('build/task'); folder.mkdir(parents=True, exist_ok=True)
    try:
        execute_task(Path(os.environ['WMS_INPUT_ROOT']) / os.environ['WMS_TASK_ID'], folder,
            task_id=os.environ['WMS_TASK_ID'], engine_commit=os.environ['WMS_ENGINE_COMMIT'])
    except Exception as exc:
        write_json(folder / 'task-failure.json', {'build_success': False, 'automatic_pass': False,
            'visual_review_complete': False, 'delivery_accepted': False, 'error': str(exc), 'traceback': traceback.format_exc()})
        raise
