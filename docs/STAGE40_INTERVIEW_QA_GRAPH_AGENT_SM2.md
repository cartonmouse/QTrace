# Stage40：QTrace 图谱、Agent 与 SM-2 面试讲解稿

这份材料用于面试前复习。目标不是背术语，而是能沿着一条真实请求链解释“数据从哪里来、谁做决定、什么时候写数据、为什么这样设计”。

## 一、90 秒项目介绍

> 我做的是一个面向 AI 应用开发岗位的个性化面试训练系统 QTrace。它把结构化简历、个人文档、训练历史、领域画像和 SM-2 复习队列连接起来，用户可以进行简历模拟面试、主题专项训练、JD 定向准备，也可以让 Personal Agent 根据长期画像制定需要确认的学习计划。
>
> 我重点实现了一个知识图谱 read model。它不新增 Neo4j 或第二份题库，而是从当前用户的主题题库、画像薄弱点和 SM-2 到期项即时重建问题关系图。问题之间的 `related` 边使用确定性的 token 重叠和中文二元片段规则，因此可解释、可测试、可复现。用户从图谱点击问题后，后端只接受 `question:<n>` ID，再按当前用户当前主题重新解析完整问题，作为专项训练的首个技术追问。
>
> 在此基础上，我让 Agent 通过受控的 `read_graph_question` 工具读取图谱问题和相近候选，并在用户明确请求时生成 draft 学习计划。计划需要用户确认，计划项进入训练时还会把图谱来源带到 session。相近题不是自动塞进计划，而是作为用户可选择的候选。系统还记录候选的父节点、训练开始/完成情况，并提供只读评估报告，但不会把点击次数误当成掌握度，也不会自动改写 related 权重或 SM-2。

## 二、一次“从图谱到训练”的完整链路

```text
GET /api/graph/rag
  -> build_topic_graph(user_id, topic, data_dir, store)
  -> 题库 + topic_profile + review_items
  -> topic/question/review nodes + contains/related/revisits links
  -> 前端点击 question:2
  -> /topic-drill?topic=rag&graph_question_id=question:2
  -> POST /api/interview/start
  -> 后端重新解析 question:2
  -> InterviewEngine 继续负责状态机
  -> sessions 保存 graph_question_id / graph_question
  -> 训练结束后 review 写回画像与 SM-2
```

如果用户从相近题候选进入，URL 还会携带：

```text
graph_entry_source=related_neighbor
graph_parent_question_id=question:1
```

后端会重新构建当前用户当前主题图谱，确认 `question:1` 和 `question:2` 确实存在 `related` 边，然后保存父问题 ID 和文本快照。前端提交的完整问题文本从来不是事实来源。

## 三、系统中的三个“决定者”不要混淆

| 机制 | 回答的问题 | 当前实现 | 不负责什么 |
| --- | --- | --- | --- |
| 图谱 related 边 | 哪些题在当前规则下相近？ | token/中文二元片段重叠 | 不代表掌握度，不自动出题 |
| SM-2 | 什么时候应该复习？ | 训练评分更新 interval/ease/repetitions/next_review | 不判断题目语义相似 |
| Personal Agent | 基于哪些上下文安排什么行动？ | 受控 read tools + draft/confirm plan | 不能绕过验证写画像或自动扩张计划 |

面试中可以明确说：图谱负责关系解释，SM-2 负责时间调度，Agent 负责上下文编排和受控行动。把三者混成一个“AI 分数”会导致难以解释和难以测试。

## 四、常见追问与回答

### 1. 为什么不用 Neo4j？

当前图谱是从题库、画像和复习表重建的 read model，节点和边没有独立生命周期。如果引入 Neo4j，就需要处理题库事实和图数据库之间的同步、删除和一致性。第一版优先保证用户隔离、可复现和可解释，因此 SQLite 事实源 + 即时图谱更合适。关系规模扩大、需要复杂图查询时，再考虑专用图数据库。

### 2. 为什么不用 Embedding 计算相似题？

真实 Embedding 对同义表达更有帮助，但会引入模型、维度、阈值、成本和版本变化。当前确定性规则是可解释基线，能明确回答“为什么连边”。项目里已经把关系算法封装在图谱读模型边界内，未来可以做 Embedding 离线对照，不需要改题库或 SM-2 事实源。

### 3. 中文二元片段会不会误连？

会。它只是第一版的可复现近似，不等同于语义相似度。阈值、公共词和短文本都会影响结果，所以我把 `weight` 命名为关系强度，而不是置信度；同时前端把相近题展示为可选候选，而不是自动任务。

### 4. 为什么不让 Agent 自动把相近题加入计划？

