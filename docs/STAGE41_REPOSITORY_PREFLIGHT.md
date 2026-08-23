# Stage41：QTrace 仓库发布前自检

这一阶段把“本地能跑”与“别人拿到公开仓库后能按说明启动”区分开。当前仍不做干净环境复现，也不执行 GitHub 提交或推送；只补齐发布前应具备的检查入口和诚实边界。

## 1. 发现并修正的问题

README 原来把依赖文件写成了 `backend\\requirements.txt`，但工程实际使用的是根目录 `requirements.txt`。正确启动顺序是：

```powershell
Set-Location -LiteralPath '<project>\\rebuild'
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

前端仍在 `frontend` 目录执行 `npm install` 和 `npm run dev`。

## 2. 只读自检脚本

入口：`scripts/repository_preflight.py`

```powershell
Set-Location -LiteralPath '<project>\\rebuild'
python scripts\\repository_preflight.py
```

脚本只做四件事：

1. 检查 README、依赖、后端入口、前端入口和面试讲解稿等必需文件是否存在；
2. 检查文本文件中是否出现明显的 OpenAI key 形态或私钥头；
3. 提醒本地 `.env`、SQLite、数据库、日志等不应进入公开仓库的产物；
4. 显示当前 Git 工作区是否有变化，提醒发布前人工审阅。

它不会安装依赖、联网、调用 LLM、读取 `data/` 中的真实资料、修改文件或删除文件。发现本地产物只给出 `WARN`，因为本地运行产生这些文件是正常的；发现必需文件缺失或明显密钥痕迹才返回失败。

## 3. `.gitignore` 边界

当前忽略规则覆盖：

- Python 缓存、pytest 缓存和虚拟环境；
- `data/`、SQLite 数据库；
- `.env` 与其他 `.env.*` 配置文件，同时允许未来加入安全的 `.env.example`；
- 前端依赖、构建产物和 TypeScript 增量缓存；
- 本地运行日志 `*.log`。

忽略规则只能降低误提交概率，不能替代提交前查看 `git status` 和变更内容。特别是 API Key、真实简历、真实录音和真实面试记录仍然不应复制到仓库目录。

## 4. 这一步能证明什么

它能证明仓库的关键启动文件和公开边界有一个可重复的静态检查入口，不能证明：

- 新电脑已经安装了兼容版本的 Python、Node.js 和 npm；
- npm/PyPI 网络依赖在目标环境中一定可下载；
- 真实 LLM API、Embedding 或 ASR 服务一定可用；
- 数据库迁移、首次注册和完整前端操作在干净目录中一定成功。

因此，项目全部功能完成后仍需单独安排一次干净环境复现；本阶段只为那次验证降低文档和遗漏风险。

## 5. 面试讲法

可以这样概括：

> 我没有把“我这台电脑能运行”直接当成发布完成，而是补了一个无副作用的 repository preflight。它检查核心入口、依赖文件、明显密钥和本地产物，并把工作区变更留给人工审阅。它是发布前的静态护栏，不是 CI，也不替代真正的干净环境安装和端到端验证。

这个回答体现了三个边界：检查器不拥有业务写权限；忽略规则不等于安全保证；本地联调、公开发布和可复现验证是三个不同阶段。
