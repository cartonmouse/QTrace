# 阶段 94：公开 Demo API Base SSRF 第一层防护

## 目标

公开 Demo 允许用户填写自己的 OpenAI-compatible API Base，但服务端不能无条件把这个地址作为出站请求目标。先补一层可解释、可测试的应用策略，阻断最常见的 localhost、私网、链路本地和内部 DNS 访问。

## 策略

`REBUILD_BLOCK_PRIVATE_API_BASE` 是显式开关：

- 本地默认 `false`，允许开发者调试本机 Ollama 或其他本地 OpenAI-compatible 服务；
- Docker Compose Demo 默认 `true`，示例环境也写入 `REBUILD_BLOCK_PRIVATE_API_BASE=true`；
- 开启时只允许 `http`/`https`，拒绝 URL 中的用户名/密码、query/fragment、localhost/内部域名、非公网 IP 字面量；
- 对 hostname 在保存/连接测试阶段执行 DNS 解析，任一解析结果不是公网地址就拒绝；
- LLM 设置、远程 Embedding 设置、独立 LLM 连接测试和 Provider 构造复用同一个校验函数；拒绝发生在 Provider 发请求之前。

## 验证证据

- `tests/test_api_base_policy.py` 安全专项覆盖：回环、RFC1918 私网、云元数据链路本地地址、IPv6 回环、localhost/内部域名、不安全协议、URL 凭据、公开 DNS 结果、私网 DNS 结果以及 API 路由前置拒绝；专项共 `23 passed`；
- `qtrace_byok_preflight.py` 和 `public_demo_preflight.py` 检查网络策略源码、Compose 和示例环境开关；
- Docker 镜像构建成功；使用 `deploy/demo.env.example` 启动 Compose 后，`http://127.0.0.1:8080/` 返回 200、同源 `/api/health` 返回 `ok`，合成账号注册成功；对 `127.0.0.1` 的 LLM 探测返回 `ok=false`，配置保存返回 400，随后只停止容器且没有删除数据卷；
- 最终收口门禁通过：全量合成回归 `148 passed`，BYOK/public-demo/final-delivery 预检通过，`git diff --check` 无内容错误；pytest 的唯一 warning 仍是当前 Windows 正式目录 `.pytest_cache` 写权限限制；
- 只使用 `synthetic-provider.example`、保留测试 IP 和 fake DNS resolver，不进行真实网络调用，不读取或输出任何 API Key。

## 仍需公网门禁

这是应用层第一道 SSRF 防护，不应被表述成完整的公网安全方案。配置时 DNS 解析和真正 HTTP 连接之间存在 DNS rebinding 时间窗口；取得公网 URL 前还必须使用云防火墙/egress proxy/允许域名策略、HTTPS、限流、调用预算、日志脱敏、监控和备份。若需要允许私有模型，应部署专用内网版本并显式关闭该开关，而不是放宽公开 Demo。
