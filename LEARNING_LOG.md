# 重建学习日志

## 目标

通过逐阶段实现一个独立版本，达到能运行、能读代码、能解释设计取舍、能应对面试追问的程度。

## 日志模板

每个阶段完成后补充：

```markdown
### 阶段 N：标题

- 日期：
- 我实现了：
- 入口和调用链：
- 关键数据结构：
- 运行命令：
- 测试结果：
- 我现在能回答：
- 仍然不懂/下一步：
```

## 阶段 1：项目边界与参考代码地图

- 日期：2026-08-20
- 我实现了：冻结参考副本的阅读边界和完整代码地图；确认参考项目包含 React/Vite 前端、FastAPI 后端、五类训练/辅助入口、长期记忆和多种实时/异步协议。
- 运行证据：参考前端 `npm test`、`npm run typecheck`、`npm run build` 通过；`npm run lint` 0 errors；本地合成账号可完成首页 -> 登录 -> ProviderGate。
- 尚未声称：没有真实模型 key，因此没有把 LLM、Embedding、ASR、搜索或实时 Copilot 说成已经验收。
- 下一步：在本目录建立自己的阶段 1 骨架，不复制参考实现。

## 阶段 2：自主实现第一条竖切片

- 日期：2026-08-20
- 我实现了：独立的 FastAPI + React/Vite 工程，包含本地账户、签名 token、密码哈希、provider 配置门禁、SQLite 会话、显式面试阶段状态机、stub provider、复盘和画像写回。
- 后端模块：`backend/security.py`、`backend/store.py`、`backend/provider.py`、`backend/interview.py`、`backend/main.py`。
- 前端模块：`frontend/src/api.ts`、`frontend/src/App.tsx`、`frontend/src/styles.css`。
- 自动化结果：后端 `2 passed`；前端 `npm run typecheck` 通过；`npm run build` 通过。
- 浏览器结果：合成账号完成注册 -> ProviderGate -> 启用 stub -> 开始模拟面试 -> 提交回答 -> 提前结束 -> 复盘 -> 画像；工作台实际运行在本地 `5174`，后端在本地 `8002`。
- 安全验证：两个账户读取对方 session 返回 404；会话查询使用 `session_id + user_id`。
- 我现在能回答：为什么需要 provider 门禁、为什么状态机要显式维护 phase、如何替换 stub provider、复盘如何写回画像。
- 下一步：逐项对照参考项目，增加真正的 provider 接口契约、主题知识库、动态专项出题和历史上下文，而不是直接复制参考代码。

## 阶段 3：Provider 适配层与动态追问

- 日期：2026-08-20
- 我实现了：`InterviewProvider` 协议、会根据阶段内问题编号变化的 StubProvider、OpenAI-compatible Chat Completions 适配器、用户级模型配置接口和首次配置页的真实 LLM 表单。
- 关键链路：`PUT /api/settings` -> `Store.set_openai_provider` -> `engine_for(user_id)` -> `OpenAICompatibleProvider` -> `/chat/completions`。
- 自动化结果：后端 `5 passed`；其中 1 个测试使用 `httpx.MockTransport` 验证兼容接口和 JSON 复盘解析；前端 typecheck/build 通过。
- 安全边界：测试只使用合成 key；设置响应不返回 key 原文；没有调用真实外部模型。
- 当前限制：Embedding 仍是本地 demo 占位；真实模型连通性、超时/重试、流式 SSE 尚未验收。
- 修复的问题：StubProvider 在 technical/project 阶段的第二次追问不再返回相同固定话术。
- 下一步：接入 PDF 简历解析和用户简历上下文，再实现主题知识库与动态专项训练。

## 阶段 4：PDF 简历上传、解析与上下文注入

- 日期：2026-08-20
- 我实现了：用户隔离的 PDF 保存目录、`multipart/form-data` 上传、`pypdf` 文本提取、简历状态/下载/删除接口，以及启动面试时的自动上下文注入。
- 关键链路：`Dashboard` 选择 PDF -> `uploadResume` -> `POST /api/resume/upload` -> `backend.resume.save_resume` -> `pypdf` -> `POST /api/interview/start` 读取文本 -> `InterviewEngine`/Provider。
- 安全边界：只测试合成 PDF；限制 20 MB；拒绝路径型文件名和非 PDF；新文件解析成功后才替换旧文件；没有上传真实简历或调用真实 LLM。
- 自动化结果：后端 `8 passed`；覆盖上传、解析、下载、删除、启动注入和非法文件名；前端 `npm run typecheck`、`npm run build` 通过。
- 我现在能回答：为什么要区分 `FormData` 和 JSON、为什么简历直接作为上下文而不是立刻向量化、为什么需要先解析再替换旧文件、文本输入如何作为 PDF 失败时的降级路径。
- 当前限制：扫描型 PDF 可能提取不到文本；真实系统还需要病毒扫描、加密、配额、保留期限和日志脱敏。
- 下一步：对照参考项目实现主题知识库与专项训练，把“简历上下文”和“知识检索上下文”接到同一个可解释的 prompt 组装层。

