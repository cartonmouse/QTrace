# QTrace domain glossary

## User

登录 QTrace 的学习者。用户拥有自己的训练记录、能力画像、学习计划和个人文档；任何长期记忆都不能跨用户读取。

## Personal document

用户主动提供给个人 Agent 的一份可引用资料，例如项目说明、技术方案、复盘笔记或学习总结。个人文档属于用户的长期资料，不等同于一次训练消息。

## Document chunk

从个人文档中切出的、可以独立作为检索证据的一段内容。文档块保留所属文档和原始顺序，Agent 读取的是文档块而不是任意数据库记录。

## Personal memory

个人 Agent 可以读取的长期资料集合，包括用户画像、复习队列、训练历史、简历和个人文档。不同类型的记忆保留各自的来源和语义，不把它们混成一张无结构的聊天记录。

## Retrieval evidence

一次检索返回给 Agent 的有限文档片段。证据只用于回答当前问题；Agent 不能把“检索到”表述成“用户已经验证”，也不能凭空补齐文档中没有的事实。

## Embedding

把文本转换成可比较的数值表示，使系统可以按内容相似度找到相关文档块。Embedding 解决的是“从资料中找相关证据”，不负责生成答案，也不等同于 LLM。

## Document import

文档导入是把用户提供的文件转换成系统可处理文本的边界。当前 `document_import.py` 只负责 PDF 文件校验和本地文本层提取，不负责分块、向量化或 Agent 回答。这样简历上传和个人文档上传可以复用基础解析逻辑，同时保留各自的保存位置和业务上限。

## Extracted text

从 PDF 文本层提取出的规范化文本。它是后续分块和检索的输入，不代表 PDF 的原始二进制，也不包含 OCR 结果。扫描版 PDF 如果没有文本层，应明确报告不支持，而不是生成空的个人记忆。

## Document identity

用户个人文档的身份由规范化后的正文决定。同一用户再次提供相同正文时，它仍然指向同一份长期资料；标题和资料来源可以不同，但不会因此产生第二份相同记忆。不同用户的相同正文仍然属于不同的个人文档。

## Evidence citation

检索证据的可追踪标识，说明片段来自哪份个人文档以及文档中的哪一段。引用只描述证据来源，不代表系统已经验证了证据内容；Agent 需要保留已有引用，不能凭空创造来源。

当前格式为 `文档标题#vN-chunk-M (文档短 ID)`，其中 `vN` 是文档版本，`chunk-M` 是当前版本中的分块序号。默认检索只使用最新版本；历史版本需要用户主动查看。

## Document version

同一份个人文档的不可变正文快照。文档 ID 表示长期资料本身，版本号表示资料在某次编辑后的状态。正文指纹未变化时更新是幂等的；正文变化时写入下一个版本，旧版本保留用于复盘和审计。当前文档和历史快照分开存储，避免默认检索混入过期内容。

## Knowledge base vs personal document

主题知识库是面向训练领域维护的公共题目材料；个人文档是当前用户自己的项目和经历资料。前者帮助出题，后者帮助 Agent 引用个人证据。

## Structured resume profile

用户主动维护的字段化简历，当前包含个人概述、技能和项目经历。项目经历进一步拆分为项目名、职责、概述、技术栈和关键工作。它是每个用户唯一的核心身份资料，适合生成面试上下文；个人文档则是可有多份、可检索的详细证据。

## Interview context renderer

把结构化简历 JSON 确定性地渲染为 InterviewEngine、JD Prep、Copilot 和 Agent 都能消费的文本。渲染器只负责格式转换，不调用 LLM，也不创造用户没有填写的事实。上下文来源优先级为用户显式文本、已上传 PDF、结构化简历。

## Project question card

从一个结构化项目生成的可解释面试准备问题。当前固定覆盖背景与目标、个人职责、关键设计、效果验证和复盘取舍五类，并记录对应字段 `field_refs`。卡片本身是只读训练入口，不会自动修改简历、画像或学习计划。

卡片还包含 `training_focus`，用户可以从编辑器进入专项训练。后端只接受卡片 ID，再按当前用户的当前简历版本重新解析项目名和版本；训练会话保存 `question_card_id`、`question_card_project` 和 `question_card_resume_version`，用于面试、复盘和历史审计。

## Resume evidence mapping

用项目名称和问题类别作为查询，去个人文档库检索项目说明、技术方案或复盘笔记，并把返回的版本化 `citation` 绑定到追问卡。没有命中证据时保留问题但返回空证据，表示用户需要补充准备材料，而不是让系统编造事实。

## Training focus composition

专项训练的 `requested_focus` 可以同时包含三类来源：用户显式输入、项目追问卡和已确认学习计划项。后端用带来源标签的文本合并它们，再交给 Stub/LLM 出题器；领域画像、近期训练和 SM-2 到期队列作为独立上下文继续参与排序。焦点只是出题约束，不代表用户已经掌握，因此点击入口不会直接改变画像或复习间隔。

## Question card session audit

训练会话的来源元数据和 InterviewEngine 的状态机分离。`InterviewEngine` 只推进阶段、消息和复盘；路由负责验证卡片/计划的用户归属并组装上下文；Store 负责持久化来源。这样既能在复盘时解释“这次为什么练这个”，也不会把简历全文或个人文档证据复制进每个 session。

## Agent question-card plan

Personal Agent 可以接收一个显式 `question_card_id`。后端先按当前用户的当前结构化简历验证卡片，再强制加入 `read_question_card` 只读工具；如果用户明确请求计划，`create_learning_plan` 会把卡片项目、类别和简历版本写入 draft 的 `source` 与计划项。用户确认计划后，计划项再次进入专项训练时会把 `question_card_id` 传回 session，形成“卡片 -> Agent draft -> 确认 -> 训练 -> 复盘”的可追踪链路。

## JD project match

JD 定向分析在用户勾选简历联动且存在结构化项目时，使用 `SKILL_CATALOG` 的确定性别名匹配项目的 `description`、`role`、`technologies` 和 `highlights`。命中结果返回岗位 focus、项目名、命中技能、证据字段和代表性 `question_card_id`，前端可以把这张卡交给 Agent。关闭简历联动或只有没有文本层的 PDF 时返回空匹配，不根据 JD 猜项目事实。

项目匹配分数由 JD 技能出现次数、`focus_areas` 的 high/medium/normal 优先级和命中字段权重组成：`technologies=3`、`role/highlights=2`、`description=1`。分数用于排序和解释准备优先级，不代表录用概率或能力评分。

## Knowledge graph read model

知识图谱是按用户和训练主题即时生成的只读视图，不是新的事实存储。主题的 Markdown 知识、高频题库、`topic_profiles` 和 `review_items` 仍然是事实源；`backend/graph.py` 只把它们组合成主题根节点、问题节点、薄弱/待复习节点和关系边。当前关系算法使用确定性的 token 重叠，并为中文补充二元字符片段，因此结果可复现、容易测试，也明确不等同于 Embedding 语义相似度。

图谱页面的价值在于把“应该练什么”和“为什么要复习它”放到同一个可视化读模型中：问题之间的相近关系帮助理解题库结构，SM-2 到期点帮助解释训练优先级，关系明细则方便面试时追溯规则。打开图谱不会写入画像、复习队列或训练会话；未知主题和跨用户数据由后端边界拒绝。

