# Stage42：OpenAI-compatible Embedding 适配器

本阶段把“真实外部 Embedding”从一句接口承诺推进为一个可测试的网络适配器，但暂时不把它接成默认索引策略，也不进行真实 API 联调。这样可以先把 Provider 的请求/响应边界讲清楚，再在下一阶段处理用户配置、已有文档重建和多种向量维度共存。

## 1. 当前链路

```text
个人文档文本
  -> split_document_text
  -> EmbeddingProvider.embed
       -> 默认 DeterministicEmbeddingProvider
       -> 可选 OpenAICompatibleEmbeddingProvider
  -> Store 保存 embedding_json + embedding_mode
  -> query 向量 + cosine similarity + token overlap
```

`PersonalDocumentService` 只依赖 `EmbeddingProvider` 协议，不知道 HTTP、API Base、请求头或供应商错误。`backend/embedding.py` 负责两种实现：

- `DeterministicEmbeddingProvider`：本地哈希向量，默认使用，离线、可复现、无需真实资料外发；
- `OpenAICompatibleEmbeddingProvider`：调用 `<api_base>/embeddings`，提交 `model` 和单条 `input`，解析 `data[0].embedding`。

## 2. 外部适配器的保护边界

适配器目前具备以下行为：

1. 启动时要求 API Base、API Key 和 Embedding Model 非空；
2. 对 HTTP 408、425、429、5xx 做最多 3 次以内的有界重试；
3. 对网络异常做同样的有界重试，避免无限等待；
4. 校验响应是 JSON，且包含非空数字向量；
5. 记录第一次返回的维度，后续维度变化直接失败；
6. 对空文本、非数字、非有限浮点数和错误状态返回明确的 Provider 错误。

鉴权错误和其他非临时 HTTP 错误不会重试。适配器不记录 API Key，也不把请求内容写入日志。

## 3. 为什么先不直接接入默认流程

真实 Embedding 接入不只是增加一个 HTTP 请求，还要回答三个数据问题：

- 用户在哪里配置 Embedding API Base、Model 和 Key，是否与 Chat LLM 共用配置；
- 旧文档块使用本地 128 维向量时，切换到外部模型后如何重建，如何避免维度不一致；
- 外部服务不可用时，是回退本地检索、阻止保存，还是保留旧索引并提示用户。

本阶段先把“调用服务”和“文档业务”拆开，保留本地 baseline 作为默认。下一阶段再增加用户级配置和显式 reindex，避免用户打开设置后悄悄把已有个人资料发送到外部服务。

## 4. 测试方式

测试使用 `httpx.MockTransport`，不访问网络：

- 检查 URL、Authorization、model 和 input 请求契约；
- 检查正常向量响应和 mode/dimension 元数据；
- 检查 503 重试；
- 检查同一 Provider 返回维度变化时失败；
- 保留既有本地确定性向量测试和文档检索测试。

## 5. 面试讲法

> 我没有把 Embedding HTTP 请求散落在文档服务里，而是把它收敛到 `EmbeddingProvider` 的适配器。默认使用本地确定性向量保证离线可运行；外部 Provider 只负责 `/embeddings` 请求、响应校验、维度一致性和有界重试。真实接入前还要解决用户级配置、已有文档重建和服务失败降级，所以这一阶段只完成契约和 Mock 测试，没有声称已经完成真实网络联调。

## 6. 当前边界

- 本阶段没有读取或上传真实简历、真实面试记录或个人文档；
- 本阶段没有调用真实 Embedding API；
- 应用默认仍使用 `local-deterministic`，设置页仍显示外部 Embedding 尚未接入用户配置；
- 下一阶段再实现用户级 Embedding 配置、文档显式重建和 mode/维度隔离。
