"""Runtime identities and tool paths shared by local and Actions execution."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
_execution = ContextVar('word_studio_execution', default=None)
_local_run_id = 'local-' + uuid.uuid4().hex
TOOL_ENV = {'officecli': 'WMS_OFFICECLI', 'dotnet': 'WMS_DOTNET', 'pandoc': 'WMS_PANDOC',
    'libreoffice': 'WMS_LIBREOFFICE', 'pdftoppm': 'WMS_PDFTOPPM', 'pdffonts': 'WMS_PDFFONTS',
    'fc-match': 'WMS_FC_MATCH', 'fc-cache': 'WMS_FC_CACHE'}


class WordError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def execution_context():
    explicit = _execution.get()
    if explicit is not None: return explicit
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_RUN_ID'):
        return {'mode': 'actions', 'run_id': os.environ['GITHUB_RUN_ID']}
    return {'mode': 'local', 'run_id': _local_run_id}


def require_execution():
    """Document operations are available in either runtime, without GitHub credentials."""
    return execution_context()


def require_actions():
    """Restrict CI publication entry points, never document APIs."""
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'):
        raise WordError('ACTIONS_REQUIRED', 'This publication entry point requires GitHub Actions.')


@contextmanager
def execution_scope(mode, run_id=None, *, output_root=None):
    if mode not in ('local', 'actions'): raise WordError('EXECUTION_MODE_INVALID', mode)
    if mode == 'actions': require_actions()
    context = {'mode': mode, 'run_id': run_id or (
        os.environ['GITHUB_RUN_ID'] if mode == 'actions' else 'local-' + uuid.uuid4().hex)}
    if output_root is not None: context['output_root'] = str(Path(output_root).resolve())
    token = _execution.set(context)
    try: yield execution_context()
    finally: _execution.reset(token)


def artifact_folder(name):
    return Path(execution_context().get('output_root', 'build')) / name


def tool(name):
    configured = os.environ.get(TOOL_ENV.get(name, ''))
    candidates = [configured] if configured else [str(ROOT / '.tools' / (name + ('.exe' if os.name == 'nt' else ''))), name]
    if name == 'libreoffice' and not configured: candidates.append('soffice')
    for candidate in candidates:
        found = shutil.which(candidate)
        if found: return str(Path(found).resolve())
    raise WordError('DEPENDENCY_MISSING', f'{name}; install it or set {TOOL_ENV.get(name, "PATH")} to its executable.')


def sdk_path():
    path = Path(os.environ.get('WMS_SDK_DLL', ROOT / '.tools/sdk/WordSdk.dll')).resolve()
    if not path.is_file(): raise WordError('DEPENDENCY_MISSING', 'WordSdk.dll; publish sdk/WordSdk.csproj or set WMS_SDK_DLL.')
    return str(path)


def uno_python():
    configured = os.environ.get('WMS_UNO_PYTHON')
    candidate = configured or ('/usr/bin/python3' if Path('/usr/bin/python3').is_file() else sys.executable)
    found = shutil.which(candidate)
    if not found: raise WordError('DEPENDENCY_MISSING', 'UNO Python; set WMS_UNO_PYTHON to Python with the uno module.')
    return str(Path(found).resolve())


def run(args, *, input_text=None, timeout=180, cwd=None, reject_warnings=False):
    args = [str(a) for a in args]
    if args[0] in TOOL_ENV: args[0] = tool(args[0])
    if args[0] == '/usr/bin/python3': args[0] = uno_python()
    args = [sdk_path() if a == '.tools/sdk/WordSdk.dll' else a for a in args]
    try:
        proc = subprocess.run(args, cwd=cwd, input=input_text,
            capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    except FileNotFoundError as exc:
        raise WordError('DEPENDENCY_MISSING', args[0]) from exc
    if proc.returncode or (reject_warnings and '[WARNING]' in proc.stderr):
        raise WordError("COMMAND_FAILED", f"{args[0]} ({proc.returncode})\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
    return proc.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def confined(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise WordError("PATH_ESCAPE", str(name))
    return path
