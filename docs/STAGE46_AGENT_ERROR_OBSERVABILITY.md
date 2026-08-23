# Stage46：Personal Agent 错误可观察性

本阶段收口“真实 LLM 失败后用户看到什么”。成功链路不变，仍然是 `plan -> tools -> answer`；本阶段只让失败阶段、错误码和前端提示更明确。所有测试使用 fake provider，没有调用外部 API，也没有读取真实资料。

## 1. 原来的问题

后端此前把 Agent 的 `ProviderError` 直接作为字符串放进 HTTP 502。这样有两个问题：

1. 前端无法区分规划失败、回答失败和模型初始化失败；
2. FastAPI 返回对象型 `detail` 时，前端 `ApiError` 会退回通用的“请求失败”，丢失服务端已经提供的 `message`。

## 2. 稳定错误边界

`run_personal_agent` 现在在两处模型调用边界包装错误：

```text
model.plan(...)   -> AgentProviderError(stage="planning")
model.answer(...) -> AgentProviderError(stage="answering")
```

Agent API 返回 502 时使用结构化 detail：

```json
{
  "code": "agent_planning_failed",
  "stage": "planning",
  "message": "Agent 规划失败，请检查模型设置或稍后重试。",
  "retryable": true
}
```

回答阶段对应 `agent_answering_failed`；模型配置本身不可用时使用 `agent_provider_error` 和 `stage=initialization`。底层异常文本不直接回传，避免把供应商内部信息变成前端协议的一部分。

前端 `ApiError` 现在会优先读取对象型 detail 的 `message`，Agent 页面会显示“Agent 请求未完成”、具体失败原因以及重试提示。

## 3. 测试

新增回归测试：

- fake provider 在规划阶段失败时返回 `agent_planning_failed`；
- fake provider 在回答阶段失败时返回 `agent_answering_failed`；
- 原始 fake provider 异常文本不会直接泄露到用户错误 message；
- 阶段 45 的真实 LLM smoke 仍在配置门禁外保持“未配置不联网”。

## 4. 面试讲法

> 我没有让前端根据 HTTP 502 的字符串猜错误发生在哪一步，而是在 Agent 的两个模型调用边界定义了稳定的 stage 和 code。规划失败与回答失败都属于可重试的 Provider 错误，但模型初始化错误单独标记。前端 ApiError 统一解析对象型 detail 的 message，页面可以给用户可理解的提示；底层供应商异常不直接作为公共协议返回。

## 5. 当前边界

- 工具执行失败仍会记录在 `tool_trace`，并让 Agent 在可用上下文范围内继续回答；这与模型规划/回答失败是不同级别的错误；
- 当前只对 Agent API 做阶段化错误码，其他面试、录音和专项训练接口仍保留各自已有的错误文字；
- 这一步没有改变重试策略，Provider 的网络重试仍由 `backend/provider.py` 负责；
- 没有新增自动提交、部署或真实数据联调。
