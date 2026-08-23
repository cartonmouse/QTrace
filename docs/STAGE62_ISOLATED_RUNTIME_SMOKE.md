# 阶段 62：隔离合成环境运行态冒烟

阶段 60/61 已经把浏览器彩排的数据库、后端端口和前端代理边界写清楚。本阶段实际启动一套全新的合成 SQLite、临时后端和临时前端，再使用已有的 `local_runtime_smoke.py` 验证隔离运行态，而不是把源码检查当成服务已启动。

## 端口占用处理

阶段 62 的第一次尝试发现推荐前端端口 `5175` 已被现有 node 进程占用，随后备用端口 `5176` 也被占用。自动任务没有停止或接管这些未知进程，而是只读确认端口状态，使用可选端口 `8004/5177` 完成了同一套合成验证。这说明端口参数不能被当成永远空闲的系统资源。

种子脚本现在支持：

```powershell
python scripts\seed_synthetic_browser_demo.py `
  --db data\qtrace-browser-demo-stage62.sqlite3 `
  --backend-port 8004 `
  --frontend-port 5177
```

脚本会把选定端口写入 `BACKEND_URL`、`FRONTEND_URL` 和 `REBUILD_API_TARGET` 输出。端口只接受 `1—65535`，不负责探测或强制关闭占用者；如果端口被占用，应换一个端口或由用户人工处理自己的进程。

阶段 63 进一步锁定了副作用顺序：非法端口会在创建合成 SQLite 之前被拒绝，详见 `docs/STAGE63_PORT_VALIDATION_BEFORE_SEED.md`。

## 隔离运行态命令

后端终端：

```powershell
$env:REBUILD_DB_PATH = (Resolve-Path 'data\qtrace-browser-demo-stage62.sqlite3').Path
$env:REBUILD_DATA_DIR = (Resolve-Path 'data').Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8004
```

前端终端：

```powershell
$env:REBUILD_API_TARGET = 'http://127.0.0.1:8004'
npm run dev -- --host 127.0.0.1 --port 5177
```

第三个终端执行：

```powershell
python scripts\local_runtime_smoke.py `
  --backend-url http://127.0.0.1:8004/api/health `
  --frontend-url http://127.0.0.1:5177/
```

该检查只输出状态码、构建入口大小和资源数量，不输出响应正文；它不会读取 SQLite、个人文档或 API Key。浏览器打开 `http://127.0.0.1:5177` 仍然是后续人工步骤。

## 实际验证结果

- 使用全新的合成 SQLite 启动隔离后端/前端，未触碰常规 `8002/5174` 实例；
- `local_runtime_smoke.py` 在备用 `8004/5177` 上通过：后端健康 `200`、前端入口 `200`、构建入口引用资源 `2` 个；
- 验证结束只停止本阶段启动的临时进程，没有停止已占用端口的未知 node 进程，也没有删除生成的合成数据库；
- 暂存/正式工程后续完整回归预期为 `88 passed`，前端 typecheck/build 和合成主链继续作为独立门禁；
- 本阶段没有读取真实数据库、简历、个人文档、浏览器存储或 API Key，没有外部 API、部署或 GitHub 提交推送。

## 面试讲解卡

### 为什么要做运行态冒烟？

单元测试和源码前置检查证明代码契约，但不能证明端口、进程、前端入口和构建资源在当前机器上真的连通。运行态冒烟补的是“服务已经启动且入口可达”这一层证据，仍然不等于完整浏览器 E2E。

### 为什么不自动杀掉占用端口的进程？

占用者可能是用户自己的开发服务或浏览器配套进程。自动任务只检查端口并换用备用端口，避免把别的任务当成自己的子进程误停；正式彩排时用户可以决定复用、停止或换端口。

## 下一步

用户确认一个全新的合成数据库路径和空闲端口后，可按脚本输出启动隔离服务并人工完成登录、图谱、专项训练和 Agent draft/confirm 彩排；自动任务不把这一步标记为已完成。