## Graph topic scope

从图谱进入 Personal Agent 时，URL 中的主题 key 只是客户端上下文，后端会按当前用户的 `topics.json` 重新校验。校验通过后，Agent 的 `read_due_reviews` 只读取该主题的 SM-2 到期项，并把 `topic` 写入学习计划 `source`。它不会把图谱节点复制到计划表，也不会因为打开图谱就更新复习状态；用户确认计划并完成训练后，现有专项训练复盘链路才会更新画像和 SM-2。

## Graph question training source

图谱中的问题节点使用稳定的 `question:<n>` ID，但 ID 只是当前主题题库的可验证索引，不是用户可以任意提交的事实。专项训练启动时，后端按当前用户和主题重新读取题库，解析 `graph_question_id`，把得到的完整问题保存为 `graph_question`，并将它放到个性化候选题的首位。训练会话因此能解释“这次为什么从图谱进入”，同时仍由后续出题器处理画像、SM-2 和动态追问。旧会话没有该字段时按空值兼容。

## Graph question Agent plan

当用户从图谱问题进入 Agent 时，`read_graph_question` 是强制加入的只读工具。它按当前用户、主题和 `question:<n>` 重新解析题库事实；`create_learning_plan` 再把 `graph_question` 写入计划 source，把 `graph_question_id` 与快照文本写入计划项。计划项进入专项训练时继续提交节点 ID，由训练路由再次校验并写入 session。这样“图谱节点 -> Agent 计划 -> 训练 session”保留同一来源，但没有把图关系复制成新的事实表。

图谱节点的 `related_question_ids` 只从当前响应中的 `related` 边派生。Agent 读取工具会把最多三个相近问题作为 `related_questions` 返回，计划只保存它们作为可选元数据；前端需要用户明确点击后才进入相近题训练或再次交给 Agent，不会因为边存在就自动扩大计划范围。

## Graph candidate feedback audit

从相近问题候选进入专项训练时，session 保存 `graph_entry_source=related_neighbor`、父问题节点 ID 和父问题文本快照；直接点击图谱问题则使用 `question_node`。后端会重新构建当前用户当前主题的图谱，确认父节点确实通过 `related` 边连接到目标节点，不能信任前端传来的父问题文本。图谱 related link 可以从当前用户当前主题的 session 事实源重建 `started_count` 和 `completed_count`，但这些次数只是行为反馈，不是掌握度、边权或 SM-2 参数；用户通过 Agent 计划进入训练时也会沿用同一来源元数据。

## Graph candidate feedback evaluation

`GET /api/graph/{topic}/feedback` 是候选行为的只读评估报告。它只聚合当前用户、当前主题、`related_neighbor` session，并把仍存在于当前图谱的 related 边作为报告边界。指标包括入口完成率、有效复盘 `average_score`、按时间排序的首末 `score_delta` 和重复训练 `repeat_rate`；没有有效复盘分数时不伪造 0 分。报告是描述性统计，不是 A/B 实验或因果结论，也不改写 related 权重、画像、SM-2 或计划。

## Agent graph feedback context

`read_graph_question` 返回的每个 `related_questions` 候选还带有 `started_count`、`completed_count` 和 `completion_rate`。这些字段来自同一条 related link 的 session 审计，Agent 可以用来解释“候选是否被练过”，但不能把行为次数说成掌握度或重要性；`create_learning_plan` 只保存元数据，不因为候选反馈自动新增计划项。

## Repository preflight

公开仓库发布前的静态护栏位于 `scripts/repository_preflight.py`。它检查核心入口是否存在、文本中是否出现明显密钥痕迹、工作区中是否有本地 `.env`/数据库/日志等产物，并提示当前 Git 变更。它是只读的发布前检查，不是 CI，不负责依赖安装、外部服务连通性或干净环境复现；真实资料、API Key 和推送操作仍然在工程边界之外。

## External embedding adapter

`backend/embedding.py` 提供 `EmbeddingProvider` 协议、默认的 `DeterministicEmbeddingProvider` 和可替换的 `OpenAICompatibleEmbeddingProvider`。外部实现只负责 `/embeddings` 请求、Bearer 鉴权、JSON/数字向量/维度校验和有界重试；`PersonalDocumentService` 只接收向量，不知道 HTTP 细节。用户级设置保存在 `settings` 表中，文档请求按用户动态构造 Provider；检索先按 `embedding_mode` 隔离，切换外部模型后只有显式 `POST /api/agent/documents/reindex` 才重建当前文档索引，不创建新版本，也不会自动外发旧资料。

## Embedding smoke gate

真实 Embedding 联调前先运行 `scripts/embedding_smoke.py`。它用 SQLite read-only URI 读取指定用户的 Embedding mode、Base、Model、模型目录和 Key 是否存在；demo 或不完整配置直接返回 `NOT_CONFIGURED`，不构造外部 Provider、不读取个人文档、不发网络请求。`local-model` 模式只用固定合成句调用本地 Provider，输出维度、耗时和 `network=disabled`，不会联网；只有显式配置完整的 `openai-compatible` 模式才会把固定合成句发送到 `/embeddings`，输出 host、model、维度和延迟，不输出密钥或向量内容。聊天模型可用不代表同一 endpoint 支持 Embedding，因此两套 Provider 配置不能混用。

## Local semantic embedding

`LocalSentenceTransformerEmbeddingProvider` 是本地确定性 baseline 之外的可选语义模型 Provider。它懒加载 `sentence_transformers.SentenceTransformer`，只接受用户在本机设置页填写的模型目录，并始终传入 `local_files_only=True`；这样“模型缺失”会变成可观察的配置/Provider 错误，而不是后台偷偷联网下载。基础 `requirements.txt` 不安装重量级模型依赖，实际需要时再安装 `requirements-local-embedding.txt`。

本地模型路径单独保存在 `settings.embedding_model_path`，不与远程 API Base、Model 或 API Key 混用。切换到 `local-model` 后，已有文档仍保留旧的 `embedding_mode`，搜索会先过滤旧索引；用户点击 `POST /api/agent/documents/reindex` 后才使用新模型重建当前版本的 chunks。这使模型切换可解释，也避免不同维度向量在同一次检索中混算。

## Real Agent smoke

真实 LLM/Agent 联调前运行 `scripts/agent_llm_smoke.py`。它通过 SQLite read-only URI 读取指定用户的聊天 Provider 配置；非 `openai` 或配置不完整时直接返回 `NOT_CONFIGURED`，不会联网。配置完整时只用固定合成画像、到期复习项和空训练历史执行两次调用：`plan` 返回 JSON 后经过 `AGENT_TOOLS` 白名单归一化，`answer` 再接收合成工具上下文生成回答。脚本只输出 host、model、工具名、耗时和回答长度，不输出 Key、完整回答或个人资料；它验证的是模型/Agent 契约，不替代真实用户数据和前端持久化验收。

## Agent error contract

