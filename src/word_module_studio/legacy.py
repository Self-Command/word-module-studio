"""Optional docxtpl compatibility fill with registered physical-rule verification."""
from pathlib import Path
from .runtime import require_execution, WordError, digest, write_json, run
from .templates import check_identity, verify_locked


def fill(manifest, output, data):
    require_execution(); check_identity(manifest)
    def semantic(value):
        if isinstance(value, dict): return all(isinstance(k, str) and semantic(v) for k, v in value.items())
        if isinstance(value, list): return all(semantic(v) for v in value)
        return value is None or isinstance(value, (str, bool, int, float))
    if not isinstance(data, dict) or not semantic(data): raise WordError('LEGACY_DATA_MUST_BE_SEMANTIC')
    from docxtpl import DocxTemplate
    from jinja2 import Environment, StrictUndefined
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    template = DocxTemplate(manifest['master'])
    template.render(data, jinja_env=Environment(undefined=StrictUndefined, autoescape=True), autoescape=True)
    template.save(output)
    verify_locked(output, manifest)
    from .verify import relationships
    integrity = relationships(output)
    run(['dotnet', '.tools/sdk/WordSdk.dll', 'validate', output])
    report = {'adapter': 'docxtpl-legacy', 'build_success': True, 'automatic_pass': True,
        'visual_review_complete': False, 'delivery_accepted': False, 'output_sha256': digest(output),
        'master_sha256': manifest['master_sha256'], 'relationships': integrity}
    write_json(output.with_suffix('.legacy.json'), report)
    return report
