---
name: word-module-studio
description: 使用可组合的 Word 模块创建、编辑和排版 DOCX，支持强制模板、原生公式及逐页视觉复检。适用于独立文档任务或其他技能调用，可按用户选择在本地或 GitHub Actions 执行。
---

# Word Module Studio

将用户要求映射为模块操作，或将内容填入登记模板。自由编辑和强制模板共用内核；图表题注、分栏、字体及审批流程由用户或调用方决定。

这是独立的通用 DOCX 技能。按用户文档需求调用模块，不内置特定业务、机构或出版场景。尊重用户选择本地或 GitHub Actions；本地任务不需要 GitHub 账号、仓库或凭证。不得将用户稿件、个人数据或其他项目资源加入技能源码仓库或安装包。

先读取能力目录和当前验收状态：安装包 `core/docs/module-coverage.json` 与 `core/docs/core-features.json`。逐功能区分上游支持、已接入、自动验收、视觉验收及证据；不能把 DOCX 构建成功表述为完整验收。

## 操作流程

1. 确定新建/编辑、自由编辑/强制模板、输入文件、输出目标与执行地点。沿用用户已经选定的方式；未指定时检查本地依赖，依赖齐全可在本地执行，缺失时说明本地安装、本地容器或 Actions 选项。用户选择本地后，不因缺依赖自动上传文档或切换云端。按需读取[执行方式](references/execution.md)。读取已有 Word 的 `DocumentSnapshot`，用对象 ID 定位；输入变化后重新检查，不能猜段落序号。
2. 新建正式文档先确认字体。可推荐 Noto Serif CJK SC＋Liberation Serif，或 Noto Sans CJK SC＋Liberation Sans；数学可推荐 TeX Gyre Pagella Math。允许用户另选字体。已有文档保留原字体；检测缺失后说明替代差异。
3. 根据需求创建 `OperationBatch` 或提供 MD、结构化数据及 `TemplateSpec`。强制模板不接受稿件控制字号、页面、分节、栏数等物理设置。未登记的母版先单独构建、验收和登记。
4. 本地使用 `core/src/word_module_studio/client.py run --manifest ... --output ...`，或在配置好依赖的本地 Python 环境调用同一 API；`doctor` 检查依赖，不自动安装。可选本地 Docker 环境。用户选择 Actions 时才使用 `submit`、`status`、`fetch`，并配置自己的公有或私有任务仓库及 `document-task.yml`。两种方式均按清单读取明确文件、保留原件；不上传整个工作区。
5. 从所选执行方式取得 Word、LibreOffice 兼容 PDF、逐页预览和复检报告。阅读全部页面，按 [视觉复检清单](references/visual-review.md) 记录真实问题；收据绑定本地运行标识或 Actions 运行及产物指纹。不用 HTML 截图证明 Word 分页。执行地点不改变验收标准。
6. 提供首版及报告；是否继续修改遵循用户授权和调用方审批流程。每次修改保留版本、批准范围和差异。其他技能调用时沿用其已经适用的审批边界，独立文档任务按用户授权执行。

数学必须保留可编辑 OMML、作者 aligned 对齐、换行和编号映射。默认 practical 只在外层运算符补断点，保留分式、上下标和根式内部结构。宽度估算产生提示；实际校样判断严重程度。报告用公式 ID 记录通过、需小幅调整或失败及位置建议。轻微行距或对齐可交付；缺符号、结构变化、严重遮挡或裁切失败。固定 LibreOffice 未显示 m:brk 原生断行，兼容默认采用外层多行数组；Word 原生渲染尚未验收。不能悄悄跨栏、缩字、栅格化或修改内容。

目录、图表目录和索引用 `refresh-fields` 回填原生域缓存，保留原 DOCX 的非域内容及部件；输出和原文件须分开。实际字体嵌入需显式提供可再分发字体，不能把嵌入开关视作已写入字体文件。文字框、首字下沉、中文禁则、分页控制、主题和表格 AutoFit 可独立调用或组合到 TemplateSpec。容器复检结合原生对象尺寸、所属节及 PDF 几何，无法确定的对象保留视觉复检提示。

按需读取 [操作接口](references/operations.md)、[模板组合](references/templates.md)。完整源码、许可、本地入口、可选 Docker 环境及 Actions 入口位于安装包 `core/`，不依赖额外模型 API。
