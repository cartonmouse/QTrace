# 阶段 11：核心前端闭环整合

## 目标

前 10 个阶段已经分别实现了训练、复盘、画像、JD 定向和 Copilot Prep。本阶段把它们连接成一个可演示的产品闭环，避免用户完成一次分析后只能停留在当前页面。

## 新增流程

```text
Dashboard
  -> 面试 Copilot
  -> 生成并保存 Prep
  -> 从历史恢复 Prep
  -> 一键带入 JD 定向页
  -> 开始定向训练
  -> 复盘写回画像和复习队列
```

### Copilot 历史恢复

Copilot 页面加载 `/api/copilot/prep`，展示当前用户最近的 Prep。后端查询返回公司、岗位、JD 快照、状态和结构化结果；点击历史项可以恢复输入和策略结果。

### 跨页面上下文交接

点击“带入 JD 定向训练”时，前端把公司、岗位、JD 和简历开关暂存到 `sessionStorage`，跳转到 `/job-prep` 后自动填充表单。JD 定向页仍然要求重新分析，避免跳过当前页面的 preview 校验。

这是一种轻量的前端路由交接方式：不把大型对象塞进 URL，也不把尚未开始的训练错误地写入后端会话。

### 统一导航

Dashboard、侧边栏和 Copilot 结果页都提供进入下一环节的入口：

- Dashboard -> Copilot Prep；
- Copilot Prep -> JD 定向训练；
- Copilot Prep -> 我的画像；
- JD 定向训练 -> InterviewEngine；
- 训练结束 -> Review -> Profile / Review Queue。

## 后端变化

`CopilotPrepView` 增加 `jd_text` 快照，配合已有的 `copilot_preps` 表实现用户级历史恢复。仍然遵守 `user_id` 隔离，不能通过 Prep ID 读取其他用户的数据。

## 为什么不直接把 Copilot 结果放进普通面试 History

Copilot Prep 不是一场已经完成的问答会话，它没有候选人回答、评分或 `SessionView` 的阶段状态。单独的 `copilot_preps` 表更符合领域模型；前端可以在 Copilot 页面展示 Prep 历史，普通 History 继续只展示训练会话。

## 面试追问卡

### 为什么使用 sessionStorage 做跨页面交接？

交接内容只需要在当前浏览器页签内短暂存在，且不应该成为长期业务数据。`sessionStorage` 比 URL 更适合承载较长 JD，比全局 React 状态更能跨路由，比数据库更轻量。进入 JD 页面读取后立即删除，避免旧上下文污染下一次训练。

### 为什么跳转后还要重新分析 JD？

Copilot Prep 的策略结果和 JD 定向训练的 preview 责任不同。重新分析可以校验当前输入仍然完整、简历开关是否变化，并让 JD 定向页生成自己的问题蓝图。

### 为什么不把所有页面都做成一个大组件？

每个页面负责一个用户任务，API client 负责通信，后端负责领域逻辑。跨页只传递明确的上下文，而不是让页面互相调用内部状态，这样更容易测试和替换。

## 当前验证

- 后端测试：`15 passed`；
- 前端：`npm run typecheck` 通过；
- 前端：`npm run build` 通过；
- Copilot SSE 运行态链路仍为 `started -> jd_analyzed -> risk_assessed -> strategy_ready -> completed`；
- Copilot 历史查询和 JD 快照恢复接口可用。

## 未声称完成的原项目页面

为了保持学习边界诚实，以下仍是可选扩展，不计入本阶段完成：

- 知识图谱可视化；
- 独立个人 Agent 页面；
- 完整简历编辑器；
- Copilot WebSocket 双向实时辅助。

这些页面可以在核心闭环稳定后逐个增加，不影响当前项目的主要演示链路。
