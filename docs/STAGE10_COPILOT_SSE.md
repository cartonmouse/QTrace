# 阶段 10：Copilot 文本 Prep 与 JSON/SSE 事件协议

## 参考项目中的 Copilot

参考项目把 Copilot 分成两个阶段：

1. Prep Phase：根据 JD、公司、简历和画像生成追问策略、风险路径和准备建议；
2. Realtime Phase：在面试过程中接收实时输入并给出辅助。

本阶段先实现第一阶段的文本版本，并用 JSON 数据承载 SSE 事件。真实实时语音、长音频、说话人分离和时间戳不属于当前项目的交付范围。

## 用户流程

```text
填写公司 / 岗位 / JD
        |
        v
POST /api/copilot/stream
        |
        +-- started
        +-- jd_analyzed       JD 拆解与技能提取
        +-- risk_assessed     简历缺口与历史弱点
        +-- strategy_ready    追问策略树
        +-- completed         完整 Prep 结果
        |
        v
SQLite copilot_preps + 前端策略展示
```

前端使用 `fetch` 读取 `text/event-stream`，而不是直接使用浏览器原生 `EventSource`，因为本阶段需要通过 POST 提交较长的 JD 和用户上下文。

## 后端模块

### `backend/copilot.py`

- `build_copilot_prep`：复用已有 `analyze_jd`，组合 JD 重点、简历匹配、画像薄弱点；
- `strategy_tree`：为每个岗位重点生成触发问题和下一层追问；
- `risk_map`：把简历缺口和历史薄弱点转为风险、证据和补救建议；
- `prep_hints`：生成面试前行动列表；
- `copilot_event_sequence`：定义稳定的事件顺序。

当前实现是本地确定性逻辑，不调用搜索或 LLM。这样可以先验证事件协议、数据结构、持久化和页面交互，再替换某个分析节点。

### `copilot_preps` 表

每次 Prep 都保存：

- `id`、`user_id`；
- 公司、岗位和 JD 输入快照；
- `running / completed / failed` 状态；
- 结构化结果或错误信息；
- 创建和更新时间。

查询接口始终带当前用户 ID，避免不同账户读取彼此的 Prep 结果。

## 为什么先实现 SSE

SSE 是服务端到浏览器的单向事件流，适合展示“后台分析进行到哪一步”。它比一次性返回 JSON 更有反馈，也比 WebSocket 更简单，适合先验证：

- 事件名称是否稳定；
- 每个事件的数据是否可解析；
- 前端断开或后端失败时如何显示状态；
- 最终结果是否能保存和重新读取。

WebSocket 适合真正的双向实时场景，例如浏览器持续发送输入、服务端持续返回建议。那是下一层协议问题，不应和当前 Prep 数据结构混在一起。

## 面试追问卡

### Copilot 和 JD 定向训练有什么区别？

JD 定向训练是按问题回答的面试状态机，目标是让候选人完成一轮训练；Copilot Prep 不直接开始问答，而是提前生成岗位重点、追问路径和风险地图，帮助候选人决定应该先准备什么。

### 为什么事件最后还要落库？

SSE 只是传输协议，连接断开后事件本身不等于可靠数据。完成事件到达时保存结构化结果，之后可以通过 GET 查询、历史页展示或再次进入策略页面。

### 为什么不一开始就用 WebSocket？

当前 Prep 是服务端计算、客户端观察进度的单向关系，SSE 已经足够。WebSocket 只有在双方持续发送事件、需要心跳、背压和断线恢复时才有明显收益。

### 如果某个分析节点失败怎么办？

当前确定性节点失败会把 Prep 标记为 `failed` 并发出 `error` 事件。将来拆成多 Agent 后，可以为每个节点增加 `node_started / node_completed / node_failed`，并决定是整体失败还是保留部分结果。

## 当前验证

- 后端测试：`15 passed`；覆盖 SSE 事件顺序、结果持久化、历史查询和结构化输出。
- 前端：`npm run typecheck` 通过；`npm run build` 通过。
- 本地服务：前端 `5174`、后端 `8002`。
- 非交付范围：WebSocket 实时辅助、实时语音、长音频、说话人分离和时间戳。

## 下一步

先把 Copilot Prep 页面和已有 JD/画像页面的上下文联动讲清楚，再考虑是否实现 WebSocket 文本实时辅助；真实外部服务仍需单独配置和验证。
