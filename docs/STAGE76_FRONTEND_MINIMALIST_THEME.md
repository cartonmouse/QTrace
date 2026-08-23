# 阶段 76：minimalist-ui 浅色主题

## 目标

在阶段 75 的深色 Tactical Telemetry / CRT Terminal 主题之上，增加一套可持久化切换的 `minimalist-ui` 浅色主题。两套主题共享 React 组件、路由、请求逻辑和业务状态，不复制业务页面，也不修改后端 API。

## 主题边界

- 深色主题仍然是默认主题，保留碳黑背景、黄色信号色、网格和扫描线；
- 浅色主题使用暖白画布、白色面板、炭黑文字和 `#EAEAEA` 结构边界；
- 标题采用本地可用的中文衬线字体回退链，正文使用系统无衬线字体，元数据保留等宽字体；
- 低饱和蓝、绿、黄、红只用于状态、标签、焦点和错误语义；
- 浅色主题使用轻量圆角和几乎不可见的分隔阴影，不使用渐变、霓虹、玻璃效果或大面积彩色背景；
- 首页保留 QTrace 的非对称信息结构，但从深色终端的描边标题切换为更安静的编辑感标题和扁平面板。

## 实现方式

- `App.tsx` 增加 `Theme` 类型、`qtrace_theme` 本地持久化键和 `ThemeToggle`；
- 登录页、模型初始化页和工作区侧栏均提供主题切换，切换通过 `document.documentElement.dataset.theme` 驱动 CSS，不影响 token、用户和业务请求；
- `styles.css` 保留深色规则，在 `:root[data-theme="minimalist"]` 下覆盖颜色、字体、面板、表单、导航、首页、设置页和常见反馈状态；
- `frontend_route_preflight.py` 新增主题选择源码契约，检查主题键、切换按钮、`data-theme`、浅色 token 和编辑感字体 token；
- 选择结果只写入浏览器本地 `localStorage`，不写数据库、不发送后端请求，也不读取个人文档。

## 快照与验证

主题改造前创建了严格白名单源码快照：

- 路径：`C:\Users\clearsnowsong\Documents\ChatGPT\秋招\techsnowsong_stage\snapshots\qtrace-pre-minimalist-theme-20260822-142528.zip`；
- SHA256：`17144E47F053B909CEA18290B3F7417942B70195E770BE98759C55CE8BB59295`；
- 快照只包含后端/前端源码、脚本、测试和工程 Markdown，没有包含 `.env`、数据库、`data`、日志、构建产物、依赖目录或阶段临时目录。

暂存工程证据：

- `npm run typecheck` 通过；
- `npm run build` 通过；
- 前端路由、恢复状态、telemetry 和主题选择源码预检通过；
- 前端预检回归为 `14 passed`。

正式工程同步后仍需再次执行全量回归、前端构建、正式源码预检和本地 runtime smoke；登录后的双色主题视觉需要用户使用合成账号人工确认，不能用源码预检替代浏览器验收。

## 面试讲解要点

可以把这次改造解释为“把视觉变化和业务变化解耦”：React 组件继续负责业务状态和 API 调用，主题状态只负责设置根节点属性，CSS token 再根据属性切换视觉层。这样新增浅色主题不需要复制页面，也不会让 LLM、Embedding、SM-2、Agent 或个人文档链路分叉。

## 后续显示修正

用户验收时发现首页左侧 `TRACE / YOUR NEXT / ANSWER.` 在较窄卡片中超过边界。修正同时覆盖深色和浅色主题：降低响应式字号上限、收紧字距、约束标题宽度；浅色主题继续保留极端尺寸下的边界保护，深色主题的字形、配色和整体构图保持不变。修正后的暂存工程 typecheck、build 和前端源码预检均通过。
