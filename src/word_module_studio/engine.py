"""Atomic operations, stable targets, policy boundary and preservation proof."""
import json
import shutil
from pathlib import Path
import tempfile
from contextlib import contextmanager
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
    with transaction_work(output_path) as work:
        shutil.copyfile(input_path, work)
        package = Package(work)
        package.objects(stamp=True)
        package.save()
        for operation in batch["operations"]:
            package = Package(work)
            action, module = operation["action"], operation["module"]
            props = operation.get("props", {})
            selected_fonts = {key: value for key, value in props.items() if key.lower() in ('font', 'font.ascii', 'font.eastasia', 'font.cs', 'font.hansi')}
            if selected_fonts:
                from .templates import check_fonts
                check_fonts(selected_fonts)
            target = package.locate(operation["target"])
            kind = operation.get("kind") if action == "add" else target["kind"]
            from .capabilities import MODULES
            if module not in MODULES: raise WordError('UNKNOWN_MODULE', module)
            if action == "get":
                if target['kind'] not in MODULES[module][1]: raise WordError('MODULE_ELEMENT_MISMATCH', module)
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
                chart_before = {name: data for name, data in package.parts.items() if '/charts/' in name and name.endswith('.xml')}
                result = backend.edit(work, target["path"], action, kind, props)
                if module == 'M12' and action != 'remove':
                    from .extensions import _sdk
                    changed = [name for name, data in Package(work).parts.items()
                        if '/charts/' in name and name.endswith('.xml') and chart_before.get(name) != data]
                    if changed: result = {'backend': result, 'editable_data': _sdk(work, target['id'], module, {'operation': 'sync_charts', 'parts': changed})}
            package = Package(work)
            package.objects(stamp=True)
            package.save()
            ledger.append({"operation_id": operation["id"], "module": module, "target": target["id"], "result": result})
        final = snapshot(work)
        touched_parts = {o["part"] for o in source["objects"]}
        preserved = [p for p in source["unknown_parts"] if p not in touched_parts]
        modules = {operation['module'] for operation in batch['operations']}
        if 'M12' in modules:
            preserved = [p for p in preserved if not p.startswith(('word/charts/', 'word/embeddings/'))]
        if 'M15' in modules:
            preserved = [p for p in preserved if not p.startswith(('word/commentsExtended', 'word/commentsIds', 'word/people'))]
        for part in preserved:
            if source["parts"][part] != final["parts"].get(part):
                original_package, final_package = Package(input_path), Package(work)
                if part.endswith('.xml') and xml_tree(original_package.xml(part)) == xml_tree(final_package.xml(part)):
                    final_package.parts[part] = original_package.parts[part]
                    final_package.roots.pop(part, None)
                    final_package.save()
                else: raise WordError("UNKNOWN_PART_CHANGED", part)
        validation = json.loads(run(["dotnet", ".tools/sdk/WordSdk.dll", "validate", work]))
        from .verify import relationships, preservation
        integrity = relationships(work)
        retained = preservation(input_path, work, batch['operations'])
        if batch["mode"] == "locked_template":
            from .templates import verify_locked
            verify_locked(work, template)
        shutil.copyfile(work, output_path)
    report = {"schema_version": 1, "build_success": True, "automatic_pass": True,
        "visual_review_complete": False, "delivery_accepted": False,
        "input_sha256": source["sha256"], "output_sha256": digest(output_path),
        "operations": ledger, "preserved_unknown_parts": preserved, "sdk": validation,
        "relationships": integrity, "content_preservation": retained}
    write_json(output_path.with_suffix(".operations.json"), report)
    return report


@contextmanager
def transaction_work(output):
    require_actions()
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work = Path(temporary) / 'transaction.docx'
        try: yield work
        except Exception as exc:
            if work.exists(): shutil.copyfile(work, output.with_suffix('.failed.docx'))
            write_json(output.with_suffix('.failure.json'), {'build_success': False, 'automatic_pass': False,
                'visual_review_complete': False, 'delivery_accepted': False, 'error': str(exc), 'diagnostic_only': True})
            raise


def xml_tree(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text or '', node.tail or '', tuple(xml_tree(c) for c in node))
