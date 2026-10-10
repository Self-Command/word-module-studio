# Explicit tasks

Choose your own task repository and install the dispatch workflow. Each manifest lists only
its required inputs; `client.py submit` calculates missing SHA-256 values before upload.
An inspect task returns a snapshot without editing its input:

```json
{"schema_version":1,"stage":"inspect","files":[{"path":"input.docx","role":"document"}]}
```

For an edit, save the returned snapshot, copy the required object ID and input SHA-256 into
`batch.json`, and list both files in the task. IDs remain stable after unrelated insertions,
but an input hash mismatch fails rather than editing a newer file accidentally.

```json
{"schema_version":1,"input_sha256":"SHA256_FROM_SNAPSHOT","mode":"free_edit",
 "operations":[{"id":"title","module":"M02","action":"set","target":"OBJECT_ID_FROM_SNAPSHOT","props":{"text":"Updated title"}}]}
```

```json
{"schema_version":1,"stage":"edit","files":[{"path":"input.docx","role":"document"},{"path":"batch.json","role":"batch"}]}
```

A formal compose task lists MD, the registered `template-manifest`, its unchanged DOCX `master`,
data and explicit image/bibliography/font resources. `font_scheme` must match the template.
For a new identity, use `template-build`, then `template-probe` with a representative MD and
the candidate master/manifest. Review that proof through `visual-receipt`, and pass the
composition report and accepted visual report to `template-register`. Later tasks reuse the
downloaded master bytes. Python `compose` also accepts candidate manifests for development
probes and regression, which are separate from registration.
The same policy can have one, two or three columns without a template-specific engine branch.

After downloading a document, a render task lists that DOCX and returns PDF/PNG/report.
Review every page and submit a `visual-receipt` task listing the render report, all page PNGs
as `proof`, and the completed receipt as `receipt`. A receipt contains the original run ID,
PDF hash, identical page hash list, reviewer, V01–V21 checklist, every page's observations
and findings. Review completion and accepted delivery are distinct states.

The Python equivalent inside Actions is:

```python
from word_module_studio.templates import build
from word_module_studio.compose import compose
from word_module_studio.render import render
manifest = build(template_spec, 'build/template')
compose('paper.md', manifest, 'build/paper.docx', resources=['figure.png'], data=metadata)
render('build/paper.docx', 'build/proof')
```

Paper applications keep model evidence, content approval, official rules and LaTeX in their
own consumer. `consumers/reference_paper.py` maps policy data to the same TemplateSpec;
the core never switches on competition or journal names.
