# 阶段 87：QTrace 画像首页工作台

## 目标

阶段 86 已经把“开始训练”页的模式选择改成 QTrace 自有编排，但登录后根路径会落到 `/profile`，这个页面仍然使用参考项目式的圆角卡片和渐变空状态。本阶段优先处理用户首次进入时看到的画像首屏，建立“个人记忆 -> 选择下一次训练”的 QTrace 视觉闭环。

## 实现

- `frontend/src/pages/Profile.jsx` 保留 `getProfile`、`getTopics`、`markProfileViewed`、画像派生函数、SM-2 到期复习计算、专题跳转和所有数据展示组件；
- 空状态改成 `00 / PERSONAL MEMORY` 标题、训练数据状态 badge、解释性首屏和三个硬边训练入口，入口仍分别跳转 `/topic-drill`、`/resume-interview`、`/job-prep`；
- 有数据状态增加同一套 QTrace 标题层，并把访问变化、到期复习、统计、知识证据、能力地图、表现特征和趋势卡统一接入 `qtrace-profile-surface`，不改变组件内部的数据契约；
- 新增 `frontend/src/pages/qtrace-profile.css`，去除画像首屏的渐变和厚重圆角，使用纸张面板、信号红、左侧统计刻度、窄屏单列和 reduced-motion；
- 新增 `scripts/qtrace_profile_preflight.py` 与 2 条回归，锁定画像 CSS 挂载、空状态入口、统计首屏和真实画像 API 边界。

## 验证

- `python scripts/qtrace_profile_preflight.py`：通过；
- `python -m pytest -q tests/test_qtrace_profile_preflight.py tests/test_qtrace_interview_preflight.py tests/test_qtrace_shell_preflight.py --basetemp <项目暂存目录>`：`7 passed`；Windows 系统 `.pytest_cache` 权限警告仍是环境问题；
- `npm run typecheck`：通过；
- `npm run build -- --configLoader runner --outDir "C:\\Users\\clearsnowsong\\Documents\\ChatGPT\\秋招\\techsnowsong_stage\\qtrace_stage87_dist"`：通过，3810 个模块转换成功，仅保留大型 bundle 提示；
- `python scripts/qtrace_entry_preflight.py`：通过；
- 5174 未登录访问 `/`：仍进入 `/login`，没有重新加载 Landing/启动视频；登录后画像空状态和训练入口仍需用户使用合成账号人工验收。

## 当前边界与下一步

本阶段没有修改画像数据模型、后端 API、SM-2、Embedding、LLM 或子组件内部交互；只是先把首屏信息架构和视觉层独立出来。下一步可继续迁移画像内部的知识证据/能力地图，或转向模型设置页的状态反馈验收；真实简历、真实 LLM 和完整浏览器 E2E 仍不在自动阶段内。

本阶段没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或 GitHub commit/push。
