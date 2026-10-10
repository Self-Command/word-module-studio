"""Versioned module handlers reuse upstream machine-readable contracts."""
import json
from pathlib import Path
from .runtime import require_actions, WordError

ROOT = Path(__file__).resolve().parents[2]
MODULES = {
 "M01": ("Document and package", ["document", "body"]),
 "M02": ("Text and characters", ["run", "paragraph", "hyperlink", "body", "document"]),
 "M03": ("Paragraphs and styles", ["paragraph", "run", "style", "styles"]),
 "M04": ("Lists and numbering", ["paragraph", "numbering", "abstractNum", "num"]),
 "M05": ("Pages and sections", ["section", "pagebreak", "document"]),
 "M06": ("Headers footers page numbers", ["header", "footer", "section", "field"]),
 "M07": ("Fields and references", ["field", "fieldchar", "bookmark", "hyperlink"]),
 "M08": ("Contents and indexes", ["toc", "field"]),
 "M09": ("Native mathematics", ["equation"]),
 "M10": ("Tables", ["table", "table-row", "table-cell"]),
 "M11": ("Pictures", ["picture"]),
 "M12": ("Editable charts", ["chart", "chart-series", "chart-axis"]),
 "M13": ("Shapes and textboxes", ["shape", "textbox", "diagram", "watermark"]),
 "M14": ("Footnotes and endnotes", ["footnote", "endnote", "section"]),
 "M15": ("Comments and revisions", ["comment", "revision", "paragraph", "run", "table", "section"]),
 "M16": ("Forms and content controls", ["sdt", "formfield"]),
 "M17": ("Extraction and merge", []),
 "M18": ("Metadata and accessibility", ["document", "picture", "table", "paragraph"]),
 "M19": ("Template composition and fonts", []),
 "M20": ("Rendering and verification", [])
}


def contract(kind):
    require_actions()
    base = ROOT / "third_party/officecli/help"
    path = base / "docx" / (kind + ".json")
    if not path.is_file(): raise WordError("UNSUPPORTED_ELEMENT", kind)
    def load(file, visiting=None):
        visiting = set(visiting or [])
        if file in visiting: raise WordError("SCHEMA_CYCLE")
        visiting.add(file)
        data = json.loads(file.read_text(encoding="utf-8-sig"))
        properties = {}
        extends = data.get("extends", [])
        for name in [extends] if isinstance(extends, str) else extends:
            properties.update(load(base / (name + ".json"), visiting)["properties"])
        properties.update(data.get("properties", {}))
        return {**data, "properties": properties}
    return load(path)


def check_properties(module, kind, action, props):
    require_actions()
    if module not in MODULES: raise WordError("UNKNOWN_MODULE", module)
    if kind not in MODULES[module][1]: raise WordError("MODULE_ELEMENT_MISMATCH", f"{module}/{kind}")
    data = contract(kind)
    if not data.get("operations", {}).get(action): raise WordError("UNSUPPORTED_ACTION", f"{kind}/{action}")
    definitions = {}
    if module == 'M15' and kind != 'revision':
        revision = contract('revision')['properties']
        for key in ('revision.type', 'revision.author', 'revision.date', 'revision.id', 'revision.action'):
            definitions[key] = {'add': True, 'set': True, 'type': 'string'}
    if module == 'M15' and kind == 'revision': definitions['revision.action'] = data['properties']['action']
    for key, value in data["properties"].items():
        definitions[key.lower()] = value
        aliases = value.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases: definitions[alias.lower()] = value
        for alias in value.get('propAliases', []): definitions[alias.lower()] = value
    for key, value in props.items():
        definition = definitions.get(key.lower())
        if definition is None or not definition.get(action, False):
            raise WordError("UNSUPPORTED_PROPERTY", f"{kind}/{action}/{key}")
        if definition.get("type") == "enum" and str(value) not in definition.get("values", []):
            aliases = definition.get("aliases", {})
            if not isinstance(aliases, dict) or not any(str(value) in values for values in aliases.values()):
                raise WordError("INVALID_ENUM", f"{key}={value}")
    return data


def catalog():
    require_actions()
    return {"schema_version": 1, "modules": [{"id": key, "name": value[0], "elements": value[1],
        "implementation": "officecli-contract-adapter" if value[1] else "native-extension",
        "automatic_acceptance": "pending", "visual_acceptance": "pending"} for key, value in MODULES.items()]}
