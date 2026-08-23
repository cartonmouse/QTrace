# 阶段 65：前端认证客户端边界

## 目标

把“登录页面能渲染”和“前端请求如何携带认证信息”区分开。阶段 64 只覆盖了登录/注册入口的页面证据，本阶段补充统一 API client 的源码契约和回归，不输入密码、不提交登录，也不读取浏览器存储。

## 代码证据

`frontend/src/api.ts` 的请求边界包含四个可检查事实：

1. 所有请求通过 `API_BASE = "/api"` 进入前端代理，不在组件中拼接后端地址。
2. `apiFetch` 统一创建请求头；只有调用方传入 `token` 时，才增加 `Authorization: Bearer <token>`。
3. `authenticate("login" | "register", payload)` 通过 `/auth/${mode}` 发起 JSON 请求，并返回后端的 `access_token` 与用户摘要。
4. JSON body 自动补 `Content-Type`，`FormData` 上传不会被错误地设置为 JSON，从而保留浏览器生成 multipart boundary 的机会。

`scripts/frontend_route_preflight.py` 现在会只读检查 `frontend/src/api.ts` 的上述认证客户端标记；`tests/test_frontend_route_preflight.py` 覆盖完整契约和缺失标记两种情况。它与认证页面入口、业务路由、Agent 恢复交互和样式检查一起运行。

## 验证结果

- 前端路由预检包含 `auth client markers` 检查。
- 本阶段新增一条回归，验证缺失认证客户端标记会被报告。
- 暂存工程完整回归为 `91 passed`；Python compileall、前端 typecheck/build 通过。
- 正式工程第一次使用默认 pytest 临时目录时，Windows 对 `C:\Users\clearsnowsong\AppData\Local\Temp\pytest-of-clearsnowsong` 返回拒绝访问，错误发生在 fixture setup 扫描临时目录时，不是业务断言失败；改用全新的 `qtrace_stage65_formal_pytest_tmp` 作为 `--basetemp` 后正式回归为 `91 passed`。
- 正式目录的隔离演示、复现、前端路由/认证客户端、简历证据和最终交付预检均通过；最终交付预检只提示已有本地产物，不自动删除。

## 面试讲解

可以这样回答“token 如何传给后端”：

> 登录/注册是无 token 的 `/api/auth/*` 请求；认证成功后，业务 API 都经过统一的 `apiFetch`，由调用方显式传入 token，再由请求层统一生成 `Authorization: Bearer` 头。这样组件不需要重复实现鉴权头，也能把未登录请求和已登录请求的边界集中在一个地方。文件上传则保留 `FormData` 的请求头行为，避免把 multipart 请求误标成 JSON。

如果继续追问“这是否证明登录成功”，必须说明：不证明。本阶段是源码契约和单元回归，不覆盖密码提交、token 的浏览器持久化、过期刷新、真实浏览器请求或后续页面；这些仍需要用户在合成账号边界下人工彩排。

## 安全边界

- 没有读取 API Key、真实简历、个人文档、数据库内容或浏览器 cookie/localStorage。
- 没有调用外部 API、启动服务、部署或修改 GitHub。
- 预检只读取源码；它不能证明供应商鉴权、网络安全策略或生产环境认证配置。

## 环境问题记录

如果明天仍遇到默认 pytest 临时目录的权限错误，优先在正式工程目录使用新的阶段临时目录运行：

```powershell
python -m pytest -q --basetemp qtrace_stage65_formal_pytest_tmp_next
```

目录名应当每次使用全新的阶段标识；不要为了清理权限问题删除未知临时目录。