## 阶段 5：主题知识库与专项训练

- 日期：2026-08-20
- 我实现了：用户隔离的训练领域、核心知识 Markdown、高频题库 CRUD；领域内容的段落切分和关键词检索；`topic_drill` 启动、出题、追问和复盘；前端专项训练选择页和知识库编辑器。
- 关键链路：`/api/topics` -> `/api/knowledge/{topic}/core` 与 `high_freq` -> `get_topic_bundle` -> `InterviewEngine.start(mode="topic_drill")` -> Provider 使用知识上下文和题库。
- 设计取舍：小语料直接返回全文，大语料使用 top-k 关键词检索；先做可解释的本地检索，保留向量检索替换边界，没有把当前实现夸大成完整生产 RAG。
- 持久化：session 保存 mode、topic、知识上下文和题库快照，保证一轮训练内容稳定、历史记录可解释；旧 Stage 1 数据库通过 sessions 表迁移继续可用。
- 自动化结果：后端 `9 passed`；前端 typecheck/build 通过；测试只使用临时目录和合成知识内容。
- 我现在能回答：为什么要区分简历上下文与领域知识、为什么不是随机题库、关键词检索如何替换成向量检索、为什么要保存训练快照、如何做用户目录和文件名安全校验。
- 当前限制：没有 Embedding、混合检索、重排和知识效果评估；预置领域是面向学习的精简样例，不是参考项目全部领域。
- 下一步：补充专项训练的历史/掌握度视图，并把复盘结果按 topic 写回画像，为后续间隔复习和图谱功能准备数据。

## 项目命名：问迹 / QTrace

- 日期：2026-08-21
- 决定：将独立重建项目正式命名为 `QTrace`，中文名为“问迹”；GitHub 仓库名称暂定为 `qtrace-interview`，目前尚未创建或推送。
- 命名意象：“问”代表面试中的持续提问与追问，“迹”代表把回答、复盘、掌握度和画像变化留下可追踪的成长轨迹。
- 边界：工程目录仍保持 `rebuild`，以兼容当前本地启动命令；界面标题、后端应用名、README、Agent 提示词和前端包名已统一为问迹 QTrace。

## 阶段 6：专项掌握度与长期画像

- 日期：2026-08-20
- 我实现了：`topic_profiles` SQLite 表、按领域累计掌握度、最近得分、薄弱点、专项历史接口和画像页进度条。
- 关键链路：首次 `finish` -> `Store.update_profile_after_review(topic=...)` -> 全局 profile + topic profile 双写 -> `/api/profile` 和画像页展示。
- 幂等性：只有第一次生成 review 才写回，重复打开或重复请求不会重复增加训练次数。
- 自动化结果：后端 `9 passed`；前端 typecheck/build 通过。
- 我现在能回答：为什么要区分全局画像和领域画像、为什么写回必须幂等、平均分为什么只是训练指标、如何进一步替换成难度/时间衰减/间隔复习算法。
- 当前限制：掌握度仍是透明的累计平均分，不等同于真实能力评估；还没有 SM-2 调度、题目难度校准和离线评估集。
- 下一步：实现“今天该练什么”的简单复习调度，之后再考虑参考项目中的更复杂记忆和图谱功能。

## 阶段 6（续）：间隔复习与今日训练队列

- 日期：2026-08-20
- 我实现了：独立的 `review_schedule.py`、`review_items` 调度表、到期复习接口、画像页今日队列，以及专项训练优先复习到期薄弱点。
- 关键链路：`finish` 首次写回 -> `weak_points` 建立或更新 `review_items` -> `/api/profile` 返回 `due_reviews` -> `topic_drill` 将到期项排到题库前面。
- 调度规则：新薄弱点立即到期；成功回忆按 1 天、3 天和 ease factor 延长；低于 6 分则重置到明天。
- 自动化结果：后端 `10 passed`；前端 typecheck/build 通过；测试使用固定日期和临时 SQLite，不修改真实数据。
- 我现在能回答：掌握度和复习排期为什么要拆表、SM-2 的最小状态有哪些、为什么新弱点立即复习、失败为什么重置、为什么调度器应该是纯模块。
- 当前限制：薄弱点使用文本精确匹配，分数还没有经过盲评校准；没有 embedding 去重和知识点图谱。
- 下一步：实现 JD 导入和岗位定向训练，把岗位要求、简历上下文、专项知识和今日队列合成训练计划。

