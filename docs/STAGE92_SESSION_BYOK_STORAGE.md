# 阶段 92：公开 Demo 的会话级 BYOK 存储

## 目标

解决公开 Demo 不应把访问者的 LLM/Embedding API Key 明文落入 SQLite 的问题，同时不破坏本地学习环境已有的持久化行为。

## 设计

`REBUILD_BYOK_STORAGE_MODE` 支持两种值：

- `persisted`：默认兼容模式，沿用本地工程原有行为，配置和 Key 都持久化到 SQLite；
- `session`：公开 Demo 模式，API Base/Model 等非敏感配置仍可保存，但 LLM/Embedding Key 只保存在当前 FastAPI 进程的内存字典中，SQLite 对应字段写入空字符串。

Compose 默认使用 `session`，示例环境文件也明确写入 `REBUILD_BYOK_STORAGE_MODE=session`。服务重启后，已有用户的 Provider 配置会被视为未完成，前端要求重新填写 Key；不会带着空 Key 误调用上游模型。

## 验证证据

- 合成存储回归覆盖：session 模式 SQLite 字段为空、进程内仍能取回 Key、重启 Store 后配置回到未完成；persisted 模式重启后保持原有行为；
- 公共 Demo 预检增加 Compose、环境文件、配置和 Store 的 session marker；
- 全量合成回归 `135 passed`、前端 typecheck/build 和 Docker 8080 健康检查继续作为发布门禁；容器内合成账号写入 session 配置后重启 API，重新登录读取到 `llm_configured=false`、`llm_key_configured=false`，验证了 Key 不依赖 SQLite 恢复。

## 安全边界

session 模式降低了“数据库泄露直接暴露 Key”的风险，但内存中的 Key 仍会被当前服务进程使用，也没有解决 API Base SSRF、私网访问、限流、调用预算、HTTPS 和日志治理。公网发布前仍需要这些门禁；真实 Key 只允许由演示者或访问者在受控页面输入，不能放进镜像、仓库、截图或公共环境变量。
