"""Execute explicit-file document tasks in the selected runtime."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from functools import wraps
from xml.etree import ElementTree as E
from .runtime import require_execution, execution_context, WordError, digest, write_json, confined
from .contracts import validate
from .package import snapshot


def _font_environment(function):
    @wraps(function)
    def scoped(root, folder, **kwargs):
        root = Path(root).resolve()
        task = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
        validate('task', task)
        fonts = [entry for entry in task['files'] if entry['role'] == 'font']
        if not fonts: return function(root, folder, **kwargs)
        if not Path('/etc/fonts/fonts.conf').is_file():
            raise WordError('FONTCONFIG_REQUIRED', 'Use the local Linux container for task-scoped custom-font preview.')
        previous = os.environ.get('FONTCONFIG_FILE')
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'fonts'; destination.mkdir()
            for entry in fonts:
                path = confined(root, entry['path'])
                if not path.is_file() or digest(path) != entry['sha256']: raise WordError('INPUT_FINGERPRINT_CHANGED', entry['path'])
                shutil.copyfile(path, destination / (entry['sha256'] + path.suffix))
            config = E.Element('fontconfig')
            E.SubElement(config, 'include').text = '/etc/fonts/fonts.conf'
            E.SubElement(config, 'dir').text = str(destination)
            E.SubElement(config, 'cachedir').text = str(Path(temporary) / 'cache')
            config_file = Path(temporary) / 'fonts.conf'
            E.ElementTree(config).write(config_file, encoding='utf-8', xml_declaration=True)
            os.environ['FONTCONFIG_FILE'] = str(config_file)
            try: return function(root, folder, **kwargs)
            finally:
                if previous is None: os.environ.pop('FONTCONFIG_FILE', None)
                else: os.environ['FONTCONFIG_FILE'] = previous
    return scoped


@_font_environment
def execute_task(root, folder, *, task_id, engine_commit=None):
    require_execution()
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
    identity = {'task_id': task_id, 'engine_commit': engine_commit, 'execution': execution_context()['mode'], 'run_id': execution_context()['run_id'],
        'input_commit': os.environ.get('WMS_INPUT_COMMIT'), 'stage': stage, 'input_files': task['files'], 'result': result}
    write_json(folder / 'task-report.json', identity)
    return identity
