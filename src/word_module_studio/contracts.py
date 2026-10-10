import json
from pathlib import Path
import jsonschema
from .runtime import require_execution, WordError

ROOT = Path(__file__).resolve().parents[2]


def validate(name, value):
    require_execution()
    schema = json.loads((ROOT / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))
    try: jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise WordError("CONTRACT_INVALID", f"{name}/{list(exc.path)}: {exc.message}") from exc
