# 阶段 48：Personal Agent 工具失败降级

## 目标

阶段 47 已经处理模型规划/回答失败后的对话和计划状态。本阶段继续处理工具执行失败：单个读取工具不可用时，Agent 应该尽可能使用其他成功上下文回答；但依赖画像、复习队列和近期训练的学习计划写工具不能在上下文不完整时继续写入草稿。

本阶段只使用 fake provider、合成账号和临时 SQLite，没有调用真实 LLM，没有读取或上传真实简历/个人文档，没有部署、删除文件或提交推送 GitHub。

## 原有问题

之前的工具循环会捕获异常并记录 `tool_trace.status=failed`，但存在两个边界：

- `str(exc)` 可能把底层依赖细节带入前端 trace 和后续回答上下文；
- 读取画像或复习历史失败后，`create_learning_plan` 仍可能根据不完整上下文生成草稿。

## 实现

### 稳定的工具失败契约

后端将内部异常映射为有限的安全码和摘要：

| code | 适用情况 | 对用户的摘要 |
| --- | --- | --- |
| `dependency_unavailable` | Embedding/其他依赖 Provider 不可用 | 工具依赖服务暂时不可用，已跳过该工具 |
| `context_unavailable` | 当前用户上下文、节点或输入不可用 | 当前上下文不可用，已跳过该工具 |
| `execution_failed` | 未分类的工具异常 | 工具执行失败，已跳过该工具 |
| `write_blocked_by_context` | 写工具缺少必要读取结果 | 必要上下文读取失败，暂不创建学习计划草稿 |

`tool_trace` 对失败或跳过项增加 `code` 和 `recovery=continue_with_partial_context`；原始异常只保留在 Python 异常链中，不进入 API 响应、前端或 LLM 上下文。

### 部分上下文回答

失败工具会写入内部 `tool_failures` 上下文。Stub/LLM 回答器可以知道哪些信息没有读取成功，因此不能把缺失数据当成“0 次训练”“没有到期项”或其他确定事实。回答仍然可以使用成功读取的画像、复习队列、训练历史或文档证据。

### 写工具依赖门禁

`create_learning_plan` 当前要求成功读取：

1. `read_profile`；
2. `read_due_reviews`；
3. `read_recent_sessions`。

其中任一工具失败，写工具会以 `status=skipped` 和 `write_blocked_by_context` 记录，不写入学习计划。这样“回答可降级”和“业务写入必须完整”被明确分开。

## 测试

`tests/test_agent_errors.py` 覆盖：

- 工具 Provider 失败时返回 200，回答继续生成；trace 使用稳定摘要，不泄露内部异常原文；
- 学习计划所需画像读取失败时，`create_learning_plan` 被安全跳过，不生成草稿；
- 阶段 46/47 的规划失败、回答失败、空对话回滚和计划草稿保留仍然通过。

本阶段验证结果：

```text
python -m pytest -q                 66 passed
python -m compileall -q backend scripts tests  passed
frontend npm run typecheck           passed
frontend npm run build               passed
```

## 面试讲解要点

### 为什么工具失败不直接让整个 Agent 失败？

读取画像失败不代表复习队列、训练历史或用户明确的问题都不可用。对只读工具采用 best-effort 可以提高可用性，但必须在上下文中留下失败事实，避免回答器把缺失当成空值。

### 为什么学习计划写工具反而要更严格？

学习计划会持久化并影响后续训练，错误上下文可能产生错误行动。因此读取可以部分成功，写入必须满足显式前置依赖；缺少必要读取时只返回可解释的跳过 trace，不创建草稿。

### 为什么不把原始异常给前端？

原始异常可能包含供应商 URL、内部实现信息或不稳定的错误文本。前端需要稳定 code 和用户可理解的摘要，日志/异常链才保留排查线索；这也避免把供应商协议绑定到 UI。

## 当前边界

当前只有学习计划写工具配置了显式读取依赖，其他未来写工具需要逐项声明依赖；没有新增自动重试和熔断器，也没有统一所有业务模块的错误协议。真实 LLM、Embedding 和个人资料仍不在本阶段联调范围内。
