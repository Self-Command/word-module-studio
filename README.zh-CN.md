# Word Module Studio

[English](README.md) | **简体中文**

独立、通用的 **Word DOCX 创建、编辑与复检技能**。可通过 Codex 技能、显式 JSON 任务或 Python API 调用。普通文档编辑和受模板约束的文档共用同一套内核。

内核组合固定版本的 OfficeCLI、Open XML SDK、Pandoc 和 LibreOffice。**用户可选择本地执行或 GitHub Actions**。本地任务无需 GitHub 账号、仓库、凭证或 Actions 环境变量；可配置本机依赖直接运行，也可选择本地 Docker 环境。不需要额外模型 API。

适用于报告、说明书、方案等需要可编辑文字、公式、表格、图表和统一排版的结构化文档。具体业务内容和规则由调用方提供。

[下载技能](https://github.com/Self-Command/word-module-studio/releases/latest) · [任务示例](examples/README.md) · [模块契约](docs/modules.md) · [验收范围](docs/status.md)

## 查看真实测试效果

以下是**通用回归测试文档的原始页面图片**，由 LibreOffice 26.8.1 实际渲染并逐页审阅。它们展示 DOCX 的兼容校样；尚未验收 Microsoft Word 桌面版原生渲染。点击图片可查看完整大图。独立测试页的空白区域是有意保留的。

| 双栏中英及阿拉伯文排版 | 三栏排版 |
| :---: | :---: |
| [<img src="docs/gallery/two-columns.png" width="400" alt="包含中文、英文、阿拉伯文、标题和编号的双栏 DOCX">](docs/gallery/two-columns.png) | [<img src="docs/gallery/three-columns.png" width="400" alt="带原生页眉和页码域的三栏 DOCX">](docs/gallery/three-columns.png) |
| **可编辑原生公式** | **保留作者公式对齐** |
| [<img src="docs/gallery/editable-math.png" width="400" alt="可编辑分式与公式编号">](docs/gallery/editable-math.png) | [<img src="docs/gallery/author-alignment.png" width="400" alt="两行公式保留等号与整体编号">](docs/gallery/author-alignment.png) |
| **浮动对象与合并表格** | **原生三行首字下沉** |
| [<img src="docs/gallery/native-objects.png" width="400" alt="浮动图片、框架、合并表格、形状、文字框和脚注">](docs/gallery/native-objects.png) | [<img src="docs/gallery/drop-cap.png" width="400" alt="原生可编辑的字母 D 跨三行下沉">](docs/gallery/drop-cap.png) |
| **带工作簿数据的可编辑图表** | **跨栏续表** |
| [<img src="docs/gallery/editable-chart.png" width="400" alt="包含三个数值点的原生散点图">](docs/gallery/editable-chart.png) | [<img src="docs/gallery/continued-table.png" width="400" alt="续表保留行数据、重复表头和题注">](docs/gallery/continued-table.png) |

8 张图片均在[来源清单](docs/gallery/provenance.json)中记录页面与 SHA-256 指纹，来自[云端运行 38059546545](https://github.com/Self-Command/word-module-studio/actions/runs/38059546545)。该次排版基线通过 **100 项回归测试、26 份通用校样和全部 49 页逐页审阅**。独立技能 0.1.2 源码在[云端运行 38069365621](https://github.com/Self-Command/word-module-studio/actions/runs/38069365621)通过 **6 组检查、104 项测试**，包含发布文件清单与未登记文件不得进入安装包的检查。这些证据对应具体场景，不能代表全部 Word 功能或任意输入均已通过。

## 支持哪些功能

| 模块 | 可调用功能 |
| --- | --- |
| M01 · 文档与文件结构 | DOCX 新建、读取、复制、保存；对象快照、部件关联及未修改部件保留。 |
| M02 · 文字与字符 | 插入、删除、替换文字；跨片段编辑；字体和字符格式；语言及从右向左属性。 |
| M03 · 段落与样式 | 对齐、缩进、间距、制表位、边框、样式继承、实际格式解析、分页规则、原生框架与首字下沉。 |
| M04 · 列表与编号 | 项目符号、多级列表、标题编号、重新编号、接续及起始值。 |
| M05 · 页面与分节 | 纸张、方向、页边距、分页分节、等宽与不等宽栏、行号、装订线及所属节。 |
| M06 · 页眉页脚与页码 | 首页／奇偶页／默认类型，各节链接、页码域及重新编号。 |
| M07 · 域与交叉引用 | 书签、超链接、原生域、图表公式独立题注编号与交叉引用。 |
| M08 · 目录与索引 | 标题目录、题注目录和索引域；按实际分页刷新可编辑域结果。 |
| M09 · 原生数学 | 受支持的 LaTeX 转可编辑 OMML；行内与独立公式、分式、上下标、矩阵、分段、编号、作者对齐与实用外层断行。 |
| M10 · 表格 | 行和单元格操作、尺寸、合并、边框底纹、重复表头、固定／AutoFit 布局、三线表与续表题注。 |
| M11 · 图片 | 插入替换、嵌入式／浮动锚点、环绕定位、比例尺寸、裁剪及替代文本。 |
| M12 · 可编辑图表 | 图表／系列／坐标轴属性；同步嵌入工作簿数据；六类有端到端验收证据。 |
| M13 · 形状与文字框 | 原生形状、连接线、文字框、水印、组合旋转、文字效果和图示接口。 |
| M14 · 脚注与尾注 | 原生注释、节内编号规则及脚注／尾注转换。 |
| M15 · 批注与修订 | 范围锚点、回复状态、修订与限定范围的接受／拒绝；主要为结构证据。 |
| M16 · 表单与内容控件 | 文本、富文本、图片、日期、复选和列表；XML 绑定、条件与重复填充、传统表单域接口；主要为结构证据。 |
| M17 · 合并与提取 | DOCX 合并提取、辅助部件、冲突 ID 重映射及明确的页眉页脚策略。 |
| M18 · 属性与辅助检查 | 文档属性；标题、语言、图片替代文本和表头检查。 |
| M19 · 模板与字体 | 模板版本、受保护母版、主题、字体继承、中文禁则、可组合版式及真实字体文件嵌入。 |
| M20 · 校样与验收 | PDF／PNG、结构引用字体检查、内容差异、容器几何与绑定页面的视觉收据。 |

具体条件见[模块与错误说明](docs/modules.md)、[功能证据](docs/core-features.json)和[模块覆盖](docs/module-coverage.json)。上游有接口不等于每个选项都已验收。柱形、条形、折线、饼图、面积和散点六类已有有限范围内的视觉证据，其他类型需单独验证。批注、修订和控件主要通过结构测试，尚未认证 Word 完整交互界面。

## 安装技能

1. 从[最新发行页](https://github.com/Self-Command/word-module-studio/releases/latest)下载 ZIP。
2. 将完整的 **`word-module-studio` 文件夹**放入 `$CODEX_HOME/skills`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills`。保留 `SKILL.md`、`references/`、`agents/` 和 `core/`。
3. 确认当前 Codex 会话可以发现技能。升级前保存已验证的旧文件夹，回退时恢复它。
4. 按下面说明选择执行方式；只有选择 Actions 时才需要任务仓库。

ZIP 包含运行内核、契约、任务工作流、文档及相关效果图片，不含测试素材、测试代码、用户文档或业务适配器。批准发布的文件见 [publication-manifest.json](publication-manifest.json)。

## 选择执行地点

| 方式 | 需要什么 | 文档在哪里处理 |
| --- | --- | --- |
| 本地 Python／命令行 | Python 依赖，以及所用操作的本机后端 | 本地任务与输出文件夹 |
| 可选的本地 Docker | 支持 Linux 容器的 Docker；构建镜像时下载固定依赖 | 本地挂载文件夹；运行时可禁用网络 |
| 可选的 GitHub Actions | 自己的任务仓库、`gh` 登录与 Actions 权限 | 用户指定的公有或私有任务仓库 |

安装技能不要求 GitHub。缺本地依赖时会报告缺项，不会自动安装软件、上传文档或切换到 Actions。

[本地环境验证](https://github.com/Self-Command/word-module-studio/actions/runs/38069365595)在随附的 Linux x64 容器中关闭网络、不提供 GitHub 凭证或 Actions 环境变量，验证检查、修改、原文件保留及实际 PDF/PNG 输出。

### 本地 Python

在安装后的技能文件夹中，安装固定版本的 Python 依赖并检查环境：

```powershell
python -m pip install -r core/requirements-resolved.lock
python core/src/word_module_studio/client.py doctor --profile inspect
python core/src/word_module_studio/client.py run --manifest "PATH_TO_TASK/task.json" --output "PATH_TO_OUTPUT/inspect-001"
```

若直接导入 Python API，可在选定环境中再运行 `python -m pip install --no-deps -e core`。检查任务的清单示例在下文。完整编辑和校样前使用不带 `--profile inspect` 的 `doctor`。每次选新的或空的输出文件夹；执行器只把清单文件暂存到 `.inputs`，保留原件，生成含 `execution: local`、`local-...` 运行标识、内核版本与源码指纹的 `task-report.json`。本地任务不要求 Git 提交。

检查功能需要 Python 依赖。编辑与完整校样还需要 OfficeCLI、编译后的 Open XML SDK 辅助程序、Pandoc、带 UNO Python 的 LibreOffice、Poppler 与 fontconfig。固定的本机环境在 Linux x64 验证；Ubuntu 24.04／WSL x64 可在 `core/` 中先创建并激活 Python 虚拟环境，再运行 `bash ci/bootstrap.sh` 和 `bash ci/render-bootstrap.sh`，它们会下载后端和安装系统包，需要时使用 `sudo`。其他原生平台需自行验证依赖与渲染。下面的可选本地 Linux 容器提供完整配置。

程序从 `core/.tools` 或 `PATH` 查找，也可用 `WMS_OFFICECLI`、`WMS_DOTNET`、`WMS_PANDOC`、`WMS_LIBREOFFICE`、`WMS_UNO_PYTHON`、`WMS_SDK_DLL`、`WMS_PDFTOPPM`、`WMS_PDFFONTS`、`WMS_FC_MATCH` 指定路径。路径表示单个程序，不能填 shell 命令。UNO Python 必须能够导入 `uno`。

### 可选：本地 Docker

安装后从 `core/` 构建；源码仓库使用 `.`。Docker 是一种本地环境选择，并非技能必需条件：

```powershell
docker build --platform linux/amd64 -t word-studio-local core
$wordTaskPath = (Resolve-Path "PATH_TO_TASK").Path
$wordOutputPath = (New-Item -ItemType Directory -Force "PATH_TO_OUTPUT").FullName
docker run --rm --platform linux/amd64 --network none --mount "type=bind,source=$wordTaskPath,target=/input,readonly" --mount "type=bind,source=$wordOutputPath,target=/output" word-studio-local run --manifest /input/task.json --output /output/inspect-001
```

构建时下载一次依赖；上述运行命令禁用网络，无需 GitHub 登录。任务文件夹只读挂载，产物留在本地输出文件夹。编辑、渲染等任务沿用相同清单和命令，换新的输出子文件夹。操作属性中的显式文件路径要指向可访问的本地文件；Docker 模式使用对应的容器挂载路径。

## 可选：配置 GitHub Actions

需要 **Python 3.12+**、**GitHub CLI（`gh`）**、写任务分支和触发 Actions 的权限，以及已初始化且启用 Actions 的任务仓库。任务仓库可以是私有仓库。无需在本地安装 Word 或文档处理依赖；工作流会安装固定版本的云端依赖。

1. 选择任务仓库，例如 `YOUR_NAME/word-tasks`，确保有默认分支及至少一个提交。
2. 将 [.github/workflows/document-task.yml](.github/workflows/document-task.yml)复制到默认分支的相同路径并提交。
3. GitHub CLI 尚未登录时执行 `gh auth login`。
4. 用完整提交 SHA 固定内核；可通过当前独立发行版标签解析：

```powershell
$wordEngineCommit = gh api repos/Self-Command/word-module-studio/git/ref/tags/v0.1.2 --jq ".object.sha"
```

将得到的 40 位 SHA 与任务一起保留，不要用会移动的分支名称。安装包入口是 `core/src/word_module_studio/client.py`；直接使用源码时改为 `src/word_module_studio/client.py`。

## 任务清单：检查已有 DOCX

在**技能和源码仓库之外**创建本地任务文件夹，放入 `input.docx` 和以下 `task.json`：

```json
{
  "schema_version": 1,
  "stage": "inspect",
  "files": [{"path": "input.docx", "role": "document"}]
}
```

本地使用上文的 `run --manifest ... --output ...`。选择 Actions 时，从已安装技能文件夹提交，清单使用自己文件的完整路径：

```powershell
python core/src/word_module_studio/client.py submit --repo YOUR_NAME/word-tasks --manifest "PATH_TO_TASK/task.json" --engine-commit $wordEngineCommit
gh run list --repo YOUR_NAME/word-tasks --workflow document-task.yml --limit 5
```

Actions 提交结果包含 `task_id` 和状态链接。找到标题为 `Word task TASK_ID` 的运行，取得数字运行 ID 后查询、下载：

```powershell
python core/src/word_module_studio/client.py status --repo YOUR_NAME/word-tasks --run-id RUN_ID
python core/src/word_module_studio/client.py fetch --repo YOUR_NAME/word-tasks --run-id RUN_ID --dir outputs
```

本地或下载的 `task-report.json` 包含 `result.snapshot.sha256`、对象 ID、能力目录和辅助检查结果。检查不会修改原文档。下载内容位于各自 artifact 子文件夹。

## 修改已有文档

将快照中的文件 SHA-256 和真实目标对象 ID 填入 `batch.json`：

```json
{
  "schema_version": 1,
  "input_sha256": "SHA256_FROM_SNAPSHOT",
  "mode": "free_edit",
  "operations": [{
    "id": "update-title", "module": "M02", "action": "set",
    "target": "OBJECT_ID_FROM_SNAPSHOT",
    "props": {"text": "Updated document title"}
  }]
}
```

使用以下清单，按所选执行方式运行：

```json
{
  "schema_version": 1,
  "stage": "edit",
  "files": [
    {"path": "input.docx", "role": "document"},
    {"path": "batch.json", "role": "batch"}
  ]
}
```

客户端上传前补齐文件指纹。输入变化后重新检查。批次在副本上原子执行，目标失效、参数不支持或输入过期时失败并保留诊断。`locked_template` 还保护已登记的物理版式。

也可直接向已安装技能提出请求：

```text
使用 $word-module-studio 修改附件 DOCX 的标题并刷新目录。
在本地执行，不上传我的文档；保留现有字体，先检查再修改，
返回可编辑 Word、兼容 PDF 和页面复检报告。
```

## 新建文档与可复用模板

正式新文档需明确字体方案。[通用组合配置](examples/core-layout.json)展示主题、中文与分页规则、分栏、AutoFit、字体嵌入和公式策略；示例值可按用户文档调整。

模板采用 `template-build` → `template-probe` → 页面复检及 `visual-receipt` → `template-register`。随后用 `compose` 提交 Markdown、已登记清单和未修改的 DOCX 母版，并明确列出数据、图片、参考文献或字体。`font_scheme` 必须与模板一致。所选环境中的 Python API 可探测候选模板，但探测不等于登记。

[任务指南](examples/README.md)说明输入角色和模板流程，[TemplateSpec](schemas/template-spec.schema.json)是权威配置。Actions 内可调用：

```python
from word_module_studio.templates import build
from word_module_studio.compose import compose
from word_module_studio.render import render

manifest = build(template_spec, "build/template")
compose("document.md", manifest, "build/document.docx", resources=["figure.png"], data=metadata)
render("build/document.docx", "build/proof")
```

文档 API 可在本地或 Actions 执行。`run` 是本地执行入口；`submit`、`status`、`fetch` 仅用于用户选择的 Actions 方式。

## 输出与复检

生成或修改文档的任务返回可编辑 DOCX、兼容 PDF、逐页 PNG 和 JSON 报告。`inspect` 返回快照，`verify` 返回结构检查，域刷新返回更新后的副本及校样。报告分别记录构建、自动检查、视觉审阅完成和交付接受。

接受交付前应阅读全部页面。`visual-receipt` 把原运行、PDF、页面指纹与审阅人、21 项清单、逐页观察和问题绑定；未解决问题会使交付保持未接受。见[复检清单](https://github.com/Self-Command/word-module-studio/blob/main/skills/word-module-studio/references/visual-review.md)。

## 文档隐私与发布范围

本仓库只包含通用技能、内核、接口、工作流、通用 Word 回归输入、证据、示例和许可证。[发布检查](ci/audit_publication.py)拒绝明确清单之外的跟踪文件，检查 README 链接，并核对效果图片与已接受页面。打包按批准文件逐项复制。

本地执行读取明确文件、写入所选输出文件夹，不上传文档。只有选择 Actions 时，输入才进入**自己选择的任务仓库**，不会自动进入本源码仓库。每次只上传清单文件，创建任务分支，Actions 产物保留 30 天。任务提交会一直保留，直到你自行管理，不会自动删除。上传敏感文档前先选择合适的仓库可见性。自定义字体校样使用任务临时 fontconfig 环境，不永久安装到个人字体目录；字体使用与嵌入需具备相应权限。

## 已知限制

- 校样使用 LibreOffice 26.8.1，尚未认证 Word 原生渲染、精确分页和打印机相关行为。
- 保留原生 OMML、作者对齐与嵌套结构。固定渲染器忽略原生运算符断点，长公式兼容策略使用外层数组。个别公式可能需小幅调整并记录；缺符号、结构改变或严重裁切不能通过。
- 请求且允许时嵌入真实字体文件；PDF 中出现字体不代表 Word 使用嵌入字体。
- 安全保留既有 SmartArt、OLE 和未知部件不等于完整支持创建、编辑或交互验收。
- 当前工作流未实现完整桌面界面控制、实时协作、VBA 执行、数字签名、加密、邮件合并和 Microsoft Editor／Copilot 服务。

## 许可证与开发

原创源码采用 **Apache-2.0**；复用 MIT 工具保留许可证与来源，依赖使用各自许可证。见 [LICENSE](LICENSE)、[第三方说明](THIRD_PARTY_NOTICES.md)和[依赖锁定](pins.json)。

项目的自动发布复检在 GitHub Actions 执行，并验证不带 Actions 环境变量的真实本地执行路径。开发者配置好依赖后也可在本地运行测试。源码包含用于验证的通用 Word 素材，安装 ZIP 排除它们。发布范围变化时，应先审阅并更新明确文件清单，再通过 CI 和发行检查。
