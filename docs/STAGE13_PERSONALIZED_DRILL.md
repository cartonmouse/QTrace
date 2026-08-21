# 阶段 13：个性化动态出题与画像 v1

## 目标

把“画像”和“SM-2”从页面上的展示数据，接到下一轮专项训练的输入中。完成后，专项训练不再只是读取固定高频题库，而是先根据用户当前状态安排本轮题目：

```text
画像 + 领域掌握度/趋势 + 到期复习项 + 近期训练 + 知识库/高频题
    -> DrillQuestionGenerator
    -> 结构化题目计划
    -> InterviewEngine 的 question_bank
    -> 回答和复盘
    -> 全局画像、领域画像、review_items
```

这不是重新实现完整 TechSpar 的知识图谱，而是先把最重要的“长期信号影响下一次训练”闭环做实。

## 本阶段实现

### 1. 独立的动态出题适配器

`backend/personalized_drill.py` 定义了 `DrillQuestionGenerator` 边界，并提供两种实现：

| 实现 | 是否联网 | 作用 |
| --- | --- | --- |
| `StubDrillQuestionGenerator` | 否 | 按确定性规则把到期项、薄弱点和高频题组合成题目计划，保证没有 API Key 也能运行 |
| `LLMDrillQuestionGenerator` | 是 | 把画像、SM-2 队列、近期训练和知识上下文发送给 OpenAI-compatible 模型，要求返回结构化 JSON |

LLM 出题的 JSON 契约是：

```json
{
  "questions": [
    {
      "question": "请说明你会如何验证 RAG 的召回质量？",
      "focus": "RAG 评估",
      "difficulty": 4,
      "reason": "当前掌握度已经进入工程验证阶段"
    }
  ]
}
```

后端会做 JSON 解析、题目去重、长度限制、难度范围限制和空结果拒绝，再把 `questions` 这一组纯字符串交给已有 `InterviewEngine`。模型不能绕过这层直接写数据库。

### 2. 专项训练真正读取长期信号

`POST /api/interview/start` 在 `topic_drill` 模式下会读取：

- 全局画像：整体掌握度、长期薄弱点、强项、行为信号和行动项；
- 当前领域画像：训练次数、累计掌握度、最近得分、趋势和领域薄弱点；
- `review_items`：当前领域到期的 SM-2 复习项；
- 最近几次该领域训练的分数、薄弱点和行动项；
- 当前领域知识上下文与高频题库。

到期复习项优先进入本轮题目。没有到期项时，Stub 会根据领域掌握度安排基础概念、工程取舍或开放式追问；LLM 模式则根据相同输入生成 4—8 道结构化题目。

题目计划最终仍然交给原来的 `InterviewEngine`，所以阶段推进、回答接口、历史快照和结束复盘都没有被新逻辑复制一份。这是本阶段的重要边界：出题策略可以替换，训练状态机不需要跟着变化。

### 3. 画像结构化写回

`profiles` 新增：

- `strong_points_json`：复盘抽取的稳定优势；
- `behavior_signals_json`：例如结构化表达、证据意识等行为信号；
- `action_items_json`：最近复盘形成的下一步行动。

`topic_profiles` 新增：

- `recent_scores_json`：最近最多 8 次领域得分；
- `trend`：根据相邻得分标记为 `new`、`improving`、`declining` 或 `stable`。

数据库使用显式迁移，因此已有本地 SQLite 不需要删除重建。每次训练首次生成复盘时才写回画像，保留原来的幂等性。

### 4. 复盘协议扩展

Stub 和真实 Provider 的 Review 现在都支持 `behavior_signals`。真实模型复盘提示词要求返回：

```text
summary, average_score, scores, strengths, weak_points,
behavior_signals, action_items
```

这些字段先经过统一解析，再进入画像和复习调度。旧模型没有返回 `behavior_signals` 时，解析器会使用空数组，旧接口仍然可用。

## 代码调用链

```text
POST /api/interview/start
  -> main.start_interview()
  -> get_topic_bundle()
  -> Store.get_profile()
  -> Store.get_topic_profile()
  -> Store.list_due_reviews()
  -> build_drill_question_generator()
  -> generator.generate()
  -> normalize_drill_plan()
  -> InterviewEngine.start(question_bank=...)

POST /api/interview/{id}/finish
  -> InterviewEngine.finish()
  -> Provider.review()
  -> Store.update_profile_after_review()
  -> profiles + topic_profiles + review_items
```

