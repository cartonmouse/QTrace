# QTrace 工程总笔记：从复现到面试可讲

> 这不是“功能清单”，而是我理解和讲解 QTrace 时应该遵循的主线。
> 项目参考 TechSpar 的产品方向和核心功能，但 QTrace 是独立重建，不应表述为官方复现。

## 1. 项目一句话

QTrace 是一个面向技术求职者的个性化面试训练系统：用户把简历、项目、目标 JD 和训练记录沉淀为个人学习上下文，系统通过简历模拟、专项训练、SM-2 间隔复习、知识图谱、Personal Agent 和个人文档检索，持续决定“下一次应该练什么、为什么练、练完如何回写画像”。

面试时最重要的表达不是“我做了很多页面”，而是：

> 我把一次面试训练做成了一个可追踪的学习闭环。模型负责理解和生成，业务代码负责鉴权、上下文边界、工具白名单、计划确认、训练状态和持久化。

## 2. 为什么做这个项目

原始动机有两个：

1. 想参考 TechSpar，学习一个包含简历、画像、专项训练、个人 Agent 和复习机制的完整 AI 应用，而不是只做一个聊天页面；
2. 想把项目本身变成 AI Agent 岗位的面试材料，所以每个功能都要能回答：输入是什么、状态如何变化、模型负责什么、代码如何约束、失败时怎么办、如何验证。

因此实现策略是“先复现主链，再逐步补齐关键能力”：保留原有可运行链路，使用合成数据做回归，真实资料、真实模型网络联调、部署和 GitHub 推送单独管理。

## 3. 系统总架构

```text
React + React Router 前端
        │ 统一 apiFetch / Bearer token / 401 过期事件
        ▼
FastAPI API 层
        │ 鉴权、输入校验、用户作用域、业务编排
        ├── Interview State Machine
        ├── Profile / SM-2 / Topic Graph
        ├── Resume / JD / Copilot
        ├── Personal Agent
        └── Personal Document Memory / RAG
                │
                ├── SQLite Store：用户、设置、简历版本、会话、画像、计划、文档
                ├── Chat Provider：StubProvider 或 OpenAI-compatible LLM
                └── Embedding Provider：local-deterministic / local-model / openai-compatible
```

### 分层职责

| 层 | 负责什么 | 不应该负责什么 |
| --- | --- | --- |
| React 页面 | 输入收集、状态展示、路由跳转、可恢复反馈 | 不决定用户是否有权限、不直接拼接数据库事实 |
| `apiFetch` | `/api` 前缀、Bearer token、结构化错误、401 事件 | 不保存 API Key 到前端、不吞掉业务错误 |
| FastAPI 路由 | 鉴权、参数校验、用户隔离、调用编排 | 不把所有模型细节和数据库细节写在路由里 |
| Domain service | 面试状态、Agent 工具、画像、检索、复盘 | 不绕过用户作用域和显式确认 |
| Store / SQLite | 持久化事实和版本 | 不让模型输出未经校验地直接写入 |
| Provider | 统一 Chat/Embedding 外部能力 | 不决定业务状态、不直接修改用户画像 |

## 4. 从用户操作到个性化复习的主链

```text
注册 / 登录
  -> StubProvider 或真实 LLM 配置
  -> 填写结构化简历、上传 PDF 或保存个人文档
  -> 选择简历模拟 / 专项训练 / JD 定向 / 录音复盘
  -> 创建 interview session
  -> 按显式 phase 生成问题、接收回答、继续追问
  -> 结束并保存复盘
  -> 更新画像、行为信号和 SM-2 复习项
  -> 画像页展示到期复习
  -> 用户点击立即复习或交给 Personal Agent 制定计划
  -> 计划 draft 经用户确认
  -> 计划项进入专项训练
```

### 面试状态机怎么讲

一次面试不是“调用一次 LLM 返回一段文字”，而是一个持久化 session。当前阶段由后端控制，例如自我介绍、技术追问、项目深挖、行为问题和反问。每次提交回答时，后端根据当前 phase、目标岗位、简历上下文、主题、画像和复习焦点组装 prompt；模型只负责生成问题或评价，后端负责校验结果、推进阶段和保存事件。

这样做的好处是：刷新页面可以恢复，模型短暂失败不会把 session 伪装成完成，历史记录和画像可以追溯每一次训练来源。

## 5. 结构化简历、JD 和知识库

### 结构化简历

