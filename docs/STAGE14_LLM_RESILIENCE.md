# 阶段 14：真实 LLM 稳定性收口

## 为什么需要这一阶段

真实模型调用不是普通的本地函数调用，失败来源至少包括：

- 请求超时；
- API Base 或网络不可达；
- 429 限流；
- 5xx 临时服务错误；
- 401/403 鉴权错误；
- HTTP 成功但响应结构不符合 Chat Completions 契约。

如果这些异常直接从 `httpx` 或 JSON 解析层冒泡，FastAPI 路由可能返回 500，前端也无法区分“模型暂时不可用”和“代码解析失败”。因此错误边界应该收敛在 Provider 适配层。

## 本阶段实现

文件：`backend/provider.py`

### 1. 有界重试

`OpenAICompatibleProvider` 新增：

- `max_retries`：默认 1 次，最多限制为 3 次；
- `retry_backoff_seconds`：指数退避，默认 0.25 秒并设置上限；
- 可重试状态：408、425、429、500、502、503、504；
- 401、403 等鉴权错误不重试，避免无意义地重复发送请求。

重试只发生在 Provider 内部，InterviewEngine、Agent 和 Analyzer 不需要各自复制一份重试逻辑。

### 2. 网络异常归一化

Provider 现在把底层异常转换为不会泄露内部堆栈的业务错误：

| 底层情况 | ProviderError |
| --- | --- |
| `httpx.TimeoutException` | `LLM 请求超时，请检查网络或增大超时配置` |
| `httpx.RequestError` | `LLM 网络连接失败，请检查 API Base 和网络设置` |
| 最终 HTTP 4xx/5xx | `LLM 请求失败，HTTP {status}` |
| 成功但响应结构错误 | `LLM 返回缺少 choices[0].message.content` |

上层路由已有 `ProviderError -> HTTP 502` 映射，因此模型服务异常不会伪装成后端内部 500。

### 3. 保留结构化输出校验

重试只解决传输层暂时失败，不会把错误 JSON 当成成功。Agent 规划、动态出题、复盘和录音分析仍然分别执行 JSON 解析、字段校验、数量限制和分数归一化。

## 代码调用链

```text
Agent / Interview / Recording Analyzer
  -> OpenAICompatibleProvider._chat()
  -> httpx Chat Completions
  -> timeout / network / 429 / 5xx retry
  -> ProviderError normalization
  -> FastAPI 502
  -> frontend readable error
```

## 验证结果

- 后端测试：`27 passed`；
- 新增测试覆盖：503 后重试成功、超时重试后给出清晰错误、网络错误归一化、401 不重试；
- Python 内存编译：20 个 Python 文件通过；
- 前端 `npm run typecheck`：通过；
- 前端 `npm run build`：通过；
- 阶段 13 的真实 LLM 联调仍然有效：Provider、Personal Agent、动态专项训练和结构化复盘均已返回成功；
- 稳定性测试不重复消耗真实 API，使用 `httpx.MockTransport`。

## 面试追问准备

### 问：为什么重试要放在 Provider，而不是每个业务模块里？

答：Provider 是所有 LLM 调用的基础设施边界。把重试放在这里可以统一处理超时、网络错误和临时 HTTP 状态，Agent、面试状态机和录音分析只关心“得到内容”或“得到 ProviderError”，避免多套逻辑不一致。

### 问：所有错误都应该重试吗？

答：不应该。429 和 5xx 通常可能是暂时性的，408 也可以有限重试；401/403 是鉴权或权限问题，重试没有意义；结构化 JSON 错误属于内容层问题，不能简单重复请求掩盖问题。

### 问：为什么默认只重试一次？

答：面试训练是交互式请求，过多重试会放大延迟和成本。默认一次可以覆盖短暂抖动，同时把上限限制在 3 次以内；更复杂的生产策略还需要读取 Retry-After、配额、熔断和请求幂等设计。

### 问：如何避免把 API Key 泄露到错误日志？

答：ProviderError 只保留状态码和面向用户的错误类别，不拼接请求头、完整 URL 查询参数或原始异常文本；设置接口也只返回 `llm_key_configured` 布尔值。

## 下一步

1. 视真实模型供应商行为增加 `Retry-After` 和限流提示；
2. 增加前端错误状态和用户可理解的重试入口；
3. 评估 Agent 写工具和用户确认机制；
4. GitHub 初始版本已发布；后续版本的提交和推送仍需用户单独确认。
