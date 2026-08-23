# Stage 81：QTrace 品牌图标挂载到工作台

## 目标

用户希望把之前生成的 QTrace 图标放到左上角标题区域展示，同时不破坏现有的浅色/深色主题、桌面收起侧栏和窄屏导航。

## 实现

- 复用已有静态资源 `frontend/public/qtrace-icon.png`，没有重新生成、上传或引入图片依赖；
- `WorkspaceLayout` 用 `<img className="brand-mark" src="/qtrace-icon.png" ... />` 替换原来的 `QT` 文字方块；
- “问迹 / QTRACE GROWTH LAB” 继续使用文本渲染，保证标题可读性和无障碍语义；
- `product.css` 为图片设置固定尺寸、`object-fit: cover` 和主题可见边框；收起侧栏时仅隐藏 `brand-copy`，图标保留；
- `frontend_route_preflight.py` 增加静态图标路径标记，防止品牌资源回退成文字占位。

## 验证

- 正式工程 `npm run typecheck`：通过；
- 正式工程 `npm run build`：通过；
- 正式工程 `python scripts/frontend_route_preflight.py`：通过；
- 正式工程前端契约回归：`14 passed`；
- `git diff --check` 未发现补丁空白错误。

## 面试讲解

这不是“把 Logo 硬编码进页面”，而是一个小型表现层改动：静态资源由 Vite/浏览器负责加载，React 只负责语义挂载，CSS 负责尺寸和响应式状态，静态预检负责防回归。业务层的认证、路由、训练状态机和 API 契约没有变化。

## 边界

当前只完成代码级验证，没有把浏览器截图或主题切换的真实观感写成自动化结论；用户仍需在本地已登录页面确认图标尺寸、浅色/深色对比度和收起侧栏状态。本阶段未读取或输出 API Key、真实简历或个人文档，没有调用外部 API、删除文件、部署或提交推送 GitHub。