## 阶段 7：JD 导入与岗位定向训练

- 日期：2026-08-20
- 我实现了：`backend/jd.py` 本地 JD 分析器、岗位 preview/start 接口、JD 定向训练页，以及公司、岗位、JD 和分析快照的会话持久化。
- 关键链路：`POST /api/job-prep/preview` -> `analyze_jd` -> `focus_areas / resume_alignment / question_blueprint` -> `POST /api/job-prep/start` -> `InterviewEngine(mode="jd_prep")`。
- 数据组合：JD 分析上下文 + 可选简历文本 + 全局待复习项 + 岗位问题蓝图 -> Provider；对话推进仍复用原有状态机。
- 自动化结果：后端 `11 passed`；前端 typecheck/build 通过；测试使用合成 JD 和临时 SQLite。
- 我现在能回答：为什么先拆 JD 再训练、规则分析器和 LLM 分析器的替换边界、为什么 JD 定向复用状态机、为什么保存 JD 快照、岗位定向和专项训练的上下文差异。
- 当前限制：关键词分析不能理解复杂语义；没有独立的 JD 逐题批量评估页面；真实 LLM preview 尚未接入。
- 下一步：接入真实 LLM 的结构化 JD 分析，并保留规则版作为可测试降级路径；随后实现录音转写复盘。

## 阶段 8：文本优先的录音转写复盘

- 日期：2026-08-20
- 我实现了：`backend/recording.py` 转写解析器和复盘分析器；前端录音复盘页；双人/个人模式；录音会话原文、元信息和复盘结果持久化；结果写回全局画像和复习队列。
- 关键链路：`录音复盘页` -> `POST /api/recording/analyze` -> `parse_transcript` -> `analyze_transcript` -> `sessions` 快照 -> `update_profile_after_review`。
- 设计取舍：当前先实现人工粘贴转写，不接麦克风、ASR 或真实 LLM。双人模式只相信明确的说话人标签，不根据换行臆造问答边界；个人模式把全文视为回答片段。
- 可替换边界：未来使用 `AudioSource -> ASRProvider -> TranscriptDocument -> RecordingAnalyzer -> Review`。ASR 和真实 LLM 都应该是适配器，规则版保留为可测试 fallback。
- 自动化结果：后端 `12 passed`；前端 typecheck/build 通过。
- 我现在能回答：为什么先做文本优先、为什么不能简单按换行切分、录音复盘如何复用统一 Review 和画像、ASR 和复盘分析的接口边界在哪里。
- 当前范围：以转写文本为输入；真实长音频、说话人分离和时间戳对齐不纳入交付目标。评分是可解释的启发式规则。
- 下一步：补充分析器适配层，保留 ASR 作为可选边界，不扩展音频处理复杂度。

## 阶段 9：ASR 与结构化复盘适配层

- 日期：2026-08-21
- 我实现了：`ASRProvider` 协议、`TextPassthroughASRProvider` 本地 mock、`RecordingAnalyzer` 协议、规则分析器和结构化 `LLMRecordingAnalyzer`；录音复盘页增加分析器选择和本地 TXT 导入。
- 关键链路：`analysis_mode=rules` -> `RuleBasedRecordingAnalyzer`；`analysis_mode=llm` -> 用户级 OpenAI-compatible Provider -> `structured_chat` -> JSON 解析/字段归一化 -> 统一 Review。
- 安全边界：LLM 模式必须显式选择且必须配置真实模型；规则版不需要网络；TXT 文件只在浏览器本地读取；测试使用 fake provider 和合成 key，不调用外部服务。
- 设计取舍：路由只负责鉴权和编排，Provider 负责 HTTP，Analyzer 负责业务 JSON；LLM 不能直接把任意自然语言写入画像，后端先校验和限制分数范围。
- 自动化结果：后端 `14 passed`；前端 typecheck/build 通过。
- 我现在能回答：为什么 ASR 和复盘要解耦、为什么需要规则 fallback、为什么 LLM 输出必须结构化校验、为什么真实模型失败时当前不自动降级。
- 范围决策：`TextPassthroughASRProvider` 只用于验证转写来源边界；真实长音频、说话人分离和时间戳对齐明确移出交付范围，真实 LLM 只通过 fake provider 验证契约。
- 下一步：实现 Copilot 的 JSON/SSE 事件协议，再评估是否需要文本版 WebSocket。