因为 `related` 只表达知识关系，不表达用户意图，也不是 SM-2 到期信号。自动加入会造成计划膨胀、重复练习和不可控副作用。当前 Agent 计划最多保存候选元数据，用户明确点击后才进入下一步。

### 5. Agent 到底做了什么？是不是只是固定话术？

系统有 Provider 抽象，Stub provider 用于本地可运行和回归测试，真实 LLM provider 可以根据配置接入。无论模型是否真实，后端都会校验请求中的 topic、question ID 和计划来源；`read_graph_question` 是只读工具，`create_learning_plan` 是受确认保护的写工具。因此 Agent 的核心不只是生成文字，而是“规划工具调用 -> 读取结构化上下文 -> 生成 draft 行动 -> 用户确认 -> 进入训练状态机”。

### 6. 为什么不让模型直接读数据库？

工具是权限和数据边界。Agent 只能拿到当前用户、当前主题、当前请求需要的有限上下文；后端可以在工具层做用户隔离、字段裁剪和失败观测，也能测试“没有调用读取工具就不能声称读过资料”。

### 7. 图谱问题为什么只传 ID，不传完整问题？

完整问题如果由前端提交，用户可以伪造或修改它。`question:<n>` 只是可验证索引；后端按当前用户和主题重新读取题库，再保存问题快照用于 session 审计。这样既防篡改，也能保留训练当时看到的文本。

### 8. 图谱和训练状态机是什么关系？

图谱只是入口和解释层，不负责推进面试阶段。启动路由把指定问题放到专项题库首位，之后仍由 `InterviewEngine` 管理消息、阶段、回答和结束；这样不会复制一套图谱专用面试状态机。

### 9. 候选反馈统计能说明哪道题更重要吗？

不能。开始/完成次数只能说明用户使用过候选入口。完成率、平均分和首末分差都是描述性指标，可能受到时间、题目难度和其他训练影响。它们不等于掌握度、录用概率或因果收益，因此不会自动改 related 权重、画像或 SM-2。

### 10. SM-2 在哪里发挥作用？

训练结束产生结构化 review 后，系统按 topic 和 review point 更新 `review_items`，计算 interval、ease factor、repetitions 和 next_review。下一次专项训练或 Agent 读取 `read_due_reviews` 时，优先看到到期项。图谱把这些到期项作为 review 节点和 `revisits` 边展示，但打开图谱本身不会更新 SM-2。

### 11. 如何保证多用户隔离？

每一个长期数据读取都带 `user_id`；主题、题库、画像、review_items、sessions、个人文档和 Agent 对话都在后端按当前用户查询。前端只传 topic 或节点 ID，后端重新校验归属；测试覆盖跨用户图谱和非法节点访问。

### 12. 这是不是多 Agent？

不是。当前是一个 Personal Agent + 受控工具集合。`read_profile`、`read_due_reviews`、`read_graph_question` 等是工具调用，不是互相通信的多个自治 Agent。这样更容易先讲清权限、状态和审计；如果未来拆分 Planner、Retriever、Coach，也应该先保持这些边界。

## 五、现场演示顺序

1. 登录并进入 `/graph`，选择 `rag`，展示问题、SM-2 到期点和 related 边。
2. 点击一个问题节点，说明相近候选来自已有 related 边，不是前端临时计算。
3. 点击“练习相近题”，展示专项训练页的来源提示；启动后在复盘页展示父节点快照。
4. 返回图谱，展示候选入口开始/完成次数和“候选反馈评估”只读面板。
5. 从问题进入 Agent，说明 `read_graph_question` 读取节点和候选；让 Agent 制定计划，展示 draft/confirm。
6. 确认计划并进入训练，指出计划项、graph question 和 session 三处来源都能对上。

## 六、必须主动说明的边界

- 当前真实长音频、麦克风采集、说话人分离和时间戳对齐不在交付范围；
- 当前图谱关系是确定性词法近似，不声称是 Embedding 语义相似；
- Stub provider 保障本地运行，真实 LLM 是可替换 Provider，不把固定话术冒充成模型能力；
- 反馈报告是描述性统计，不是实验结论；
- 当前未做真实外部部署、GitHub 推送和干净环境复现；这些应在项目完成后单独验证。

## 七、代码定位

- 图谱读模型：`backend/graph.py`；
- 数据契约：`backend/models.py`；
- session 持久化与迁移：`backend/store.py`；
- 路由编排和来源校验：`backend/main.py`；
- Agent 工具与计划：`backend/agent.py`；
- 图谱与 Agent 页面：`frontend/src/App.tsx`；
- 前端 API 类型：`frontend/src/api.ts`；
- 相关回归测试：`tests/test_graph.py`、`tests/test_agent.py`。
