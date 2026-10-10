# Word Module Studio

通过可组合模块生成、编辑与复检 Word。源码、JSON 契约、Python 接口和 Codex 技能公开；用户文档可在自己选择的公有或私有 GitHub 仓库执行。

当前为 **0.1.0 核心排版版**。[云端运行](https://github.com/Self-Command/word-module-studio/actions/runs/38059546545)通过 100 项测试，并完成 26 份通用文档、49 页校样的逐页视觉审阅。具体能力与边界见 [实施记录](docs/status.md)、[功能证据](docs/core-features.json) 和 [产物收据](docs/core-acceptance.json)。

## 使用

从 [发行页](https://github.com/Self-Command/word-module-studio/releases/tag/v0.1.0)下载技能 ZIP，将其中 `word-module-studio` 文件夹放入 Codex 技能目录。升级前保存旧文件夹；回退时恢复已验证的旧包。安装包包含 `core/`，不含测试论文、模型数据及生成产物。

在任务仓库安装 [.github/workflows/document-task.yml](.github/workflows/document-task.yml)，使用 GitHub CLI 登录，调用本地传输入口：

```powershell
python core/src/word_module_studio/client.py submit --repo OWNER/TASK-REPO --manifest task.json --engine-commit 完整提交SHA
python core/src/word_module_studio/client.py status --repo OWNER/TASK-REPO --run-id 运行ID
python core/src/word_module_studio/client.py fetch --repo OWNER/TASK-REPO --run-id 运行ID --dir outputs
```

清单显式列出输入文件及角色。已有 Word 先提交 `inspect`，取得输入指纹和对象 ID，再使用 `OperationBatch` 修改。新建正式文档需明确字体方案；`compose` 将 MD 与数据填入已登记的 `TemplateSpec`。新模板只提供配置、资源及验收例，不在内核中增加期刊或比赛名称分支。

`free_edit` 允许明确指定的版式操作；`locked_template` 保护母版的页面、区域、样式和字体。数学为可编辑 OMML，图表带原生可编辑工作簿；不容纳的对象和未知对象破坏风险会产生具体诊断。

全部测试、转换、编译、渲染与程序验收仅在 GitHub Actions 执行。本地仅编辑源码、提交、查询和下载。输出包含 DOCX、LibreOffice 兼容 PDF、逐页 PNG 和报告；生成成功、自动检查通过、视觉审阅完成及交付接受分别记录。需阅读全部页面并提交绑定产物指纹的视觉收据。

参考 [任务示例](examples/README.md)、[组合配置](examples/core-layout.json)、[模块说明](docs/modules.md) 与 [技能入口](skills/word-module-studio/SKILL.md)。主题和字体继承、中文与分页控制、自动表格宽度、真实字体嵌入、原生框架与首字下沉、可编辑域缓存及实用公式策略已接入。论文模板继续暂停，后续单独接入与验收。

视觉证据使用 LibreOffice 26.8.1，尚未认证 Word 桌面原生渲染。该渲染器忽略 OMML 原生运算符断点，兼容默认策略使用外层公式数组；源 OMML 和作者对齐保留。具体文档仍需完成其自身的逐页校样。

原始源码使用 Apache-2.0，复用代码保留其许可证，详见 [第三方来源](THIRD_PARTY_NOTICES.md)。不需要额外模型 API。