`run_personal_agent` 在模型规划和回答边界把 `ProviderError` 包装为 `AgentProviderError(stage)`. Agent API 对这两类失败返回稳定的 502 detail：`agent_planning_failed` 或 `agent_answering_failed`，并带 `stage`、面向用户的 `message` 和 `retryable`。模型初始化失败使用 `agent_provider_error`/`initialization`。底层供应商异常不直接回传；工具执行失败仍作为 `tool_trace.status=failed` 记录，回答模型可以在剩余上下文上继续。前端 `ApiError` 会解析对象型 detail 的 message，Agent 页面展示可理解的失败提示。

## Agent failure consistency

Agent 的失败状态需要区分“请求没有产生业务结果”和“请求已经产生可确认的草稿”。新建对话在规划/回答失败时，只有在消息为空、没有关联学习计划且属于当前用户时，才允许通过 `delete_empty_agent_conversation` 清理空壳；已有对话返回 `conversation_unchanged`，已经写入学习计划草稿则返回 `preserved_draft`。API 将该状态放入错误 detail，前端移除未持久化的乐观用户消息并恢复输入文本。它是模型调用后的补偿策略，不把外部网络调用伪装成 SQLite 事务，也不删除文件或用户资料。

## Agent tool degradation

工具执行失败与模型规划/回答失败是两条不同边界。只读工具失败时，`_tool_failure_contract` 将内部异常归一化为 `dependency_unavailable`、`context_unavailable` 或 `execution_failed`，把稳定摘要写入 `tool_trace` 和 `tool_failures`，回答可以继续使用成功上下文，但不能把缺失值当成事实。`create_learning_plan` 需要 `read_profile`、`read_due_reviews` 和 `read_recent_sessions` 全部成功；任一依赖失败时只返回 `status=skipped`/`write_blocked_by_context`，不写入 draft。前端将失败或跳过工具显示为“已降级”，并说明回答基于其他成功读取的上下文；原始异常不进入 API、UI 或 LLM prompt。

## Agent recovery UI

前端 `submitMessage` 统一处理表单发送和显式重试：失败时移除乐观用户消息、恢复输入文本并保存 `retryMessage`，不自动重试。后端只有在 `preserved_draft` 状态下才把已验证的 `conversation_id` 放入错误 detail；前端加载草稿时按该 ID 和当前用户返回的 `status=draft` 过滤，避免跨对话误载入计划。成功、重试失败、草稿加载失败都通过可见的 `role=alert` 状态呈现，原有 draft/confirm 仍是计划进入执行状态的唯一入口。

## Local runtime smoke

`scripts/local_runtime_smoke.py` 是发布前和本地演示前的只读运行态门禁。它探测 `GET /api/health` 和前端入口是否返回 2xx，再读取 `frontend/dist/index.html`，确认其中引用的 `assets/` 文件都存在。脚本不读取 SQLite、个人文档或 API Key，不输出响应正文，不自动启动进程，也不调用外部网络；因此它不能替代浏览器端到端测试，只负责快速区分“服务没启动/构建资源不完整”和“业务代码行为失败”。

## Reproduction preflight and demo runbook

`scripts/reproduction_preflight.py` 是干净环境复现前的只读结构检查。它验证核心入口文件、前端 `dev/typecheck/build` 脚本和本地数据忽略规则，并只报告 Python/Node/npm 是否在 PATH 中；它不安装依赖、不启动服务、不读取 SQLite、个人文档或密钥。`docs/STAGE51_REPRODUCTION_DEMO_RUNBOOK.md` 将复现清单与面试演示分开：前者是项目完整后待执行的准备工作，后者以合成账号和 StubProvider 解释简历、图谱、SM-2、Agent 工具调用、draft/confirm 和失败恢复链路，避免把未验证的功能说成已完成。

## Synthetic demo rehearsal

`scripts/synthetic_demo_smoke.py` 是后端主链的合成彩排器。它创建唯一的临时 SQLite 路径，使用 `TestClient` 和 StubProvider 依次验证注册、结构化简历、个人文档、追问卡、知识图谱、Agent 计划草稿、用户确认和计划完成。它不读取正式数据库，不输出响应正文或资料内容，也不删除生成的临时数据库；它证明的是 API/状态链路可重复，不是浏览器 E2E 或真实模型质量。浏览器人工彩排和面试口述证据见 `docs/STAGE52_SYNTHETIC_DEMO_REHEARSAL.md`。

## Frontend route preflight

`scripts/frontend_route_preflight.py` 是浏览器人工彩排前的只读源码契约检查。它检查 `App.tsx` 中的主要业务路由、认证入口、认证状态生命周期、401 过期回退、画像待复习项到专项训练的入口、画像加载错误和重试入口、Agent 的重试/保留草稿/`role="alert"` 标记，`api.ts` 中的 `/api`、Bearer token、认证请求和过期事件边界，以及 `styles.css` 中的错误操作区和工具 trace 样式。它不打开浏览器、不读取 cookie/localStorage、不启动 HTTP、不读取数据库或个人资料；因此它只能证明前端入口、请求层/状态标记和关键样式仍在，不能证明密码提交、token 刷新、跨标签页同步、实际持久化安全、请求状态和视觉布局已经通过 E2E。账号状态和真实点击应由用户在合成数据边界下单独彩排。

## Final delivery preflight

`scripts/final_delivery_preflight.py` 是公开交付前的只读材料核对。它检查核心代码/脚本、阶段 40—59 文档和 README 中的测试/构建命令，并复用 repository preflight 的明显密钥模式检查；本地日志与数据库只作为数量警告，不删除它们。它不提交、推送、部署、安装依赖、读取 SQLite、读取个人文档或调用外部 API，也不把浏览器人工彩排、真实 LLM/Embedding 联调和全新目录复现视为完成。

## Interview defense pack

`docs/STAGE55_INTERVIEW_DEFENSE_PACK.md` 是面向 AI Agent 岗位的讲解和追问材料。它把架构、两步 Agent、工具白名单、RAG/个人文档、确定性图谱、SM-2、失败一致性、安全和评估组织为“设计 -> 证据 -> 限制”的回答；`scripts/interview_pack_preflight.py` 只检查关键章节存在，不判断模型质量，也不读取真实资料。回答中必须明确 SQLite、本地 StubProvider、尚未完成的浏览器 E2E/公开复现/部署等边界。

## Resume project entry

`docs/STAGE56_RESUME_PROJECT_ENTRY.md` 把简历项目描述、面试口述和工程证据矩阵放在一起。它明确 QTrace 是参考 TechSpar 方向的个人独立重建，不把项目说成官方复现；`scripts/resume_claims_preflight.py` 只检查技术版/精简版/证据/边界章节，以及 Agent、RAG、图谱/SM-2 和验证材料是否仍然存在。它不读取用户真实简历、个人文档或浏览器资料，也不判断项目效果是否达到生产标准；投递前仍应重新运行测试并由用户完成浏览器彩排和公开发布确认。

## Synthetic browser demo seed

`scripts/seed_synthetic_browser_demo.py` 只创建全新的合成 SQLite 数据库，使用 StubProvider 准备登录账号、结构化简历、五类项目追问卡、个人文档、RAG 高频题和图谱入口。默认路径是 OS 临时目录；显式 `--db` 也必须是不存在的新路径，目标文件或 SQLite sidecar 已存在时直接失败，不覆盖、不删除。脚本不读取现有数据库、个人资料、浏览器存储或 API Key，不联网，也不自动启动/登录浏览器。用户把输出的合成账号用于人工彩排时，还要通过 `REBUILD_DB_PATH` 和 `REBUILD_DATA_DIR` 让后端使用同一份新库；这只证明演示数据准备成功，不等同于浏览器 E2E 或真实模型验收。

