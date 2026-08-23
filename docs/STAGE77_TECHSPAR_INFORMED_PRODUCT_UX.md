# 阶段 77：TechSpar-informed 产品工作台重设计

## 目标

用户反馈当前 QTrace 前端虽然已经有较多页面和功能，但整体像“临时拼起来的网站”，使用起来不够顺滑。本阶段把 `D:\3BUPT\mark'workshop\techspar` 作为只读产品参考，借鉴它的工作台结构和交互节奏，重做 QTrace 的应用壳层与“开始训练”入口。

本阶段不是复制 TechSpar 的代码或品牌，而是把可迁移的产品规律落到 QTrace：

```text
成熟工作台
  -> 清晰的导航分组和当前路由
  -> 先选择训练模式
  -> 只展示当前模式的一主操作
  -> loading / empty / error 都有可见反馈
  -> 桌面侧栏可收起，窄屏侧栏变为抽屉
```

设计取向：`DESIGN_VARIANCE=5`、`MOTION_INTENSITY=3`、`VISUAL_DENSITY=4`。这是多页面学习产品，不是营销落地页；视觉重点放在任务层级、信息节奏和可恢复交互，保留 QTrace 的深色/浅色主题选择。

## 只读审计结论

TechSpar 的流畅感主要来自结构，而不是单个颜色或组件：

- AppShell 统一包裹 Sidebar 和主内容，Sidebar 有桌面收起、移动抽屉、路由 active 状态和主题入口；
- 首页先选择训练模式，再展开一个主操作；没有把所有动作同时堆在首屏；
- 复杂页面使用 skeleton、空态、错误态和重试，而不是只显示一句“加载中”；
- 页面使用稳定的最大宽度、页面级标题区、Card/Button/Badge 等重复模式；
- 操作按钮和训练来源被显式放在上下文中，用户知道“现在在哪里”和“下一步做什么”。

QTrace 当前只有 React、React Router、Vite 和 TypeScript，没有直接照搬 TechSpar 的 Tailwind、Radix、Framer Motion 或图标依赖。本阶段用原生 CSS 与现有 React 组件完成同样的交互结构，避免为视觉参考引入不必要的依赖迁移。

## 实现内容

### 1. 工作台导航

`frontend/src/App.tsx` 的 `WorkspaceLayout` 现在：

- 用 `NAV_GROUPS` 统一维护 Interview Loop、Knowledge System、System Control 三组导航，避免手写链接造成结构漂移；
- 增加桌面侧栏收起状态，持久化键为 `qtrace_sidebar_collapsed`；收起后保留标记式导航和 `title` 文本，不丢失路由能力；
- 增加窄屏菜单按钮、抽屉侧栏和遮罩层，路由变化后自动关闭抽屉；
- 保留 `ThemeToggle`、退出登录、当前用户和既有 `NavLink` active 状态；
- 不改变路由、认证门禁、Outlet、API 请求或业务页面。

### 2. 开始训练入口

首页从“左侧巨大展示标题 + 右侧表单”改为两段工作流：

1. `TRAINING_MODES` 提供四个训练入口：简历模拟、专项训练、JD 定向、录音复盘；
2. 用户选择模式后只展示当前路径的一主操作；
3. 简历模拟继续保留原来的岗位、PDF 上传、项目摘要和 `/interview/start` 请求；
4. 其他模式通过已有路由进入对应页面，不复制后端逻辑；
5. PDF 简历状态增加明确的读取 skeleton，上传失败和启动失败使用 `role="alert"`；
6. 页面底部增加三步训练节奏说明，让用户理解“选择入口 -> 完成动作 -> 写回复盘”的闭环。

这解决了之前首屏的问题：展示型标题占据大量空间，却没有帮助用户理解训练入口；现在首页先回答“我今天要练什么”，再展示“这个动作如何开始”。

### 3. 视觉与响应式

`frontend/src/styles.css` 新增 Stage 77 的工作台层：

