# 阶段 71：本地语义 Embedding

## 目标

此前 QTrace 有两种向量模式：默认的本地确定性哈希向量，以及需要 API Key 的 OpenAI-compatible 远程向量。本阶段补上第三种模式：从本机已经下载的 Sentence-Transformers 模型目录生成语义向量，让个人文档检索可以在不上传资料、不访问外部网络的前提下使用真正的本地模型。

本阶段仍然不把“能加载模型”说成“检索质量已经证明”。质量评估需要固定语料、标注查询和离线指标，留到模型目录确认后再做。

## 实现内容

### 1. Provider 边界

`backend/embedding.py` 新增 `LocalSentenceTransformerEmbeddingProvider`：

- 延迟导入 `sentence_transformers`，默认安装仍然可以使用本地确定性模式；
- 构造模型时强制传入 `local_files_only=True`，禁止缺文件时自动联网下载；
- 调用 `encode(..., normalize_embeddings=True, convert_to_numpy=True)`；
- 兼容 numpy、torch tensor 和普通 list 的单条向量结果；
- 校验非空、数字类型、有限浮点值和跨请求维度一致性；
- 依赖缺失、目录内容不完整或推理失败时抛出稳定的 `EmbeddingProviderError`。

Provider 的 `mode` 为 `local-model`。文档服务只依赖 `EmbeddingProvider` 协议，不知道模型库、torch 或 HTTP 的细节，所以切换 Provider 不需要改分块、持久化和检索排序代码。

### 2. 用户级配置

设置表新增 `embedding_model_path`，并通过迁移兼容已经存在的 SQLite：

```text
settings.embedding_mode       = demo | local-model | openai-compatible
settings.embedding_model_path = 后端进程可访问的本地模型目录
```

`PUT /api/settings/embedding` 在 `local-model` 模式下只接收模型目录并要求目录存在。路径不会被当作 API Base、远程模型名或 API Key 使用；设置响应也不会返回任何 Key。

前端“模型设置”新增“本地语义模型”选项。它明确提示：需要可选的 `sentence-transformers` 依赖、模型目录必须位于后端可访问的机器上，并且加载不会联网。

### 3. 显式重建索引

切换到本地语义模型不会自动重写旧文档。当前文档 chunks 仍带有旧的 `embedding_mode`，检索时只读取与当前 Provider 相同的模式；用户点击“重建索引”后，当前版本的 chunks 才会用本地模型重新生成。

因此可以回答两个面试追问：

1. 为什么不在切换模型后自动重建？因为重建可能很慢，也可能意外触发外部 Provider；显式动作让成本和资料流向可见。
2. 为什么要按 `embedding_mode` 过滤？不同模型可能维度不同、空间不同，混算余弦相似度会产生不可解释的结果。

## 依赖与启动

基础运行不安装重量级模型依赖。确认本机已经有模型目录后，在项目的 Python 环境中执行：

```powershell
python -m pip install -r requirements-local-embedding.txt
```

然后启动后端和前端，在“模型设置”中选择“本地语义模型”，填写模型目录，保存后到“个人文档库”点击“重建索引”。模型目录需要是 Sentence-Transformers 能识别的完整本地目录，不能只填一个尚未下载的模型名称。

## 合成验收

本阶段没有读取真实简历、个人文档、浏览器存储或 API Key，也没有调用外部 API。验收分为三层：

```text
Provider 契约测试
  -> fake loader 验证 local_files_only、向量校验和维度一致性

API/数据链测试
  -> 合成模型目录 + fake Provider 验证设置、用户隔离、旧索引隐藏和显式 reindex

Smoke 边界测试
  -> SQLite 只读读取 local-model 配置，只对固定合成句调用 Provider，输出 network=disabled
```

运行命令：

```powershell
python -m pytest tests/test_local_embedding.py tests/test_embedding_smoke.py tests/test_personal_documents.py tests/test_frontend_route_preflight.py
python scripts\frontend_route_preflight.py
python -m compileall -q backend scripts tests
Set-Location frontend
npm run typecheck
npm run build
Set-Location ..
```

在真实本地模型目录确认后，可以用合成数据配置对应用户，再运行：

```powershell
python scripts\embedding_smoke.py --db-path <synthetic-db> --user-id <synthetic-user-id>
```

本次使用本机缓存的 `shibing624/text2vec-base-chinese` snapshot 和全新合成 SQLite 完成真实 Smoke：输出 `dimension=768`、`network=disabled`，加载和推理成功。验收只证明模型能在本地离线加载并满足向量契约，不代表语义检索质量已经经过标注集评估。

## 我现在能回答的面试追问

- Embedding 和 LLM 的职责是什么？Embedding 负责把查询和文档块映射到可比较的向量空间，LLM 负责基于检索上下文生成或评估回答。
- 为什么默认还保留 deterministic provider？它不需要下载模型，启动稳定、结果可复现，适合基础回归和没有模型目录的环境；本地语义模型是可选增强。
- 为什么一定要 `local_files_only=True`？因为“本地模型”如果缺文件就自动联网，会违反资料不外发和离线运行的预期；显式失败更容易定位。
- 本地模型和远程 Embedding 如何切换？设置按用户保存模式，文档索引保留模式标记，切换后显式 reindex，再由检索过滤当前模式。
- 这是否证明语义检索质量更好？没有。当前验收证明的是加载边界、向量契约、索引切换和无网络安全边界；质量需要离线标注集和 Recall@K/MRR 等指标。

## 当前限制与下一步

- `sentence-transformers` 仍不放入默认 `requirements.txt`，避免所有复现者被迫安装大依赖；本次已在当前 E:\\Anaconda 环境按可选依赖清单安装并完成真实 Smoke；
- 本次只读定位了 Hugging Face 常见缓存中的两个模型目录，实际验收使用中文 `text2vec-base-chinese`，没有读取真实简历或个人文档；
- 暂不做模型下载器、自动模型选择、GPU 调度和向量数据库迁移；
- 下一步可在合成文档和人工标注查询上比较 deterministic 与本地语义模型的 Recall@K/MRR，并把结果整理成单独的离线评估阶段；
- 浏览器人工彩排、正式全新目录复现、外部部署、GitHub 提交推送仍按既有人工确认边界处理。
