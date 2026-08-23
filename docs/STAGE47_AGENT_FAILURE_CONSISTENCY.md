# 阶段 47：Personal Agent 失败一致性

## 目标

阶段 46 已经让规划失败和回答失败拥有稳定的错误协议。本阶段继续处理失败之后的状态一致性：用户不能因为一次失败看到一条实际上没有持久化的对话消息，也不能因为回答失败丢失已经生成的学习计划草稿。

本阶段只使用 fake provider 和合成账号回归，没有调用真实 LLM，没有读取或上传真实简历/个人文档，没有部署、删除文件或提交推送 GitHub。

## 失败前的隐患

`run_personal_agent` 原先会在模型规划前创建 Agent 对话。若规划或回答失败，数据库可能留下一个没有消息的空对话。前端则会先乐观地显示用户消息，失败后只展示错误，导致页面看起来像已经保存了这条消息。

回答失败还可能发生在 `create_learning_plan` 工具已经成功写入 draft 之后。此时如果简单删除整条对话或计划，会破坏用户已经获得的可确认状态。

## 实现

### 后端状态判定

- 新建对话在规划或回答边界失败时，调用 `delete_empty_agent_conversation`；该方法同时校验 `user_id`、消息列表为空且没有关联学习计划，只允许清理这次失败产生的空壳对话；
- 如果是已有对话，保留原有历史，返回 `conversation_unchanged`；
- 如果新对话已经关联学习计划草稿，保留对话和计划，返回 `preserved_draft`；
- `AgentProviderError` 增加 `state`，API 错误 detail 在原有 `code`、`stage`、`message`、`retryable` 之外返回该状态；
- 不删除文件；这一步只处理一次 Agent 请求在 SQLite 中产生的、经过条件校验的空对话行。

### 前端状态恢复

Agent 发送失败时：

1. 移除刚刚添加的乐观用户消息；
2. 把文本恢复到输入框，方便用户修改或重试；
3. 若后端报告 `preserved_draft`，提示用户已有计划草稿仍然保留；
4. 保留后端返回的阶段化错误提示，不把失败伪装成成功回答。

## 测试

`tests/test_agent_errors.py` 覆盖：

- 规划失败返回 `agent_planning_failed` 和 `rolled_back`，且没有遗留空对话；
- 回答失败返回 `agent_answering_failed` 和 `rolled_back`，且没有遗留空对话；
- 学习计划草稿已写入后回答失败返回 `preserved_draft`，计划仍为 `draft`，关联对话仍存在。

本阶段验证结果：

```text
python -m pytest -q                 64 passed
python -m compileall -q backend scripts tests  passed
frontend npm run typecheck           passed
frontend npm run build               passed
```

## 面试讲解要点

### 为什么不直接删除失败请求产生的所有数据？

因为 Agent 的一次请求可能已经完成了受控写工具，例如生成学习计划草稿。清理策略必须区分“没有任何业务结果的空壳对话”和“已经产生可确认业务状态的草稿”，否则重试会让用户丢失计划或产生重复计划。

### 为什么状态由后端判定？

前端的消息和 URL 都是可被修改的客户端状态。只有后端持有对话、计划和用户归属信息，才能判断是否真的为空、是否存在关联计划，并保证清理不会越过用户边界。

### 这是不是事务？

它是失败补偿和条件清理，不是把模型网络调用纳入 SQLite 事务。模型调用无法回滚，因此系统在外部调用前后用最小持久化状态、明确的 draft 状态和幂等接口降低不一致风险。更严格的生产实现还可以继续引入请求幂等键和 outbox/audit 设计。

## 当前边界

本阶段没有新增真实 LLM 重试按钮，也没有把所有模块的错误协议统一；工具本身失败仍记录在 `tool_trace`，只有模型规划/回答边界进入本阶段的状态补偿。真实资料外发、外部部署、干净环境复现和 GitHub 提交推送仍需后续单独处理。
