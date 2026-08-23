# 阶段 91：BYOK 独立 LLM 连接测试

## 目标

把模型设置页的“测试 LLM”从前端占位提示改成真实的后端探测请求，使演示者能够在保存前判断自己填写的 OpenAI-compatible 配置是否可达。测试使用最小合成提示，不读取简历、个人文档或历史对话。

## 接口契约

`POST /api/settings/test-llm` 接收：

```json
{
  "api_base": "https://provider.example/v1",
  "model": "demo-model",
  "api_key": "由用户在当前会话表单填写"
}
```

- 当前表单字段优先；字段为空时，才回退到当前用户已保存的 Provider 配置；
- 端点只构造 `OpenAICompatibleProvider` 并调用 `probe()`，不调用 `Store.set_openai_provider`，因此“测试”不会保存新配置；
- `probe()` 请求 `/chat/completions`，使用固定连接测试提示、`max_tokens=1` 和零重试；
- 成功只返回 `ok/message`，失败只返回通用的超时、网络或 HTTP 状态错误，不返回 Authorization header、API Key 或完整上游响应；
- 前端 adapter 真实调用该端点，设置页的已有 `testing/ok/fail` 状态因此可以反映真实请求结果。

## 验证证据

- `python scripts/qtrace_byok_preflight.py` 通过；
- BYOK 静态契约回归 `2 passed`；Provider 探测和 API 端点合成回归 `8 passed`；
- 全量合成 Python 回归 `133 passed`；
- 前端 `npm run typecheck` 通过，备用输出目录生产构建成功并转换 3811 个模块；
- 测试只使用 `synthetic-provider.example`、合成模型和 mock provider，没有调用真实 LLM API。
- 更新后的 Docker 镜像在本机 8080 端口通过健康检查；合成账号调用空配置测试分支返回预期缺少配置错误，未触发外部请求。

## 公网边界

这个端点解决的是“连接测试可观察性”，不是完整的公网安全方案。公开 Demo 前仍需把 API Key 从 SQLite 明文持久化迁移到加密或会话存储，限制 API Base 的 SSRF/私网访问，增加用户级限流、预算和审计；真实 LLM 联调仍要由用户在本地或受控演示环境使用自己的 Key 完成。