## Agent smoke redaction

`scripts/agent_llm_smoke.py` 在读取配置后只使用合成上下文执行 plan/answer 两步真实模型契约；未配置时直接退出且不联网。阶段 58 在它的失败输出层对 API Key 和完整 API Base 做替换、换行压缩和长度限制，防止未来供应商异常文本越过 Provider 通用错误边界。它不打印完整回答、Key、个人资料或原始异常；回归测试用合成异常验证 `<redacted>` 输出。Embedding smoke 已有同等 `_redact` 保护，两者的网络调用仍必须经过显式配置门禁。

## Generated test artifact boundary

阶段回归会产生 `qtrace_stage*_pytest_tmp/`、`qtrace_stage*_formal_pytest_tmp/`、`qtrace_stage*_target_tmp/` 等临时目录。`.gitignore` 明确忽略它们，`scripts/reproduction_preflight.py` 也把主要模式作为配置契约检查；`repository_preflight.py` 仍只读报告本地产物，不删除它们。忽略规则只防止误提交，不允许把真实简历、个人文档或 API Key 放入这些目录，也不代表公开发布已经完成。

## Isolated synthetic browser rehearsal

阶段 60 的 `scripts/isolated_demo_preflight.py` 是浏览器人工彩排前的只读环境契约检查。它确认后端 `backend/config.py` 支持 `REBUILD_DB_PATH`/`REBUILD_DATA_DIR`，前端 Vite 支持 `REBUILD_API_TARGET`，并保留默认 `5174 -> 8002` 的本地开发路径；合成种子脚本仍使用全新 SQLite、`--db` 存在性门禁和 StubProvider。实际隔离彩排时可以把新库接到后端 `8003`，把前端启动在 `5175`，并将 `REBUILD_API_TARGET` 指向 `http://127.0.0.1:8003`，从端口和数据库两层避免误连日常实例。检查不创建数据库、不启动服务、不打开浏览器、不读取 cookie/localStorage、SQLite 或个人资料，也不调用外部 API；通过只证明源码契约存在，不能替代用户对登录、请求状态和视觉布局的人工验收。

## Synthetic demo endpoint output

阶段 61 的 `scripts/seed_synthetic_browser_demo.py` 在成功创建全新合成 SQLite 后，除了 `REBUILD_DB_PATH`/`REBUILD_DATA_DIR`、合成邮箱和密码，还输出推荐的 `BACKEND_URL=http://127.0.0.1:8003`、`FRONTEND_URL=http://127.0.0.1:5175` 和 `REBUILD_API_TARGET=http://127.0.0.1:8003`。这些是本地启动提示，不是外部服务凭据；脚本不会自动启动服务、打开浏览器或读取现有账号。回归用 fake seed 结果锁定输出契约，避免测试为了验证端点而创建不必要的数据库。端点输出仍不等于浏览器 E2E，实际页面请求和视觉布局需要人工彩排。

## Isolated runtime smoke

阶段 62 复用了 `scripts/local_runtime_smoke.py` 的可配置 `--backend-url`/`--frontend-url`，在全新合成 SQLite 上实际启动临时后端和前端，再检查健康接口、页面入口和 `frontend/dist` 资源。种子脚本的 `--backend-port`/`--frontend-port` 默认输出 `8003/5175`，端口冲突时可以显式改成空闲端口，例如 `8004/5177`；脚本不自动停止未知进程，运行态检查也不输出响应正文。阶段 62 已在 `8004/5177` 上通过，证明的是本机进程和 HTTP 入口连通，不是浏览器 E2E、真实模型质量或部署能力；生成的合成数据库不由自动任务删除。

## Seed argument side-effect order

阶段 63 的 `scripts/seed_synthetic_browser_demo.py` 先校验 `--backend-port`/`--frontend-port` 是否处于 `1—65535`，再调用 `seed_browser_demo` 创建 SQLite 和写入合成上下文。非法端口返回稳定失败状态，不创建文件、不注册账号、不写简历/个人文档/知识库，也不启动服务；测试用不可调用的 fake seed 锁定这一顺序。端口值合法不代表端口空闲，端口占用仍由启动前检查或用户人工处理，脚本不会杀掉未知进程。

## Synthetic browser auth entry

阶段 64 在隔离合成服务上实际观察到登录页和注册页的 DOM 入口，确认邮箱/密码字段、“进入学习工程”和“创建本地账户”按钮可以渲染；`scripts/frontend_route_preflight.py` 通过 `REQUIRED_AUTH_MARKERS` 把这两个认证入口纳入源码契约。自动任务没有输入密码、提交登录或读取 cookie/localStorage：浏览器策略把密码输入视为敏感操作，需要临时确认，因此本阶段证据只覆盖页面入口和注册视图，不覆盖 token、认证请求、后续业务页面或完整 E2E。

阶段 65 将 `frontend/src/api.ts` 的认证客户端边界纳入同一个只读预检：统一 `/api` 前缀、条件式 `Authorization: Bearer`、`/auth/${mode}` 登录/注册请求，以及 JSON 与 `FormData` 的请求头区别。新增回归验证认证客户端标记缺失时会失败；这仍然只是源码和测试证据，不等于密码提交、token 持久化、过期刷新或真实浏览器 E2E。

阶段 66 将 `frontend/src/App.tsx` 的认证状态生命周期纳入只读预检：启动读取 token，认证成功后保存，账户校验失败和主动退出时清除，并在认证状态不完整时阻止业务路由渲染。新增回归验证状态标记缺失时会失败；当前 localStorage 只服务于本地学习项目，生产环境仍需评估 HttpOnly Cookie、刷新轮换、XSS/CSRF 防护和完整 E2E。

阶段 67 补充带 token 请求收到 401 时的统一回退：`apiFetch` 派发 `AUTH_EXPIRED_EVENT`，`App.tsx` 监听后复用 `clearAuthState()` 清理 token/user/settings，并利用认证门禁回到登录入口；新增回归验证事件客户端和状态监听标记。请求层仍抛出 `ApiError`，事件只负责状态一致性，不把它说成 token 刷新或生产级认证方案。

阶段 68 将画像页的 SM-2 到期项接到专项训练：`buildDueReviewPath` 保留复习点 `focus`，有领域时同时传递 `topic`，复用 `TopicDrillPage` 和后端的 `mode=topic_drill` 链路。新增回归验证画像待复习入口、参数构造和文案标记；后端仍负责主题校验、个性化出题和训练 session 审计。

阶段 69 为 `ProfilePage` 的 `/profile` 与 `/topics` 并行加载增加错误状态和重试入口：失败时展示 `role="alert"` 错误卡，成功时继续显示画像、SM-2 队列和直达训练入口；重试只重新读取，不产生数据库副作用。新增回归验证画像恢复标记，不能把加载失败误报为空画像。