简历编辑器把个人概述、技能、项目名称、职责、项目描述、技术栈、关键工作与结果保存为版本。保存后确定性地生成面试上下文和项目追问卡，避免每次都让模型从一整段简历里猜重点。

每个项目会生成背景、职责、设计、验证、取舍等追问方向。追问卡带有项目字段引用、简历版本和可选个人文档 citation，因此面试时可以解释“这道题为什么出现”。

### JD 定向

JD 页面先提取岗位技能、优先级和出现次数，再与结构化项目的技术栈、职责、描述和关键工作做确定性匹配，得到可解释的项目分数和代表性追问卡。模型可以参与后续准备，但“岗位要求命中了哪个项目字段”由业务代码提供证据。

### 知识图谱

当前知识图谱是一个确定性读模型：按主题组织高频问题、相关问题和 SM-2 复习节点。问题节点可以进入精确训练，也可以交给 Agent 制定计划。`related` 边只表示候选关系，不自动等同于事实、不自动改权，也不会因为打开图谱就修改画像。

## 6. Personal Agent 怎么工作

QTrace 的 Agent 不是“把所有数据库权限交给 LLM”。它采用规划、工具执行、回答三段边界：

```text
用户请求
  -> planning LLM：输出结构化意图和允许的工具名
  -> 工具白名单归一化
  -> 只读工具读取画像、到期复习、最近会话、图谱问题、个人文档
  -> 如需行动，create_learning_plan 只生成 draft
  -> 用户确认
  -> 计划项才进入可执行状态
  -> 专项训练完成后显式完成计划项
  -> answering LLM 基于已验证工具上下文回答
```

### 工具边界

- `read_profile`、`read_due_reviews`、`read_recent_sessions`、`read_graph_question` 和文档搜索属于只读上下文工具；
- `create_learning_plan` 不是直接写画像，而是先检查依赖上下文，最多生成有限数量的 draft 计划项；
- 用户没有确认时，Agent 不能把 draft 当作已执行；
- 工具失败会被归一化为可观察的降级状态，回答不能把缺失值当成事实；
- Agent 规划失败、回答失败、工具失败、草稿保留和显式重试分别处理，避免把一次网络失败伪装成空回答。

### 面试追问：为什么不用一个大 prompt 直接完成？

因为一个大 prompt 难以控制写权限、失败恢复和事实来源。两步 Agent 加工具白名单让模型只负责“选择和解释”，业务代码负责“读取什么、能不能写、何时写、写入什么状态”。代价是编排复杂度更高，但可测试、可审计、可解释。

## 7. Personal Document Memory、Embedding 和 RAG

个人文档库支持手工文本/Markdown、Markdown 文件导入和文本型 PDF 导入。文档会按用户隔离、按版本保存并切分为 chunks；检索结果带文档 ID、版本和 citation，Agent 只能使用当前用户的证据。

文件导入端点根据扩展名选择 PDF 文本层提取或 UTF-8 Markdown 解码，解析后统一进入 `PersonalDocumentService`。原始文件路径不进入数据库，扫描 PDF 没有 OCR 能力，模型切换后仍需显式重建索引。

Embedding 分成三种模式：

| 模式 | 用途 | 关键边界 |
| --- | --- | --- |
| `local-deterministic` | 默认可运行 baseline、测试和离线演示 | 不是语义模型，优点是稳定、无网络、易复现 |
| `local-model` | 本机 Sentence-Transformers 语义检索 | 只接受用户填写的目录，强制 `local_files_only=True`，切换后显式 reindex |
| `openai-compatible` | 用户明确配置的远程 Embedding | 配置与 Chat LLM 分离，Key 不返回前端，不能把聊天接口能力当成 Embedding 能力 |

为什么切换模型后不自动重建？因为不同模型可能维度不同，旧 chunks 的向量和新向量不能混算。QTrace 先按 `embedding_mode` 隔离，用户显式点击重建索引后再重建当前文档版本。

当前已有的离线证据是固定合成查询集上的 Recall@K/MRR：确定性 baseline 和本地中文模型在小样本上都达到 Recall@2=1.000、MRR=1.000。这个结果只能证明小样本契约和排序逻辑，不能声称真实简历语料质量已经被证明。

## 8. SM-2 和用户画像

训练结束后，系统把结果拆成掌握度、强项、薄弱点、行为信号和行动项。SM-2 用于安排下一次复习时间，不是单纯的分数展示：到期项会进入画像页的 review queue，并能把 `topic/focus` 带回专项训练。

