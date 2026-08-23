# 阶段 89：QTrace 本地验收清单

这份清单用于项目收口后的人工验收。自动化证据已经覆盖源码契约、Python 回归、前端 typecheck、备用生产构建、未登录入口和后端健康；以下项目必须在本机使用“全新合成账号”完成，不能用真实简历、真实个人文档或真实 API Key 代替。

## 1. 启动与入口

- [ ] 后端运行在 `127.0.0.1:8002`，前端运行在 `127.0.0.1:5174`；访问 `http://127.0.0.1:5174/` 能打开登录页；
- [ ] 首屏不播放 Landing/启动视频，不出现黑屏；刷新后仍能回到登录页；
- [ ] `http://127.0.0.1:5174/api/health` 返回 `status=ok`、`mode=qtrace`；
- [ ] 用全新合成账号注册/登录，不复用任何个人账号。

## 2. 工作台与核心训练

- [ ] 登录后看到 QTrace 工作台、图标和分组导航；桌面收起、移动抽屉、主题切换和退出入口可操作；
- [ ] `/profile` 首屏能看到 `PERSONAL MEMORY` 信息层；空状态下三个训练入口分别能跳转到专项训练、简历面试和 JD 备面；
- [ ] “开始训练”页的 `live`/`targeted` 模式可切换，浏览器后退/刷新后 URL 模式仍可恢复；键盘左右/Home/End 切换不越界；
- [ ] 简历模拟只使用合成文本或无敏感的测试 PDF；能够进入训练，不把静态页面当成已完成的面试链路。

## 3. 模型设置可观察性

- [ ] `/settings` 首屏看到 LLM、Embedding、保存三块状态读数；初始状态为“待测试/待保存”，不会误显示“已连接”；
- [ ] 点击 LLM“测试连接”后能看到“测试中”，成功显示“已连接”，失败显示 `role=alert` 的脱敏诊断；页面不展示 API Key；
- [ ] 选择 Embedding“本地”，填写合成或已下载模型目录，保存后能看到“已保存”；点击测试后能区分“测试中/已连接/连接失败”；
- [ ] 修改 Embedding 配置后出现“需要更新向量索引”提示；点击重建后能看到进度、完成或失败状态；
- [ ] 未启动后端或填写故意无效的合成配置时，页面显示失败原因而不是只刷新；恢复配置后可重新测试。

## 4. 文档、Agent 与图谱

- [ ] 个人文档库用合成 `.md` 和文本型 `.pdf` 各导入一次，能看到处理中、成功/重复/失败状态；
- [ ] 个人 Agent 能读取合成画像、SM-2 到期项、知识图谱或文档 citation；计划先是 draft，确认后才写入；
- [ ] 知识图谱页面能从主题/问题节点进入训练或 Agent，且 URL 来源参数可恢复；
- [ ] 不把“有文档”“有向量”“有 Agent 回答”混为同一个证据：分别记录导入、reindex、检索引用和回答结果。

## 5. 自动化复核命令

在正式工程根目录运行：

```powershell
python scripts\qtrace_entry_preflight.py
python scripts\qtrace_shell_preflight.py
python scripts\qtrace_interview_preflight.py
python scripts\qtrace_profile_preflight.py
python scripts\qtrace_settings_preflight.py
python scripts\final_delivery_preflight.py
Set-Location frontend
npm run typecheck
npm run build -- --configLoader runner --outDir "C:\Users\clearsnowsong\Documents\ChatGPT\秋招\techsnowsong_stage\qtrace_final_dist"
```

本次收口使用全新的合成 SQLite（通过 `REBUILD_DB_PATH` 指向工程暂存目录）运行全量 Python 回归：`124 passed`。正式工程默认 SQLite 不作为回归目标，避免把个人运行态数据和测试写入混在一起；Windows 正式 `.pytest_cache` 的权限警告不影响测试结果。代码语法也通过了不写入 `__pycache__` 的内存编译检查。

当前 Windows 环境对正式 `frontend/node_modules/.vite-temp` 和 `frontend/dist` 的写入存在既有 `EPERM`；不得删除依赖或构建产物来“修复”它。备用输出目录构建成功即可作为本机当前环境的构建证据，标准构建边界要在汇报中如实说明。

## 通过标准与未完成边界

当入口、工作台、训练、设置反馈、文档导入和 Agent/图谱人工路径均勾选，且自动化预检/typecheck/备用 build 通过时，可称为“本地可验收版本”。这不等于全新机器复现、真实 LLM 质量、真实资料隐私治理、完整浏览器 E2E、真实长音频/说话人分离/时间戳、外部部署或 GitHub 推送已经完成；这些仍是单独的后续工作，不应在面试中夸大。

本清单只使用合成数据，不读取或输出 API Key、真实简历、个人文档或浏览器存储。