阶段 70 为 `TopicDrillPage` 的训练领域、SM-2 到期队列和可选图谱问题并行加载增加 loading/失败/成功三态：失败时清空当前读模型并展示 `role="alert"` 错误卡与“重新加载训练领域”入口，成功后仍按 URL 的 `topic`、领域名称和首个主题选择逻辑恢复上下文；重试只重新读取，不创建 session、不修改画像或复习队列。异步结果用 `active` 标记隔离卸载页面，前端源码预检和回归锁定恢复标记；后端开始训练时继续重新校验主题、计划、追问卡和图谱来源。

阶段 71 加入可选的本地语义 Embedding：后端 `local-model` Provider 使用懒加载的 Sentence-Transformers，并强制 `local_files_only=True`；设置接口和 SQLite 迁移新增独立的模型目录字段，前端“模型设置”增加“本地语义模型”入口，个人文档切换模式后仍必须显式重建索引。新增 `requirements-local-embedding.txt` 和合成 Smoke 路径；当前机器的 `E:\Anaconda` 已安装可选依赖，并使用本地缓存的 `shibing624/text2vec-base-chinese` 模型通过真实离线 Smoke（768 维、`network=disabled`），全新环境仍需单独安装依赖并填写模型目录。

## Settings feedback contract

阶段 72 的模型设置页是一个局部的操作面，不改变 LLM、Embedding、个人文档或 Agent 的后端协议。LLM 与 Embedding 分别维护 busy/message/error 状态，所以一次保存只锁定对应按钮，反馈只出现在对应面板；失败使用 `role="alert"`，成功使用 `role="status"`。`frontend/src/api.ts` 的 `formatApiErrorDetail` 将后端校验数组转换为字段位置和错误消息，但不打印请求体、API Key 或供应商原始凭据。

## Settings industrial Swiss-print surface

阶段 72 按浅色 Swiss Industrial Print 处理设置页：米白背景、碳黑边界、单一警示红、硬边 2px 分区、直角输入框和等宽技术标签。所有新样式限定在 `.settings-page`，不重写全局卡片，也不引入渐变、阴影、半透明层或新依赖；窄屏和 `prefers-reduced-motion` 通过局部媒体查询处理。界面同时给出两条验证路径：LLM 是“保存配置 => 个人 Agent => 合成问题 => 返回结果”，Embedding 是“保存目录 => 重建索引 => 个人文档库检索 => 查看证据”。

## Browser visual verification boundary

阶段 72 的本地浏览器自动化只能确认前端入口返回登录页，因为当前会话没有可复用的已登录标签。没有在浏览器中输入密码、创建账号或读取 localStorage，因此“登录后模型设置页视觉验收”仍然属于人工合成账号清单，不得把 typecheck/build 或源码契约误报为完整浏览器 E2E。

## Settings load recovery

阶段 73 为 `SettingsPage` 的 `/settings` 初始化请求补充 loading、failure、success 三态。请求失败时保留 `ApiError` 的安全 message，显示 `role="alert"` 错误卡和“重新读取模型设置”按钮；重试只递增 `loadKey` 并重新读取，不保存配置、创建索引或调用模型。请求用 `active` 标记忽略卸载后的旧响应，避免路由切换产生状态覆盖。`settings-load-card` 继续使用工业瑞士印刷的硬边和警示红。配置可读、配置保存、本地模型重建索引和检索命中仍是四层不同证据，不能互相替代。

## Synthetic embedding retrieval evaluation

scripts/embedding_eval.py 使用固定的四份合成技术文档、四个查询和人工相关文档 ID，比较 local-deterministic 与可选 local-model Provider 的 Recall@K、MRR 和向量维度。脚本不读取 SQLite、简历、个人文档或 API Key；只有显式传入已下载模型目录时才加载本地模型，且既有 Provider 强制 local_files_only=True。当前中文模型在合成集上输出 768 维，Recall@2=1.000、MRR=1.000；这只是小样本离线回归证据，不代表真实语料质量，也不替代显式重建索引和浏览器人工验收。

## Frontend Tactical Telemetry redesign

阶段 75 将前端从原先的浅色 Swiss-print 局部改造推进为完整的深色 Tactical Telemetry / CRT Terminal 视觉系统，目标是匹配参考图的战术终端气质，同时不改变既有路由、业务功能、API 契约和中文内容：

- `WorkspaceLayout` 统一加入深色侧栏、技术导航分组、顶部 command bar、底部状态栏和在线节点信号；首页保留原有训练表单，但改成左侧巨大展示型标题、右侧表单的非对称主构图；
- `frontend/src/styles.css` 增加统一的深色 token、碳黑底色、米白正文、单一黄色信号色、硬边网格、扫描线和低强度纹理；通过响应式媒体查询、焦点态和 reduced-motion 维持窄屏与可访问性；
- 旧页面组件继续复用，模型设置、知识库、画像、训练和 Agent 等功能不因视觉改造而改变；设置页的保存成功/失败、加载、重试和本地 Embedding 可观察性仍由既有状态逻辑负责；
- `frontend_route_preflight.py` 新增 telemetry shell、视觉 token、首页主构图和状态点标记，防止后续修改只保留旧壳层；
- 阶段 75 的证据为前端 typecheck/build、源码预检、相关回归测试、全量 pytest 和本地运行态 smoke 均通过；登录后的真实浏览器视觉仍需用户使用合成账号人工确认，不能用源码检查替代。

## Frontend minimalist-ui theme

阶段 76 在阶段 75 深色主题之上增加可持久化的 `minimalist-ui` 浅色主题。主题只改变前端视觉层，不复制页面、不改变路由、认证、LLM、Embedding、Agent、SM-2 或个人文档 API：

- `App.tsx` 增加 `Theme` 类型、`qtrace_theme` 本地键和 `ThemeToggle`；登录页、模型初始化页和工作区侧栏均可切换 `DARK/LIGHT`；
- 切换通过 `document.documentElement.dataset.theme` 驱动 CSS，选择只写入浏览器 `localStorage`，不写 SQLite、不发送后端请求；
- `styles.css` 在 `:root[data-theme="minimalist"]` 下提供暖白画布、白色面板、炭黑正文、细灰边界、中文衬线标题、系统无衬线正文和低饱和语义色；浅色主题明确隐藏深色主题的扫描线和终端网格；
- 首页、侧栏、表单、列表、状态反馈和模型设置页都有浅色覆盖规则，主题切换不是简单的背景色反转；
- `frontend_route_preflight.py` 新增主题选择契约，检查主题键、根节点属性、切换按钮、浅色根选择器和编辑感字体 token；
- 改造前白名单源码快照为 `qtrace-pre-minimalist-theme-20260822-142528.zip`，SHA256 为 `17144E47F053B909CEA18290B3F7417942B70195E770BE98759C55CE8BB59295`；
- 首页展示标题在深色和浅色主题下的窄卡片溢出已通过统一的字号、字距和宽度约束修正，两套主题的字形与配色保持独立；
- 暂存工程 typecheck、build、主题源码预检和前端预检 `14 passed` 已通过；正式工程全量回归、同步后的 runtime smoke 和登录后双色主题人工视觉验收仍需完成。

## Frontend TechSpar-informed product workspace

