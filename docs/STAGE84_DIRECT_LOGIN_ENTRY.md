# 阶段 84：移除启动动画并直达登录

## 目标

用户认为首页开场视频和滚动介绍没有实际训练价值，而且会暴露 TechSpar 前端来源。因此 QTrace 的根路径不再展示 Landing 动画，未登录用户直接进入登录页。

## 实现

- `frontend/src/App.tsx` 移除 `Landing` 活动入口；未登录访问 `/` 直接 `Navigate` 到 `/login`。
- 已登录访问 `/` 直接进入 `/profile`；访问 `/login` 时已有 token 也直接进入 `/profile`，避免多一次跳转。
- `Landing.jsx` 和视频资源没有删除，保留在工程中作为可恢复材料；它们不再被 `App.tsx` 引用，启动视频不会进入活动路由或首屏加载。
- 新增 `scripts/qtrace_entry_preflight.py` 与两条回归，锁定“根路径直达登录”和“Landing/hero-intro 不得成为活动入口”的契约。

## 验证

- `python scripts/qtrace_entry_preflight.py`：通过。
- `python -m pytest -q tests/test_qtrace_entry_preflight.py`：`2 passed`。
- `npm run typecheck`：通过。
- `npm run build`：通过；生产构建不再包含活动入口对开场视频的引用，仅保留已有大型 bundle 提示。
- 浏览器访问 `http://127.0.0.1:5174/`：未登录时路由进入 `/login`，不再播放开场动画。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。工程快照在修改前已保存，路径和 SHA256 记录在阶段总结中。