- `qtrace-workspace-shell` 负责稳定的侧栏/主区网格；
- `training-mode-grid`、`dashboard-action-panel` 和 `dashboard-ritual` 负责首页的信息层级；
- 深色模式继续使用 QTrace 的技术终端 token，浅色模式继续使用 `minimalist-ui` 暖白 token；两套主题共享布局和交互，不复制业务页面；
- 训练卡有 hover、focus-visible、selected、disabled 等状态；
- 980px 以下切换为移动抽屉，680px 以下收束为单列；
- skeleton 动效受 `prefers-reduced-motion` 约束。

## 验证记录

暂存工程已完成：

```text
frontend: npm run typecheck       PASS
frontend: npm run build           PASS
python scripts/frontend_route_preflight.py  PASS
python -m pytest -q tests/test_frontend_route_preflight.py  14 passed
```

前端预检新增 `REQUIRED_PRODUCT_UX_MARKERS`，只读检查工作台壳层、移动菜单、模式选择、首页主操作和 skeleton 标记。它仍然是源码契约，不等同于浏览器 E2E。

正式工程同步后的验证也已完成：

```text
frontend: npm run typecheck       PASS
frontend: npm run build           PASS
python scripts/frontend_route_preflight.py  PASS
python -m pytest -q tests/test_frontend_route_preflight.py  14 passed
python -m pytest -q -p no:cacheprovider --basetemp <synthetic-temp>  109 passed
python scripts/local_runtime_smoke.py       PASS
python scripts/final_delivery_preflight.py  PASS
```

全量回归使用全新合成 SQLite 和暂存目录作为测试临时目录，避免读取或写入正式日常数据库；交付预检只提示现有 15 个本地日志/数据等产物待人工审阅，没有发现明显密钥模式。第一次直接运行全量 pytest 时，系统临时目录因 Windows 权限拒绝而失败，改用项目暂存 basetemp 后通过；这属于运行环境问题，不是测试断言失败。

改造前源码白名单快照：

```text
qtrace-pre-techspar-ux-20260822-144831.zip
SHA256: 4FC3E7C3D53C703A5804D31DF474733805BC2A9E894336879D88D292E2A10BCE
```

快照只包含源码、测试、脚本和 Markdown 文档，没有包含 `.env`、API Key、数据库、真实简历、个人文档、日志、依赖目录或构建产物。

## 仍需人工验收

以下内容不在静态预检能力内，需要用户在已登录的本地浏览器中使用合成数据确认：

1. 桌面侧栏收起、刷新后状态保留、active 路由是否符合预期；
2. 窄屏菜单打开、遮罩关闭、点击路由后抽屉自动关闭；
3. 深色/浅色主题下首页四种模式选择、焦点态和主按钮是否舒服；
4. 简历模拟的 PDF 上传、摘要输入和启动面试是否仍正常；
5. 专项训练、JD 定向、录音复盘三个入口是否能进入既有页面；
6. 后端未启动或请求失败时，首页错误提示是否清晰且不会误显示成功。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或提交推送 GitHub。

## 面试讲法

> 我没有把参考项目的组件库直接搬过来，而是先拆它为什么顺滑：统一 AppShell、路由感知导航、模式选择后再展示主操作、明确的 loading/empty/error 状态，以及桌面和移动端不同的导航形态。QTrace 保留原有 React Router、FastAPI API 和业务链路，用现有依赖实现了同样的工作流结构。这样视觉重构不会改变面试状态机、Agent、Embedding 或 SM-2 的数据契约，风险集中在前端交互层，也更容易回归验证。

可继续追问：

- 为什么首页不直接展示四个“开始”按钮？因为选择模式和执行动作是两个不同决策，先选模式可以减少首屏竞争；
- 为什么侧栏收起状态只放 localStorage？它是纯 UI 偏好，不属于用户业务事实，不需要写入 SQLite；
- 为什么没有直接安装 TechSpar 的 Tailwind/Radix？参考的是交互规律，不是依赖清单；在现有项目上引入整套 UI 栈会扩大变更面并增加复现成本；
- 静态预检能证明什么？能证明主要路由和关键 UI 标记还在，不能证明真实浏览器点击、请求持久化或视觉观感，所以仍要做合成账号人工彩排。
