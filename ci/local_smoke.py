"""Verify the actual local container without GitHub credentials or Actions variables."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, '/opt/word-studio/src')
from word_module_studio.backend import OfficeBackend
from word_module_studio.runtime import digest, write_json

assert not any(key.startswith(('GITHUB_', 'GH_')) for key in os.environ)
root = Path('/work'); source = root / 'local input.docx'
backend = OfficeBackend(); backend.invoke('create', source)
backend.edit(source, '/body', 'add', 'paragraph', {'text': 'Local execution sample'})
baseline = digest(source)
manifest = root / 'task.json'
client = '/opt/word-studio/src/word_module_studio/client.py'
def invoke(*args):
    process = subprocess.run([sys.executable, client, *args], cwd=root, text=True, capture_output=True, timeout=180)
    if process.returncode: raise RuntimeError(process.stderr)
    return json.loads(process.stdout)
assert invoke('doctor')['ready']
manifest.write_text(json.dumps({'schema_version': 1, 'stage': 'inspect', 'files': [{'path': source.name, 'role': 'document'}]}))
inspection = invoke('run', '--manifest', manifest, '--output', root / 'inspection')
target = next(item for item in inspection['result']['snapshot']['objects'] if item['kind'] == 'paragraph' and item['text'] == 'Local execution sample')
(root / 'batch.json').write_text(json.dumps({'schema_version': 1, 'input_sha256': baseline, 'mode': 'free_edit',
    'operations': [{'id': 'title', 'module': 'M02', 'action': 'set', 'target': target['id'], 'props': {'text': 'Local execution verified'}}]}))
manifest.write_text(json.dumps({'schema_version': 1, 'stage': 'edit', 'files': [{'path': source.name, 'role': 'document'}, {'path': 'batch.json', 'role': 'batch'}]}))
edited = invoke('run', '--manifest', manifest, '--output', root / 'edited')
assert edited['execution'] == 'local' and edited['run_id'].startswith('local-')
assert edited['result']['automatic_pass'] and edited['result']['proof']['automatic_pass']
assert not edited['result']['proof']['delivery_accepted'] and digest(source) == baseline
assert (root / 'edited/document.docx').is_file() and (root / 'edited/proof/document.pdf').is_file()
assert list((root / 'edited/proof').glob('page-*.png'))
manifest.write_text(json.dumps({'schema_version': 1, 'stage': 'inspect',
    'files': [{'path': 'edited/document.docx', 'role': 'document'}]}))
confirmed = invoke('run', '--manifest', manifest, '--output', root / 'confirmation')
assert 'Local execution verified' in [item['text'] for item in confirmed['result']['snapshot']['objects'] if item['kind'] == 'paragraph']
write_json(root / 'qualification.json', {'automatic_pass': True, 'execution': 'local',
    'github_credentials_required': False, 'actions_environment_present': False,
    'original_preserved': True, 'inspect_edit_render': True, 'visual_delivery_auto_accepted': False,
    'edited_text_confirmed': True, 'runtime_network_disabled': True,
    'inspection_run_id': inspection['run_id'], 'editing_run_id': edited['run_id']})
