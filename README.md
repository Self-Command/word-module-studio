# Word Module Studio

Composable DOCX generation, editing and verification for AI agents and Python applications.
The public engine uses pinned OfficeCLI, Open XML SDK, Pandoc/OMML and LibreOffice.
Core layout version: **0.1.0**. The [accepted cloud run](https://github.com/Self-Command/word-module-studio/actions/runs/38059546545)
passes 100 tests. Direct page review covers 26 generic proofs and 49 pages; see
[acceptance scope](docs/status.md) and the [bound receipts](docs/core-acceptance.json).

中文：将 Word 功能拆成可复用模块。新模板只提供区域、样式、字体和对象规则；
自由编辑与强制模板共用内核。源码公开，个人任务可在自己选择的公有或私有仓库执行。
所有文档执行、测试、转换和渲染在 GitHub Actions；本地仅提交、查询和下载。

```text
User / AI / application
  → skill / JSON task / Python API
  → fingerprint + stable object IDs + template policy
  → layout context + module operations
  → OfficeCLI / Open XML SDK / Pandoc OMML
  → content + structure + LibreOffice pagination proof
  → editable DOCX + PDF + pages + report + visual receipt
```

Install the [release ZIP](https://github.com/Self-Command/word-module-studio/releases/tag/v0.1.0) by copying its `word-module-studio` folder into your
Codex skills directory. Preserve the previous folder before upgrading; rollback replaces
the installed version with that verified previous folder. Installation includes `core/` but excludes
test manuscripts, model evidence, upstream showcase inputs and generated outputs.

For standalone use, install `.github/workflows/document-task.yml` in your execution repository,
authenticate GitHub CLI, and pin a full engine commit. Python 3.12 or newer is needed for the
local transport; document dependencies are installed by the cloud workflow.

```powershell
python core/src/word_module_studio/client.py submit --repo OWNER/TASK-REPO --manifest task.json --engine-commit FULL_40_CHAR_SHA
python core/src/word_module_studio/client.py status --repo OWNER/TASK-REPO --run-id RUN_ID
python core/src/word_module_studio/client.py fetch --repo OWNER/TASK-REPO --run-id RUN_ID --dir outputs
```

See [working task examples](examples/README.md), [module contracts](docs/modules.md),
[feature acceptance](docs/core-features.json), [coverage evidence](docs/module-coverage.json),
and the [skill entry](skills/word-module-studio/SKILL.md).
The API can be imported inside Actions: `snapshot`, `execute`, `templates.build`, `compose`,
`merge`, `extract`, `render`, and `receipt`. These reject local business execution.

The [generic core configuration](examples/core-layout.json) combines theme and effective fonts,
CJK/pagination controls, table AutoFit, actual font data embedding and practical math rules.
Native frames/drop caps and editable field-cache refresh are independent interfaces.
Paper-template development and its test suites remain paused for separate consumer acceptance.

Formal new documents require an explicit font choice. LibreOffice PDF is a compatibility proof;
Microsoft Word desktop rendering is not asserted. Automatic checks and visual acceptance are
separate report fields. Existing SmartArt/OLE and other unknown parts are preserved where
safe; desktop UI, online collaboration, VBA execution and digital signatures are outside scope.

Original code is Apache-2.0. Reused MIT code and unmodified dependency licenses are retained
in [third-party notices](THIRD_PARTY_NOTICES.md). No extra model API is required.
