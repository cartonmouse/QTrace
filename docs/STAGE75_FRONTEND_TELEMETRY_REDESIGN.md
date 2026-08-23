# 阶段 75：前端 Tactical Telemetry 重设计

## 背景

前一轮阶段 72 只对模型设置页做了浅色 Swiss Industrial Print 局部改造，主应用仍然是米白背景、绿色侧栏、圆角卡片和柔和阴影。这与用户提供的深色终端风格参考图不一致，也没有形成完整的 QTrace 视觉系统。

本阶段重新按两份前端 skill 审计并选择单一视觉原型：industrial-brutalist-ui 中的 Tactical Telemetry / CRT Terminal。用户参考图是方向依据，保留的是 QTrace 的功能、路由、中文内容和品牌，不复制参考图中的旅行产品文案。

## 实现

### 应用壳层

- 左侧导航改为深色现场系统面板，按 INTERVIEW LOOP、KNOWLEDGE SYSTEM、SYSTEM CONTROL 分组；
- 当前路由使用黄色信号色和 >> 指示，非当前路由使用 // 技术前缀；
- 主工作区增加 QTRACE / PERSONAL INTERVIEW SYSTEM 顶栏、ROUTE ENGINE / ONLINE 状态和底部系统标语；
- 保留所有既有导航路径、认证状态、退出逻辑和 Outlet 渲染边界。

### 视觉系统

- 全局底色改为近黑色终端基底，前景使用暖白，黄色作为唯一主信号色，橙红只用于错误和危险状态；
- 采用硬边框、直角控件、无阴影、无圆角和深色面板；
- 通过低对比扫描线和网格纹理模拟 CRT / 现场遥测介质，但不加入第三方依赖；
- 使用巨型紧缩无衬线显示字与等宽技术标签形成比例对比；
- 所有旧页面的卡片、表格、状态行、标签和输入控件统一接入同一套 token，模型设置页保留原有成功、失败、loading 和重试语义。

### 首页主构图

首页改为参考图的非对称工作台：左侧展示 TRACE / YOUR NEXT / ANSWER. 的系统主标题、训练阶段和运行读数，右侧保留目标岗位、PDF 简历上传、项目摘要和开始面试表单。表单仍调用原有接口，没有改变面试启动协议。

### 响应式和可访问性

- 980px 以下将侧栏和工作区收束为单列，首页表单与主标题按顺序堆叠；
- 680px 以下压缩导航网格、巨型标题和阶段列表，保持输入控件可操作；
- 保留 loading、error、success、disabled 和 role 反馈；
- 增加全局 reduced-motion 保护，焦点状态使用黄色高对比轮廓。

## 快照

改造前快照已保存到：

    C:\Users\clearsnowsong\Documents\ChatGPT\秋招\techsnowsong_stage\snapshots\qtrace-pre-telemetry-redesign-20260822-140204.zip

SHA256：

    5C9F2FFFA14A7663F4BA36378814DD1EC314EB33E24D4B548B21AF9DABBD2620

快照没有纳入 .git、.env、SQLite 数据库、日志、node_modules、dist 或阶段临时目录。

## 验收证据

正式工程通过：

    npm run typecheck       PASS
    npm run build           PASS
    python scripts/frontend_route_preflight.py .    PASS
    pytest tests/test_frontend_route_preflight.py -q    13 passed
    pytest --basetemp qtrace_telemetry_formal_pytest_tmp    108 passed
    python scripts/local_runtime_smoke.py ...    PASS

本地运行态仍确认 backend health、前端入口和 dist 资源可访问。新增前端预检锁定 telemetry-shell、workspace-command-bar、sidebar-signal、dashboard-display-title、status-dot 和主题 token。

## 面试讲法

> 我先承认前一轮只是设置页局部样式，没有形成完整视觉系统。根据参考图，我把方向切换到 Tactical Telemetry / CRT Terminal：用统一的暗色基底、黄色信号色、硬边网格、终端状态栏和巨型结构化标题重做应用壳层，同时只改变 presentation layer，不动 React 路由、后端 API 和业务状态机。首页把训练输入和系统输出做成非对称工作台，页面内的 loading、error、success 和 disabled 状态继续沿用原有语义。

## 未完成边界

- 当前自动化只能验证源码契约、构建和 HTTP 入口，没有在已登录浏览器中输入密码或读取 localStorage；
- 需要用户使用合成账号人工查看首页、模型设置、专项训练、Agent 和知识库页面的视觉细节；
- 本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或提交推送 GitHub。
