# Stage38：图谱候选离线评估报告

## 目标

Stage37 已经记录了相近题候选入口的开始/完成次数。本阶段把这些行为和已保存的复盘分数整理成只读评估报告，回答“候选入口是否被使用、是否完成、训练分数有没有变化”，但不把报告结果写回任何事实源。

```text
sessions + review_json
        ↓
按 parent_question_id / graph_question_id 聚合
        ↓
完成率 / 平均复盘分 / 首末分差 / 重复训练比例
        ↓
GET /api/graph/{topic}/feedback
        ↓
图谱页评估面板
```

## 指标定义

对每一条当前仍存在的 `related` 边：

- `started_count`：从 `related_neighbor` 入口创建的专项训练 session 数；
- `completed_count`：上述 session 中 `is_finished=1` 的数量；
- `completion_rate`：`completed_count / started_count`，无样本时为 0；
- `average_score`：完成 session 的 `review.average_score` 平均值，没有有效复盘分数时为空；
- `score_delta`：按 session 时间排序的最后一次有效复盘分数减第一次有效复盘分数，少于两次有效分数时为空；
- `repeat_rate`：`max(started_count - 1, 0) / started_count`，用于识别同一候选边是否被重复练习。

这些指标是描述性统计，不是因果结论。分数变化可能受焦点、时间和其他训练影响，系统不声称候选一定提升了能力。

## 数据边界

- 只读取当前用户、当前主题、`graph_entry_source=related_neighbor` 的 session；
- 只报告当前图谱仍然存在的 related 边，旧题目删除或关系消失后不继续显示为有效候选边；
- 普通图谱问题训练、Agent 主题级计划和其他主题数据不计入；
- 失败或没有 `review.average_score` 的复盘不进入平均分和 score_delta，但仍然保留在 started/completed 计数中；
- 评估接口是 GET，不修改 session、画像、SM-2、计划或图谱边权。

## 前端展示

图谱页增加“候选反馈评估”面板：展示候选边总数、观察到行为的边数和候选入口训练总次数；逐边展示完成率、平均分和分数变化。没有样本时明确显示“尚无反馈样本”，避免把 0 当成低质量结论。

## 验证重点

- 没有行为数据时报告为空且 summary 为 0；
- 一个已开始但未完成的 session 只增加 started_count；
- 完成并有复盘分数后进入 completed/average_score；
- 两次有分数的候选训练可以产生 score_delta；
- 其他用户、其他主题和非 related_neighbor session 不会混入；
- 删除/修改题库后，报告只保留当前图谱中的 related 边；
- 旧数据库可以通过增量迁移读取，现有阶段测试继续通过。

## 当前限制与下一步

本报告只做候选入口的描述性评估，不是 A/B 实验，也没有控制变量。后续如果积累了足够的本地样本，可以设计更严格的离线评估或 Embedding 对照，但仍需保留当前确定性规则作为可复现基线。