需要强调：画像写回必须来自完成的训练和确定性业务逻辑，不能让模型随意覆盖用户画像；图谱 related 边的点击次数也只是行为反馈，不等于掌握度或边权。

## 9. 前端重设计为什么这样做

前端经历了三个方向阶段：

1. Stage 75：深色 Tactical Telemetry 壳层和技术导航；
2. Stage 76：可切换的 minimalist-ui 浅色主题；
3. Stage 77：参考 TechSpar 的成熟工作台交互，加入导航分组、桌面收起、移动抽屉、四种训练模式选择、单一主操作和 skeleton/错误反馈。
4. Stage 79：把“参考 TechSpar”继续收敛为 QTrace 自己的浅色产品工作台，新增 `PageHeader`、`Surface`、`StatusBadge`、`StatePanel`，并迁移首页、画像和个人 Agent 三条核心路径。
5. Stage 80：把个人文档库的文件入口补齐为 PDF/Markdown，增加 Markdown UTF-8 解码、统一上传分流和前端导入反馈，不改变文档分块、Embedding、版本和 Agent 只读检索边界。
6. Stage 82：根据用户最终选择，把 TechSpar 的源码页面图作为正式活动 UI 基线，使用 QTrace API adapter、品牌资源和显式不支持降级接回 QTrace 后端。

Stage 77 和 Stage 79 的关键不是“做一个更花的首页”，而是把首屏决策、异步状态和页面分区组织成稳定工作台：先回答“今天练什么”，再展示“如何开始”，并让 loading/empty/error/ready 都能被用户看到。视觉层没有改变 API、路由、面试状态机、Agent、Embedding 或 SM-2。

Stage 79 使用 `frontend/src/product.css` 建立暖灰画布、白色工作表、碳黑正文、砖红信号色和低饱和蓝/绿语义色，默认浅色，深色仍可切换；不引入 TechSpar 的依赖或代码。源码契约新增组件、工作台挂载点和产品样式关键选择器，暂存工程 typecheck/build、前端预检和 14 条前端契约回归通过。登录入口已做独立暂存浏览器视觉检查，登录后工作区和真实请求仍需合成账号人工验收。

## 10. 验证证据和当前状态

正式工程当前已验证：

```text
前端 typecheck                    PASS
前端 production build             PASS
techspar_frontend_preflight       PASS
TechSpar 迁移契约回归              2 passed
全量 Python 回归                  113 passed
local_runtime_smoke                PASS
final_delivery_preflight           PASS
```

Stage 79 同步后的正式工程还重新通过了前端产品化契约和本地运行态检查：新的 `ProductUI.tsx`、`product.css`、工作台挂载点和页面状态组件均被静态预检覆盖；隔离合成后端的 `/api/health` 返回 200，前端开发入口返回 200，production dist 的两个资产引用存在。第一次 runtime 使用了错误的 URL，第一次前端契约回归遇到系统临时目录权限问题，修正参数后均通过；这些是验证环境问题，不是业务断言失败。

全量回归使用全新合成 SQLite 和项目暂存目录作为 pytest basetemp，避免触碰日常数据库。交付预检报告的 15 个本地日志/数据产物只是待审警告，没有自动删除；没有发现明显密钥模式。

### 当前仍不能宣称完成的内容

- 登录后的完整浏览器 E2E 和所有页面的视觉人工验收；
- 真实长音频、麦克风采集、说话人分离、时间戳对齐；
- 外部 Embedding 的网络兼容性和真实资料质量评估；
- 外部部署、全新机器复现、公开发布和 GitHub commit/push；
- 真实个人简历或个人文档的生产级隐私治理。

## 11. 三分钟项目介绍

> 我做的是 QTrace，一个面向技术求职者的个性化面试训练系统。它参考了 TechSpar 的产品方向，但我自己重建了核心链路。用户可以上传简历或维护结构化项目，选择简历模拟、专项训练或 JD 定向。一次训练会保存为 session，由后端状态机控制阶段，LLM 负责问题生成和回答评价，业务代码负责鉴权、上下文组装、状态推进和持久化。
>
> 在个性化部分，我用训练结果更新画像和 SM-2 到期复习项，画像页的薄弱点可以直接进入专项训练，也可以交给 Personal Agent。Agent 采用规划加工具调用，工具读取画像、到期复习、知识图谱和个人文档，学习计划先保存为 draft，用户确认后才进入执行，避免让 LLM 直接修改用户事实。
>
> 文档检索支持确定性 baseline、本地 Sentence-Transformers 和 OpenAI-compatible Embedding。个人文档还支持文本型 PDF 和 Markdown 文件导入，文件解析后统一进入分块与索引链路。模型切换后必须显式重建索引，并按 embedding mode 隔离旧向量。当前我用合成数据完成了 111 条后端回归、前端构建和运行态检查。真实资料、完整浏览器 E2E、部署和公开发布仍然作为独立边界，没有把未验证内容写成完成。

