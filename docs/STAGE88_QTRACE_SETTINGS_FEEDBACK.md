# 阶段 88：QTrace 模型设置反馈工作台

## 目标

用户此前在模型设置页遇到“点击本地语义 Embedding 后只刷新页面”和“LLM 请求失败但不知道失败在哪里”的问题。本阶段不改动 LLM、Embedding、密钥保存或重建索引接口，只把已有异步状态提升到可观察的 QTrace 操作面，并继续减少设置页对参考项目卡片风格的依赖。

## 实现

- `frontend/src/pages/Settings.jsx` 挂载 `qtrace-settings.css`，增加 `MODEL CONTROL / 01` 标题层和 LLM、Embedding、保存三块首屏状态读数；状态区明确显示“待测试 / 测试中 / 已连接 / 连接失败 / 已保存”等状态；
- LLM 与 Embedding 的连接测试保留原有 `testLLMConnection`、`testEmbeddingConnection` 调用，只增加 `role="status"`、`role="alert"` 和 `data-qtrace-state`，失败信息可以在页面上被读到；
- 保存、加载和向量重建错误统一经过 `redactSettingsError`，截断过长供应商回显并隐藏 Bearer/token 类凭据片段；页面不会回显 API Key；
- `frontend/src/pages/qtrace-settings.css` 只作用于设置页：纸张面板、硬边分区、单一信号红、直角输入框、无渐变/无阴影保存栏、窄屏三块状态区改为单列，并保留 reduced-motion；
- 新增 `scripts/qtrace_settings_preflight.py` 和 `tests/test_qtrace_settings_preflight.py`，锁定设置页 CSS 挂载、状态反馈、脱敏边界、既有 API adapter 和显式重建入口。

## 验证

- `python scripts/qtrace_settings_preflight.py`：通过；
- `python -m pytest -q tests/test_qtrace_settings_preflight.py --basetemp <项目暂存目录>`：`2 passed`；Windows 正式工程 `.pytest_cache` 仍有既存 WinError 5 权限警告；
- 入口、QTrace shell、开始训练、画像、设置和最终交付预检：全部通过；最终交付预检仍只提示 15 个本地产物需要人工审阅，没有发现明显密钥模式；
- `npm run typecheck`：通过；
- `npm run build -- --configLoader runner --outDir "C:\\Users\\clearsnowsong\\Documents\\ChatGPT\\秋招\\techsnowsong_stage\\qtrace_stage88_dist"`：通过，3811 个模块转换成功，仅有大型 bundle 提示；正式 `dist`/Vite 临时目录的 Windows `EPERM` 写入边界没有通过删除依赖或构建产物解决；
- 5174 `/` 返回 200 且不含 `/@vite/client`，`/api/health` 返回 `{"status":"ok","mode":"qtrace"}`；浏览器当前未登录根路径进入 `/login`，没有使用真实账号、API Key 或真实资料。

## 当前边界与下一步

本阶段没有真实 LLM/Embedding 联调，也没有把“设置已保存”误报成“模型推理成功”：本地模型是否能加载仍需用户在合成账号下点击 Embedding 测试，LLM 是否可用仍需用户点击 LLM 测试。登录后的设置页桌面/窄屏视觉、失败详情和本地模型成功路径属于最后的人工验收清单；静态契约、typecheck、备用构建和未登录运行态不能替代这一步。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。
