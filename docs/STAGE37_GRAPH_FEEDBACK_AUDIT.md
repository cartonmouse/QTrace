# Stage37：图谱候选训练反馈审计

## 目标

Stage36 把 `related` 边变成了可选候选，但系统还不知道用户是否真的从候选进入训练、训练是否完成。本阶段增加最小的行为审计闭环，用于评估候选入口是否值得保留：

```text
当前问题节点
  -> 用户点击相近问题候选
  -> graph_entry_source=related_neighbor
  -> 记录父问题 ID/快照
  -> 专项训练与复盘
  -> 图谱 related 边展示开始次数/完成次数
```

这是一份行为统计，不是新的能力画像，也不是第二套 SM-2。系统不根据次数自动改写 related 边权、掌握度或复习间隔。

## 数据契约

训练会话新增三个来源审计字段：

- `graph_entry_source`：`question_node` 或 `related_neighbor`；缺省的旧链接按 `question_node` 兼容；
- `graph_parent_question_id`：当来源为 `related_neighbor` 时，记录用户从哪一个问题节点看到候选；
- `graph_parent_question`：保存父问题快照，避免未来题库调整后审计含义漂移。

当来源为 `related_neighbor` 时，后端必须重新构建当前用户当前主题的图谱，并确认父节点的 `related_question_ids` 包含目标节点。前端不能通过伪造父节点文本制造关系。

## 统计规则

`related` 边的反馈统计只从当前用户、当前主题的 `sessions` 读取：

- started：已经创建专项训练 session 的次数；
- completed：`is_finished=1` 的次数；
- 两者都按父问题 ID + 目标问题 ID 组成的无向边聚合；
- 不把普通图谱节点训练、Agent 主题计划或非图谱训练计入候选反馈。

统计附加到图谱响应的 related link 上，前端在候选列表中展示。它是 read model，每次请求都可以从 session 事实源重建。

## 为什么不直接改边权

候选被训练一次只能说明用户选择过，不说明题目相似度更高，也不说明用户掌握度发生变化。完成次数还会受到时间、计划安排和用户偏好的影响。因此：

- related `weight` 继续表示确定性 token/中文二元片段关系强度；
- SM-2 继续由真实训练复盘评分更新；
- 用户画像继续由复盘结果更新；
- 候选反馈只用于之后离线评估候选入口的实用性。

## 前端入口

- 图谱问题列表的“按此题训练”发送 `graph_entry_source=question_node`；
- 相近问题候选的“练习相近题”发送 `graph_entry_source=related_neighbor` 和父问题 ID；
- 相近问题候选的“交给 Agent”保存同样的来源元数据，确认计划后进入训练仍然保留它；
- 复盘页显示这次是否来自相近问题候选，以及父问题快照。

## 验证重点

- 直接图谱问题训练保留 `question_node` 来源；
- 合法的 related candidate 可以启动训练并保存父问题；
- 非 related 的父子问题组合被后端拒绝；
- Agent 计划能保存候选来源，计划项训练后仍能传回来源；
- graph link 的 started/completed 统计只计入当前用户、当前主题和 related_neighbor；
- 旧数据库迁移后已有 session 仍可读取，旧链接按 direct node 兼容；
- 所有后端测试、前端类型检查、生产构建和本地运行检查继续通过。

## 当前限制与下一步

当前统计只回答“用户是否从候选入口训练过”，不能证明候选提高了学习效率，也没有使用真实 Embedding 或训练结果校准关系。下一阶段可以基于足够的本地行为样本设计离线评估指标，但仍需先保持确定性图谱作为基线。
