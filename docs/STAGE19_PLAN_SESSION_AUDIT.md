# 阶段 19：学习计划项与训练会话审计关联

## 目标

阶段 18 已经让计划项能够把 `focus` 带入专项训练，但训练结束后仍无法回答“这一次训练到底对应哪个计划项”。本阶段增加最小的业务关联：训练会话记录来源计划和计划项，复盘页提供显式的完成动作。

## 关键设计

计划模块和 `InterviewEngine` 继续保持独立。两者之间的 seam 是 `POST /api/interview/start` 和 `sessions` 表中的两列：

```text
学习计划卡
  -> /topic-drill?focus=...&plan_id=...&plan_item_id=...
  -> POST /api/interview/start
  -> 校验当前用户拥有该计划，且计划已经 active
  -> InterviewEngine.start()
  -> sessions.learning_plan_id / learning_plan_item_id
  -> 复盘页显式“完成这个计划项”
  -> POST /api/agent/plans/{plan_id}/items/{item_id}/complete
```

新增字段：

- `StartInterviewRequest.plan_id`、`plan_item_id`：只用于从计划进入专项训练；
- `SessionView.learning_plan_id`、`learning_plan_item_id`：向前端返回会话来源；
- `sessions.learning_plan_id`、`sessions.learning_plan_item_id`：作为训练历史快照保存。

后端会拒绝只提供其中一个 ID、把计划关联到简历面试模式、跨用户访问计划，或在计划仍是 `draft` 时进入训练。计划项的领域不强制覆盖当前领域：`综合能力` 没有可靠的题库映射，前端仍然允许用户选择领域；如果计划项有具体领域键，则自动预选该领域。

## 为什么不自动完成计划项

“开始训练”只能证明用户打开了训练，“完成训练”只能证明产生了复盘结果，都不能证明用户已经掌握该知识点。自动完成会把行为事件误当成学习结果，污染计划状态。当前流程把训练结果作为证据，把“完成计划项”保留为用户看完复盘后的显式动作；后续如果要自动化，应先定义成绩阈值、回答质量和重复练习等更可靠的完成规则。

## 数据迁移

`Store._migrate_sessions()` 只增加两个可空字段，不删除旧会话。旧记录读取时字段为空，历史和复盘页面继续正常工作。新会话即使计划项已经完成，也允许再次训练；训练和计划完成是两个可独立审计的事件。

## 面试追问速答

### 为什么把关联放在 sessions，而不是让 InterviewEngine 直接管理计划？

`InterviewEngine` 的职责是阶段推进、回答和复盘，不应该知道 Agent 计划表的业务语义。把关联作为 session metadata 保存，既能保留历史快照，又不让状态机依赖计划 Store。

### 如何保证计划关联不会越权？

解析计划项时调用带 `user_id` 的 Store 查询；计划不存在、属于其他用户或计划项不存在时统一返回不可用结果。前端的 URL 参数只是提示，真正的权限校验在后端。

### 计划项如何影响题目？

`focus` 仍然通过现有 `DrillQuestionGenerator` 契约进入 Stub/LLM 出题器；`plan_id/item_id` 只用于审计来源，不参与面试阶段推进。这样内容选择、会话状态和业务审计各自有清晰职责。

### 如果用户刷新复盘页，完成操作是否还有效？

有效。会话和计划都已经持久化，复盘页会按会话中的关联 ID 重新读取计划；完成接口是幂等的，重复点击不会重复生成记录。

## 验证结果

- 暂存工程后端：`30 passed`；
- 正式工程后端：`30 passed`；
- Python `compileall`：通过；
- 前端 `npm run typecheck`：通过；
- 前端 `npm run build`：通过；
- 运行态 `/api/health`：`{"status":"ok","mode":"qtrace"}`；
- 运行时 SQLite 已出现 `learning_plan_id`、`learning_plan_item_id` 两个迁移字段；
- 真实账号页面验证：计划入口 URL 同时带有 `focus`、`plan_id`、`plan_item_id`，专项训练页显示计划焦点；没有提交新的真实 LLM 请求。

## 当前限制

本阶段仍不做计划提醒、独立计划历史页、自动根据成绩完成计划，也不把计划完成按钮直接写入掌握度或 SM-2。下一步可以先做干净环境复现和发布收口，再决定是否需要更复杂的计划统计。
