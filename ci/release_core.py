"""Validate exact cloud tests and human/agent page receipts before packaging."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from word_module_studio.runtime import require_actions, WordError, run, write_json
from word_module_studio.render import receipt
from word_module_studio.distribution import build_package

require_actions()
parser = argparse.ArgumentParser(); parser.add_argument('--acceptance', required=True)
args = parser.parse_args(); manifest = json.loads(Path(args.acceptance).read_text())
run_id = str(manifest['run_id'])
if not run_id.isdigit(): raise WordError('INVALID_ACCEPTANCE_RUN')
workflow = json.loads(run(['gh', 'run', 'view', run_id, '--json', 'headSha,conclusion,jobs']))
if workflow['headSha'] != manifest['engine_commit'] or workflow['conclusion'] != 'success': raise WordError('CORE_CI_NOT_ACCEPTED')
suites = {'core', 'advanced', 'composition', 'rendering', 'layout', 'distribution'}
if {j['name'] for j in workflow['jobs'] if j['conclusion'] == 'success'} != {'core (' + s + ')' for s in suites}:
    raise WordError('CORE_SUITES_INCOMPLETE')
run(['git', 'fetch', '--depth=1', 'origin', manifest['engine_commit']])
protected = ['src', 'schemas', 'sdk', 'ci', 'third_party', '.github/workflows', 'skills', 'pins.json', 'Dockerfile', '.dockerignore',
    'pyproject.toml', 'requirements.lock', 'requirements-resolved.lock', 'publication-manifest.json']
if run(['git', 'diff', '--name-only', manifest['engine_commit'], 'HEAD', '--', *protected]).strip():
    raise WordError('CORE_SOURCE_CHANGED_AFTER_ACCEPTANCE')

local_run_id = str(manifest.get('local_runtime_run_id', ''))
if not local_run_id.isdigit(): raise WordError('LOCAL_RUNTIME_QUALIFICATION_REQUIRED')
local_workflow = json.loads(run(['gh', 'run', 'view', local_run_id, '--json', 'headSha,conclusion']))
if local_workflow['headSha'] != manifest['engine_commit'] or local_workflow['conclusion'] != 'success':
    raise WordError('LOCAL_RUNTIME_NOT_ACCEPTED')
local_folder = Path('build/local-qualification')
run(['gh', 'run', 'download', local_run_id, '--name', 'local-runtime-' + local_run_id, '--dir', local_folder], timeout=300)
local_report = json.loads((local_folder / 'qualification.json').read_text())
if not local_report.get('automatic_pass') or local_report.get('actions_environment_present') is not False or local_report.get('github_credentials_required') is not False:
    raise WordError('LOCAL_RUNTIME_NOT_ACCEPTED')
download = Path('build/accepted-ci'); download.mkdir(parents=True, exist_ok=True)
run(['gh', 'run', 'download', run_id, '--pattern', 'module-ci-*', '--dir', download], timeout=300)
proofs = []
for entry in manifest['proofs']:
    if entry['suite'] not in suites or '..' in Path(entry['path']).parts: raise WordError('INVALID_PROOF_PATH')
    folder = download / ('module-ci-' + entry['suite'] + '-' + run_id) / entry['path']
    value = json.loads(Path(entry['receipt']).read_text())
    result = receipt(folder, value)
    if not result['delivery_accepted']: raise WordError('CORE_VISUAL_NOT_ACCEPTED', entry['path'])
    proofs.append({'suite': entry['suite'], 'path': entry['path'], 'output_sha256': result['output_sha256'],
        'input_sha256': result['input_sha256'], 'pages': result['pages'], 'reviewer': result['reviewer']})
if len(proofs) < 15 or not {'rendering', 'layout'} <= {p['suite'] for p in proofs}: raise WordError('CORE_VISUAL_COVERAGE_INCOMPLETE')
acceptance = {'profile': 'core-layout', 'run_id': run_id, 'engine_commit': manifest['engine_commit'],
    'execution_modes': ['local', 'actions'], 'local_runtime_run_id': local_run_id, 'local_runtime_qualification': local_report,
    'automatic_pass': True, 'visual_review_complete': True, 'delivery_accepted': True, 'proofs': proofs,
    'limitations': manifest.get('limitations', [])}
write_json('build/core-acceptance-report.json', acceptance)
build_package('build/release', acceptance=acceptance)