## 12. 高频追问速答

1. **为什么不用 LLM 直接决定所有流程？**  LLM 负责理解和生成，后端状态机、工具白名单、用户作用域和显式确认负责约束事实和写入。
2. **Agent 和普通聊天有什么区别？**  Agent 有目标分解、受控工具、结构化计划和可观察状态，不只是把历史消息发给模型。
3. **为什么计划要 draft/confirm？**  模型输出可能不完整或不符合用户意图，先 draft 可以让用户审阅，确认才允许进入执行链。
4. **为什么 Embedding 和 LLM 分开配置？**  两者接口、模型能力和维度契约不同；能聊天不代表 endpoint 支持 Embedding。
5. **为什么本地模型强制 `local_files_only`？**  防止模型缺失时后台偷偷联网，也让失败成为可定位的配置错误。
6. **为什么切换 Embedding 要显式 reindex？**  旧向量可能维度或分布不同，不能在同一个检索空间里混用。
7. **SM-2 怎样真正影响训练？**  到期复习项会带着 topic/focus 进入专项训练，而不是只在画像页展示一个分数。
8. **知识图谱是不是让 LLM 自动生成关系？**  当前关系是确定性读模型，related 候选可追溯，不能把行为次数当成掌握度。
9. **如何验证检索质量？**  用固定合成文档、查询和相关性标注计算 Recall@K/MRR；小样本结果不代表真实资料质量。
10. **当前项目最大的限制是什么？**  浏览器 E2E、真实音频、部署和真实资料质量还没有被完整验证，我会把它们作为边界说明，而不是夸大项目完成度。

## 13. 下一步学习方式

不要继续无目标地添加页面。接下来按一条主线复述和演示：

```text
结构化简历
  -> 项目追问卡
  -> 简历模拟 session
  -> 复盘写回画像 / SM-2
  -> Personal Agent 读取到期项
  -> draft 计划
  -> 用户确认
  -> 专项训练
```

每次学习一个模块时，至少回答四个问题：

1. 它解决了什么用户问题？
2. 它的输入、输出和持久化事实是什么？
3. LLM、业务代码和数据库各自负责什么？
4. 失败、越权、重复请求和模型不可用时如何处理？

这四个问题能把“我看过代码”变成“我能解释设计和取舍”。

## 14. 品牌资产与工作台壳层

阶段 81 没有重新设计业务页面，而是把已有的 QTrace 图标资源挂载到工作台品牌区。`frontend/public/qtrace-icon.png` 由浏览器以静态资源方式加载，`src/components/Logo.jsx` 和 `index.html` 分别负责页面品牌与 favicon；品牌文字仍然是可读文本，收起侧栏只隐藏文字而保留图标，因此展开、收起和窄屏抽屉共用同一份品牌入口。

这个改动的工程边界很小：不改认证、路由、API、训练状态机和业务数据，也不把图片转成 Base64 或复制出新的资产。前端 typecheck、生产 build、路由预检和前端契约回归 `14 passed` 均通过；浏览器中实际的尺寸观感仍属于人工验收范围。

## 15. TechSpar 前端迁移：活动 UI 与后端适配分离

用户最终选择直接采用 TechSpar 的成熟前端体验，因此阶段 82 将本地 TechSpar `frontend/src` 的 275 个文件按相对路径迁入正式工程。此后活动 UI 的入口是 TechSpar 的 `App.tsx`、页面、侧栏和组件图；QTrace 不再把旧的 `api.ts`、`styles.css`、`product.css` 或 `ProductUI.tsx` 当作活动 UI。旧文件仅移动到 `frontend/migration_leftovers`，便于审计和恢复，未删除。

