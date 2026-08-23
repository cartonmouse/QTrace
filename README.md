# 问迹 QTrace：从空目录自主复现

<p align="center"><img src="frontend/public/qtrace-icon.png" alt="问迹 QTrace 图标" width="160" /></p>

这是学习用的独立重建工程，目标不是给上游项目打补丁，而是通过自己的代码逐步实现参考项目的核心用户体验和主要功能。

## 名称

项目名为“问迹 QTrace”。“问”代表面试中的持续提问与追问，“迹”代表把回答、复盘、掌握度和画像变化留下可追踪的成长轨迹。项目会把一次次练习沉淀为知识、历史记录和能力画像，而不是把每轮面试当成彼此无关的一次问答。GitHub 仓库：[cartonmouse/QTrace](https://github.com/cartonmouse/QTrace)。

## 快速启动

以下命令在 Windows PowerShell 中执行，需要两个终端分别启动后端和前端。路径中的 `<project>` 替换为本地工程目录；当前学习环境的独立工程位于 `D:\3BUPT\mark'workshop\techsnowsong\rebuild`。

后端终端：

```powershell
Set-Location -LiteralPath '<project>\rebuild'
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

前端终端：

```powershell
Set-Location -LiteralPath '<project>\rebuild\frontend'
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5174`。首次进入后注册本地账号，在“模型设置”中启用本地演示模型即可离线体验；使用真实 LLM 时再填写 OpenAI-compatible API Base、Model 和 API Key。普通本地运行默认使用 `persisted` 兼容模式，API Key 只保存在本地 SQLite 设置表且不会由设置接口返回给前端；公开 Demo Compose 默认使用 `session` 模式，访问者 Key 只留在当前后端进程内存，服务重启后需要重新输入。

如果已经下载了 Sentence-Transformers 模型，可以额外安装 `requirements-local-embedding.txt`，然后在“模型设置”中选择“本地语义模型”，填写后端可访问的模型目录；加载始终使用 `local_files_only=True`，不会因为缺少本地文件而联网下载。

如果 PowerShell 禁止激活虚拟环境，可以不激活，直接使用该环境中的 `python -m pip` 和 `python -m uvicorn`。前端开发服务器通过 Vite proxy 将 `/api` 请求转发到 `127.0.0.1:8002`。

## 验证命令

在 `rebuild` 目录执行：

```powershell
python -m pytest -q
python -m compileall -q backend tests
Set-Location frontend
npm run typecheck
npm run build
Set-Location ..
python scripts\techspar_frontend_preflight.py
python scripts\qtrace_shell_preflight.py
python scripts\qtrace_interview_preflight.py
python scripts\qtrace_profile_preflight.py
python scripts\qtrace_settings_preflight.py
python scripts\qtrace_entry_preflight.py
python scripts\repository_preflight.py
python scripts\resume_claims_preflight.py
python scripts\seed_synthetic_browser_demo.py --help
```

测试使用临时 SQLite、合成账号和 fake provider，不会调用真实模型。不要把真实简历、录音或 API Key 放入仓库；`.env`、`data/`、SQLite 文件、前端依赖和构建产物已加入 `.gitignore`。

## 学习边界

- 原项目只作为行为、页面、接口和架构参考：`..\reference`。
- 本地 TechSpar 只作为交互规律和信息架构参考；当前活动 AppShell 已由 QTrace 自有 `QTraceWorkspaceShell` 承担，页面仍按阶段逐步迁移。QTrace API 适配、后端和品牌由本项目维护；改编许可与非商业限制见 `THIRD_PARTY_NOTICES.md`。
- 允许先用本地 deterministic stub provider 跑通流程，再接入兼容 OpenAI 的真实模型服务。
- 真实简历、真实录音、真实 API key 不进入仓库；测试只使用合成数据。
- 本项目不把真实长音频、说话人分离和时间戳对齐纳入交付范围；录音模块以转写文本和可替换边界为主。
- GitHub 仓库已经发布；后续每次新提交和推送仍需单独确认。

## 当前前端收口：模型设置反馈

阶段 88 为模型设置页增加了 QTrace 自有的首屏状态读数：LLM 连接、Embedding 模式/连接和配置保存分别显示待测试、测试中、成功或失败；LLM/Embedding 测试按钮的结果使用 `role="status"`/`role="alert"`，保存、加载和重建错误会先脱敏再显示。设置页的卡片、输入框和保存栏采用硬边纸张面板与单一信号红，视觉层不改变 `testLLMConnection`、`testEmbeddingConnection`、`updateSettings` 或显式 reindex 契约。新增 `qtrace_settings_preflight.py` 与 2 条回归；typecheck、备用输出目录 build、入口/API health 运行态检查通过。标准正式 dist 的 Windows `EPERM` 写入边界仍需保留，不用删除依赖或构建产物解决。登录后模型设置页的真实 LLM/本地 Embedding 成功与失败路径仍需使用合成账号人工验收。

## 本地验收清单

阶段 89 的逐项人工验收记录见 `docs/STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md`（PowerShell 路径写法：`docs\STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md`）。它覆盖直达登录、QTrace 工作台、开始训练、画像首屏、模型设置状态、Embedding 显式重建、PDF/Markdown 文档导入、Personal Agent、知识图谱和主题/窄屏路径。自动化证据和人工证据分开记录；当前环境的正式 `dist` 写入 `EPERM`、登录后浏览器视觉、真实 LLM/本地 Embedding 路径仍按清单如实验收，不把静态检查说成完整 E2E。

## 面试 Demo 部署包

阶段 90 增加了 `docker-compose.demo.yml` 和 `deploy/` 部署包：Nginx 提供前端生产构建并把 `/api` 代理到 FastAPI，后端使用命名卷保存 Demo 数据，`REBUILD_JWT_SECRET` 必须由部署环境提供。先运行 `python scripts\public_demo_preflight.py` 做只读契约检查；有 Docker 时复制 `deploy\demo.env.example` 为 `deploy\demo.env`，替换 JWT secret 后再按 `docs\STAGE90_PUBLIC_DEMO_DEPLOYMENT_CONTRACT.md` 启动。

公开 Demo 不内置开发者 LLM Key。用户仍可在网页“模型设置”中填写自己的 OpenAI-compatible API Base、Model 和 API Key；Stub 只作为没有 Key 时的明确离线降级。Compose 默认的 `session` BYOK 模式不会把访问者 Key 写入 SQLite，但仍需 HTTPS、API Base 白名单/SSRF 防护、限流、预算、备份和日志治理，不能把本地 Compose 契约写成“已经上线”。

部署包已在本机完成 Docker 验证：前后端镜像构建成功，8080 端口的 Nginx 首页和 `/api/health` 代理均返回 200；容器验证结束后已停止，未删除命名卷。正式公网 URL、HTTPS 和云端账号仍未配置。

阶段 91 已把模型设置页的 LLM 连接测试接到 `POST /api/settings/test-llm`：测试当前表单配置，空字段可复用已保存配置，但不会保存新值；探测只发最小合成请求并隐藏凭据。运行 `python scripts\qtrace_byok_preflight.py` 可检查该契约。公网前仍需完成 BYOK 加密/会话存储、SSRF 防护和限流。

阶段 92 为 Demo Compose 默认启用 `REBUILD_BYOK_STORAGE_MODE=session`：访问者的 LLM/Embedding Key 只在当前后端进程内存中存在，SQLite 不保存 Key；服务重启后需要重新填写。普通本地运行仍默认使用 `persisted` 以保持学习环境兼容，完整公网发布前仍需 HTTPS、SSRF 防护、限流、预算和日志治理。

阶段 93 完成本地运行态交接：重启 8002 后端时使用 `techsnowsong_stage` 下的合成 SQLite/Data 目录，5174 当前前端通过 `/api` 代理访问该后端；合成账号注册、设置读取、空配置 `POST /api/settings/test-llm`、前端入口和代理健康检查均已通过。session 模式下切换到 Demo/本地 Embedding 会清除进程内旧远程 Key，并有回归锁定；全量合成回归 `136 passed`，typecheck/build 和发布预检通过。正式目录的 Vite `.vite-temp` 与默认 SQLite 写入仍受当前 Windows `EPERM`/只读边界影响，使用暂存输出和隔离环境验证，不删除或覆盖正式产物。

阶段 94 为公开 Compose 增加 `REBUILD_BLOCK_PRIVATE_API_BASE=true`：保存 LLM/Embedding 配置和独立 LLM 测试前会校验 `http/https`、URL 凭据、localhost/内部域名、私网/回环/链路本地 IP，以及 DNS 解析结果是否全部为公网地址；本地默认关闭，以保留 Ollama 等本机兼容服务调试能力。该校验是应用层第一道门，真正公网发布仍需云防火墙/egress policy 防止 DNS rebinding，并应继续保留限流、预算和日志治理。

阶段 94 的容器验收也已完成：Compose 镜像构建通过，8080 首页和同源健康检查通过；合成账号访问私有 API Base 时，连接测试被安全拒绝、配置保存返回 400，验证后仅停止容器，未删除数据卷。该结果证明“可部署并有第一层边界”，不代表已经配置公网 URL 或完成云端安全发布。
最终收口门禁：全量合成回归 `148 passed`，BYOK/public-demo/final-delivery 预检通过，`git diff --check` 通过；正式目录 `.pytest_cache` 的 Windows 写权限 warning 保留为环境边界记录。

## 目标形态

采用与参考项目接近、但由本项目自行实现的技术栈：

- 前端：React + TypeScript + Vite + React Router
- 后端：FastAPI + Pydantic
- 存储：SQLite + 本地用户目录
- AI 边界：`ModelProvider` 提供 `stub`/OpenAI-compatible；`EmbeddingProvider` 提供本地确定性 baseline、本地 Sentence-Transformers 语义模型和 OpenAI-compatible 适配器
- 实时协议：先实现 JSON，再实现 SSE，最后实现 Copilot WebSocket

## 阶段路线

| 阶段 | 自己实现的结果 | 学会回答的问题 |
| --- | --- | --- |
| 1. 骨架 | 前端路由、FastAPI、健康检查、统一 API client | 前后端如何启动和通信？ |
| 2. 认证与配置 | 注册/登录、JWT、首次 provider 配置门禁 | token 如何传递？为什么有第二道门禁？ |
| 3. 简历面试主链 | 简历文本、会话状态机、追问、结束 | 一轮面试状态如何保存和推进？ |
| 4. 复盘闭环 | 评估、画像、薄弱点、历史记录 | 本次训练怎样影响下一次？ |
| 5. 专项训练 | 主题、知识文件、题库驱动的专项训练 | 为什么不是静态题库随机抽题？ |
| 6. 检索与复习 | 简单向量/关键词检索、掌握度、间隔复习 | RAG 和长期记忆分别解决什么问题？ |
| 7. JD 备面 | JD 解析、岗位匹配、定向问题和评估 | 如何把 JD、简历、画像合成上下文？ |
| 8. 录音复盘 | 文本优先，之后接 ASR | 外部 ASR 失败时主链如何降级？ |
| 9. 分析适配层 | ASRProvider、规则 fallback、结构化 LLM 复盘 | 为什么 ASR、Provider 和 Analyzer 要解耦？ |
| 10. Copilot Prep | 文本 Prep、策略树、风险地图、JSON/SSE | 为什么 Prep 和实时辅助分阶段？SSE 和 WebSocket 如何选择？ |
| 11. 核心前端闭环 | Copilot 历史、跨页上下文、统一导航、训练回流 | 如何把多个功能组织成统一产品？ |
| 12. Personal Agent v1 | 画像/复习/历史/简历只读工具、规划、对话记忆 | Agent 如何规划、调用工具并利用长期画像？ |
| 13. 个性化出题与画像 v1 | 画像信号、SM-2 到期项、LLM 结构化动态出题、画像写回 | 系统如何从“固定题库”变成“根据个人状态安排训练”？ |
| 14. LLM 稳定性收口 | 超时/网络错误归一化、429/5xx 有界重试、鉴权错误不重试 | Provider 如何处理外部模型服务的不稳定性？ |
| 15. Agent 受控行动工具 | 明确请求触发学习计划草稿生成、计划持久化、用户隔离和计划展示 | 如何让 Agent 从“给建议”走向“可控地提出动作”？ |
| 16. Agent 确认与完成 | 草稿确认、计划项完成、状态机和幂等接口 | 如何让 Agent 行动经过用户确认并可追踪？ |
| 17. Agent 计划恢复 | 计划绑定 Agent 对话、旧库迁移、历史对话重新展示计划卡 | 如何保证 Agent 行动不是一次性响应，而是可恢复的业务状态？ |
| 18. 计划驱动专项训练 | 计划项跳转专项训练、focus 传递、出题器按计划焦点约束、到期容量透明化 | 如何把 Agent 的计划真正接到训练执行链路？ |
| 19. 计划训练审计 | 训练会话保存 plan/item 关联，复盘页显式完成计划项，旧 sessions 增量迁移 | 如何把计划执行和训练结果关联，同时避免自动误判完成？ |
| 20. 发布前行为收口 | 否定意图防误写、计划强制读取近期训练、复盘加载错误可见、已完成项支持再次训练 | 如何保证 Agent 写操作安全、上下文完整且前端失败可观察？ |
| 21. TechSpar 功能差距审计 | 对照参考代码地图盘点已复现、替代实现和未实现功能，确定下一阶段优先级 | 如何诚实说明复现项目完成度，为什么下一步先做文档库和 Embedding？ |
| 22. Personal Agent 文档记忆 | 文档分块、本地确定性 Embedding、用户隔离检索、Agent 只读文档工具和前端文档库 | RAG 的文档为什么要分块？Embedding、检索证据和 Agent 回答如何解耦？ |
| 23. PDF 文档导入 | 复用共享 PDF 文本解析器，把文本型 PDF 导入个人文档库并接入分块、Embedding 和检索 | 为什么简历和个人文档共用解析模块？扫描件为什么暂不支持？ |
| 24. 文档引用与重复导入收口 | 规范化正文指纹、旧库迁移、幂等重复导入、检索 citation 和 Agent/前端来源展示 | 为什么精确去重而不是用 Embedding 去重？引用如何帮助 Agent 可解释？ |
| 25. 文档版本管理 | 文档版本快照、当前版本检索、历史版本查看、版本化 citation 和编辑后新版本保存 | 为什么不能直接覆盖文档？为什么当前检索只使用最新版本？如何保证版本查询的用户隔离？ |
| 26. 结构化简历编辑器 | 姓名/方向/概述/技能/项目字段、确定性面试上下文渲染、结构化简历版本和 Agent 回退读取 | 为什么要字段化简历？结构化简历、PDF 和个人文档如何分工？ |
| 27. 项目追问卡与证据映射 | 按项目字段生成背景/职责/设计/验证/取舍追问，并用项目名检索个人文档 citation | 为什么先用确定性追问模板？没有文档证据时为什么仍然保留问题？ |
| 28. 追问卡驱动专项训练 | 追问卡一键进入专项训练，合并卡片焦点、JD 学习计划焦点和 SM-2 到期队列，并保存训练来源 | 如何把一个可解释的问题入口接到 Agent 计划、出题器和长期复习？ |
| 29. Agent 追问卡计划 | Agent 先读取指定追问卡，再生成带卡片来源的 draft 学习计划；确认后计划项仍可回到专项训练 | 如何让 Agent 的写操作受控、可追溯，并把项目问题继续传到训练执行？ |
| 30. JD 与项目追问映射 | 用 JD 技能词匹配结构化项目字段，返回命中证据和代表性追问卡，并可直接交给 Agent 制定计划 | 如何解释“这个项目为什么能证明岗位要求”，又如何避免模型编造匹配？ |
| 31. JD focus 权重 | 在项目命中结果中加入岗位优先级和确定性匹配分数，帮助排序项目准备顺序 | 如何设计一个可解释的匹配评分，而不是只展示关键词命中？ |
| 32. 知识图谱最小读模型 | 按主题把高频问题、相近问题、画像薄弱点和 SM-2 待复习项组织成用户隔离的可解释关系图，并提供前端图谱页 | 为什么图谱可以从已有数据重建？为什么这一版不需要 Neo4j 或向量数据库？ |
| 33. 图谱到 Agent 计划联动 | 从主题图谱进入 Personal Agent，限定读取该主题的 SM-2 队列，并把主题写入计划来源后回到专项训练 | 如何让图谱真正参与个性化行动，又避免 Agent 读取无关复习项？ |
| 34. 图谱问题到精确训练 | 将 `question:<n>` 节点按当前用户题库重新校验，作为首个技术追问并写入训练会话来源 | 如何保证图谱点击的题目没有被前端伪造，且仍能复用动态出题和状态机？ |
| 35. 图谱问题到 Agent 计划 | Agent 读取并验证指定图谱问题，把节点 ID/文本写入计划来源与计划项，再回到精确专项训练 | 如何把 Agent 的计划动作和图谱节点、训练 session 串成一条可审计链？ |
| 36. 图谱相近问题候选 | 从已有 `related` 边派生可选后续题，展示在图谱页并保存在 Agent 计划元数据中，但不自动扩张计划 | 如何把图谱关系转成训练建议，又避免相似度误差污染个性化计划？ |
| 37. 图谱候选训练反馈审计 | 记录相近题候选的父节点来源、训练开始/完成次数，并把统计回显到 related 边；不自动修改权重或画像 | 如何把用户选择变成可评估反馈，同时避免把点击次数误当成掌握度？ |
| 38. 图谱候选离线评估 | 增加候选完成率、平均复盘分、首末分差和重复训练比例的只读报告，并在图谱页展示 | 如何从行为日志做描述性评估，同时避免把相关性说成因果效果？ |
| 39. Agent 读取图谱候选反馈 | 将 related 边的开始/完成统计补充到 Agent 候选上下文和计划元数据，不自动扩张计划 | Agent 如何解释候选历史，同时不把行为次数误当成能力或重要性？ |
| 40. 图谱/Agent/SM-2 面试讲解稿 | 整理 90 秒项目介绍、请求链路、架构取舍、常见追问、演示顺序和诚实边界 | 如何把实现讲成可验证的工程故事，而不是堆砌名词？ |
| 41. 仓库发布前自检 | 修正依赖启动说明，补充只读的必需文件、敏感配置和本地产物检查 | 如何让公开仓库的启动路径可信，同时说明自检不能替代干净环境复现？ |
| 42. 外部 Embedding 适配器 | 将 `/embeddings` 网络、响应校验、维度一致性和有界重试封装在独立 Provider 中，默认仍使用本地 baseline | Embedding Provider 如何与文档分块/检索解耦？外部服务失败时边界在哪里？ |
| 43. 用户级 Embedding 配置与显式重建 | 配置按用户隔离，设置页支持本地/外部模式，文档切换模型后必须显式 reindex，旧索引按 mode 隔离 | 如何避免 API Key 泄露、旧向量维度混用和未经确认的资料外发？ |
| 44. 真实 Embedding 联调门禁 | 用只读配置探针判断是否具备外部 Embedding 条件；只对固定合成文本发起请求，未配置时不联网 | 为什么不能复用聊天模型？如何证明真实联调没有误传个人简历？ |
| 45. 真实 LLM 与 Agent 合成联调 | 用固定合成上下文验证 Agent 的规划 JSON、工具白名单和 grounded answer 两步链路 | Agent 为什么不是固定话术？模型规划、工具执行和回答如何分层？ |
| 46. Agent 错误可观察性 | 为规划/回答失败增加稳定 stage、code、retryable 字段，前端保留对象型错误 message | 如何区分模型规划失败、回答失败和工具执行失败？为什么不把供应商异常原文直接返回？ |
| 47. Agent 失败一致性 | 新建空对话失败回滚、已有学习计划草稿保留、前端乐观消息恢复 | 为什么失败补偿不能简单删除所有状态？后端如何区分空壳对话和已产生的草稿？ |
| 48. Agent 工具失败降级 | 工具异常安全归一化、部分上下文继续回答、学习计划写工具依赖门禁 | 为什么只读工具可以降级，而写工具必须在必要上下文完整时才执行？ |
| 49. Agent 可恢复交互 | 显式重试、输入恢复、保留草稿按 conversation_id 精确加载、失败状态引导 | 为什么重试必须由用户触发？为什么不能直接加载最新 draft？ |
| 50. 本地运行态冒烟 | 后端健康、前端入口和生产构建资源的只读检查 | 为什么单元测试和构建检查之外，还需要一个轻量运行态门禁？ |
| 51. 复现与面试演示收口 | 干净环境复现前置检查、合成数据演示顺序和追问速答 | 如何证明项目能复现？如何诚实说明已完成和未完成边界？ |
| 52. 合成数据本地彩排 | TestClient + StubProvider 串联简历、图谱、Agent draft/confirm 和计划完成 | 如何用可重复证据证明主链路，而不是只展示页面？ |
| 53. 浏览器彩排前置检查 | 前端路由、Agent 恢复交互和样式的只读契约检查 | 为什么静态路由检查不能代替浏览器 E2E？为什么人工账号状态要单独确认？ |
| 54. 最终交付前置检查 | 阶段文档、README 验证证据、核心脚本和公开边界的只读核对 | 如何在不推送的情况下证明项目已经具备公开交付材料？ |
| 55. AI Agent 面试追问防守包 | 架构、工具、RAG、图谱、SM-2、稳定性、安全、评估和不足的系统化回答 | 如何在面试官连续追问时用证据和边界回答，而不是堆概念？ |
| 56. 简历项目表述与证据对齐 | 简历技术版/精简版、工程证据矩阵、面试口述和不夸大边界 | 如何让简历上的每个技术关键词都能落到代码、测试或文档？ |
| 57. 合成浏览器演示账号种子 | 只创建全新 SQLite 的合成账号、简历、文档、知识库和图谱上下文 | 如何让人工浏览器彩排既真实可操作，又不触碰现有账号和真实资料？ |
| 58. 真实 Agent Smoke 输出脱敏 | Agent 真实联调失败时对 API Base/Key 做最后一层脱敏，并用回归锁定输出边界 | 为什么不能直接打印供应商原始错误？如何证明 smoke 输出没有泄露凭据？ |
| 59. 回归临时产物公开边界 | `.gitignore` 忽略 qtrace 阶段临时目录，复现前置脚本验证规则，发布检查继续只读提示 | 为什么忽略规则和发布扫描要同时存在？为什么不自动删除本地产物？ |
| 60. 隔离浏览器彩排配置前置 | 检查独立 SQLite、后端端口和 Vite API target 的隔离契约，避免人工彩排误连日常实例 | 为什么要同时隔离数据库、后端端口和前端代理？为什么静态契约仍不能代替浏览器 E2E？ |
| 61. 合成演示端点输出 | 种子脚本输出推荐的后端 `8003`、前端 `5175` 和 `REBUILD_API_TARGET`，减少人工抄写错误 | 为什么让数据种子脚本输出端点？它为什么仍不能证明浏览器 E2E？ |
| 62. 隔离合成环境运行态冒烟 | 在全新合成 SQLite 和备用端口上实际启动后端/前端，复用运行态冒烟检查连通性，并安全处理端口占用 | 为什么单元测试之外还要验证真实端口和进程？为什么不能自动停止未知占用者？ |
| 63. 端口校验先于合成数据创建 | 非法端口在 `seed_browser_demo` 之前被拒绝，避免错误参数产生 SQLite 或半成品上下文 | 为什么输入校验必须放在有副作用的操作之前？如何用回归证明没有创建数据？ |
| 64. 合成浏览器认证入口检查 | 实际检查隔离登录/注册页面，并把认证按钮标记纳入前端源码前置契约 | 为什么页面入口检查仍不能代替密码提交和完整浏览器 E2E？ |
| 65. 前端认证客户端边界 | 检查统一 API client 的 `/api`、Bearer token 和登录/注册请求契约，并区分源码证据与浏览器认证 | token 如何进入请求？为什么这仍不能证明登录成功？ |
| 66. 前端认证状态生命周期 | 检查 token 的读取、保存、失效清除、退出登录和业务路由门禁，并记录 localStorage 的安全取舍 | token 失效或刷新页面时如何回到登录页？为什么本地方案不等于生产认证？ |
| 67. 认证过期统一回退 | 对带 token 的 401 派发认证过期事件，由根组件统一清理状态并回到登录页 | 页面停留期间 token 过期怎么办？为什么请求层和 React 状态层要解耦？ |
| 68. 画像待复习项直达训练 | 为 SM-2 到期项补充带 topic/focus 的专项训练入口，打通画像展示到训练执行 | 画像如何真正影响下一场训练，而不是只展示掌握度？ |
| 69. 画像页可恢复加载 | 为画像/主题并行加载增加错误状态、可观察提示和重试入口，避免页面永久停留在 loading | 请求失败时为什么不能展示空画像？重试如何保证不产生副作用？ |
| 70. 专项训练页可恢复加载 | 为训练领域、SM-2 队列和可选图谱问题的初始读取增加失败态、重试入口和卸载保护 | 为什么请求失败不能渲染成“没有训练领域”？重试如何保证不创建训练或修改画像？ |
| 71. 本地语义 Embedding | 新增 `local-model` Provider、模型目录配置、可选依赖、离线加载和文档显式重建索引 | 本地模型如何加载？为什么必须 `local_files_only`？模型切换后为什么要显式重建？ |
| 72. 模型设置工业化前端收口 | 分离 LLM/Embedding 的反馈状态、显示可执行验证路径、补充结构化 API 错误和工业瑞士印刷样式 | 为什么保存成功不等于模型已调用？前端如何让配置失败可定位，且不破坏既有业务路由？ |
| 73. 模型设置加载恢复 | 为 `/settings` 增加 loading/失败/成功三态、错误详情和无副作用重试 | 请求失败时为什么不能永久 loading？如何区分配置可读、保存成功、模型加载和检索生效？ |
| 80. 个人文档 PDF/Markdown 文件导入 | 文件扩展名校验、PDF 文本层提取、Markdown UTF-8 解码、统一分块/Embedding/检索和前端入口 | 为什么不保存文件路径？扫描 PDF 为什么暂不支持？为什么切换 Embedding 后仍需显式重建？ |
| 81. QTrace 品牌图标挂载 | 复用 `frontend/public/qtrace-icon.png` 接入工作台左上角品牌区，并覆盖收起侧栏与前端静态预检 | 为什么使用图片资源而不是继续渲染 QT 文字？如何避免主题切换或收起侧栏时品牌标识丢失？ |
| 82. TechSpar 前端迁移 | 以 TechSpar 源码作为活动 UI 基线，通过 QTrace API adapter、品牌替换和显式能力降级接回后端 | 为什么复用成熟前端？API 不一致时如何避免假功能？如何证明旧 UI 不再是活动入口？ |
| 83. Vite 开发运行时黑屏恢复 | 禁止异常的 Vite 8 开发客户端注入，保留手动刷新开发模式并验证 5174 页面重新渲染 | 为什么 HTTP 200 仍可能黑屏？如何区分开发工具注入故障和 React/API 业务故障？ |
| 84. 直达登录入口 | 移除首页开场动画和 Landing 活动入口，根路径按认证状态进入登录或画像，并增加防回归预检 | 为什么启动动画不属于核心价值？如何证明未登录用户不会再加载它？ |

## 当前第一里程碑：最小完整闭环

先不追求页面数量，先完成一个可以解释、测试和演示的竖切片：

```text
登录
  -> 首次模型配置（stub provider 也可用）
  -> 选择一个主题/目标岗位
  -> 开始一场简历模拟面试
  -> 状态机生成问题并接收回答
  -> 结束并生成本地复盘
  -> 历史记录和画像能看到结果
```

这一竖切片完成后，再按照阶段 5—10 扩展，而不是在没有主链的情况下平铺大量页面。

## 当前功能边界

已完成的可演示链路包括：

- 本地注册/登录、用户隔离和 Provider 配置门禁；
- PDF 简历上传与文本注入；
- Personal Agent 文档库支持文本/Markdown 保存、PDF 文本层解析以及 PDF/Markdown 文件导入；
- 简历模拟面试、专项训练、JD 定向训练和文本转写复盘；
- 领域知识 Markdown、关键词检索、领域画像和简化 SM-2；
- Copilot Prep 的策略树、风险地图、JSON/SSE 进度事件和历史恢复；
- Personal Agent v1 的规划、只读工具、长期画像上下文和对话记忆；
- Personal Agent 的受控学习计划写工具：先读取上下文，再将最多 5 项计划以 draft 保存，经用户确认后逐项完成；
- Agent 历史对话会恢复其关联的学习计划卡，刷新页面后仍可继续确认或完成计划项；
- 学习计划项可以进入专项训练，计划焦点会传给 Stub/LLM 出题器；计划只负责选择训练目标，不直接推进面试状态机；
- 专项训练会话会保存来源学习计划和计划项，复盘页支持用户显式完成计划项；训练开始或结束不会自动改写计划状态；
- 发布前收口已补齐 Agent 否定意图保护、计划近期训练上下文前置、复盘加载错误提示和已完成计划项再次训练入口；
- 已完成 TechSpar 与 QTrace 功能差距审计，明确优先补齐 Personal Agent 文档记忆；
- Personal Agent 已支持文本/Markdown 文档保存、文本型 PDF 导入、自动分块、本地确定性、本地 Sentence-Transformers 语义模型或用户显式配置的 OpenAI-compatible Embedding、用户隔离检索和 `search_personal_documents` 只读工具；
- Personal Agent 检索结果已包含文档引用标识，同一用户重复保存相同正文会幂等返回已有文档而不重复写入；
- Personal Agent 个人文档支持版本快照、历史版本查看和编辑后生成新版本；当前检索和 Agent 引用明确标出 `vN`；
- 结构化简历编辑器支持个人概述、技能和项目证据字段，生成可预览的面试上下文并以版本快照保存；没有 PDF 时简历面试、JD Prep、Copilot 和 Agent 可以读取它；
- 结构化简历页面会按项目生成五类可解释追问卡，并从个人文档库返回带版本号的 citation 证据；
- 项目追问卡可以一键进入专项训练；出题器会合并追问卡焦点、已确认学习计划焦点、领域画像和 SM-2 到期项，训练会话、复盘页和历史记录会保存并展示追问卡来源；
- 项目追问卡可以交给 Personal Agent 制定训练计划；Agent 先验证卡片归属，再把卡片 ID、项目名和简历版本写入 draft 计划，用户确认后计划项可以继续进入专项训练；
- JD 定向备面会在结构化简历可用时，把岗位技能映射到项目的技术栈、职责、概述和关键工作字段，返回命中字段与代表性追问卡；用户可以从命中项目直接交给 Agent 制定计划；
- JD→项目映射会结合技能在 JD 中的优先级、出现次数和命中字段权重计算可解释分数，并按分数排序项目；页面展示 high/medium/normal 优先级和匹配分数；
- 根据画像、领域趋势和到期复习项生成专项题目计划，并回写强项、行为信号和行动项。
- 知识图谱读模型会按主题组织高频问题、相近问题和 SM-2 复习节点；图谱问题可以进入精确训练或交给 Agent 制定计划，并可查看可选相近题。
- 图谱相近题入口会记录父问题和训练完成情况，related 边展示开始/完成次数；这些统计只用于候选效果审计，不改写关系权重、画像或 SM-2。
- 图谱页提供候选离线评估报告，按当前 related 边计算完成率、有效复盘平均分、首末分差和重复训练比例；报告只读，不将指标写回事实源。
- Agent 读取图谱问题时会同时看到相近候选的历史开始/完成次数和完成率，并把它们作为可追溯元数据保存到图谱计划；不会因为反馈自动增加计划项。
- 本地运行态冒烟脚本会只读检查后端健康接口、前端入口和 `dist` 中被引用的构建资源，不读取数据库或个人资料。
- 干净环境复现前置脚本会只读检查核心文件、前端 `dev/typecheck/build` 脚本和本地数据忽略规则；面试演示以合成账号和 StubProvider 为基线。
- 合成彩排脚本会在临时 SQLite 中串联结构化简历、追问卡、知识图谱、Personal Agent 计划草稿、确认和完成，不接触正式数据库。
- 浏览器人工彩排前置脚本会只读检查前端入口路由、重试/保留草稿标记和对应样式，不读取浏览器存储或页面个人资料。
- 最终交付前置脚本会只读核对核心入口、阶段 40—70 文档、README 验证命令和明显密钥模式；本地日志/数据库只提示，不自动删除。
- AI Agent 面试防守包把项目介绍、调用链、数据边界、失败一致性、评估证据和未完成能力整理成可复述回答，并明确禁止过度声称。
- 简历项目入口把技术表述、工程证据和未完成边界对齐，并由 `resume_claims_preflight.py` 只读检查文档章节和证据链接。
- 合成浏览器种子脚本只创建全新的 SQLite 演示库，拒绝已有文件和 sidecar，不自动登录浏览器或接触现有账号。
- Agent LLM smoke 的失败输出会在脚本边界再次脱敏 API Base/Key，并由合成异常回归测试锁定；未配置时仍不联网。
- 回归临时目录使用明确的 `qtrace_stage*` 忽略规则，复现前置检查会验证这些规则存在；现有目录只提示、不自动删除。
- 隔离浏览器彩排前置脚本会只读检查 `REBUILD_DB_PATH`/`REBUILD_DATA_DIR`、Vite `REBUILD_API_TARGET` 和独立端口契约；它不创建数据库、不启动服务、不读取浏览器状态。
- 合成浏览器种子脚本会在创建新库后输出推荐的 `BACKEND_URL`、`FRONTEND_URL` 和 `REBUILD_API_TARGET`，但不会自动启动服务或接管浏览器。
- 本地隔离运行态冒烟可以把 `local_runtime_smoke.py` 的后端/前端 URL 指向自定义端口；阶段 62 已用全新合成 SQLite 的 `8004/5177` 端口验证健康接口、前端入口和构建资源，端口占用时不自动停止未知进程。
- 合成种子脚本会先校验 `1—65535` 端口范围，再创建 SQLite；非法端口只返回失败状态，不触发账号、简历、文档或知识库写入。
- 浏览器隔离检查已确认登录/注册页面的邮箱、密码和本地账户入口可渲染；`frontend_route_preflight.py` 还会只读检查 `进入学习工程`/`创建本地账户` 认证标记，但自动任务不代填密码。
- 前端统一请求层的认证边界也纳入只读契约：`api.ts` 负责 `/api`、Bearer token 和 `/auth/*` 请求；这只证明源码结构，不把密码提交或 token 持久化说成已完成。
- 前端认证状态生命周期也纳入只读契约：`App.tsx` 会读取/保存/清除 token，并在账户校验失败或认证状态不完整时回到登录入口；当前 localStorage 方案仅用于本地学习演示，生产安全仍需单独设计。
- 业务页面停留期间收到带 token 的 401 时，`apiFetch` 会派发认证过期事件，根组件统一清理 token/user/settings 并回到登录入口；这解决状态回退一致性，但不等于实现了生产级 token 刷新。
- 画像页的 SM-2 到期复习项现在有“立即复习”入口，会把 `topic` 和 `focus` 带入专项训练；`frontend_route_preflight.py` 只读检查这条画像→训练链路，后端仍负责主题校验和 session 审计。
- 画像页加载 `/profile` 或 `/topics` 失败时会显示可观察的错误卡和“重新加载画像”入口，不再永久停留在 loading，也不会为了重试写入数据库。
- 专项训练页加载训练领域、SM-2 队列或可选图谱问题失败时，会显示“训练领域加载失败”和“重新加载训练领域”错误卡；重试只重新读取，不创建 session、不修改画像或复习队列。

明确未纳入当前交付范围：真实长音频、麦克风采集、说话人分离、时间戳对齐、真实外部 Embedding 的网络联调和供应商兼容性验证、外部向量数据库、完整多 Agent 并行 Copilot、WebSocket 实时辅助、简历模板排版/PDF 导出、计划提醒和画像自动写回。当前本地语义模型已在本机缓存的中文模型上完成离线 Smoke；全新机器仍需单独安装可选依赖并提供模型目录，默认运行仍使用本地确定性方案。

## 代码约定

1. 每个阶段先增加一份设计说明和测试，再实现代码。
2. 后端路由只做输入校验、鉴权和编排；模型调用、状态机和存储分别放在独立模块。
3. 所有用户数据访问都显式带 `user_id`。
4. 模型输出先解析和校验，再写入数据库。
5. 任何失败都要有可观察的错误状态，不能把解析失败伪装成成功复盘。
6. 每完成一个阶段，记录“运行命令、测试结果、我能回答的追问、还不懂的地方”。

## 参考文档

- `..\reference\docs\FULL_PROJECT_CODE_MAP.md`：完整代码地图和调用链
- `..\reference\docs\REFERENCE_RUN.md`：冻结参考副本的本地验收记录
- `..\reference\docs\getting-started.md`：上游建议的用户使用顺序
- `docs\STAGE1_DESIGN.md`：认证、配置门禁和面试状态机
- `docs\STAGE1_INTERVIEW_QA.md`：第一阶段面试追问卡
- `docs\STAGE2_PROVIDER.md`：Provider 适配层与真实 LLM 配置
- `docs\STAGE3_RESUME.md`：PDF 简历上传、解析和面试上下文注入
- `docs\STAGE4_TOPIC_DRILL.md`：主题知识库、关键词检索和专项训练
- `docs\STAGE5_MASTERY.md`：专项掌握度、领域历史和长期画像写回
- `docs\STAGE6_REVIEW_SCHEDULE.md`：间隔复习、今日队列和专项优先出题
- `docs\STAGE7_JD_PREP.md`：JD 导入、岗位拆解和定向训练
- `docs\STAGE8_RECORDING_REVIEW.md`：文本优先的录音转写复盘和 ASR 替换边界
- `docs\STAGE9_ANALYZER_ADAPTER.md`：ASR/分析器接口、规则 fallback 和结构化 LLM 复盘
- `docs\STAGE10_COPILOT_SSE.md`：Copilot 文本 Prep、策略树、持久化和 JSON/SSE 事件协议
- `docs\STAGE11_FRONTEND_INTEGRATION.md`：Copilot 历史恢复、跨页交接和核心前端闭环
- `docs\STAGE12_PERSONAL_AGENT.md`：文本 Personal Agent、只读工具、规划/回答两步调用和对话持久化
- `docs\STAGE13_PERSONALIZED_DRILL.md`：画像驱动的动态出题、SM-2 到期复习和画像结构化写回
- `docs\STAGE14_LLM_RESILIENCE.md`：真实 LLM 的超时、网络错误、限流和重试策略
- `docs\STAGE15_AGENT_ACTIONS.md`：受控学习计划写工具、权限边界和 Agent 行动链路
- `docs\STAGE16_AGENT_CONFIRMATION.md`：Agent 行动的草稿、确认、完成和幂等状态
- `docs\STAGE17_AGENT_PLAN_PERSISTENCE.md`：学习计划与 Agent 对话绑定、旧数据库迁移和历史恢复
- `docs\STAGE18_PLAN_TO_DRILL.md`：计划项到专项训练的 focus 联动、模块接口和到期容量取舍
- `docs\STAGE19_PLAN_SESSION_AUDIT.md`：计划项与训练会话审计关联、显式完成和数据库迁移
- `docs\STAGE20_RELEASE_HARDENING.md`：Agent 意图边界、上下文完整性、失败可观察性和发布前收口
- `docs\STAGE21_TECHSPAR_GAP_AUDIT.md`：参考项目与 QTrace 的功能差距矩阵和下一阶段路线
- `docs\STAGE22_PERSONAL_DOCUMENT_MEMORY.md`：个人文档、文档分块、EmbeddingProvider 和 Agent 检索工具
- `docs\STAGE23_PDF_DOCUMENT_IMPORT.md`：共享 PDF 导入、文本抽取、个人文档持久化和扫描件边界
- `docs\STAGE24_PERSONAL_DOCUMENT_CITATION.md`：文档身份、精确去重、引用标识和旧库迁移
- `docs\STAGE25_DOCUMENT_VERSIONING.md`：个人文档版本快照、当前检索、历史查看和版本化引用
- `docs\STAGE26_STRUCTURED_RESUME_EDITOR.md`：结构化简历字段、面试上下文渲染、版本管理和 Agent 回退读取
- `docs\STAGE27_PROJECT_QUESTION_CARDS.md`：项目追问卡、字段证据映射和个人文档 citation
- `docs\STAGE28_QUESTION_CARD_TRAINING.md`：追问卡到专项训练、JD focus、SM-2 队列和训练来源审计
- `docs\STAGE29_AGENT_QUESTION_CARD_PLAN.md`：Agent 验证追问卡、生成 draft 计划和计划项来源传递
- `docs\STAGE30_JD_PROJECT_MAPPING.md`：JD 技能、结构化项目字段和项目追问卡的确定性映射
- `docs\STAGE31_JD_FOCUS_SCORING.md`：岗位 focus 优先级、字段权重和项目匹配排序
- `docs\STAGE32_KNOWLEDGE_GRAPH.md`：主题问题图、SM-2 复习节点、确定性关系边和前端图谱页
- `docs\STAGE33_GRAPH_AGENT_PLAN.md`：图谱主题作用域、Agent 复习计划来源和训练回流
- `docs\STAGE34_GRAPH_QUESTION_DRILL.md`：图谱问题 ID 校验、精确训练入口和 session 来源审计
- `docs\STAGE35_GRAPH_AGENT_QUESTION_PLAN.md`：图谱问题读取工具、Agent 计划项来源和精确训练回流
- `docs\STAGE36_GRAPH_RELATED_CANDIDATES.md`：related 边候选、可选后续练习和 Agent 计划元数据
- `docs\STAGE37_GRAPH_FEEDBACK_AUDIT.md`：候选父节点来源审计、训练开始/完成统计和不自动改权边界
- `docs\STAGE38_GRAPH_FEEDBACK_EVALUATION.md`：候选完成率、复盘分数、重复训练比例的离线评估契约
- `docs\STAGE39_AGENT_GRAPH_FEEDBACK.md`：Agent 读取候选反馈、解释边界和计划元数据
- `docs\STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md`：图谱、Agent、SM-2 的项目介绍、调用链、追问回答和演示顺序
- `docs\STAGE41_REPOSITORY_PREFLIGHT.md`：公开仓库启动说明、只读自检、敏感配置和干净环境复现边界
- `docs\STAGE42_EXTERNAL_EMBEDDING_ADAPTER.md`：OpenAI-compatible Embedding 适配器、响应契约、重试和接入边界
- `docs\STAGE43_EMBEDDING_CONFIG_REINDEX.md`：用户级 Embedding 配置、Key 隔离、mode 过滤和显式文档重建
- `docs\STAGE44_EMBEDDING_SMOKE_GATE.md`：真实 Embedding 联调门禁、只读配置探针和合成文本边界
- `docs\STAGE45_REAL_LLM_AGENT_SMOKE.md`：真实 LLM/Agent 两步联调、合成上下文和工具白名单边界
- `docs\STAGE46_AGENT_ERROR_OBSERVABILITY.md`：Agent 规划/回答失败的错误码、阶段字段和前端提示
- `docs\STAGE47_AGENT_FAILURE_CONSISTENCY.md`：Agent 失败补偿、空对话回滚、计划草稿保留和前端消息恢复
- `docs\STAGE48_AGENT_TOOL_DEGRADATION.md`：工具失败安全归一化、部分上下文回答和写工具依赖门禁
- `docs\STAGE49_AGENT_RECOVERY_UI.md`：Agent 显式重试、输入恢复和保留计划草稿的精确加载
- `docs\STAGE50_LOCAL_RUNTIME_SMOKE.md`：本地后端/前端入口和构建资源的只读运行态检查
- `docs\STAGE51_REPRODUCTION_DEMO_RUNBOOK.md`：干净环境复现前置清单、15 分钟演示顺序和面试追问速答
- `docs\STAGE52_SYNTHETIC_DEMO_REHEARSAL.md`：合成数据主链彩排、浏览器人工操作顺序和面试讲解卡
- `docs\STAGE53_BROWSER_REHEARSAL_PREP.md`：浏览器彩排前置检查、账号边界和页面操作卡
- `docs\STAGE54_FINAL_DELIVERY_PREFLIGHT.md`：最终交付证据、公开边界和待人工门禁的只读清单
- `docs\STAGE55_INTERVIEW_DEFENSE_PACK.md`：AI Agent 岗位深度追问、证据组织和诚实边界
- `docs\STAGE56_RESUME_PROJECT_ENTRY.md`：简历技术版/精简版、工程证据对照、面试口述和不应夸大的表述
- `docs\STAGE57_SYNTHETIC_BROWSER_DEMO_SEED.md`：合成浏览器演示账号、独立 SQLite 启动方式和安全边界
- `docs\STAGE58_AGENT_SMOKE_REDACTION.md`：真实 Agent smoke 的输出脱敏、回归边界和面试讲解
- `docs\STAGE59_REPOSITORY_ARTIFACT_IGNORES.md`：回归临时产物忽略规则、发布边界和复现检查
- `docs\STAGE60_ISOLATED_BROWSER_REHEARSAL.md`：隔离合成数据库、后端端口、Vite API target 和浏览器人工彩排边界
- `docs\STAGE61_SYNTHETIC_DEMO_ENDPOINT_OUTPUT.md`：合成种子脚本端点输出、启动提示和人工彩排边界
- `docs\STAGE62_ISOLATED_RUNTIME_SMOKE.md`：隔离合成环境的实际运行态冒烟、端口占用处理和验证证据
- `docs\STAGE63_PORT_VALIDATION_BEFORE_SEED.md`：端口参数值域校验、无副作用失败顺序和回归边界
- `docs\STAGE64_SYNTHETIC_BROWSER_ENTRY_CHECK.md`：合成浏览器登录/注册入口检查、密码输入边界和前端认证标记
- `docs\STAGE65_AUTH_CLIENT_BOUNDARY.md`：统一 API client 的认证头、登录/注册请求和源码证据边界
- `docs\STAGE66_AUTH_STATE_LIFECYCLE.md`：认证状态读取、保存、失效清除、退出登录和 localStorage 安全取舍
- `docs\STAGE67_AUTH_EXPIRY_RECOVERY.md`：401 认证过期事件、根组件状态回退和请求层/状态层解耦
- `docs\STAGE68_REVIEW_QUEUE_ENTRY.md`：画像 SM-2 到期项直达专项训练、topic/focus 参数和链路边界
- `docs\STAGE69_PROFILE_RECOVERY.md`：画像页加载错误、可观察重试和无副作用边界
- `docs\STAGE70_TOPIC_DRILL_RECOVERY.md`：专项训练初始加载失败、错误态、重试和卸载保护边界
- `docs\STAGE71_LOCAL_SEMANTIC_EMBEDDING.md`：本地 Sentence-Transformers 模型、离线加载、配置和显式重建索引
- docs\STAGE74_EMBEDDING_RETRIEVAL_EVAL.md：固定合成查询集上的 Embedding Recall@K、MRR 离线评估和本地模型质量边界
- docs\STAGE75_FRONTEND_TELEMETRY_REDESIGN.md：深色 Tactical Telemetry / CRT Terminal 应用壳层、首页主构图和全局视觉 token
- docs\STAGE76_FRONTEND_MINIMALIST_THEME.md：可持久化的 minimalist-ui 浅色主题、主题切换入口和双主题视觉边界
- docs\STAGE77_TECHSPAR_INFORMED_PRODUCT_UX.md：参考 TechSpar 的工作台导航、训练模式选择、响应式侧栏和一主操作首页
- docs\STAGE79_LIGHT_PRODUCT_WORKSPACE.md：浅色产品化工作台、统一 UI 状态组件、首页/画像/Agent 核心路径迁移和人工验收边界
- docs\STAGE80_PERSONAL_DOCUMENT_FILE_IMPORT.md：PDF 文本层解析、Markdown UTF-8 文件导入、统一分块索引和扫描件边界
- docs\STAGE82_TECHSPAR_FRONTEND_MIGRATION.md：以 TechSpar 为活动前端基线、QTrace API 适配、许可归属和迁移验证
- docs\STAGE83_VITE_DEV_RENDER_RECOVERY.md：Vite 8 开发客户端黑屏定位、注入关闭和 5174 浏览器渲染验证
- docs\STAGE84_DIRECT_LOGIN_ENTRY.md：移除启动动画、认证状态直达登录/画像和入口防回归预检
- docs\QTRACE_ENGINEERING_NOTE.md：项目架构、Agent/RAG/Embedding/SM-2 链路、验证证据和面试讲解主线
- docs\STAGE95_TENCENT_VPS_PUBLIC_DEMO.md：独立腾讯云 VPS 部署、镜像源覆盖、真实公网 IP/安全组和外部浏览器验收门禁
- docs\STAGE96_TENCENT_VPS_BROWSER_ACCEPTANCE.md：`49.232.104.202` 公网 IP、TCP 80 入口、Compose healthy 和外部浏览器登录页验收记录
- docs\STAGE97_ONBOARDING_SKIP.md：保留模型配置表单，同时支持按账号暂时跳过并稍后到设置页补齐
- 当前 Demo：`http://49.232.104.202/`；这是 HTTP 面试演示入口，不等同于域名/HTTPS/高可用生产服务。更新代码时先 `git pull --ff-only`，再使用服务器本地 `deploy/demo.env` 重建。
