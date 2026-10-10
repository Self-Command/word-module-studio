"""W0: actual pinned backend commands, readback and native object evidence."""
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from word_module_studio.runtime import require_actions, run, write_json, digest

require_actions()
folder = Path("build/qualification")
folder.mkdir(parents=True, exist_ok=True)
document = folder / "baseline.docx"
commands = [
    ["create", document],
    ["add", document, "/body", "--type", "paragraph", "--prop", "text=Word Module Studio qualification"],
    ["add", document, "/body", "--type", "paragraph", "--prop", "text=中文 English العربية"],
    ["set", document, "/body/p[2]", "--prop", "bold=true"],
    ["add", document, "/", "--type", "section", "--prop", "type=continuous", "--prop", "columns=2"],
    ["add", document, "/body", "--type", "equation", "--prop", r"formula=\frac{x^{2}}{1+y}+\sum_{i=1}^{n}i"],
    ["add", document, "/body", "--type", "table", "--prop", "rows=2", "--prop", "cols=2"],
    ["get", document, "/section[2]", "--json"],
]
results = []
for cmd in commands:
    try:
        output = run(["officecli", *cmd])
        results.append({"command": [str(a) for a in cmd], "success": True, "output": output})
    except Exception as exc:
        results.append({"command": [str(a) for a in cmd], "success": False, "error": str(exc)})
write_json(folder / "commands.json", results)
assert all(r["success"] for r in results), "BACKEND_QUALIFICATION_FAILED"
with ZipFile(document) as archive:
    root = etree.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    assert "中文 English العربية" in "".join(root.xpath("//w:t/text()", namespaces=ns))
    assert root.xpath("//w:cols[@w:num='2']", namespaces=ns)
    assert root.xpath("//m:oMath//m:f", namespaces=ns)
    assert root.xpath("//w:tbl", namespaces=ns)
sdk = run(["dotnet", ".tools/sdk/WordSdk.dll", "validate", document])
write_json(folder / "sdk-validation.json", json.loads(sdk))
write_json(folder / "report.json", {"stage": "W0", "build_success": True, "automatic_pass": True,
    "visual_review_complete": False, "release_allowed": False, "run_id": os.environ["GITHUB_RUN_ID"],
    "input_commit": os.environ.get("GITHUB_SHA"), "docx_sha256": digest(document), "commands": len(results)})
