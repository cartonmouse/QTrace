# 问迹 QTrace：从空目录自主复现

<p align="center"><img src="frontend/public/qtrace-icon.png" alt="问迹 QTrace 图标" width="160" /></p>

这是学习用的独立重建工程，目标不是给上游项目打补丁，而是通过自己的代码逐步实现参考项目的核心用户体验和主要功能。

## 名称

项目名为“问迹 QTrace”。“问”代表面试中的持续提问与追问，“迹”代表把回答、复盘、掌握度和画像变化留下可追踪的成长轨迹。项目会把一次次练习沉淀为知识、历史记录和能力画像，而不是把每轮面试当成彼此无关的一次问答。GitHub 仓库名称暂定为 `qtrace-interview`，目前尚未创建或推送。

## 快速启动

以下命令在 Windows PowerShell 中执行，需要两个终端分别启动后端和前端。路径中的 `<project>` 替换为本地工程目录；当前学习环境的独立工程位于 `D:\3BUPT\mark'workshop\techsnowsong\rebuild`。

后端终端：

```powershell
Set-Location -LiteralPath '<project>\rebuild'
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

前端终端：

```powershell
Set-Location -LiteralPath '<project>\rebuild\frontend'
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5174`。首次进入后注册本地账号，在“模型设置”中启用本地演示模型即可离线体验；使用真实 LLM 时再填写 OpenAI-compatible API Base、Model 和 API Key。API Key 只保存在本地 SQLite 设置表，不会由设置接口返回给前端。

如果 PowerShell 禁止激活虚拟环境，可以不激活，直接使用该环境中的 `python -m pip` 和 `python -m uvicorn`。前端开发服务器通过 Vite proxy 将 `/api` 请求转发到 `127.0.0.1:8002`。

## 验证命令

在 `rebuild` 目录执行：

```powershell
python -m pytest -q
python -m compileall -q backend tests
Set-Location frontend
npm run typecheck
npm run build
```

测试使用临时 SQLite、合成账号和 fake provider，不会调用真实模型。不要把真实简历、录音或 API Key 放入仓库；`.env`、`data/`、SQLite 文件、前端依赖和构建产物已加入 `.gitignore`。

## 学习边界

- 原项目只作为行为、页面、接口和架构参考：`..\reference`。
- 本目录不直接复制上游实现；每个模块先写“我理解的职责和接口”，再自己实现。
- 允许先用本地 deterministic stub provider 跑通流程，再接入兼容 OpenAI 的真实模型服务。
- 真实简历、真实录音、真实 API key 不进入仓库；测试只使用合成数据。
- 本项目不把真实长音频、说话人分离和时间戳对齐纳入交付范围；录音模块以转写文本和可替换边界为主。
- GitHub 仓库创建、提交和推送需要单独确认，目前不执行。

## 目标形态

采用与参考项目接近、但由本项目自行实现的技术栈：

- 前端：React + TypeScript + Vite + React Router
- 后端：FastAPI + Pydantic
- 存储：SQLite + 本地用户目录
- AI 边界：`ModelProvider` 接口，提供 `stub` 和 OpenAI-compatible 两种实现
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
- 简历模拟面试、专项训练、JD 定向训练和文本转写复盘；
- 领域知识 Markdown、关键词检索、领域画像和简化 SM-2；
- Copilot Prep 的策略树、风险地图、JSON/SSE 进度事件和历史恢复；
- Personal Agent v1 的规划、只读工具、长期画像上下文和对话记忆；
- 根据画像、领域趋势和到期复习项生成专项题目计划，并回写强项、行为信号和行动项。

明确未纳入当前交付范围：真实长音频、麦克风采集、说话人分离、时间戳对齐、知识图谱、Embedding/向量检索、完整多 Agent 并行 Copilot、WebSocket 实时辅助和 Agent 自动写操作。

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
