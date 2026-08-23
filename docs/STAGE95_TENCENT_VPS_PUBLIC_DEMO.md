# 阶段 95：腾讯云 VPS 浏览器 Demo 部署

## 目标

把 QTrace 从“本机 Compose 契约”推进到新建的独立腾讯云 VPS 上运行，让其他人可以通过浏览器访问同一个前端入口。Qidian 使用的旧 VPS 不在本阶段范围内；QTrace 使用独立实例。

## 已完成的本地准备

- GitHub `main` 已包含 Docker Compose、Nginx 同源 `/api` 代理、session 级 BYOK、公开 API Base 第一层私网阻断和部署预检。
- Docker 构建支持 `PIP_INDEX_URL` 与 `NPM_REGISTRY` 构建参数，国内 VPS 可以在 `deploy/demo.env` 覆盖依赖镜像而不改业务代码。
- 移除公开构建不稳定的 `@fontsource/noto-serif-sc` 依赖；简历模块保留 Noto Sans 自托管字体，衬线字体回退到系统字体栈。
- 本地 `npm run typecheck` 与 `npm run build` 通过；Compose 配置解析通过。

## VPS 操作边界

远端只允许使用合成账号和合成内容。`deploy/demo.env` 只在 VPS 上生成，`REBUILD_JWT_SECRET` 不进入聊天、日志或 GitHub；不在公开 Demo 内置开发者 LLM Key。远端临时构建文件只用于排查镜像网络，不作为源码交付物。

## 当前验收门禁

1. VPS 上 Docker/Compose 已安装，QTrace 仓库从 `main` 拉取。
2. `docker compose ... up -d --build` 成功，API 健康检查为 healthy，Nginx 首页与同源 `/api/health` 返回 200。
3. 腾讯云安全组只开放面向演示所需的 Web 端口；SSH 不因防火墙调整而中断。
4. 用新的合成账号从浏览器注册/登录，确认首页、开始训练和 Stub 降级路径可用；不上传真实简历或个人文档。
5. 只有拿到腾讯云控制台显示的真实公网 IPv4 并从外部浏览器访问成功后，才能记录“公网可访问”；`10.x.x.x` 等私网地址不能作为 Demo URL。

## 尚未完成项

公网 IP/安全组和最终浏览器外部访问需要腾讯云控制台侧信息；域名、HTTPS、限流、备份、监控和更严格的 BYOK 出站策略仍是演示版上线前的后续门禁。Docker 构建成功不等于已经获得公网 URL。
