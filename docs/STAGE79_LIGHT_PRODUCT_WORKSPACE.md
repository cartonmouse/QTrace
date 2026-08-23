# 阶段 79：浅色产品化工作台

## 目标

用户对前一版前端的反馈是“功能很多，但像临时拼起来的网站”。这一阶段不再继续叠加单页装饰，而是参考 TechSpar 的信息架构和交互节奏，建立 QTrace 自己的浅色产品工作台：

- 默认使用 `minimalist-ui` 浅色主题，深色 Tactical Telemetry 继续作为可选主题；
- 借鉴统一 AppShell、分组导航、模式选择后一主操作、清晰的 loading/empty/error 状态和桌面/移动差异；
- 保留 QTrace 品牌、中文内容、已有路由、React Router、API 契约、Agent、Embedding、个人画像和 SM-2；
- 不复制 TechSpar 的代码、品牌、依赖或页面文案，不引入新的 UI 依赖。

## 实现

### 1. 统一组件层

新增 `frontend/src/components/ProductUI.tsx`，提供三个轻量基础组件：

- `PageHeader`：统一页面 kicker、标题、说明和右侧状态/操作区；
- `Surface`：统一工作台内容表面，避免页面继续直接拼接不同风格的卡片；
- `StatusBadge` 与 `StatePanel`：统一正向/警告/错误状态，以及 loading/empty/error 的可观察反馈。

它们只负责表现层，不持有业务状态，也不发起请求，因此可以逐页迁移而不改变后端接口。

### 2. 工作台壳层

`WorkspaceLayout` 继续保留 `NAV_GROUPS` 和原有路由，但增加产品化语义：

- `product-workspace-shell`：浅色纸张背景、固定侧栏、主区 topbar 和底部状态栏；
- 侧栏显示 QTrace 品牌、个人面试系统定位、分组导航和本地节点状态；
- 桌面侧栏收起偏好继续使用 `qtrace_sidebar_collapsed`，不写入业务数据库；
- 窄屏使用抽屉、遮罩和路由后自动关闭，保留已有移动行为；
- 新增 `product.css`，使用暖灰画布、白色工作表、碳黑正文、砖红信号色和低饱和蓝/绿语义色；不使用渐变和厚重阴影。

### 3. 三条核心路径

- “开始训练”接入 `PageHeader`、模式工作台和一主操作区；四个入口仍然对应原有简历模拟、专项训练、JD 定向和录音复盘；
- “我的画像”接入统一标题、今日复习状态、SM-2 队列和 loading/error 状态；
- “个人 Agent”接入统一标题、对话历史、空状态、文档库、工具 trace 和学习计划区域；Agent 的请求、工具白名单、草稿确认和计划完成逻辑不变；
- 其他旧页面通过工作台级样式获得统一的标题、输入、表面和按钮语言，后续可以继续按同一组件层迁移。

## 验证

暂存工程已通过：

```text
frontend: npm run typecheck       PASS
frontend: npm run build           PASS
python scripts/frontend_route_preflight.py  PASS
python -m pytest -q tests/test_frontend_route_preflight.py  14 passed
```

源码预检新增 `REQUIRED_PRODUCT_WORKSPACE_MARKERS` 和 `REQUIRED_PRODUCT_STYLE_MARKERS`，检查新的组件文件、工作台挂载点、页面状态组件和浅色样式关键选择器是否存在。

已用本地独立暂存前端打开浅色登录入口进行视觉检查，确认浅色主题、中文衬线标题、表单层级和主题切换入口能够渲染；登录后工作区、真实请求、侧栏交互和窄屏布局仍需用户在合成账号边界下人工验收，不能把静态构建或登录页截图说成完整 E2E。

同步正式工程后补充通过：

```text
正式 frontend: npm run typecheck       PASS
正式 frontend: npm run build           PASS
正式 frontend_route_preflight          PASS
正式前端契约回归                        14 passed
正式全量 Python 回归                    109 passed
正式 local_runtime_smoke                PASS
正式 final_delivery_preflight           PASS
```

第一次正式 runtime smoke 使用了缺少 `/api/health` 的端口参数，因此只报告后端不可达；修正为 `http://127.0.0.1:8007/api/health` 后，在隔离合成数据库上通过。第一次正式前端契约回归还遇到 Windows 系统临时目录权限拒绝，改用项目范围内全新的 basetemp 后通过。这两次都不是断言失败，也没有删除系统临时目录。

本阶段改造前源码白名单快照：

```text
C:\Users\clearsnowsong\Documents\ChatGPT\秋招\techsnowsong_stage\snapshots\qtrace-pre-light-product-workspace-20260822-151302.zip
SHA256: 0A1C3C9E9ED64F87241051629460102A3CE0A07E3EECE2E3727C5973E0833D06
```

快照不包含 `.env`、API Key、数据库、真实简历、个人文档、日志、依赖目录或构建产物。本阶段没有调用外部 API、删除文件、部署或提交推送 GitHub。

## 面试讲法

> 我没有把 TechSpar 的页面直接复制过来，而是先拆它为什么顺滑：AppShell 统一、导航有层级、用户先选训练模式再执行一个主动作、异步状态可见、桌面和移动端有不同的导航形态。然后我在不改变 FastAPI 接口和训练状态机的前提下，新增 QTrace 的 PageHeader、Surface、StatusBadge、StatePanel 和浅色 token，把首页、画像和 Agent 三条主链迁移到同一套工作台。这样视觉改造的风险集中在表现层，既能保留后端功能，也方便逐页回归。

## 下一步

1. 用户使用当前合成账号验收开始训练、个人 Agent、我的画像、模型设置，以及 DARK/LIGHT 和窄屏布局；
2. 若视觉方向通过，再继续把旧页面头部逐步替换为 `PageHeader`，不一次性重写所有业务页面；
3. GitHub 提交/推送、公开部署和真实资料复现仍需单独确认。
