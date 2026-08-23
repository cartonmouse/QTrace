# 阶段 85：QTrace 自有工作台外壳

## 目标

阶段 84 已经移除首页开场动画，但登录后的活动界面仍然直接使用 TechSpar 的侧栏壳层。为了保留成熟交互规律、同时降低“原样复用”的风险，本阶段先把最上层的 AppShell 改成 QTrace 自有实现。页面业务和 API adapter 暂不改动，避免一次变更同时影响训练状态机。

## 实现

- 新增 `frontend/src/components/QTraceWorkspaceShell.tsx`，独立维护 QTrace 品牌区、训练路径/长期记忆/素材图谱三组导航、当前路径 command bar、主题切换、设置入口、账户区、桌面收起和移动抽屉；
- 新增 `frontend/src/components/qtrace-workspace.css`，建立 QTrace 自有的纸张画布、碳黑文字、砖红信号色、硬边分区和响应式 token；没有新增依赖，也没有把 TechSpar 的 `Sidebar` 继续挂到活动 `App.tsx`；
- `frontend/src/App.tsx` 只把 `AppShell` 的外壳替换为 `QTraceWorkspaceShell`，保留认证、ProviderGate、路由、页面和 API adapter；阶段 84 的根路径直达登录契约仍然有效；
- `scripts/qtrace_shell_preflight.py` 与 3 条回归锁定 QTrace 外壳的活动挂载、自有 CSS、可访问导航和禁止重新导入 `Sidebar`/`Landing`；
- `scripts/techspar_frontend_preflight.py` 调整为“参考基线审计”：TechSpar 文件集合差异只作为 INFO 输出，不再把 QTrace 自有外壳当成错误；真正的活动外壳由独立 shell preflight 阻断回归。

## 验证

- `python scripts/qtrace_shell_preflight.py`：通过；
- `python scripts/techspar_frontend_preflight.py`：通过；输出 QTrace 自有文件的参考差异为 INFO，不再要求活动源码集合与参考仓库完全相同；
- `python -m pytest -q tests/test_qtrace_shell_preflight.py tests/test_techspar_frontend_preflight.py --basetemp <项目暂存目录>`：`5 passed`；Windows 系统 `.pytest_cache` 权限警告仍是环境问题，不影响结果；
- `npm run typecheck`：通过；
- `npm run build`：标准命令在本机既有 `node_modules/.vite-temp` 和正式 `dist/qtrace-icon.png` 写入点遇到 Windows `EPERM`；未删除或修改依赖/构建目录，改用 `npm run build -- --configLoader runner --outDir "C:\\Users\\clearsnowsong\\Documents\\ChatGPT\\秋招\\techsnowsong_stage\\qtrace_stage85_dist"` 完成构建，3808 个模块转换成功，仅保留大型 bundle 提示；
- `python scripts/qtrace_entry_preflight.py`：阶段 84 入口契约继续通过。

## 当前边界与下一步

本阶段完成的是活动 AppShell 去同质化，不代表所有业务页面已经重写。`Landing.jsx`、`Sidebar.tsx` 和 TechSpar-derived 页面文件仍作为可审计/可恢复材料存在；`App.tsx` 当前不再导入 `Landing` 或 `Sidebar`，页面内部业务功能和 adapter 仍保持可运行。下一阶段优先重写 `/profile` 首页信息层和 `/mock-interview` 开始训练入口，继续复用交互规律而不是复制源码。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。登录后的完整工作区仍需要用户使用合成账号进行视觉和交互验收。
