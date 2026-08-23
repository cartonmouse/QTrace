# Stage29：Agent 追问卡计划

## 目标

Stage28 已经把项目追问卡接入专项训练，但用户还需要手动决定“这一张卡应该怎样安排进学习计划”。本阶段让 Personal Agent 接收一个显式的 `question_card_id`，先验证卡片，再生成带卡片来源的 draft 学习计划。确认计划后，计划项可以继续进入专项训练，并把卡片来源传入 session。

## 用户链路

```text
结构化简历编辑器
  -> 项目追问卡
  -> “让 Agent 制定计划”
  -> /agent?question_card_id=...
  -> 用户确认默认请求或编辑请求
  -> POST /api/agent/chat(question_card_id=...)
  -> Agent 强制 read_question_card
  -> 用户明确请求计划时 create_learning_plan
  -> draft 计划写入 card source/item metadata
  -> 用户确认计划
  -> 计划项进入 /topic-drill
  -> POST /api/interview/start(question_card_id=...)
```

Agent 不是因为 URL 中出现 ID 就自动写数据。只有消息明确包含“制定/生成/安排计划”等意图时，`create_learning_plan` 才会被允许；否则只读取卡片并给出解释。计划仍然先保存为 `draft`，用户确认后才变成 `active`。

## 后端设计

### 显式参数而非从自然语言猜 ID

`AgentChatRequest` 增加可选的 `question_card_id`。卡片 ID 不从消息文本中正则提取，避免模型或用户输入一段看似相同的字符串就触发错误资料。`run_personal_agent` 在创建会话和执行工具前，调用 `StructuredResumeService.get_question_card(user_id, card_id)` 做一次用户隔离校验。

校验失败直接返回 404，不创建空的 Agent 会话，也不写入学习计划。这样另一位用户即使知道卡片 ID，也只能得到“不存在或不属于当前简历版本”。

### 受控工具

新增只读工具 `read_question_card`：

- 返回项目名、类别、问题、目的、字段引用和结构化简历版本；
- 由后端强制加入 Agent tool plan，真实 LLM 不能通过漏写工具调用来绕过验证；
- 只读取当前用户的卡片，不修改简历、画像、SM-2 或训练记录。

如果同时请求个人资料检索，检索查询会自动附加卡片项目名和类别，让文档证据更容易命中，但仍然沿用 Personal Document 的用户隔离和 citation。

## 计划如何保存卡片来源

当 `create_learning_plan` 执行时，`_build_learning_plan` 会优先生成一个 `project_followup` 计划项：

```json
{
  "type": "project_followup",
  "topic": "综合能力",
  "point": "问迹 QTrace：关键设计",
  "question_card_id": "project-1-question-3",
  "question_card_project": "问迹 QTrace",
  "question_card_resume_version": 2
}
```

同时，计划的 `source.question_card` 保存卡片 ID、项目名、类别和简历版本。计划项的 `topic` 暂时使用“综合能力”，因为一张项目卡可能横跨 Agent、RAG、后端和系统设计多个领域；用户进入专项训练页面后仍需明确选择具体领域，避免 Agent 把项目问题强行映射到错误题库。

## 为什么仍然需要 draft 和确认

追问卡属于用户的项目事实，学习计划属于会改变后续训练节奏的持久化动作。把两者连接起来不代表 Agent 可以替用户安排一切：

- 读取卡片是只读动作，可以自动执行；
- 生成计划是写动作，但只生成 `draft`；
- 用户确认后计划才是 `active`；
- 进入训练和结束训练都不会自动把计划项标记为完成；
- 只有复盘结果和用户显式操作才会影响后续状态。

这条边界让 Agent 有实际行动能力，但仍然可解释、可撤回和可测试。

## 前端行为

结构化简历页面的每张追问卡现在有两个入口：

- “进入专项训练”：直接进入已有专项训练页面；
- “让 Agent 制定计划”：进入 Personal Agent 页面，预填一条可编辑的计划请求，并携带 `question_card_id`。

Agent 计划卡中的项目追问项保留 `question_card_id`。确认计划后点击“进入专项训练”，前端将该 ID 再次带入专项训练 URL，最终由后端验证并保存到 session。用户可以在面试页、复盘页和历史记录中看到来源。

## 可用于面试的追问

### 为什么不让 Agent 直接调用 `create_learning_plan` 并把项目名放进文本？

项目名和自然语言描述不是可靠的身份键。显式卡片 ID 让后端能够按用户和当前版本重新解析事实；计划保存的是经验证的来源元数据，而不是模型自己猜出的项目。

### 为什么要强制 `read_question_card`，不能只在提示词里要求模型读取？

提示词是软约束，模型可能漏掉工具调用。后端在有 `question_card_id` 时把只读工具插入规范化后的 tool plan，并在执行前验证归属，使安全边界不依赖模型是否听话。

### 为什么计划项主题是“综合能力”？

项目追问卡的“关键设计”可能同时涉及 Agent、RAG、数据库和前端，单凭问题类别无法安全映射到一个领域。让用户在专项训练页选择领域，比 Agent 静默选择错误题库更可解释；计划焦点和卡片来源仍然会保留。

### 这是不是多 Agent？

不是。这里仍然是一个两步 Personal Agent：规划器决定读取/写入工具，执行器读取数据并生成 draft，回答器基于工具结果回复。新增的是一个受控工具和来源 seam，不是并行 Agent 编排。

## 验证结果

- `AgentChatRequest` 支持可选 `question_card_id`；
- 当前用户卡片验证失败时返回 404，不创建会话或计划；
- Agent tool trace 会显示 `read_question_card` 和 `create_learning_plan`；
- draft 计划的 `source.question_card` 和项目计划项都保存卡片 ID、项目名和简历版本；
- 计划项进入专项训练时会继续传递卡片来源；
- 暂存工程后端 `44 passed`，Python compileall、前端 typecheck 和生产构建通过。

## 当前限制与下一步

- 卡片仍然需要用户在专项训练页选择具体领域；
- Agent 还不会根据 JD 自动为项目卡生成领域权重或改写问题；
- 计划草稿没有独立的“取消/归档”动作，目前主要通过不确认保持 draft；
- 下一步可以继续做岗位 JD focus 与项目字段的匹配解释，再统一进行干净环境复现；真实资料联调、外部部署和 GitHub 推送仍需单独确认。
