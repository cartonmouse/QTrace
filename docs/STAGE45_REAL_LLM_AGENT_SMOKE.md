# Stage45：真实 LLM 与 Personal Agent 合成联调

本阶段验证当前账号的真实聊天模型是否能完成 QTrace Personal Agent 的最小两步链路：先生成工具规划，再根据合成工具上下文生成回答。联调只使用固定合成文本，没有读取或上传真实简历、个人文档或训练历史。

## 1. 当前配置检查

运行账号的 LLM 配置元数据显示：

- provider mode：`openai`；
- endpoint host：`api.deepseek.com`；
- model：`deepseek-v4-flash`；
- API Key：已配置，但不输出密钥内容。

这与 Embedding 配置是两套独立设置。当前 Embedding 仍是 `demo`，本阶段只验证聊天模型和 Agent，不把聊天模型当成向量模型。

## 2. 两步真实调用

新增只读脚本：

```powershell
python scripts\agent_llm_smoke.py `
  --db-path "path\to\rebuild.sqlite3" `
  --user-id "USER_ID"
```

脚本固定使用：

- 合成用户请求：围绕 RAG 评估给出一条个性化练习建议；
- 合成画像：`synthetic-rag` 掌握度 0.4，薄弱点为召回率与准确率区分；
- 合成到期复习项：检索评估指标；
- 空的近期训练历史。

它执行两个真实请求：

```text
1. model.plan(message)   -> 结构化 JSON -> 工具名白名单归一化
2. model.answer(message, history, tool_context) -> grounded 中文回答
```

本次结果：

```text
PASS: synthetic Agent LLM 联调成功
model=deepseek-v4-flash
plan_tools=read_profile,read_due_reviews,read_recent_sessions
plan_ms=6839.6
answer_chars=892
answer_ms=7868.5
```

脚本只输出工具名、endpoint host、模型名、耗时和回答长度，不输出 API Key，也不输出完整回答。

## 3. 这证明了什么

- 真实 LLM endpoint 可以返回 Agent 规划所需的 JSON 结构；
- Agent 能在第二步接收工具结果并生成非空回答；
- 规划结果会经过 `AGENT_TOOLS` 白名单和写工具权限归一化，模型不能凭空获得未注册工具；
- “Agent”不是一段固定话术，而是模型规划、后端工具执行、上下文拼装和模型回答组成的受控链路。

## 4. 这还没有证明什么

- 两次调用的耗时受网络和供应商负载影响，不能当作性能基准；
- 合成上下文联调不等于真实简历引用、跨用户隔离和前端会话持久化已经完成，这些由已有接口测试覆盖；
- 真实 LLM 返回“可解析”不代表每次都正确，所以生产路径仍保留 JSON 提取、字段归一化、工具白名单和 Provider 错误归一化；
- 当前没有启用真实 Embedding，Agent 文档检索仍使用本地确定性向量，直到用户单独配置并显式重建索引。

## 5. 面试讲法

> 我把 Agent 拆成两次模型调用。第一次只负责把用户意图规划成工具名和原因，后端再校验工具白名单、用户权限和是否允许写入；第二次把工具返回的画像、到期复习项、历史和引用证据拼成上下文，让模型生成回答。联调时我没有把真实简历发给模型，而是用固定合成上下文验证 JSON 规划和 grounded answer 两个契约；这样能区分“模型能返回文本”和“Agent 链路真的可控”。

## 6. 当前结果与下一步

- 暂存工程新增 `scripts/agent_llm_smoke.py` 和两条“未配置时不联网”的回归测试；
- 当前账号真实 LLM 两步联调成功：规划约 6.8 秒，回答约 7.9 秒，回答非空；
- 没有写入数据库，没有创建 Agent 对话，没有读取真实个人资料；
- 下一步继续完善 Agent 前端体验和失败可观察性，再在项目完整后统一做干净环境复现。