## 阶段 10：Copilot 文本 Prep 与 JSON/SSE 事件协议

- 日期：2026-08-21
- 我实现了：`backend/copilot.py` 文本 Prep 逻辑、`copilot_preps` 持久化表、Copilot Prep 查询接口、SSE 事件流和前端 Copilot 页面。
- 关键链路：Copilot 页面提交 JD -> `POST /api/copilot/stream` -> `started` -> `jd_analyzed` -> `risk_assessed` -> `strategy_ready` -> `completed` -> SQLite 保存结果。
- 结果结构：岗位重点、简历匹配、追问策略树、风险地图、面试前行动和问题蓝图；复用已有 JD 分析器、简历文本和全局画像。
- 设计取舍：先实现文本 Prep 和单向 SSE，验证事件协议与持久化；没有把 WebSocket、多 Agent 并行一次性混进来。真实长音频、说话人分离和时间戳继续不属于交付范围。
- 自动化结果：后端 `15 passed`；前端 typecheck/build 通过。
- 我现在能回答：Copilot Prep 与 JD 定向训练的区别、为什么 SSE 适合进度事件、为什么最终结果仍要落库、WebSocket 何时比 SSE 更合适。
- 当前限制：Prep 使用本地确定性分析，没有公司联网搜索、真实 LLM 多 Agent 和 WebSocket 双向实时辅助。
- 下一步：把 Prep 结果与已有训练入口联动，再决定是否实现文本版 WebSocket 实时建议。

## 阶段 11：核心前端闭环整合

- 日期：2026-08-21
- 我实现了：Copilot Prep 历史列表和恢复；Copilot 结果到 JD 定向训练的跨页上下文交接；Dashboard、Copilot、JD 定向、画像之间的下一步入口。
- 关键链路：`GET /api/copilot/prep` -> 恢复公司/岗位/JD 快照 -> `sessionStorage` 交接 -> `/job-prep` 自动填充 -> 重新 preview -> `InterviewEngine(mode="jd_prep")`。
- 设计取舍：Copilot Prep 继续使用独立 `copilot_preps` 表，不混入普通训练 History，因为它不是一场完成的问答会话；跨页只传递明确上下文，进入 JD 页面后立即清理临时数据。
- 自动化结果：后端 `15 passed`；前端 typecheck/build 通过。
- 我现在能回答：为什么使用 sessionStorage、为什么跳转后仍需重新分析 JD、为什么 Copilot Prep 和普通训练 History 分表、如何避免页面之间耦合内部状态。
- 当前边界：核心闭环已连通，但 Personal Agent、知识图谱、完整简历编辑器和 WebSocket 实时辅助仍未完成。
- 下一步：为了匹配 AI Agent 岗位目标，先实现文本 Personal Agent，再做发布前收口。

## 阶段 12：Personal Agent v1

- 日期：2026-08-21
- 我实现了：文本 Personal Agent 页面；用户级 Agent 对话表；画像、SM-2 到期队列、近期训练和简历四个只读工具；规划/回答两步模型边界；Stub 和 OpenAI-compatible 两种模式；对话历史恢复和工具轨迹展示。
- 关键链路：`Agent 页面` -> `POST /api/agent/chat` -> `AgentModel.plan` -> 白名单工具执行 -> `AgentModel.answer` -> `agent_conversations` 持久化。
- Agent 的边界：模型只能提出工具规划，后端负责校验并执行工具；第一版工具没有任何写操作，不会自动修改画像、创建训练或删除数据。
- 个性化上下文：Agent 可以读取长期画像、领域掌握度、SM-2 今日队列、最近训练复盘和上传简历，因此回答不再只依赖当前一句用户问题。
- 真实 LLM 接口：OpenAI-compatible 模式执行两次结构化 Chat Completions，第一次输出规划 JSON，第二次根据工具结果生成回答；本地 Stub 模式不访问网络。
- 自动化结果：后端 `18 passed`；Python compileall、前端 typecheck 和生产构建通过；本地联调成功返回 `plan + tool_trace + answer`，并能恢复对话历史。
- 我现在能回答：普通 LLM 调用和 Agent 的区别、为什么需要工具白名单、为什么 Agent 工具先做只读、如何实现用户数据隔离、规划失败和工具失败如何处理。
- 当前限制：仍是单 Agent 文本版，没有文档向量检索、自动写回长期画像、多 Agent 并行、任务创建工具和 WebSocket 实时辅助。
- 下一步：用本地模型设置接入一次真实 LLM；然后升级专项训练的 LLM 个性化出题和画像结构化抽取。

