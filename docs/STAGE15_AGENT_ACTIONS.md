# 阶段 15：Personal Agent 受控行动工具

## 目标

阶段 12 的 Agent 只能读取画像、SM-2 复习项、训练历史和简历。本阶段增加第一个受控写工具：`create_learning_plan`。用户明确请求制定、生成或安排学习计划时，Agent 才能根据已经读取的上下文生成计划草稿，并保存到当前用户自己的 SQLite 数据库，等待用户确认。

## 端到端链路

```text
用户请求“生成今天的个性化学习计划”
  -> Agent 规划器返回工具意图
  -> 规范化器过滤非法工具，并强制排列为“读取 -> 写入”
  -> read_profile / read_due_reviews / read_recent_sessions
  -> create_learning_plan
  -> learning_plans 表持久化为 draft
  -> Agent 回答 + 待确认计划卡片
  -> 用户确认后转为 active
```

## 为什么只做一个写工具

- 写工具不是任意 SQL，也不直接接受模型生成的表名和字段名；
- 只有明确的计划请求才能触发写入，普通“我该复习什么”仍然是只读建议；
- 所有计划查询和写入都带 `user_id`，用户不能读取其他人的计划；
- 计划项由后端确定性规则生成，模型负责理解请求和选择工具，避免把未经校验的自由文本直接写入业务状态；
- 画像、SM-2 参数、简历和历史会话不会被这个工具直接修改。

## 数据结构

`learning_plans` 保存计划元信息、计划项和生成来源：

- `title`、`summary`、`status`：计划展示和 draft/active/completed 生命周期；
- `items_json`：最多 5 个计划项，每项包含 topic、point、action、reason、duration、priority 和 scheduled_for；
- `source_json`：到期复习数、长期薄弱点数、近期训练数和生成版本；
- `source_message`：用户的原始计划请求，限制长度后保存；
- `user_id`：所有读写接口的隔离边界。

接口：

- `POST /api/agent/chat`：触发 Agent 规划，响应中的 `created_plan` 返回本次新计划；
- `GET /api/agent/plans`：读取当前用户的计划列表；
- `GET /api/agent/plans/{plan_id}`：读取当前用户的单个计划。
- `POST /api/agent/plans/{plan_id}/confirm`：将草稿确认成 active 计划；
- `POST /api/agent/plans/{plan_id}/items/{item_id}/complete`：幂等地完成一个计划项，全部完成后计划变成 completed。

## 当前边界

这还不是完整的任务管理系统：当前没有拖拽排序、提醒任务或自动改写 SM-2，也没有把完成计划项反向写入能力画像。

## 面试追问卡

### 为什么不让 Agent 直接修改画像？

画像是长期状态，错误写入会污染后续出题和复习。因此先写入独立的 `learning_plans` 表，把可逆、可观察的计划和核心画像隔离。草稿确认和计划项完成也只改变计划状态，不直接写回画像。

### 如何避免模型绕过权限？

工具名称由后端白名单控制；规划结果会重新解析和规范化，非法工具被丢弃；写工具还要满足“用户明确提出计划请求”和“读取工具先执行”两个条件。模型不能提交 SQL、文件路径或任意数据库字段。

### 为什么计划项先用规则生成？

当前目标是验证 Agent 的工具调用和长期状态链路。规则生成让计划可解释、可测试、可复现；未来可以让 LLM 提供候选排序，但仍需要结构化 schema、字段校验和用户确认后再落库。
