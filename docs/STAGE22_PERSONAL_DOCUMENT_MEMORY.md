# Stage22：Personal Agent 个人文档记忆

## 目标

把 Personal Agent 从“只能读取画像、复习队列、训练历史和简历”扩展为“可以检索用户主动保存的项目资料和学习笔记”。本阶段先做本地可运行版本，不把任何真实资料发送给外部 Embedding 服务。

## 领域模型

```text
User
  |
  +-- PersonalDocument
          |
          +-- DocumentChunk (ordered)
                  |
                  +-- embedding
```

- `PersonalDocument` 是用户拥有的一份资料，保存标题、来源类型和原文长度等元数据。
- `DocumentChunk` 是文档中可以独立引用的一段内容，保存文档归属和原始顺序。
- `embedding` 是文档块的可比较数值表示，不是答案，也不是用户画像。
- Agent 只能调用 `search_personal_documents` 读取相关文档块；文档新增由用户显式提交。

## 模块接口

个人文档模块对路由和 Agent 暴露一个小接口：

```text
add_document(user_id, title, content, source_type)
list_documents(user_id)
search(user_id, query, limit)
```

Embedding 在模块内部通过 `EmbeddingProvider` 接口替换：

```text
embed(text) -> vector[float]
```

当前实现是本地确定性向量适配器：使用稳定哈希把中英文词元映射到固定维度，再做归一化和余弦相似度。它用于学习检索链路和离线测试，不应在面试中描述成高质量语义模型。

## 数据流

```text
用户提交文本/Markdown
  -> 清理和长度校验
  -> 按段落/句子切分为有序文档块
  -> EmbeddingProvider 生成向量
  -> personal_documents + document_chunks 持久化

Agent 问题
  -> 规划 search_personal_documents
  -> 使用当前 user_id 检索文档块
  -> 按余弦相似度取 Top-K
  -> 将标题、分块序号、分数和内容交给回答模型
```

## 权限和安全边界

1. 所有文档和文档块查询都带 `user_id`，跨用户只能得到空结果或 404。
2. Agent 工具是只读工具，不能创建、修改或删除个人文档。
3. 检索结果限制数量和内容长度，避免把整个个人资料库无界地塞进提示词。
4. 本阶段只使用本地确定性 Embedding；以后接入外部 Embedding 时，必须明确选择并确认真实资料的外发范围。

## 当前取舍

- 先支持文本/Markdown 内容，再复用已有 PDF 文本解析能力接入文件导入。
- 先用 SQLite 保存文档块和向量，使用 Python 计算相似度；数据量增大后再考虑向量数据库或专用索引。
- 不让 Agent 直接修改长期画像。文档检索只提供证据，画像仍由训练复盘信号更新。

## 验证重点

- 同一文本的本地向量在不同调用中一致。
- 长文本能被切成多个有序文档块，检索结果包含相关片段。
- 用户 A 的 Agent 不能检索用户 B 的文档。
- 没有文档时检索工具稳定返回空列表，不影响 Agent 对话主链。
- 旧 SQLite 启动时自动补齐新表，已有用户和训练记录不受影响。

## 面试追问卡

### 为什么不能把整份文档直接塞给 LLM？

因为上下文窗口、成本和噪声都会随文档变大。分块后先检索相关证据，可以减少输入规模，并让回答更容易解释来源。

### 本地确定性向量和真正的 Embedding 有什么区别？

当前实现只是稳定的词元哈希表示，能验证分块、存储、相似度和 Agent 工具链路，但不具备通用模型的深层语义理解。真正的 Embedding 只需要替换 Provider，不应改变文档服务和 Agent 工具协议。

### 为什么 Agent 不直接写文档？

文档是用户长期资料，写入会改变后续回答依据。当前先让用户显式提交，Agent 只负责读取证据；未来若增加“保存记忆”动作，也应采用草稿、确认和审计机制。
