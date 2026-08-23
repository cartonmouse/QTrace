# 阶段 18：学习计划驱动专项训练

## 目标

阶段 17 已经让学习计划成为可恢复的业务状态，但“完成计划项”仍然只是手动状态更新。阶段 18 把计划项连接到已有的专项训练入口，让用户可以从计划直接开始一次带焦点的训练。

## 模块接口和 seam

本阶段保留三个职责清晰的模块：

1. `LearningPlan` 模块负责读取计划项、确认状态和记录完成状态；
2. `TopicDrillPage` 负责把计划项转换成训练入口，并让用户选择或确认领域；
3. `DrillQuestionGenerator` 模块负责根据画像、SM-2 和 `requested_focus` 生成题目，最终仍交给 `InterviewEngine`。

计划模块不直接调用 `InterviewEngine`。两者之间的 seam 是已有的 `POST /api/interview/start` 接口，新增可选的 `focus` 字段：

```text
计划项
  -> /topic-drill?topic=<topic>&focus=<point>
  -> POST /api/interview/start { mode: "topic_drill", topic, focus }
  -> DrillQuestionGenerator.generate(requested_focus=focus)
  -> InterviewEngine.start(question_bank=...)
```

这样训练状态机仍只有一个实现，计划只是选择训练目标；后续如果替换出题器，TopicDrill 页面和 Agent 都不需要跟着修改。

## 计划焦点如何生效

- Stub 出题器把 `requested_focus` 放入本轮题目首位，并标记原因是“由学习计划项指定”；
- LLM 出题器把它放入结构化输入的 `plan_focus`，提示模型至少生成一道直接覆盖该焦点的题；
- 后端仍会对题目做 JSON 解析、去重、数量和难度校验；
- 进入专项训练不会自动把计划项标记为完成，只有用户完成训练并确认行动后才改变计划状态。

## 到期复习容量取舍

Agent 当前最多把前 3 个到期复习点纳入当天计划，避免一次生成过量任务。阶段 18 将摘要改为“已安排数/到期总数”，例如：

```text
优先处理 3/6 个到期复习点
```

剩余任务不会消失，仍留在 SM-2 队列中；下一次生成计划时可以继续读取。这个限制是确定性业务规则，不由 LLM 自行决定，回答中也必须明确说明。

## 验证结果

- 阶段定向测试和正式目录全量测试均通过：`29 passed`；
- Python `compileall`、前端 `npm run typecheck` 和 `npm run build` 通过；
- 运行态 `/api/health` 返回 `status=ok, mode=qtrace`，OpenAPI 的 `StartInterviewRequest` 已包含 `focus`；
- 真实账号页面已出现“进入专项训练”按钮；点击后跳转到 `/topic-drill`，页面显示计划焦点且没有自动提交新的真实 LLM 请求；
- 当前计划项的领域是“综合能力”，系统没有擅自映射到某个具体知识领域，而是让用户在页面选择领域。

## 面试追问卡

### 为什么计划不直接调用 InterviewEngine？

计划和训练是两个不同的模块。计划负责“应该练什么”，InterviewEngine 负责“如何推进一轮训练”；通过已有 start 接口传递 focus，可以避免复制状态机和扩大 Agent 权限。

### focus 为什么是可选字段？

普通专项训练不一定来自学习计划，旧客户端也只发送 topic。因此 focus 采用可选字段，空值时保持原来的画像、SM-2、知识库和题库逻辑不变。

### 进入训练后为什么不能自动标记计划完成？

开始训练只代表用户开始行动，不代表训练已经完成，更不代表能力已经提升。计划完成仍需要用户标记或后续把训练会话完成事件接入审计逻辑；掌握度继续由回答和复盘决定。

### 为什么不把 6 个到期点全部塞进一份计划？

学习计划需要可执行性。当前用最多 3 个到期项控制当天负担，并在摘要中显示 `3/6`，避免给用户造成“系统遗漏”的错觉。后续可以让用户确认是否扩展容量，但这应是明确的业务动作。

## 当前限制

- 计划项进入专项训练时还没有保存 `plan_id/item_id` 到训练会话；当前先传递 focus，保持训练主链改动最小；
- 没有完成训练后自动回写计划项的审计关联；
- 还没有独立计划历史页、提醒、拖拽排序和画像/SM-2 自动写回。
