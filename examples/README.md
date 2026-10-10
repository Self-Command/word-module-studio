# Explicit document tasks

Choose local execution or Actions. A manifest lists only files needed for one stage, relative to its own folder. Locally, use `client.py run --manifest task.json --output NEW_OUTPUT_FOLDER`; it fills missing file hashes and needs no GitHub account or engine commit. For Actions, choose a task repository with `document-task.yml` and use `submit`, which also supplies the pinned engine commit before upload. Keep task inputs outside the skill/source repository.

## Inspect and edit

An inspect task returns a snapshot without editing its input:

```json
{"schema_version":1,"stage":"inspect","files":[{"path":"input.docx","role":"document"}]}
```

Read `result.snapshot` in the downloaded task report. Use its `sha256` and a target object's `id` in the batch. Do not guess paragraph positions; inspect again after changing the input.

```json
{"schema_version":1,"input_sha256":"SHA256_FROM_SNAPSHOT","mode":"free_edit",
 "operations":[{"id":"title","module":"M02","action":"set","target":"OBJECT_ID_FROM_SNAPSHOT","props":{"text":"Updated title"}}]}
```

```json
{"schema_version":1,"stage":"edit","files":[{"path":"input.docx","role":"document"},{"path":"batch.json","role":"batch"}]}
```

Submit/status/fetch commands are in the English and Chinese READMEs. Edits return a new DOCX and compatibility proof. A `locked_template` task also carries the registered manifest, exact master and matching `font_scheme`.

## Build and register a reusable template

Copy `core-layout.json` to a task folder and choose its identity, fonts and layout. The example uses cloud-installed fonts and embeds the declared redistributable Latin font. Use that declaration only when the actual font permits it.

1. Submit `template-build` with one `template` JSON and `font_scheme` matching its `fonts`.
2. Download the candidate manifest and master. Submit `template-probe` with representative `markdown`, the candidate `template-manifest`, unchanged `master`, matching `font_scheme`, and explicitly needed resources.
3. Review every page. Submit `visual-receipt` with the completed receipt and its proof files.
4. Submit `template-register` with the candidate `template-manifest`, exact `master`, matching `font_scheme`, accepted `composition-report` and `visual-report`. Download the registered manifest and retain its master bytes.
5. Submit `compose` with `markdown`, the registered `template-manifest`, exact `master` and matching `font_scheme`. Optional `data`, `image`, `bibliography` and `font` files are explicit entries. A changed font scheme or physical layout requires a new identity/version.

```json
{
  "schema_version":1,
  "stage":"template-build",
  "font_scheme":{"latin":"Liberation Serif","cjk":"Noto Serif CJK SC","math":"TeX Gyre Pagella Math","rtl":"Noto Sans Arabic"},
  "files":[{"path":"core-layout.json","role":"template"}]
}
```

```json
{
  "schema_version":1,
  "stage":"compose",
  "font_scheme":{"latin":"Liberation Serif","cjk":"Noto Serif CJK SC","math":"TeX Gyre Pagella Math","rtl":"Noto Sans Arabic"},
  "files":[
    {"path":"document.md","role":"markdown"},
    {"path":"registered-manifest.json","role":"template-manifest"},
    {"path":"master.docx","role":"master"},
    {"path":"figure.png","role":"image"}
  ]
}
```

Content cannot override the registered master's pages, columns or protected styles. TemplateSpec supplies layout data to the same shared engine.

## Other stages

| Stage | Input roles | Purpose |
| --- | --- | --- |
| `render` | One `document` | Copy the DOCX and create PDF, page PNGs and report. |
| `refresh-fields` | One `document` | Refresh supported editable field results in a distinct copy with proof. |
| `verify` | One `document` | SDK structure, relationships, snapshot and accessibility checks. |
| `merge` | Two or more `document` files | First file is the master; choose `header_policy: master` or `source_regions`. |
| `extract` | One `document`, one `data` | Data JSON supplies `object_ids` from the input snapshot. |
| `visual-receipt` | One `receipt`, explicit `proof` files | Validate the bound review. |
| `package` | No document input | Build a candidate installation from approved engine files. |

For `visual-receipt`, include the render report (`report.json`) and every page PNG as `proof`. The receipt holds the original run ID, PDF hash, identical page list, reviewer, V01–V21 checklist, observations for every page and findings. Review completion and delivery acceptance are distinct. See the skill's visual-review reference.

## Python API inside Actions

```python
from word_module_studio.templates import build
from word_module_studio.compose import compose
from word_module_studio.render import render

manifest = build(template_spec, "build/template")
compose("document.md", manifest, "build/document.docx", resources=["figure.png"], data=metadata)
render("build/document.docx", "build/proof")
```

Candidates are allowed for development probes. A successful probe does not register a template or accept its pages. Document execution is available locally or in Actions, with the same review requirements.
