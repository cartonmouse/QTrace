# 阶段 86：QTrace 开始训练工作台

## 目标

阶段 85 只替换了活动 AppShell，`/mock-interview` 内部仍保留参考项目式的圆角卡片和通用 Tailwind 排版。本阶段把“开始训练”页的上层信息架构改成 QTrace 自有的训练工作台：保留两个业务模式、URL 参数、键盘切换和子流程，但让用户先看清当前路径、输入要求和唯一主任务。

## 实现

- `frontend/src/pages/MockInterview.tsx` 保留 `live/targeted` 两种模式和 `ResumeInterview`/`JobPrep` 嵌入，不改变 `/mock-interview?mode=...`、`/resume-interview` 和 `/job-prep` 路由契约；
- 页面新增 QTrace 自有的 `01 / INTERVIEW LOOP` 首屏信息、当前模式 readout、`02 / SELECT MODE` 模式选择、输入要求说明和专项训练跳转；
- 新增 `frontend/src/pages/qtrace-interview.css`，使用工作台的纸张画布、砖红信号色、硬边模式条、响应式双列/单列和 reduced-motion；去除该页原先依赖的圆角模式卡和装饰性阴影；
- 使用真实 `role=tablist`/`role=tab`/`role=tabpanel` 和原有左右/Home/End 键盘切换，视觉改造没有牺牲可访问交互；
- 新增 `scripts/qtrace_interview_preflight.py` 与 2 条回归，锁定 QTrace 页面样式挂载、模式选择和子面板边界。

## 验证

- `python scripts/qtrace_interview_preflight.py`：通过；
- `python -m pytest -q tests/test_qtrace_interview_preflight.py tests/test_qtrace_shell_preflight.py tests/test_techspar_frontend_preflight.py --basetemp <项目暂存目录>`：`7 passed`；Windows 系统 `.pytest_cache` 权限警告仍是环境问题；
- `npm run typecheck`：通过；
- `npm run build -- --configLoader runner --outDir "C:\\Users\\clearsnowsong\\Documents\\ChatGPT\\秋招\\techsnowsong_stage\\qtrace_stage86_dist"`：通过，3809 个模块转换成功，仅有大型 bundle 提示；
- `python scripts/qtrace_entry_preflight.py`：阶段 84 入口契约继续通过；
- 未登录浏览器入口检查：`http://127.0.0.1:5174/` 仍进入 `/login`；登录后该页的视觉和模式交互需要用户用合成账号验收。

## 当前边界与下一步

本阶段只重写“开始训练”的页面编排层，`ResumeInterview` 和 `JobPrep` 的资料上传、JD 解析和 `/interview/start` 仍由原业务组件负责。下一步优先迁移 `/profile` 的空状态/训练统计首屏，使画像能和训练入口形成一条 QTrace 自有的学习闭环；真实 LLM、真实简历和浏览器完整 E2E 不在本阶段自动调用。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。