## 阶段 13：个性化动态出题与画像 v1

- 日期：2026-08-21
- 我实现了：`backend/personalized_drill.py` 出题适配层；Stub 和 OpenAI-compatible LLM 两种出题器；专项训练启动时读取全局画像、领域画像、近期训练、SM-2 到期项和知识上下文；复盘新增强项、行为信号、行动项、最近得分序列和领域趋势写回。
- 关键链路：`POST /api/interview/start(topic_drill)` -> `get_topic_bundle` -> `Store.get_profile/get_topic_profile/list_due_reviews` -> `DrillQuestionGenerator.generate` -> JSON 归一化 -> `InterviewEngine`；结束时 `Review` 写回 `profiles`、`topic_profiles` 和 `review_items`。
- 设计取舍：LLM 只负责生成结构化题目计划，后端负责白名单式字段校验和数量/难度限制；状态机仍由 `InterviewEngine` 统一推进；Stub 仍然优先到期复习项，保证离线可运行和可测试。
- 数据迁移：已有 SQLite 通过 `_migrate_profiles` 增加画像字段和领域得分序列，不删除旧数据库；复盘写回保留幂等性。
- 自动化结果：后端 `23 passed`；Python compileall、前端 typecheck 和生产构建通过；本地黑盒验证确认专项训练可运行、画像新字段可返回、领域趋势初始为 `new`。
- 我现在能回答：个性化出题读取哪些信号、SM-2 如何影响题目优先级、为什么题目生成器和状态机要解耦、LLM JSON 失败如何处理、为什么得分趋势不是完整能力评估。
- 当前限制：还没有使用真实 API Key 做动态出题联调；趋势只是可解释的相邻分数规则；没有知识图谱、Embedding 去重、题目难度校准和 Agent 写工具。
- 下一步：配置用户自己的兼容模型完成真实 LLM 联调，再做发布收口和面试讲解材料；GitHub 创建、提交和推送仍需单独确认。

## 真实 LLM 联调记录

- 日期：2026-08-21
- 用户已明确同意使用当前账号的画像、SM-2 复习项、近期训练和知识上下文进行真实联调。
- Provider 连通性：OpenAI-compatible 请求成功返回合法 JSON，未输出 API Key。
- Personal Agent：`POST /api/agent/chat` 返回 200；完成规划调用、只读工具执行和回答生成，返回非空回答与工具轨迹。
- 动态专项训练：`topic_drill` 启动返回 200；真实 LLM 生成开场和一次追问，追问接口返回 200 且内容非空。
- 结构化复盘：`POST /api/recording/analyze` 的 LLM 模式返回 200；摘要、浮点评分和 4 条行动项成功解析，并生成复盘会话。
- 数据边界：联调使用了当前账号的画像上下文和合成两问两答文本，但没有上传真实简历文件。
- 当前判断：真实 LLM 已经可以被 QTrace 的 Provider、Personal Agent、专项训练和结构化复盘业务链路调用，不再只是底层连通性测试。

## 阶段 14：真实 LLM 稳定性收口

- 日期：2026-08-21
- 我实现了：`OpenAICompatibleProvider` 的超时/网络错误归一化、408/425/429/5xx 有界重试、指数退避和鉴权错误不重试。
- 关键取舍：重试放在 Provider 层，Agent、InterviewEngine 和 Analyzer 不复制基础设施逻辑；结构化 JSON 错误仍然直接校验，不用重试掩盖内容问题。
- 自动化结果：后端 `27 passed`；覆盖 503 重试成功、超时最终错误、网络错误归一化和 401 不重试；Python 内存编译 20 个文件通过；前端 typecheck/build 通过。
- 真实联调证据：阶段 13 的 Provider、Personal Agent、动态出题和结构化复盘均已成功，稳定性边界测试不消耗真实 API。
- 我现在能回答：为什么 Provider 是重试边界、哪些 HTTP 状态可以重试、为什么鉴权错误不能重试、如何避免错误日志泄露 API Key。
- 当前限制：还没有读取供应商的 `Retry-After`、熔断、配额观测和前端细粒度重试按钮。
- 下一步：评估 Agent 写工具和用户确认机制；GitHub 创建、提交和推送仍需单独确认。