QTrace-specific 逻辑集中在 `src/api/interview.ts` 和 `src/api/personalAgent.ts`：前者把页面调用映射到面试 session、历史、画像、主题、模型设置和 Embedding 重建接口，后者映射个人文档和 Agent chat。QTrace 不提供的删除、参考答案和独立连接测试接口会显式失败；同步 answer 通过 TechSpar 的 callback 兼容层返回完整消息，不虚构 token 流。品牌使用 `qtrace-icon.png`、`问迹` 和 `QTrace`，favicon 也已替换，未使用的 TechSpar SVG 移到迁移备份区。

TechSpar 采用 CC BY-NC 4.0，正式工程在 `THIRD_PARTY_NOTICES.md` 保留链接、归属、改动和非商业限制。阶段 82 的源码集合预检、前端 typecheck/build、全量回归 `113 passed`、5174 页面/代理/图标运行态检查和 final delivery preflight 均通过；交付预检仍只提示 15 个本地日志/数据产物待人工审阅。登录后的页面视觉、真实资料、公开部署和 GitHub push 仍是独立人工门禁。

## 16. Vite 开发运行时黑屏的定位与恢复

TechSpar 前端迁移后曾出现“5174 HTTP 200 但页面全黑”。排查顺序是先读取页面 HTML，再查看浏览器 console，最后用 DOM 确认 React 是否挂载。控制台错误为 `/@vite/client` 中的 `ReferenceError: __BUNDLED_DEV__ is not defined`，因此故障点在 Vite 开发注入层，早于 QTrace API、认证和业务组件。

修复集中在 `frontend/vite.config.js`：关闭 `server.hmr`，并用 post `transformIndexHtml` 插件移除 Vite 8 仍注入的 `/@vite/client`。开发模式保留手动刷新，5174 的 `/api`、`/ws` 代理和生产 build 不变。修复后 HTML 不再包含 Vite/React Refresh 开发脚本，浏览器 DOM 能看到 QTrace 首页；`npm run typecheck`、`npm run build` 均通过。这个案例可以用于面试说明“HTTP 健康、入口健康和业务健康是三层不同证据”，也说明为什么不能只看到 200 就宣布前端可用。

## 17. 直达登录与前端去同质化的第一步

阶段 84 先处理最容易暴露参考来源、但不属于 QTrace 核心价值的首页开场视频。`App.tsx` 不再导入 `Landing`，未登录的 `/` 直接进入 `/login`，已登录状态直接进入 `/profile`；`Landing.jsx` 和资源保留但不再由活动路由引用，也没有删除文件。

新增入口预检检查认证跳转和 Landing/`hero-intro` 禁止成为活动入口。这样做的边界是“复用成熟交互规律”与“原样暴露上游首页”分离：QTrace 仍保留登录后的面试、画像、Agent、Embedding 和知识图谱能力，下一步再重写自己的 AppShell、首页和训练入口。阶段 84 的入口专项回归 `2 passed`、前端 typecheck/build 和 5174 浏览器入口验证通过。改造前快照和 SHA256 见 `LEARNING_LOG.md` 与阶段文档。

## 18. QTrace 自有 AppShell：参考规律与活动代码分离

阶段 85 把前端去同质化落到一个可验证的技术边界：TechSpar 继续提供成熟的导航分组、工作路径和异步状态设计参考，但活动 AppShell 不再由它的 `Sidebar` 负责。`QTraceWorkspaceShell` 负责 QTrace 的品牌锁定、训练路径/长期记忆/素材图谱三组导航、当前路由 command bar、主题、设置、账户和移动抽屉；`qtrace-workspace.css` 只承载这一层的 QTrace token 和布局。

这里没有一次性重写所有页面，因为 AppShell 是一个风险较低、影响面清楚的深模块边界：它可以替换导航和视觉骨架，同时把认证、ProviderGate、嵌套路由、业务页面和 API adapter 保持原样。后续再把 `/profile` 和 `/mock-interview` 迁移到同一套工作台语义，能把每次改动控制在一个可回归阶段内。

为了防止“文件存在但没有真正挂载”，`qtrace_shell_preflight.py` 检查 `App.tsx` 的活动挂载、自有 shell/CSS、导航可访问性，并禁止重新导入 `Sidebar` 或 `Landing`。`techspar_frontend_preflight.py` 不再把 TechSpar 文件集合当作活动源码的唯一真相，而是输出参考差异 INFO；这体现了“参考基线”和“产品所有权”两个不同的验证问题。