阶段 77 针对“功能已经很多，但前端像临时拼装”的反馈，参考 `techspar` 做只读产品审计并重做 QTrace 的工作台交互。借鉴点是 AppShell、分组导航、模式选择后的一主操作、skeleton/empty/error 状态和桌面/移动导航差异，不是复制上游代码、品牌或依赖清单。

- `WorkspaceLayout` 用 `NAV_GROUPS` 统一维护三组路由，增加 `qtrace_sidebar_collapsed` 的桌面收起偏好；窄屏使用移动菜单、抽屉侧栏和遮罩，路由变化后自动关闭；既有路由、认证、Outlet、API 和主题切换不变；
- 首页用 `TRAINING_MODES` 提供简历模拟、专项训练、JD 定向、录音复盘四个入口。用户先选择路径，再只看到当前模式的一主操作；简历模拟继续使用原有 PDF/摘要与 `/interview/start` 请求，其他入口转到既有页面；
- 首页简历状态增加可见 skeleton，上传/启动失败使用 `role="alert"`；训练卡有 selected、hover、focus-visible 和响应式单列状态；
- `styles.css` 新增 `qtrace-workspace-shell`、`training-mode-grid`、`dashboard-action-panel` 等结构层，深色 Tactical Telemetry 与浅色 minimalist-ui 共享产品布局，避免再依赖巨大展示标题支撑首页；
- `frontend_route_preflight.py` 新增 `REQUIRED_PRODUCT_UX_MARKERS`，锁定工作台、移动菜单、训练模式、一主操作和 skeleton 契约；
- 改造前源码白名单快照为 `qtrace-pre-techspar-ux-20260822-144831.zip`，SHA256 为 `4FC3E7C3D53C703A5804D31DF474733805BC2A9E894336879D88D292E2A10BCE`；
- 暂存工程和正式工程 typecheck、build、前端源码预检以及前端预检回归 `14 passed` 已通过；正式工程全量回归使用全新合成 SQLite 和显式 basetemp，结果为 `109 passed`，`local_runtime_smoke.py` 与 `final_delivery_preflight.py` 也已通过。交付预检提示 15 个本地日志/数据等产物待人工审阅，没有发现明显密钥模式；登录后桌面/窄屏双色主题人工验收仍需完成。

静态契约仍不等于浏览器 E2E：用户需要使用合成账号确认侧栏收起/抽屉、四种模式跳转、简历模拟启动、错误反馈以及深色/浅色主题的真实观感。本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或提交推送 GitHub。

## Light product workspace

阶段 79 将“参考 TechSpar”落到交互结构和可复用表现层：新增 `frontend/src/components/ProductUI.tsx` 的 `PageHeader`、`Surface`、`StatusBadge`、`StatePanel`，新增 `frontend/src/product.css` 的浅色工作台 token，并把 `WorkspaceLayout` 接到新的 `product-workspace-shell`。默认主题改为 `minimalist`，只有显式保存为 `dark` 时才进入深色主题；既有 `qtrace_theme` 偏好仍然可切换。

首页、画像和 Personal Agent 是本阶段的核心迁移对象；既有 `/interview/start`、画像/SM-2、Agent 对话、个人文档、工具 trace 和计划草稿确认逻辑不变。其他页面先通过工作台级样式统一输入、标题、表面、按钮和设置反馈，后续逐页迁移。新的 `frontend_route_preflight.py` 同时检查工作台挂载点、状态组件和产品化样式关键选择器。

本阶段改造前快照为 `qtrace-pre-light-product-workspace-20260822-151302.zip`，SHA256 为 `0A1C3C9E9ED64F87241051629460102A3CE0A07E3EECE2E3727C5973E0833D06`。暂存前端 typecheck、build、前端预检和 14 条前端契约回归通过；同步正式工程后，正式 typecheck/build、预检、14 条前端契约回归、全量合成回归 `109 passed`、local runtime smoke 和 final delivery preflight 也通过。第一次正式契约回归因 Windows 系统临时目录权限失败，改用项目范围内全新 basetemp 后通过；第一次 runtime 使用错误的健康 URL，改为 `/api/health` 后通过。本地登录入口已做视觉检查，登录后核心工作区、真实请求和窄屏仍需用户用合成账号验收，不能把静态证据误报成浏览器 E2E。

## Interview-ready engineering note

`docs/QTRACE_ENGINEERING_NOTE.md` 是当前项目的总工程笔记。它把多阶段实现压缩为一条可复述主线：结构化简历 -> 面试 session -> 画像/SM-2 -> Agent draft/confirm -> 专项训练；同时说明 React、FastAPI、SQLite、Provider、Embedding、个人文档检索和知识图谱的职责边界，以及 `111 passed`、前端 build 和 runtime smoke 等证据。面试讲解时优先按“用户问题、数据流、职责分层、失败边界、验证证据”组织，不按页面数量背诵。

## Personal document file import

阶段 80 将个人文档库的文件入口统一为 PDF 和 Markdown。`/api/agent/documents/upload` 根据扩展名选择 `pypdf` 文本层提取或 UTF-8 Markdown 解码，随后复用 `PersonalDocumentService` 的规范化、正文指纹去重、版本快照、分块和 Embedding。前端在 Personal Agent 的个人文档库中提供“导入 PDF”和“导入 Markdown”两个入口，并显示处理中、成功、重复和失败状态。

这条链路只在本机解析文件并保存正文，不保存原始文件路径，不调用外部 API。扫描 PDF 没有文本层时仍会提示暂不支持 OCR；Markdown 只接受 `.md`/`.markdown` 和 UTF-8。导入后的检索仍受当前用户和 `embedding_mode` 约束，切换模型后必须显式重建索引。阶段 80 的合成导入专项回归为 `5 passed`，前端契约回归为 `14 passed`，全量 Python 回归为 `111 passed`。

## Brand icon in workspace

阶段 81 复用已有的 `frontend/public/qtrace-icon.png`，把 `WorkspaceLayout` 左上角原来的 `QT` 文字方块替换为图片品牌标识；“问迹 / QTRACE GROWTH LAB”文字、副标题、桌面收起和窄屏导航逻辑保持不变。图标使用固定图片尺寸与 `object-fit: cover`，不引入新依赖、不改变路由或 API。`frontend_route_preflight.py` 增加 `src="/qtrace-icon.png"` 静态标记，避免后续回归时品牌资源被误删或退回文字占位。

## TechSpar frontend migration

阶段 82 起，正式前端的活动源码以本地 `techspar/frontend/src` 为基线，QTrace 不再继续使用旧的自有 UI 入口。页面结构、导航、训练入口和交互节奏通过源码迁移复用；QTrace 的差异集中在 `frontend/src/api/interview.ts` 与 `frontend/src/api/personalAgent.ts` 两个适配模块、品牌资源和后端实际能力边界。旧 QTrace UI 文件仅作为可恢复迁移材料保存在 `frontend/migration_leftovers`，没有删除。

适配层只调用 QTrace 已存在的接口；同步回答不会伪装成流式，缺少删除/参考答案/独立连接测试接口时显式返回不支持。TechSpar 原项目采用 CC BY-NC 4.0，归属和非商业限制记录在 `THIRD_PARTY_NOTICES.md`，未经原作者许可不用于商业用途。