## 为什么先做“题目计划”，不直接让 Agent 全程控制面试

本阶段的问题是“本轮专项训练应该练什么”，它适合用一个受约束的生成器回答。`InterviewEngine` 仍然负责阶段顺序和结束条件，Agent 仍然负责解释画像和给建议。

如果让 Agent 同时决定题目、推进阶段、写回画像和修改复习项，权限和失败边界会混在一起。先把“画像 -> 题目计划”做成一个可测试的模块，后续再考虑让 Personal Agent 通过需要用户确认的写工具创建训练计划。

## 验证结果

- 后端测试：`23 passed`；
- 覆盖 Stub 优先到期项、LLM JSON 契约、非法题目拒绝、旧数据库迁移、画像信号写回和专项训练路由接入；
- Python `compileall`：通过；
- 前端 `npm run typecheck`：通过；
- 前端 `npm run build`：通过；
- 运行态黑盒验证：本地 Stub 专项训练启动成功，下一题来自领域高频题库；训练完成后 `/api/profile` 返回强项、行为信号、行动项和领域趋势；
- 真实 LLM 连通性验证：OpenAI-compatible 请求成功返回合法 JSON；
- 真实业务联调：`POST /api/agent/chat` 返回 200，`topic_drill` 启动返回 200，真实追问返回 200；Agent 返回回答和工具轨迹，动态专项训练返回非空开场与追问；
- 真实结构化复盘：`POST /api/recording/analyze` 在 `analysis_mode=llm` 下返回 200，摘要、浮点评分和行动项成功解析并写入复盘会话；
- 联调使用了当前账号的画像/复习上下文，但没有上传真实简历文件，也没有在日志或文档中输出 API Key。

## 面试追问准备

### 问：你的个性化出题到底个性化在哪里？

答：专项训练启动时会读取当前用户的全局画像、领域掌握度和趋势、领域薄弱点、SM-2 到期复习项以及最近训练结果。到期薄弱点优先进入题目计划，领域掌握度较低时偏概念和边界，掌握度较高时增加工程取舍、验证和开放场景题。LLM 只负责生成结构化题目，后端负责校验和交给统一状态机执行。

### 问：为什么不直接随机抽高频题？

答：随机抽题只利用题库，不利用用户状态。它不能保证今天优先复习到期薄弱点，也不能根据掌握度改变难度。当前实现保留高频题作为参考，但先用复习队列和画像调整题目顺序与关注点。

### 问：SM-2 在系统里具体影响了什么？

答：复盘产生的薄弱点会进入 `review_items`。调度器根据得分更新间隔和下一次复习日期；专项训练启动时读取当前领域到期项，把它们放到本轮问题计划前面。SM-2 不负责生成题目内容，只负责决定哪些知识点现在值得优先复习。

### 问：LLM 返回自然语言或错误 JSON 怎么办？

答：出题器只接受 JSON 对象，后端会去除代码围栏、解析对象、检查 `questions` 数组、去重、限制题目数量和难度范围。解析失败或空题目直接返回错误，不把不可信的自然语言写进会话或画像；Stub 模式可以继续作为离线开发基线。

### 问：为什么要把最近得分序列存下来？

答：单个累计平均分看不出近期变化。保存最近最多 8 次领域分数后，可以用简单可解释的相邻得分差标记上升、下降或稳定，先为动态难度和 Agent 建议提供输入。它还不是经过校准的能力测量，后续需要题目难度、盲评一致性和离线评估集。

### 问：这是不是已经等同于 TechSpar 的知识图谱和完整用户画像？

答：不是。当前完成的是画像信号、SM-2 调度和动态出题的最小闭环；还没有实现知识实体/关系图谱、向量记忆、跨领域概念传播和完整的多 Agent Personal Agent。面试中应明确这是独立重建项目的 v1 阶段。

## 下一步

1. 补充不同模型返回风格下的 JSON 错误提示测试；
2. 检查真实模型超时、限流和失败重试策略；
3. 再决定是否增加 Agent 的“生成训练计划”写工具，并设计用户确认；
4. 最后做发布收口、README、截图和面试讲解材料；GitHub 创建、提交和推送仍需单独确认。
