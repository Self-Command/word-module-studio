---
name: word-module-studio
description: 使用可组合的 Word 模块创建、编辑和排版 DOCX，执行强制模板、原生公式及云端视觉复检。适用于独立文档任务或其他技能调用；转换和验收在 GitHub Actions 完成。
---

# Word Module Studio

将用户要求映射为模块操作，或将内容填入登记模板。自由编辑和强制模板共用内核；图表题注、分栏、字体及审批流程由用户或调用方决定。

先读取能力目录和当前验收状态：安装包 `core/docs/module-coverage.json`。仅调用已实现能力，区分自动与视觉验收状态；不能把上游支持或 DOCX 构建成功表述为本技能完整验收。

## 操作流程

1. 确定新建/编辑、自由编辑/强制模板、输入文件、输出目标。读取已有 Word 的云端 `DocumentSnapshot`，用对象 ID 定位；输入变化后重新检查，不能猜段落序号。
2. 新建正式文档先确认字体。可推荐 Noto Serif CJK SC＋Liberation Serif，或 Noto Sans CJK SC＋Liberation Sans；数学可推荐 TeX Gyre Pagella Math。允许用户另选字体。已有文档保留原字体；检测缺失后说明替代差异。
3. 根据需求创建 `OperationBatch` 或提供 MD、结构化数据及 `TemplateSpec`。强制模板不接受稿件控制字号、页面、分节、栏数等物理设置。未登记的母版先单独构建、验收和登记。
4. 本地只运行 `core/src/word_module_studio/client.py` 的 `submit`、`status`、`fetch`。提交清单逐项列出文件；不上传整个工作区。用户可选择自己的公有或私有任务仓库，须安装 `document-task.yml` 入口。源代码公开不要求用户文档公开。
5. 下载 Word、LibreOffice 兼容 PDF、逐页预览和复检报告。阅读全部页面，按 [视觉复检清单](references/visual-review.md) 记录真实问题；收据绑定运行及产物指纹。不用 HTML 截图证明 Word 分页。
6. 提供首版及报告；是否继续修改遵循用户授权和调用方审批流程。每次修改保留版本、批准范围和差异。在论文套件中，沿用 MD 确认、字体选择、生成和修复审批；独立普通文档任务不额外套用论文审批。

数学必须保留可编辑 OMML 和编号映射。无法安全换行、缺资源或破坏未知对象时交付具体诊断；不能悄悄跨栏、缩字、栅格化或修改内容。

按需读取 [操作接口](references/operations.md)、[模板组合](references/templates.md)。完整源码、许可和云端入口位于安装包 `core/`，不依赖额外模型 API。
