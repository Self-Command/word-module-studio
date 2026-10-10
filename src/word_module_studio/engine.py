"""Atomic operations, stable targets, policy boundary and preservation proof."""
import json
import shutil
from pathlib import Path
import tempfile
from .runtime import require_actions, WordError, digest, write_json, run
from .package import Package, snapshot, semantic
from .backend import OfficeBackend
from .capabilities import check_properties
from .context import LayoutContext


PHYSICAL = {"font", "font.eastasia", "font.ascii", "size", "bold", "italic", "color", "align",
    "style", "spacing", "lineSpacing", "indent", "columns", "columnSpace", "width", "height",
    "pageWidth", "pageHeight", "orientation", "marginTop", "marginBottom", "marginLeft", "marginRight"}


def execute(batch, input_path, output_path, *, template=None):
    require_actions()
    from .contracts import validate
    validate("operation-batch", batch)
    if len({o['id'] for o in batch['operations']}) != len(batch['operations']): raise WordError('DUPLICATE_OPERATION_ID')
    if digest(input_path) != batch["input_sha256"]: raise WordError("STALE_INPUT")
    if batch["mode"] == "locked_template" and not template: raise WordError("TEMPLATE_REQUIRED")
    if batch["mode"] == "locked_template":
        from .templates import check_identity, check_operations
        check_identity(template)
        check_operations(batch["operations"], template)
    source = snapshot(input_path)
    backend = OfficeBackend()
    ledger = []
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as temporary:
        work = Path(temporary) / "transaction.docx"
        shutil.copyfile(input_path, work)
        package = Package(work)
        package.objects(stamp=True)
        package.save()
        for operation in batch["operations"]:
            package = Package(work)
            action, module = operation["action"], operation["module"]
            props = operation.get("props", {})
            target = package.locate(operation["target"])
            kind = operation.get("kind") if action == "add" else target["kind"]
            if action == "get":
                ledger.append({"operation_id": operation["id"], "object": {k: v for k, v in target.items() if k != "element"}})
                continue
            if action == "extension":
                from .extensions import apply
                result = apply(package, target, module, props)
                package.save()
            else:
                check_properties(module, kind, action, props)
                context = LayoutContext.resolve(package, target) if target["part"] == "word/document.xml" else None
                if context and any(key.lower().startswith("margin") for key in props) and module != "M05":
                    raise WordError("CONTEXT_LAYOUT_OVERRIDE")
                result = backend.edit(work, target["path"], action, kind, props)
            package = Package(work)
            package.objects(stamp=True)
            package.save()
            ledger.append({"operation_id": operation["id"], "module": module, "target": target["id"], "result": result})
        final = snapshot(work)
        touched_parts = {o["part"] for o in source["objects"]}
        preserved = [p for p in source["unknown_parts"] if p not in touched_parts]
        for part in preserved:
            if source["parts"][part] != final["parts"].get(part): raise WordError("UNKNOWN_PART_CHANGED", part)
        validation = json.loads(run(["dotnet", ".tools/sdk/WordSdk.dll", "validate", work]))
        if batch["mode"] == "locked_template":
            from .templates import verify_locked
            verify_locked(work, template)
        shutil.copyfile(work, output_path)
    report = {"schema_version": 1, "build_success": True, "automatic_pass": True,
        "visual_review_complete": False, "delivery_accepted": False,
        "input_sha256": source["sha256"], "output_sha256": digest(output_path),
        "operations": ledger, "preserved_unknown_parts": preserved, "sdk": validation}
    write_json(output_path.with_suffix(".operations.json"), report)
    return report
