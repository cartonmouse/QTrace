# Stage39：Agent 读取图谱候选反馈

## 目标

Stage38 已经有候选反馈评估报告，但 Agent 的 `read_graph_question` 只知道候选问题和关系权重。本阶段把同一份 related link 行为统计补充到 Agent 的只读上下文，让 Agent 能解释候选的历史训练使用情况。

```text
read_graph_question
  -> related_questions
  -> related edge weight + started/completed
  -> Stub/LLM 回答与计划元数据
```

## 数据边界

- Agent 只读取当前用户、当前主题和当前图谱中的 related 边；
- `started_count` 与 `completed_count` 来自 Stage37 的 session 审计，不是模型推断；
- 反馈字段只作为候选解释元数据，不触发新的计划项、不修改画像/SM-2/边权；
- Agent 仍然不能把“有人练过”描述成“这道题更重要”或“用户已经掌握”。

## 返回字段

每个 `related_questions` 候选增加：

- `started_count`：从该候选入口开始的训练次数；
- `completed_count`：已完成并产生复盘的次数；
- `completion_rate`：完成率，只有开始过才计算；

`weight` 仍然只是确定性关系强度。Agent 计划保存这些字段作为来源元数据，方便复盘时解释候选背景。

## 验证重点

- 没有候选训练时反馈字段为 0/0/0；
- 有候选训练时 Agent 读取结果和计划 source 保留最新统计；
- 用户隔离和主题隔离继续有效；
- Agent 不因为候选反馈自动扩展学习计划。

## 当前限制

反馈统计仍是描述性行为数据，不能代表语义质量、掌握度或学习因果收益。真实 Embedding、离线对照和更严格的实验设计继续保持为后续可选工作。
