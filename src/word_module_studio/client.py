"""The only local entry points: explicit-file submission, status and fetch."""
import sys
# Direct invocation must not expose the package's math.py as the stdlib math
# module while argparse/pathlib initialise. Module invocation needs no change.
if __name__ == '__main__' and sys.path: sys.path.pop(0)
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid


def gh(args, payload=None):
    command = ['gh', *args]
    if payload is not None: command += ['--input', '-']
    process = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                             text=True, capture_output=True, encoding='utf-8')
    if process.returncode: raise RuntimeError(process.stderr.strip())
    return process.stdout


def submit(repository, manifest_file, engine_commit):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository): raise ValueError('Repository must be owner/name')
    if not re.fullmatch(r'[a-f0-9]{40}', engine_commit): raise ValueError('Pin a full engine commit')
    manifest_file = Path(manifest_file).resolve()
    manifest = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    task = 'task-' + uuid.uuid4().hex[:16]
    manifest['task_id'], manifest['engine_commit'] = task, engine_commit
    entries = []
    for item in manifest['files']:
        path = (manifest_file.parent / item['path']).resolve()
        if not path.is_relative_to(manifest_file.parent) or not path.is_file(): raise ValueError('Input must be an explicit file within the manifest folder')
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if item.get('sha256') and item['sha256'] != actual: raise ValueError('INPUT_FINGERPRINT_CHANGED: ' + item['path'])
        item['sha256'] = actual
        blob = json.loads(gh(['api', '--method', 'POST', f'repos/{repository}/git/blobs'], {'encoding': 'base64', 'content': base64.b64encode(data).decode()}))
        entries.append({'path': 'tasks/' + task + '/' + item['path'].replace('\\', '/'), 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    metadata = json.loads(gh(['api', f'repos/{repository}']))
    base_ref = json.loads(gh(['api', f"repos/{repository}/git/ref/heads/{metadata['default_branch']}"]))['object']['sha']
    base_tree = json.loads(gh(['api', f'repos/{repository}/git/commits/{base_ref}']))['tree']['sha']
    blob = json.loads(gh(['api', '--method', 'POST', f'repos/{repository}/git/blobs'], {'encoding': 'utf-8', 'content': json.dumps(manifest, ensure_ascii=False, indent=2)}))
    entries.append({'path': 'tasks/' + task + '/manifest.json', 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    tree = json.loads(gh(['api', '--method', 'POST', f'repos/{repository}/git/trees'], {'base_tree': base_tree, 'tree': entries}))
    commit = json.loads(gh(['api', '--method', 'POST', f'repos/{repository}/git/commits'], {'message': 'Word task ' + task, 'tree': tree['sha'], 'parents': [base_ref]}))
    ref = 'tasks/' + task
    gh(['api', '--method', 'POST', f'repos/{repository}/git/refs'], {'ref': 'refs/heads/' + ref, 'sha': commit['sha']})
    gh(['workflow', 'run', 'document-task.yml', '--repo', repository, '-f', 'task_ref=' + commit['sha'],
        '-f', 'task_id=' + task, '-f', 'engine_commit=' + engine_commit])
    return {'repository': repository, 'task_id': task, 'input_commit': commit['sha'], 'engine_commit': engine_commit,
            'status_url': 'https://github.com/' + repository + '/actions/workflows/document-task.yml'}


def main():
    parser = argparse.ArgumentParser(description='Cloud-only Word operations: submit/status/fetch')
    commands = parser.add_subparsers(dest='command', required=True)
    send = commands.add_parser('submit'); send.add_argument('--repo', required=True); send.add_argument('--manifest', required=True); send.add_argument('--engine-commit', required=True)
    status = commands.add_parser('status'); status.add_argument('--repo', required=True); status.add_argument('--run-id', required=True)
    fetch = commands.add_parser('fetch'); fetch.add_argument('--repo', required=True); fetch.add_argument('--run-id', required=True); fetch.add_argument('--dir', required=True)
    args = parser.parse_args()
    if args.command == 'submit': print(json.dumps(submit(args.repo, args.manifest, args.engine_commit), ensure_ascii=False, indent=2))
    elif args.command == 'status': print(gh(['run', 'view', args.run_id, '--repo', args.repo, '--json', 'status,conclusion,url,jobs']))
    else: print(gh(['run', 'download', args.run_id, '--repo', args.repo, '--dir', str(Path(args.dir).resolve())]))


if __name__ == '__main__': main()
