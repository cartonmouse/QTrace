# Stage44：真实 Embedding 联调门禁与合成文本探针

本阶段先检查当前运行账号的 Embedding 配置，再决定是否允许发起真实网络请求。检查结果是：当前账号只配置了聊天模型，Embedding 仍为 `demo` 本地模式，因此本阶段没有调用外部 Embedding 服务，也没有读取或上传真实简历。

## 1. 为什么不能直接复用聊天模型

聊天模型负责根据消息生成文本；Embedding 模型负责把文本映射成向量。两者的请求路径、返回结构、向量维度和用途都不同。当前账号的聊天配置如下：

- Chat provider：OpenAI-compatible；
- Chat endpoint/model：已配置；
- Embedding mode：`demo`；
- Embedding endpoint/model/key：未配置。

所以不能因为聊天模型可用，就假设同一个 endpoint 或 model 支持 `/embeddings`。QTrace 继续把 `ModelProvider` 和 `EmbeddingProvider` 分开。

## 2. 配置探针

新增只读脚本：

```powershell
python scripts\embedding_smoke.py `
  --db-path "path\to\rebuild.sqlite3" `
  --user-id "USER_ID"
```

脚本遵守四个约束：

1. 只读取指定 SQLite 数据库中的 Embedding 配置，不读取个人文档表；
2. 只有当 mode 为 `openai-compatible` 且 Base、Model、Key 都存在时，才发起请求；
3. 请求正文固定为一段合成句，不接受简历、录音或其他真实资料作为输入；
4. 只输出 endpoint host、model、向量维度和耗时，不输出 API Key、向量内容或个人数据。

当前账号执行结果：

```text
NOT_CONFIGURED: embedding_mode=demo；当前为本地模式，未发起网络请求
```

退出码 `2` 表示“尚未配置，未联调”，不是服务故障；退出码 `0` 表示合成文本联调成功；退出码 `1` 表示读取配置或外部服务失败。

## 3. 回归保护

新增测试覆盖：

- demo 模式不会构造外部 Provider，也不会发起网络请求；
- 找不到用户时只读返回，不创建或修改数据库。

这样可以把“真实联调必须经过显式配置”变成代码约束，而不是依赖口头约定。

## 4. 面试讲法

> 我先把聊天模型和 Embedding 模型拆开看。当前账号的聊天 endpoint 可用，但 Embedding 还是 demo，因此我没有直接复用聊天配置。项目提供一个只读的 synthetic smoke test：它只在用户显式配置 OpenAI-compatible Embedding 的 Base、Model 和 Key 后，向 `/embeddings` 发送固定合成句，并只记录返回维度和延迟；配置不完整时直接退出，不触碰个人文档。这样既能验证 Provider 契约，又把真实资料外发放在显式 reindex 之后。

## 5. 当前结果与下一步

- 暂存工程新增 `scripts/embedding_smoke.py` 和两条回归测试；脚本测试结果为 `2 passed`；
- 当前运行账号的真实 Embedding 联调未执行，因为 Embedding 配置不完整；
- 现有文档仍默认使用本地确定性向量，系统可以继续正常运行；
- 若后续配置独立的 Embedding endpoint/model/key，可先运行本探针，再用合成文档执行显式 reindex；
- 在项目完整交付前，仍不做真实资料的外部上传、干净环境复现、部署或 GitHub 推送。
