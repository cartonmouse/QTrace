# 阶段 67：认证过期的统一回退

## 发现的问题

阶段 66 只覆盖了应用启动时读取 token，以及 `/me`/`/settings` 加载失败后的回登录路径。用户已经进入业务页面后，如果某个请求才返回 401，原来的 `apiFetch` 只抛出 `ApiError`，React 应用不会统一清理本地认证状态，页面可能继续保留旧的已登录外观。

## 实现

本阶段补了一条小而完整的跨层闭环：

```text
带 token 的 apiFetch 收到 401
    -> 派发 AUTH_EXPIRED_EVENT
    -> App 监听事件并清理 token/user/settings
    -> token 或 user 缺失
    -> 回到 LoginPage
```

具体行为如下：

- `frontend/src/api.ts` 对带 token 的 401 响应派发 `qtrace:auth-expired` 事件，然后仍然抛出原有 `ApiError`，不吞掉调用方的错误处理；
- `frontend/src/App.tsx` 注册事件监听，复用 `clearAuthState()` 清理 token、用户和模型设置；
- 组件主动退出和应用启动时账户校验失败也复用同一个清理函数，避免三套状态清理逻辑逐渐分叉；
- 没有 token 的登录/注册请求不会触发过期事件，因此登录失败不会被误判成已登录会话过期。

## 预检与回归

`scripts/frontend_route_preflight.py` 新增两组只读契约：

- `REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS`：401 条件、事件常量和事件派发；
- `REQUIRED_AUTH_EXPIRY_STATE_MARKERS`：清理函数、事件注册和卸载。

`tests/test_frontend_route_preflight.py` 新增缺失事件回退标记的回归。该检查不启动浏览器、不读取 cookie/localStorage、不发起 HTTP 请求，只防止跨层回退逻辑被意外删掉。

## 面试讲解

可以这样回答“token 在页面停留期间过期怎么办”：

> 我把 401 处理分成请求层和状态层。统一 `apiFetch` 只对带 token 的 401 发出一个认证过期事件，同时保留 `ApiError` 让当前请求可以显示错误；根组件监听事件，清除 token、用户和设置，利用现有的认证门禁回到登录页。这样请求层不直接依赖 React，React 也不需要让每个业务页面重复写 401 处理。当前事件是本地单页应用的轻量方案，生产环境还要配合刷新 token、并发请求去重、Cookie 策略和跨标签页同步。

## 边界

- 本阶段没有读取或输出 API Key，没有读取或上传真实简历、个人文档或数据库内容。
- 没有调用外部 API、输入密码、启动服务、部署、删除文件或提交推送 GitHub。
- 事件回退只改善前端状态一致性，不证明真实身份校验、token 刷新、跨标签页同步或生产级认证安全已经完成。
