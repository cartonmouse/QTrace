# 阶段 82：TechSpar 前端迁移与 QTrace API 适配

## 用户目标

用户明确要求不再保留 QTrace 原有的临时拼装式前端，尽可能复用本地 `techspar` 的前端体验。此次采用“TechSpar 源码作为活动 UI 基线，QTrace 作为后端/API 适配层”的方案，而不是继续在旧 QTrace UI 上局部修补。

## 实现边界

- 正式 `frontend/src` 按相对路径逐文件合并 TechSpar 前端源码；当前活动源码集合与 `D:\3BUPT\mark'workshop\techspar\frontend\src` 的 275 个文件保持一致。
- `src/App.tsx`、页面组件、侧栏、表单、交互节奏和响应式布局来自 TechSpar 基线；QTrace 自有品牌通过 `qtrace-icon.png`、`问迹` 和 `QTrace` 文案替换。
- `src/api/interview.ts` 将 TechSpar 的面试调用适配到 QTrace 的 `/api/interview/start`、`/{session_id}/answer`、`/{session_id}/finish`、历史、画像、主题和模型设置接口。
- `src/api/personalAgent.ts` 将文档上传、会话读取和 Agent 对话适配到 QTrace 的 `/api/agent/*` 接口；本地 Markdown/PDF 入口仍由 QTrace 后端解析和索引。
- `index.html` 的 favicon 和数据导出默认文件名改为 QTrace 品牌；未使用的 TechSpar SVG 资源移到 `frontend/migration_leftovers/techspar-public-unused-20260822`。
- 旧 QTrace 专属 UI 文件没有删除，而是移到 `frontend/migration_leftovers/qtrace-legacy-ui-20260822`；误生成的嵌套副本移到 `frontend/migration_leftovers/components-nested-20260822`。活动源码树不再引用这些旧入口。

## 功能差异与诚实降级

TechSpar 页面可以完整复用，但后端能力不是一一相同。因此适配层保留清晰边界：QTrace 没有独立参考答案、历史删除、文档/对话删除和独立模型连接测试接口时，前端显示明确的“不支持”错误，不伪造成功；QTrace 的回答接口是同步响应，`sendMessageStream` 只把完整回答交给 TechSpar 的回调，不伪装成逐 token 流式输出。接口返回的 API Key 始终不回传。

## 许可与归属

TechSpar 的许可证是 CC BY-NC 4.0。正式仓库保留原项目链接、许可证链接和本说明，明确这是改编版本并保留非商业限制。QTrace 的 API 适配、后端、品牌资源和差异处理属于本项目修改；未经原作者另行许可，不把该前端改编版本用于商业用途。详见 `THIRD_PARTY_NOTICES.md`。

## 验证证据

以下检查均使用本地源码或合成运行态，不读取真实简历、个人文档或 API Key：

- `python scripts/techspar_frontend_preflight.py "D:\\3BUPT\\mark'workshop\\techsnowsong\\rebuild" --reference "D:\\3BUPT\\mark'workshop\\techspar"`：通过；活动源码文件集合无缺失、无旧 UI 文件、QTrace 适配标记和品牌资源齐全。
- `python -m pytest -q --basetemp "C:\\Users\\clearsnowsong\\Documents\\ChatGPT\\秋招\\techsnowsong_stage\\pytest-basetemp-techspar-full"`：`113 passed`。
- `npm run typecheck`：通过。
- `npm run build`：通过；Vite 仍提示部分大型 bundle 超过 500 kB，这是性能优化提示，不是构建失败。
- 本地运行态：`http://127.0.0.1:5174/` 返回 200，`/src/App.tsx` 返回活动入口，前端代理 `/api/health` 返回 `{"status":"ok","mode":"qtrace"}`，`/qtrace-icon.png` 返回 200。

pytest 默认系统临时目录存在 WinError 5 权限问题，因此正式回归必须显式使用项目范围 `--basetemp`；这不是代码失败，也没有修改系统临时目录权限。

## 面试讲解主线

可以这样回答“为什么复用 TechSpar 前端”：

> 我先把 TechSpar 当作成熟的交互基线，复用它的 AppShell、导航分组、训练入口、表单节奏和状态反馈，再把 QTrace 的 FastAPI 接口收敛到一个 adapter 层。这样视觉和交互不需要重新发明，训练状态机、用户隔离、画像、SM-2、个人文档检索和 Agent 仍由 QTrace 后端负责。遇到后端没有对应能力的页面操作，我让适配层明确失败，而不是把前端按钮做成假功能。最后用源码集合预检、TypeScript、构建、全量回归和合成运行态分层验证。

下一步是用户在浏览器中用合成账号验收登录后核心页面、深色/浅色主题、移动侧栏、开始训练、个人 Agent、个人文档导入和模型设置；这部分不能用静态预检替代。GitHub commit/push、公开部署和真实资料联调仍需单独确认。
