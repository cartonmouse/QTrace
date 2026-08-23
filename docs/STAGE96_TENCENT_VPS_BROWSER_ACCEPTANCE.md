# 阶段 96：腾讯云公网浏览器验收

## 结果

QTrace 已在独立的腾讯云 Ubuntu VPS 上启动，并从外部 Chrome 浏览器验证通过：

- 公网 IPv4：`49.232.104.202`
- 公网入口：`http://49.232.104.202/`
- 首页访问后按设计跳转到 `/login`
- 页面标题：`问迹 QTrace · 个性化面试训练`
- 容器：`qtrace-api-1` healthy，`qtrace-web-1` started
- 容器内 Nginx 代理的 `/api/health` 返回 `{"status":"ok","mode":"qtrace"}`
- 腾讯云安全组已存在 TCP 80 放行规则；为避免新增 8080 规则，运行时将 Web 映射到主机 80 端口

## 部署边界

- 这是“公网 IP + HTTP 80”的面试 Demo，不是正式生产上线。
- Demo Compose 使用 session 级 BYOK；访问者需要在自己的浏览器会话中填写 OpenAI-compatible API Base、Model 和 API Key。
- 没有 Key 时只能使用明确标注的 Stub 降级路径；服务器没有内置开发者 Key。
- 本阶段只使用合成数据，没有上传真实简历、个人文档或调用真实 LLM API。
- VPS 上的 JWT secret 和 `deploy/demo.env` 不进入聊天记录、日志或 GitHub。

## 更新代码时的操作

当前 VPS 到 GitHub 的 HTTPS 拉取曾出现超时，因此本次运行对远端工作树应用了与 GitHub `main` 等价的最小构建修复，并记录为部署阻塞项。网络恢复后应优先执行：

```bash
cd /opt/qtrace
git pull --ff-only
```

拉取后用服务器自己的 `deploy/demo.env` 启动；公开入口需要在环境文件中设置 `QTRACE_DEMO_PORT=80`，本地开发仍可使用示例默认的 `8080`。

```bash
sudo docker compose --env-file deploy/demo.env -f docker-compose.demo.yml up -d --build
sudo docker compose --env-file deploy/demo.env -f docker-compose.demo.yml ps
```

## 尚未达到的生产标准

仍需在正式上线前补齐域名与 HTTPS、限流/预算、监控和备份、API Base 的更严格 egress/SSRF 防护，以及公网 BYOK 的隐私与滥用治理。当前结果证明“他人可以用浏览器打开并进入 QTrace”，不应表述为高可用生产服务。