阶段 82 验证命令：`python scripts/techspar_frontend_preflight.py ... --reference ...` 通过；正式全量 Python 回归 `113 passed`（使用项目范围 basetemp）；前端 `npm run typecheck`、`npm run build` 通过；5174 页面、前端 `/api/health` 代理和 QTrace 图标资源均返回 200。构建只保留大型 bundle 警告；登录后的浏览器视觉验收仍需合成账号人工完成。

## Vite development render recovery

阶段 83 处理了 TechSpar 前端迁移后 `5174` 页面纯黑的问题。浏览器控制台显示 Vite 8 注入的 `/@vite/client` 抛出 `ReferenceError: __BUNDLED_DEV__ is not defined`，因此问题发生在 React 入口执行之前，不是 QTrace API 或登录状态失败。`frontend/vite.config.js` 现在关闭 HMR，并用 post `transformIndexHtml` 插件移除异常开发客户端注入；开发期间修改代码后手动刷新即可。

修复后 5174 返回 200，HTML 不再包含 `/@vite/client` 或 `/@react-refresh`，浏览器 DOM 已渲染 QTrace 首页；`npm run typecheck` 与 `npm run build` 通过，build 只保留大型 bundle 提示。API 代理、路由、认证、Agent、Embedding 和生产构建行为没有改变。

## Direct login entry

阶段 84 移除了未登录用户进入首页时的 Landing 开场动画。`frontend/src/App.tsx` 不再导入 `Landing`：根路径根据认证状态直接进入 `/login` 或 `/profile`，登录页已有 token 也直接进入 `/profile`。Landing 源文件和视频没有删除，但不再属于活动入口；`scripts/qtrace_entry_preflight.py` 防止它们重新成为首屏依赖。专项回归 `2 passed`，typecheck/build 通过，浏览器 5174 未登录访问已进入登录页。

## QTrace-owned workspace shell

阶段 85 开始把“参考 TechSpar 的交互规律”和“活动 UI 原样复用”拆开。`frontend/src/components/QTraceWorkspaceShell.tsx` 与 `qtrace-workspace.css` 现在承担活动 AppShell：训练路径、长期记忆、素材与图谱三组导航，当前路径 command bar，主题/设置/账户操作，桌面收起和移动抽屉都由 QTrace 自己维护。`App.tsx` 不再导入 TechSpar 的 `Sidebar`，也不重新接入 `Landing`；认证、ProviderGate、路由、业务页面和 API adapter 保持不变。

新增 `scripts/qtrace_shell_preflight.py` 与 3 条回归，阻断活动 AppShell 退回 `Sidebar`/`Landing`，同时检查 QTrace 外壳的 CSS 和可访问导航标记。原 `techspar_frontend_preflight.py` 改成参考基线审计：与 TechSpar 的文件集合差异只作 INFO，不再要求活动源码和参考仓库完全同构。阶段 85 的 shell 专项回归为 `5 passed`，typecheck、备用输出目录构建和入口预检通过；标准 build 受正式 `node_modules/.vite-temp`/`dist` 写入点的 Windows `EPERM` 阻塞，未删除依赖或构建目录。登录后完整工作区视觉仍需合成账号人工验收。下一步优先重写 `/profile` 与 `/mock-interview` 的活动页面层。

## QTrace interview workspace

阶段 86 将 `/mock-interview` 的页面编排层改成 QTrace 自有的“开始训练”工作台。保留 `live/targeted` 查询参数、键盘可访问 tab、`ResumeInterview`/`JobPrep` 子流程和既有路由/API；新增 `01 / INTERVIEW LOOP` 首屏、当前模式 readout、`02 / SELECT MODE` 硬边模式条和明确的输入要求。样式位于 `qtrace-interview.css`，与 AppShell 共用纸张画布和信号色，不再依赖原先的圆角模式卡和装饰性阴影。

新增 `qtrace_interview_preflight.py` 与 2 条回归；shell/参考审计/训练页专项回归共 `7 passed`，typecheck 通过，备用暂存目录 build 转换 3809 个模块成功。标准正式 `dist` 构建的 Windows `EPERM` 写入边界仍按阶段 85 记录。下一步优先迁移 `/profile` 的空状态与训练统计首屏；登录后真实模式切换仍需合成账号人工验收。

## QTrace profile workspace

阶段 87 继续迁移登录后的第一屏 `/profile`。画像 API、派生函数、SM-2 到期复习和所有知识/行为组件保持不变；空状态新增 `00 / PERSONAL MEMORY` 标题、训练数据说明和三个硬边训练入口，有数据状态统一使用 `qtrace-profile-surface`、统计左刻度和纸张面板。入口仍跳转 `/topic-drill`、`/resume-interview`、`/job-prep`，没有改变路由或后端契约。

新增 `qtrace-profile.css`、`qtrace_profile_preflight.py` 与 2 条回归；专项回归、typecheck、备用输出目录 build 和入口预检通过，备用 build 转换 3810 个模块。正式 dist 的 Windows 写入 EPERM 仍按前阶段记录。下一步可迁移画像内部的知识证据/能力地图，或进行模型设置页状态反馈验收；登录后画像视觉仍需合成账号人工验收。

## QTrace model settings feedback

阶段 88 把模型设置页的已有异步状态提升为 QTrace 自有的可观察操作面：首屏显示 LLM 连接、Embedding 模式/连接和配置保存三块状态读数；测试中的状态有 `role="status"`，失败状态有 `role="alert"`，保存、加载、测试和向量重建错误先经过 `redactSettingsError` 再呈现，不回显 API Key。`qtrace-settings.css` 只作用于设置页，使用硬边纸张面板、信号红、直角输入框和无渐变/无阴影保存栏，并保留窄屏与 reduced-motion。新增 `qtrace_settings_preflight.py` 与 2 条回归；设置预检、入口/shell/训练/画像预检、最终交付预检、typecheck、备用 build、5174 登录入口和 `/api/health` 均通过。正式 dist 的 Windows `EPERM` 写入边界仍需保留；登录后的实际模型测试和双色/窄屏视觉仍是合成账号人工验收项。本阶段没有读取或输出 API Key、真实简历或个人文档，没有外部 API、部署、删除文件或 GitHub 推送。

## Local acceptance checklist

阶段 89 不再扩展业务范围，新增 `docs/STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md` 作为最终本地验收清单。清单把自动证据和人工证据分开，覆盖直达登录、QTrace 工作台、画像、开始训练、模型设置、Embedding 显式 reindex、PDF/Markdown 文档、Personal Agent、知识图谱、主题和窄屏。自动预检、全量合成 Python 回归 `124 passed`、69 个 Python 文件内存编译、typecheck、备用 build、5174 登录入口和 `/api/health` 已通过；登录后合成账号路径、真实 LLM/本地 Embedding 路径、正式 dist 的 Windows `EPERM` 边界仍按清单如实记录，不把静态检查说成完整浏览器 E2E。

## Public interview demo deployment contract

