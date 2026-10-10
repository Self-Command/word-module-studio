"""Execution boundary for all document processing, including validation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


class WordError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def require_actions():
    if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("GITHUB_RUN_ID"):
        raise WordError("CLOUD_ONLY", "Document operations, tests, conversion and validation require GitHub Actions.")


def run(args, *, input_text=None, timeout=180, cwd=None):
    require_actions()
    proc = subprocess.run([str(a) for a in args], cwd=cwd, input=input_text,
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if proc.returncode:
        raise WordError("COMMAND_FAILED", f"{args[0]} ({proc.returncode})\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}")
    return proc.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    require_actions()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def confined(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise WordError("PATH_ESCAPE", str(name))
    return path
