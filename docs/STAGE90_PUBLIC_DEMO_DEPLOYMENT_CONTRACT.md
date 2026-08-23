# 阶段 90：面试 Demo 公网部署契约

## 目标

把 QTrace 从“本机 `127.0.0.1` 可运行”整理为可以部署到支持 Docker 的服务器或托管平台的单体 Demo 包。这个阶段完成部署契约和本机 Docker 验证，但不代表已经获得公网地址或完成外部部署。

## 运行结构

```text
浏览器
  -> web: Nginx 静态前端
       /api/*、/ws/* -> api: FastAPI
                         -> /app/data/rebuild.sqlite3
```

- `api` 只暴露给 Compose 内部网络，不把 SQLite 或后端端口直接暴露到公网。
- `web` 构建前端生产产物，并用同源 `/api` 代理到 FastAPI，避免把后端地址写进浏览器。
- 命名卷 `qtrace_demo_data` 保存 Demo 运行数据；公开部署前仍应配置备份和容量策略。
- `REBUILD_JWT_SECRET` 必须由部署环境提供，不能继续使用本地默认值。
- `REBUILD_ALLOWED_ORIGINS` 可通过环境变量覆盖；同源 Nginx 访问时不需要额外跨域请求。

## 本地验证方式

```powershell
Copy-Item deploy\demo.env.example deploy\demo.env
# 编辑 deploy\demo.env，至少替换 REBUILD_JWT_SECRET；不要填写 LLM API Key
docker compose --env-file deploy\demo.env -f docker-compose.demo.yml config
docker compose --env-file deploy\demo.env -f docker-compose.demo.yml up --build
```

浏览器访问 `http://localhost:8080`。停止时使用 `Ctrl+C`；不要用 `down -v`，否则会删除 Demo 命名卷中的数据。

在没有 Docker 的机器上，仍然可以先运行：

```powershell
python scripts\public_demo_preflight.py
```

该检查只读取 Dockerfile、Compose、Nginx 和示例环境文件，不启动容器、不联网、不读取 SQLite、真实简历、个人文档或 API Key。

本机 Docker 验证已完成：`docker compose ... build` 成功构建 `rebuild-api` 和 `rebuild-web`；使用示例环境配置短暂启动 Compose 后，`http://127.0.0.1:8080/` 返回 200，`http://127.0.0.1:8080/api/health` 经 Nginx 代理返回 `{"status":"ok","mode":"qtrace"}`。验证结束后仅停止容器，没有执行 `down -v`，命名卷未删除。正式工程的 `frontend/dist` 仍受 Windows `EPERM` 写入边界影响，因此不把 `local_runtime_smoke.py` 对该目录的失败误判为 Docker 生产构建失败；生产构建已在容器内完成。

## LLM / BYOK 边界

公开 Demo 不内置开发者的 LLM Key。用户可以登录后在“模型设置”中填写自己的 OpenAI-compatible API Base、Model 和 API Key，真实请求由后端 Provider 发出；Stub 只作为没有 Key 时的明确离线降级，不得在演示中冒充真实 LLM。

当前本地版本的配置保存和真实 Provider 调用已经存在，但公开部署前仍需完成：

1. 独立的真实 LLM 连接测试接口；
2. API Key 加密保存或仅会话保存，避免明文落入公网服务器 SQLite；
3. API Base 白名单/私网地址阻断，防止把任意 URL 当作服务端请求目标；
4. 用户级限流、请求超时、调用预算和错误脱敏；
5. 真实 LLM/Embedding 的合成数据联调，不把 Stub 回归当成模型质量证据。

## 尚未完成的外部动作

- 尚未选择或配置云服务器/托管账号；
- 尚未配置域名、HTTPS、备份和监控；
- 尚未执行公网/外部部署；
- 尚未把本阶段变更推送到 GitHub；
- 当前 WebSocket 代理只是保留部署边界，不能据此宣称 Copilot WebSocket 已上线。

## 面试演示建议

第一版公开 Demo 使用合成账号和合成资料，允许面试官注册自己的临时账号。需要展示真实 LLM 时，让演示者在会前临时填写自己的 API 配置；不要把 Key 放到仓库、截图、浏览器 URL 或公共环境变量中。
