# Stage35：图谱问题到 Agent 计划

## 目标

Stage34 已经支持图谱问题直接进入精确专项训练。本阶段把同一个问题节点接入 Personal Agent 的受控计划链路，让用户可以先让 Agent 围绕这道题制定计划，再确认计划，最后回到 Stage34 的精确训练入口。

```text
图谱 question:1
        ↓
Agent 请求 topic=rag + graph_question_id=question:1
        ↓
read_graph_question（后端重读题库）
        ↓
create_learning_plan
        ↓
计划 source / item 保存节点 ID + 文本快照
        ↓ 用户确认
计划项进入专项训练
        ↓
graph_question_id 再次校验并写入 session
```

这使图谱、Agent、训练和复盘之间形成可解释的来源链，而不是让 Agent 自己猜测问题内容。

## 新增 Agent 工具

`AGENT_TOOLS` 新增只读工具：

```text
read_graph_question：读取当前主题知识图谱中的指定问题节点
```

工具执行时需要：

- 当前用户 ID；
- 当前主题 key；
- `graph_question_id`，格式为 `question:<n>`；
- 当前数据目录。

工具内部调用 Stage34 的 `get_topic_question`，从当前用户当前主题题库重新解析 ID，返回：

```json
{
  "id": "question:1",
  "topic": "rag",
  "question": "RAG 为什么需要 chunk？切分过大或过小分别会造成什么问题？"
}
```

即使 OpenAI-compatible Agent 规划器没有主动请求这个工具，后端在存在 `graph_question_id` 时也会把它强制加入读取计划。这是因为工具调用计划可以由模型生成，但数据归属和事实校验不能交给模型决定。

## 计划模型

当 `create_learning_plan` 执行时，`_build_learning_plan` 会优先生成一个 `graph_question` 类型的计划项：

| 字段 | 作用 |
| --- | --- |
| `topic` | 进入专项训练时选择的主题 |
| `point` | 图谱问题文本，作为计划项标题 |
| `graph_question_id` | 可重新校验的节点 ID |
| `graph_question` | 生成计划时读取到的问题快照 |
| `action` | 说明要围绕原理、取舍和验证指标作答 |
| `reason` | 说明该计划项由图谱节点触发 |

计划 source 同时保存：

```json
{
  "topic": "rag",
  "graph_question": {
    "id": "question:1",
    "topic": "rag",
    "question": "..."
  }
}
```

保存文本快照很重要：题库未来可能被编辑，同一个 `question:1` 之后可能指向另一道题。ID 说明来源，文本说明当时的计划事实。

## 前端行为

图谱问题列表现在提供两个入口：

- “按此题训练”：直接进入 Stage34；
- “让 Agent 制定计划”：进入 `/agent?topic=<topic>&graph_question_id=<id>`。

Agent 页面会：

- 预填“围绕这张图谱问题制定计划”的请求；
- 显示图谱问题 ID 和主题来源提示；
- 发送时把 `topic`、`graph_question_id` 作为结构化字段提交；
- 在计划项的训练按钮上继续传递 `graph_question_id`，从而回到精确问题训练。

自然语言只描述意图，结构化字段负责来源和权限边界。

## 与 Stage34 的衔接

计划项进入训练时，前端把：

```text
topic=<plan item topic>
graph_question_id=<plan item graph question id>
plan_id=<confirmed plan id>
plan_item_id=<plan item id>
```

一起提交。后端同时执行：

1. 计划必须已确认，不能从 draft 直接训练；
2. 主题必须存在；
3. 图谱问题 ID 必须属于当前用户当前主题题库；
4. 指定问题作为首个技术追问，session 保存图谱来源；
5. 计划项不会因为进入页面自动标记完成。

这样计划状态和训练来源是两条相互关联但不混淆的状态机。

## 为什么不复制图谱数据

图谱节点是从高频题库即时计算的 read model，Agent 计划只需要保存被用户选择的节点快照。将所有节点复制到计划表会造成：

- 题库修改后节点和计划事实难以同步；
- 图关系边被误当成业务事实；
- 计划表承担图遍历职责；
- 用户隔离和迁移复杂度上升。

当前设计只保存用户明确选择的节点，不保存整张图。

## 安全边界

- `graph_question_id` 没有主题时返回 400；
- 主题不存在或问题索引超出当前题库范围时返回 400；
- `read_graph_question` 只读，不修改画像、SM-2、题库或计划；
- `create_learning_plan` 只有用户明确请求计划时才允许执行；
- Agent 计划仍然是 draft，需用户确认；
- 进入训练时重新校验节点，不信任计划 JSON 或 URL 中的完整文本；
- 计划和 session 都使用当前用户作用域，不能跨用户读取。

## 验证结果

新增测试覆盖：

- 图谱问题能被 Agent 读取；
- 计划 source 和首个计划项保存 ID 与问题文本；
- 缺少主题、非法主题和非法问题 ID 都被拒绝；
- 计划项来源可继续传回 Stage34 精确训练入口；
- 既有计划确认、用户隔离、否定意图和专项训练测试保持通过。

暂存工程验证结果：后端 `50 passed`，Python `compileall`、前端 `npm run typecheck` 和 `npm run build` 均通过。

## 面试追问准备

### 为什么 Agent 还需要一个读取工具，不能直接使用 URL 里的问题？

URL 只提供客户端上下文，不能证明问题属于当前用户。读取工具把节点 ID 重新绑定到后端事实源，并让 Agent trace 明确展示它读过什么。

### 为什么计划项要保存问题快照？

因为题库会变。ID 适合重新校验，文本快照适合解释计划生成时的历史事实，两者语义不同，不能互相替代。

### 这是不是多 Agent？

不是。仍然只有一个 Personal Agent，新增的是一个受控只读工具和一个来源字段；没有新的 Agent 角色、消息队列或跨 Agent 协议。

### 如何防止 Agent 计划绕过精确训练校验？

计划项只携带节点元数据，进入训练时后端再次按当前用户和主题解析 `graph_question_id`。即使计划 JSON 被修改，后端也不会信任其中的完整问题文本。

## 当前限制与下一步

当前链路已经记录图谱节点来源，但关系边仍是确定性词法近似，Agent 也没有根据图谱邻居自动扩展计划。下一步可以在保留用户确认的前提下，研究如何把相近问题作为“可选后续练习”加入计划，并用训练结果评估关系是否真的帮助学习。
