# Stage43：用户级 Embedding 配置与显式文档重建

本阶段把 Stage42 的外部 Embedding 适配器接到产品闭环，但默认仍然使用本地确定性向量。核心原则是：配置可以按用户保存，资料索引必须由用户明确重建，旧 mode 的向量不能被新 Provider 误读。

## 1. 用户级配置

设置表新增：

- `embedding_api_base`
- `embedding_model`
- `embedding_api_key`

设置接口新增：

```text
GET  /api/settings
PUT  /api/settings/embedding
```

返回给前端的只有 API Base、Model、`embedding_key_configured` 和模式，不返回 API Key。每次文档读写请求都会按当前用户读取 Embedding 配置，再构造自己的 `PersonalDocumentService`；不会使用一个全局用户混用的 Provider。

本地模式写入 `embedding_mode=demo`，实际文档块使用 `local-deterministic`。外部模式写入 `embedding_mode=openai-compatible`，实际调用 Stage42 的 `/embeddings` 适配器。

## 2. 为什么切换后不自动上传旧文档

如果用户把本地模式切换到外部模型，数据库里的旧文档块仍然是本地向量；直接用外部查询向量去比较它们会遇到两类问题：

1. 向量维度可能不同，余弦相似度没有意义；
2. 即使维度碰巧相同，也不能把两种模型的数值空间当成同一个索引。

因此检索会先按 `embedding_mode` 过滤。切换后未重建的旧文档暂时不会出现在外部模式检索结果里，用户必须在个人文档库点击“重建索引”。这是显式的资料外发动作边界。

## 3. 显式 reindex

入口：

```text
POST /api/agent/documents/reindex
```

它遍历当前用户的当前文档版本，重新分块并用当前 Provider 生成向量，然后只替换 `document_chunks` 和当前版本的索引元数据：

- 不修改正文和内容指纹；
- 不创建新的文档版本；
- 不读取其他用户的文档；
- 外部 Provider 失败时返回 502，不伪造成功；
- 重建完成后返回 mode、文档数量和文档块数量。

前端设置页保存外部配置后会提示用户去文档库手动重建；文档库也显示当前 mode 并提供“重建索引”按钮。

## 4. 面试讲法

> 我把 Embedding 配置做成用户级设置，API Key 只写入本地设置表，响应只返回是否配置。切换模型后我没有自动重建，因为旧向量可能来自不同模型、不同维度；检索会先按 embedding mode 隔离，用户明确点击 reindex 后才重建当前文档版本的 chunk。reindex 只替换索引，不创建新文档版本，这样内容历史和索引生命周期是分开的。

这条链路体现了三个工程边界：密钥不回传，用户数据不跨账号，模型切换不隐式触发资料外发。

## 5. 测试与当前限制

- 回归测试覆盖用户设置隔离、Key 不回传、旧 mode 在重建前不可检索、重建后的 mode/数量返回和用户文档边界；
- 外部 Provider 仍使用 MockTransport 契约测试，尚未调用真实 Embedding API；
- 当前没有引入向量数据库，向量仍保存在 SQLite 的 JSON 字段中，适合学习和小规模本地项目，不代表生产级索引方案；
- 下一步可以用用户提供的 API 做一次最小真实联调，只上传合成文档，并记录响应维度、延迟和失败行为。
