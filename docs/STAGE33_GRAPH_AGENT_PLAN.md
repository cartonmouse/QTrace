# Stage33：图谱到 Agent 计划联动

## 目标

Stage32 的知识图谱已经能解释一个主题里有哪些问题、哪些关系和哪些 SM-2 待复习点。本阶段把它接到已有 Personal Agent 的受控行动链路：用户从某个主题图谱进入 Agent 后，Agent 只围绕这个主题读取复习队列，并生成带主题来源的 draft 计划。

```text
知识图谱 /rag
    ↓ 主题上下文
Personal Agent /agent?topic=rag
    ↓ 后端校验 topic
read_due_reviews(topic=rag)
    ↓
create_learning_plan(source.topic=rag)
    ↓ 用户确认
专项训练 -> 复盘 -> 画像 / SM-2 写回
```

这是一条“主题作用域”链路，不是给图谱增加第二套计划业务。

## 为什么需要主题作用域

Personal Agent 原本可以读取全局到期复习队列，适合回答“我今天总体应该复习什么”。但从某一张主题图谱进入 Agent 时，用户表达的是更窄的意图：先处理这个主题中的待复习点。

如果仍然读取全局队列，会产生两个问题：

1. Agent 可能把 Python、RAG 和 Agent 的到期项混在同一张计划里，用户无法理解它为什么从当前图谱跳到了别的领域；
2. 计划项虽然可以进入训练，但没有保存“这张图谱为什么触发了它”的来源，后续复盘难以解释。

因此 Stage33 增加可选的 `topic` 请求字段，同时保留没有主题时的旧行为。

## 后端契约

`AgentChatRequest` 新增：

```json
{
  "message": "请根据知识图谱生成今天的专项复习计划。",
  "topic": "rag"
}
```

处理顺序：

1. `/api/agent/chat` 读取 `topic`；
2. 后端用当前用户的 `list_topics` 校验主题 key，未知主题直接返回 400；
3. `run_personal_agent` 把主题传给工具执行层；
4. `read_due_reviews` 调用 `store.list_due_reviews(user_id, topic=topic)`；
5. `create_learning_plan` 调用 `_build_learning_plan(..., topic=topic)`；
6. 计划的 `source.topic` 保存这个作用域，计划项仍然复用现有 `spaced_review` 类型。

没有 `topic` 的旧请求继续读取全局到期队列，保证现有 Agent 对话和接口兼容。

## 前端入口

知识图谱页面新增：

```text
让 Agent 安排复习 ↗
```

它跳转到 `/agent?topic=<topic>`。Agent 页面读取 query 参数后：

- 预填主题复习计划请求；
- 在输入区提示当前计划限定在哪个主题；
- 发送时把主题作为独立字段提交，而不是只把主题拼进自然语言；
- 仍然展示原有 Agent 规划、工具轨迹、draft/confirm 和计划项训练入口。

把主题作为结构化字段传递的好处是后端可以验证和过滤；自然语言只适合作为模型理解上下文，不能作为权限边界。

## 与图谱事实源的边界

Agent 不直接读取 `backend/graph.py` 的 SVG 布局，也不把所有问题节点复制成计划项。当前关系如下：

| 数据 | 责任模块 |
| --- | --- |
| 主题、高频问题、相近关系 | `graph.py` 只读图谱视图 |
| 到期复习点、间隔、ease factor | `review_items` + Store |
| 计划草稿、确认状态、计划项 | `learning_plans` + Store |
| 训练回答、复盘、画像写回 | InterviewEngine + Store |

本阶段只把主题作用域和到期队列连接起来。这样每个模块的事实边界仍然清楚，后续可以再讨论是否把某一条具体问题节点也绑定到计划项。

## 安全和行为边界

- topic 由后端按当前用户重新校验，不能通过伪造 URL 读取别人的主题数据；
- 主题过滤只影响 Agent 读取的到期复习项，不改变用户的复习间隔；
- Agent 生成的计划仍然先是 `draft`，必须由用户确认后才会进入 `active`；
- 点击“让 Agent 安排复习”不会创建计划，只有用户真正发送明确计划请求才会触发 `create_learning_plan`；
- 训练结束也不会自动把计划项标记为完成，用户需要显式确认完成，避免把打开页面或提交无效回答误判为学习完成。

## 验证结果

新增回归测试验证：

- RAG 和 Python 各有到期项时，topic=`rag` 的 Agent 计划只安排 RAG 到期项；
- 计划 `source.topic` 保存为 `rag`；
- 未知 topic 返回 400；
- 既有 Agent 对话、否定计划语义、用户隔离和计划确认测试保持通过。

暂存工程验证结果：后端 `48 passed`，Python `compileall`、前端 `npm run typecheck` 和 `npm run build` 均通过。

## 面试追问准备

### 为什么不把 topic 只放在自然语言中？

因为自然语言是模型输入，不应该承担权限和数据过滤职责。结构化 topic 可以由后端验证，并直接传到 Store 的主题过滤参数。

### 为什么计划来源还要记录 topic？

因为“读取了哪个主题”与“计划当前包含哪些项目”是不同信息。来源元数据帮助复盘时解释计划触发原因，也方便后续审计和 UI 展示。

### 为什么不让图谱直接创建计划？

打开图谱是读操作，直接写计划会让浏览行为产生副作用。当前仍由用户发送明确请求触发受控写工具，再经过 draft/confirm 状态机。

### 这算不算多 Agent？

不算。这里仍然是一个 Personal Agent，通过主题作用域改变同一个 Agent 的工具上下文；没有新增独立 Agent、消息总线或跨 Agent 协议。

## 当前限制与下一步

当前计划只绑定到主题和复习点文本，还没有绑定到图谱中的具体 `question:<id>` 节点。下一步可以在不复制图数据的前提下，为确定性关系最强的题目生成 `question_id` 计划元数据，再由专项训练入口优先选择该问题，同时继续保留 SM-2 队列的权威状态。
