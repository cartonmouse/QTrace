# 阶段 93：本地运行态交接与 session Key 状态清理

## 目标

让本地浏览器验收使用当前 QTrace 前端和当前后端，避免旧监听实例掩盖新接口；同时修正公开 Demo 的 session BYOK 在切换 Embedding 模式后可能残留内存 Key 的状态问题。

## 实现

- 通过健康接口、OpenAPI 路由和前端源码标记确认 5174 当前实例是 QTrace 活动前端，包含自有工作台、直达登录和真实 `testLLMConnection` adapter；
- 只重启确认属于 QTrace 的 8002 旧后端，把 `REBUILD_DB_PATH`/`REBUILD_DATA_DIR` 指向阶段暂存目录的合成运行数据，避免读取或修改正式本地数据库；
- 在 `Store.set_embedding_demo` 和 `Store.set_local_embedding` 中仅对 `session` 模式清除对应用户的进程内 Embedding Key；本地 `persisted` 模式保持兼容；
- 增加回归，覆盖“远程 Embedding -> Demo”和“远程 Embedding -> 本地模型”两条切换路径，确认 `get_embedding_config().api_key` 与 `embedding_key_configured` 都被清零。

## 验证证据

- `test_byok_storage.py`：`3 passed`；
- 隔离全量 Python 回归：`136 passed`，仅有当前 Windows 正式 `.pytest_cache` 写入权限警告；
- `npm run typecheck`：通过；
- 暂存目录生产构建：3811 modules transformed，只有 outDir/大 chunk/插件耗时提示；
- `public_demo_preflight.py`、`qtrace_byok_preflight.py`、`final_delivery_preflight.py`：通过；
- HTTP 合成彩排：5174 前端和 `/api/health` 代理返回 200；合成账号注册、受保护设置读取、空配置 LLM 测试分支通过；8002 OpenAPI 包含 `/api/settings/test-llm` 与 `/api/agent/documents/upload`；
- 本地服务当前使用阶段暂存 SQLite/Data 目录，不调用真实 LLM、Embedding 或其他外部 API。

## 未完成与交接

这是本地可验收交接，不是公网部署。当前没有公网 URL、云账号、域名或 HTTPS；公开前仍需 API Base SSRF/私网阻断、限流、调用预算、日志治理、备份和部署环境配置。正式工程的 Vite `.vite-temp` 与默认 SQLite 写入仍受当前 Windows 权限边界影响，不能通过删除文件规避；构建和运行态验证使用暂存输出与隔离数据完成。

人工验收入口：`http://127.0.0.1:5174/login`。请使用新的合成账号验证登录、Stub 离线训练、模型设置反馈、PDF/Markdown 导入、Personal Agent、知识图谱、主题切换和窄屏布局；不要输入真实简历、真实 API Key 或真实个人文档。
