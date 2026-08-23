# 阶段 60：隔离浏览器彩排配置前置检查

阶段 57 已经可以准备一套全新的合成 SQLite，阶段 53 也明确浏览器点击需要由用户人工完成。本阶段把“后端使用哪一份库”和“前端请求转发到哪个后端”固定成可检查的环境契约，降低误把演示操作发到日常本地账号的风险。

## 新增只读检查

`python scripts\isolated_demo_preflight.py` 检查三件事：

- `backend/config.py` 是否支持 `REBUILD_DB_PATH` 和 `REBUILD_DATA_DIR`；
- `frontend/vite.config.ts` 是否保留 `REBUILD_API_TARGET`，以及默认端口 `5174`/后端端口 `8002`；
- `scripts/seed_synthetic_browser_demo.py` 是否仍然提供新 SQLite、`--db` 门禁和 StubProvider 合成数据入口。

它只读源码，不创建数据库、不启动服务、不打开浏览器、不读取浏览器存储、不读取 SQLite 或个人资料，也不调用外部 API。通过只说明隔离启动入口仍然存在，不能说明浏览器彩排已完成。

## 使用新库启动隔离演示

应当选择一个尚不存在的路径。下面示例使用项目 `data` 目录中的新文件名；如果该文件或 SQLite sidecar 已经存在，种子脚本会拒绝覆盖，用户应换一个新文件名：

```powershell
Set-Location -LiteralPath '<project>\rebuild'
python scripts\seed_synthetic_browser_demo.py --db data\qtrace-browser-demo-stage60.sqlite3
$env:REBUILD_DB_PATH = (Resolve-Path 'data\qtrace-browser-demo-stage60.sqlite3').Path
$env:REBUILD_DATA_DIR = (Resolve-Path 'data').Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8003
```

另开前端终端，使用不同端口和显式的后端目标：

```powershell
Set-Location -LiteralPath '<project>\rebuild\frontend'
$env:REBUILD_API_TARGET = 'http://127.0.0.1:8003'
npm run dev -- --host 127.0.0.1 --port 5175
```

浏览器打开 `http://127.0.0.1:5175`，使用种子脚本输出的合成账号登录。这样后端使用新库、前端使用新端口，现有的 `8002/5174` 本地运行实例不会被彩排请求复用。彩排结束后不要把合成演示库当成真实用户数据，也不要把它提交到公开仓库。

阶段 61 起，种子脚本还会直接打印 `BACKEND_URL`、`FRONTEND_URL` 和 `REBUILD_API_TARGET`，可以把输出作为本次启动的端点核对单；这些提示不会自动启动服务。

如果 `8003` 或 `5175` 已被其他本地进程占用，不要自动停止未知进程；种子脚本支持 `--backend-port` 和 `--frontend-port`，换用一组空闲端口后，再把输出的 `REBUILD_API_TARGET` 传给前端。实际端口连通性检查见阶段 62。

## 面试讲解卡

### 为什么要同时改数据库路径、后端端口和前端端口？

只换账号不够安全，因为新前端仍可能请求旧后端。只换数据库也不够直观，因为两个服务端口相同会让人工操作难以确认当前连接。阶段 60 通过 `REBUILD_DB_PATH`/`REBUILD_DATA_DIR`、后端 `8003`、前端 `5175` 和 Vite 的 `REBUILD_API_TARGET` 把隔离边界显式化。

### 这个脚本是否证明了浏览器 E2E？

不证明。它只证明源码仍保留隔离启动契约；种子脚本证明新库可以准备，后端合成彩排证明 API 状态链路，真正的登录、页面请求、图谱跳转、Agent draft/confirm 和视觉布局仍需用户在合成数据下人工点击。

### 为什么不让自动化直接操作当前浏览器？

当前浏览器可能已经有用户账号、cookie 或真实页面内容。自动任务不读取也不接管这些状态；需要浏览器证据时，用户明确选择新的合成库后再人工完成彩排，并记录截图和操作结果。

## 验证结果

- 新增 `scripts/isolated_demo_preflight.py` 与两条回归测试，覆盖完整契约和缺失环境变量标记；
- 本阶段只增加配置前置检查和文档，不改变业务 API、数据模型或模型调用；
- 未读取真实数据库、简历、个人文档、浏览器存储或 API Key，没有调用外部 API、部署、删除文件或提交推送 GitHub；
- 浏览器人工彩排、正式全新目录复现、公开发布和 GitHub 提交推送仍未完成。

## 下一步

用户在确认一个全新的合成数据库路径后，按本说明启动隔离后端/前端并完成浏览器人工彩排；自动任务继续保持不读取浏览器状态、不删除文件和不执行 GitHub 操作的边界。