阶段 90 从“本地可运行”进入“可部署准备”：新增 `docker-compose.demo.yml`、`deploy/Dockerfile.backend`、`deploy/Dockerfile.web`、`deploy/nginx.conf`、`deploy/demo.env.example` 和 `scripts/public_demo_preflight.py`。前端生产产物由 Nginx 提供，`/api` 与预留的 `/ws` 由同源代理转发到 FastAPI，后端只在 Compose 内网暴露 8000，SQLite 数据进入命名卷；`REBUILD_JWT_SECRET` 不再允许通过生产 Compose 使用本地默认值。`REBUILD_ALLOWED_ORIGINS` 支持由部署环境配置允许来源。

这仍是部署契约，不是公网已上线证据。公开 Demo 的产品边界是“用户登录后自带 OpenAI-compatible LLM 配置（BYOK），没有 Key 时明确降级到 Stub”，不把开发者 Key 写进镜像或示例环境文件。当前后端配置仍会把用户 Key 放入 SQLite，正式公网前必须补充加密/会话保存、API Base SSRF 防护、限流和连接测试接口。`scripts/public_demo_preflight.py` 只读检查文件、代理、卷、secret 和示例配置，不启动 Docker、不联网、不读取真实资料或 API Key。

本机 Docker 验证已完成：`docker compose build` 成功构建 API/Web 镜像；临时启动后 `http://127.0.0.1:8080/` 和经 Nginx 代理的 `/api/health` 均返回 200。验证结束后只停止容器，没有删除命名卷。正式公网部署、域名和 HTTPS 仍未完成。

阶段 91 新增 `POST /api/settings/test-llm` 和 `OpenAICompatibleProvider.probe()`。端点只测试未保存的表单值，空字段才回退到用户已保存配置，不调用设置写入方法；探测请求使用固定合成提示和 `max_tokens=1`，前端 `testLLMConnection` 已从占位返回改为真实 fetch。BYOK 的明文 SQLite 存储、API Base SSRF、限流和真实外部联调仍是公网前门禁。

阶段 92 新增 `REBUILD_BYOK_STORAGE_MODE`。本地默认 `persisted` 保持既有行为；`docker-compose.demo.yml` 默认 `session`，Store 将 LLM/Embedding Key 留在进程内存、向 SQLite 写入空字符串，重启后 `llm_configured/embedding_configured` 会回到未完成并要求重新输入。该模式不是完整安全方案，公网前仍需 API Base SSRF/私网阻断、HTTPS、限流、预算和日志治理。

## Local runtime handoff

阶段 93 处理了本地验收时“前端是新代码、后端却是旧监听实例”的运行态问题：确认 5174 前端已包含 QTrace 自有外壳、直达登录和真实 LLM 测试 adapter 后，只重启确认属于 QTrace 的 8002 后端，并把运行数据库与数据目录指向 `techsnowsong_stage` 合成路径。当前 8002 OpenAPI 已包含 `/api/settings/test-llm` 和 PDF/Markdown 文档上传，5174 `/api/health` 同源代理、合成注册、受保护设置读取和空配置测试分支均通过。

本阶段还修复 session BYOK 在切换到 Demo/本地 Embedding 后残留内存 Key 的状态一致性问题。Store 只在 `session` 模式清除对应内存项，`persisted` 本地兼容行为不变。隔离全量回归 `136 passed`，前端 typecheck、暂存目录 build、public demo/BYOK/final delivery 预检通过。新启动前端尝试仍会受到正式 `node_modules/.vite-temp` 的 Windows `EPERM`，因此保留已运行的当前前端实例并用 HTTP/代理检查验证，不把权限边界写成应用失败。

本地运行态不等于公网部署：没有创建公网 URL、域名或 HTTPS，也没有读取真实资料、输出 API Key、调用真实外部模型、删除文件或推送 GitHub。浏览器验收仍应使用新的合成账号；公开 Demo 仍需 SSRF/私网阻断、限流、预算、日志治理和部署环境配置。

## Public API Base network policy

阶段 94 为 BYOK 增加应用层 API Base 安全边界。`REBUILD_BLOCK_PRIVATE_API_BASE` 默认关闭以兼容本地 Ollama/OpenAI-compatible 调试，公开 Compose 和示例环境默认开启。开启后，设置保存、Embedding 远程配置、LLM 独立连接测试和 Provider 构造都会拒绝非 `http/https`、URL 中嵌入凭据、localhost/内部域名、私网/回环/链路本地 IP；主机名还会在配置时解析，任一结果不是公网地址就拒绝。

这不是完整的 SSRF 终点：配置时 DNS 检查不能单独消除之后的 DNS rebinding，因此真正上线还必须配置云侧出站网络策略/代理、HTTPS、限流、调用预算、日志脱敏和监控。所有拒绝都发生在 Provider 请求前，LLM/Embedding API Key 不进入错误响应或日志。专项回归只使用合成地址和 fake resolver。

本阶段的 Compose 运行态证据已补齐：API/Web 镜像构建成功，8080 首页与 `/api/health` 代理通过，合成账号注册成功；公开模式下对 `127.0.0.1` 的 LLM 探测返回失败但不发起上游请求，设置保存返回 400。验证完成后仅停止容器，没有删除命名卷；仍未进行外部部署。

## Tencent VPS public demo deployment

阶段 95 进入实际云主机部署准备：QTrace 使用独立腾讯云 Ubuntu VPS，不触碰 Qidian 旧实例。远端 Docker Hub 访问超时时，验证了腾讯容器镜像的 Python/Node 基础镜像和腾讯 PyPI、npmmirror 依赖镜像；部署文件因此新增 `PIP_INDEX_URL` 与 `NPM_REGISTRY` 构建参数，镜像源可以通过未提交的 `deploy/demo.env` 注入。为降低 npm 国内镜像缺少字体包版本造成的脆弱性，简历模块移除 `@fontsource/noto-serif-sc`，保留系统衬线字体回退。

阶段 95 的“公网可访问”判定必须同时具备 Compose healthy、Nginx 首页/`/api/health` 通过、腾讯云安全组放行演示端口、控制台显示的真实公网 IPv4 和外部浏览器合成账号验收。服务器内 `10.x.x.x` 私网地址、Docker 构建成功或本机 curl 不能单独证明公网可访问。远端环境文件中的 JWT secret 不输出、不回显、不提交，访问者仍需在网页中自带 BYOK Key；Stub 只用于无 Key 的明确降级路径。

## Tencent VPS browser acceptance

阶段 96 已完成新 QTrace VPS 的公网浏览器验收：公网 IPv4 为 `49.232.104.202`，安全组已有 TCP 80 规则，远端 Web 运行时通过 `QTRACE_DEMO_PORT=80` 映射到主机 80。Compose 中 API 为 healthy，Nginx 首页与同源 `/api/health` 在服务器内返回 200；从外部 Chrome 打开 `http://49.232.104.202/` 后进入 `/login`，页面标题为“问迹 QTrace · 个性化面试训练”。这才是“其他人能通过浏览器打开”的证据，和本机 curl、私网地址或镜像构建证据区分开。

本次 VPS 到 GitHub 的 HTTPS 拉取遇到超时，部署时对远端工作树应用了与已推送 `main` 等价的构建修复；网络恢复后更新流程必须优先 `git pull --ff-only`，不要用手工覆盖替代长期同步。当前入口仍是 HTTP 面试 Demo，不宣称正式生产上线；域名/HTTPS、限流、预算、监控、备份和更严格的 BYOK egress/SSRF 治理仍是后续门禁。