阶段 85 的 shell 专项回归为 `5 passed`，QTrace shell 预检、TechSpar 参考审计、前端 typecheck、备用输出目录构建和阶段 84 入口预检通过。标准 build 本次在既有 `node_modules/.vite-temp`/正式 `dist` 写入点遇到 Windows `EPERM`，没有删除依赖或构建目录；备用构建已完成 3808 个模块转换。尚不能据此宣称所有登录后页面的浏览器视觉和业务 E2E 完成，仍需合成账号人工验收。

## 19. 开始训练页：只换编排层，不动面试子流程

阶段 86 选择 `/mock-interview` 作为第二个 QTrace-owned 页面边界。该页的职责是让用户选择 `live` 或 `targeted`，随后嵌入既有 `ResumeInterview` 或 `JobPrep`；因此可以把首屏信息、当前路径 readout、输入要求和模式条重写成 QTrace 语义，而不触碰 `/interview/start`、资料上传、JD 解析和训练状态机。

新页面仍使用 query parameter 作为可分享/可恢复的界面状态，仍保留 tab roles 和左右/Home/End 键盘导航；改变的是 CSS class 和结构层。`qtrace_interview_preflight.py` 通过静态标记检查 CSS 挂载、模式面板和专项训练跳转，专项回归 `7 passed`。备用输出目录 build 转换 3809 个模块成功；正式 dist 的既有 Windows 写入权限问题仍是环境边界。

这条迁移路径的面试讲法是：先把页面编排和业务子模块解耦，先验证导航、状态可见性和可访问性，再逐步迁移资料表单和画像页；这样失败时能定位在 presentation shell，而不是把 API、状态机和视觉问题混成一个故障。

## 20. 画像首页：把个人记忆变成下一次训练入口

阶段 87 迁移 `/profile` 的首屏表现层。这里没有复制画像数据，而是保留 `getProfile`/`getTopics`、访问标记、画像派生、SM-2 due reviews、知识证据、能力地图、行为模式和趋势组件；QTrace 自有 CSS 只负责标题层、空状态、训练入口、统计刻度和面板边界。

空状态现在明确表达“个人记忆尚未形成”，用户可以从专项训练、简历面试或 JD 备面开始第一轮；有数据状态仍显示原有统计和证据，只是统一到纸张面板和信号色。`qtrace_profile_preflight.py` 用静态契约锁定 API/跳转标记与 QTrace CSS 挂载，专项回归、typecheck 和备用 build 通过。完整登录后画像视觉和真实数据状态仍需人工验收。

## 21. 模型设置：把“能保存”与“能工作”分成可验证状态

阶段 88 处理了一个典型的前端可观察性问题：设置接口可能已经返回成功，但用户只看到刷新，或者连接失败时只能看到模糊的“请求失败”。`Settings.jsx` 继续调用既有的 `testLLMConnection`、`testEmbeddingConnection`、`updateSettings` 和 `rebuildEmbeddingIndex`，新增的只是首屏状态读数、可访问状态角色和 QTrace 表现层。

设置页现在把三类事实分开：LLM/Embedding 连接测试证明“当前填写配置能否完成最小请求”；保存状态证明“配置是否写入”；向量重建状态证明“新 Embedding 是否重新作用于资料索引”。模型设置页不把“已配置”说成“推理成功”，也不把“重建完成”说成“检索质量已经被评估”。失败消息通过 `redactSettingsError` 截断并隐藏 Bearer/token 类凭据片段，前端不会展示 API Key。

视觉上，`qtrace-settings.css` 使用硬边纸张面板、单一信号红、直角输入框和窄屏状态栈，去掉设置页对圆角卡片、渐变和厚重阴影的依赖。`qtrace_settings_preflight.py` 与 2 条回归锁定 CSS 挂载、状态节点、脱敏函数和 API 边界；typecheck、备用构建、入口和 `/api/health` 运行态检查通过。登录后的模型测试、真实本地模型成功/失败和视觉验收仍需合成账号人工完成。

## 22. 本地验收的结束条件

阶段 89 把项目结束条件写成 `docs/STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md`：启动入口、工作台、画像/训练、模型设置反馈、文档导入、Agent/图谱和主题/窄屏必须由合成账号人工走通；静态预检、全量合成 Python 回归 `124 passed`、69 个 Python 文件内存编译、typecheck、备用构建和 `/api/health` 作为自动证据单独记录。这样“项目可以本地验收”不等于“真实模型质量、全新机器复现、完整浏览器 E2E、部署或 GitHub 推送已完成”。
