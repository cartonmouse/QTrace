# 阶段 83：Vite 开发运行时黑屏恢复

## 问题定位

TechSpar 前端迁移后，浏览器访问 `http://127.0.0.1:5174/` 只能看到纯黑背景。HTTP 层仍返回 200，但入口没有继续渲染。通过本地浏览器控制台和 DOM 检查定位到 Vite 8 开发客户端错误：

```text
ReferenceError: __BUNDLED_DEV__ is not defined
at /@vite/client:837:22
```

这不是 QTrace API、认证或 React 业务组件错误，而是开发服务器注入的 `/@vite/client` 在当前浏览器运行时崩溃，导致 React 入口没有正常挂载。

## 修复方案

- 在 `frontend/vite.config.js` 中设置 `server.hmr = false`，关闭不需要的热更新通道；开发期间改动后手动刷新页面即可。
- 增加 `qtrace-disable-vite-client-injection` Vite 插件，在开发 HTML 的 post 阶段移除 Vite 8 仍然注入的 `/@vite/client` 标签。
- 保留 `/api`、`/ws` 代理、5174 端口和生产构建行为；没有修改 React 路由、QTrace API 契约、认证、Agent、Embedding 或真实数据。

## 验证证据

- 修复后的 `http://127.0.0.1:5174/` 返回 HTTP 200；HTML 不再包含 `/@vite/client` 或 `/@react-refresh`。
- 本地浏览器重新打开 5174 后，DOM 已出现 QTrace 首页 banner、主标题、在线体验按钮和闭环内容，确认入口已渲染。
- `npm run typecheck`：通过。
- `npm run build`：通过；仅保留大型 bundle 的 Vite 性能提示。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。后续开发服务器不再提供 HMR，修改前端代码后需要手动刷新浏览器。
