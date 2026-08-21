# 阶段 9：ASR 与结构化复盘适配层

## 目标

第 8 阶段已经能处理人工粘贴的转写文本，但“转写来源”和“复盘分析器”还没有明确接口。本阶段把两层拆开：

```text
转写来源 -> ASRProvider -> transcript document
                                      |
                                      v
                          RecordingAnalyzer -> Review
```

这样可以先用本地规则分析跑通，再显式选择真实 LLM；未来如果需要接入外部转写服务，也不需要改写会话持久化和前端复盘页。

## 新增边界

### `ASRProvider`

`ASRProvider.transcribe(source, filename, content_type)` 返回统一文档：

- `text`：转写正文；
- `provider`：来源标识；
- `filename` / `content_type`：原始来源元信息；
- `segments`：当前用于保存已经解析出的对话片段，不承担音频时间戳或自动说话人分离。

当前实现是 `TextPassthroughASRProvider`，只接受 UTF-8 的 `.txt/.md` 文本。它不是音频识别器，而是一个本地 mock，用于验证转写来源边界和输入校验。

### `RecordingAnalyzer`

分析器统一返回：

```text
(messages, review)
```

其中 `review` 继续包含 `summary`、`average_score`、`scores`、`strengths`、`weak_points`、`action_items`、`transcript_meta` 和 `segments`。

- `RuleBasedRecordingAnalyzer`：默认实现，不访问网络，便于演示、测试和降级；
- `LLMRecordingAnalyzer`：通过一个结构化 chat callable 调用真实模型，解析并校验 JSON 后再合并本地转写元信息；
- `OpenAICompatibleProvider.structured_chat`：复用已有 HTTP、鉴权和响应错误处理，但不把录音业务逻辑塞进 Provider。

## 请求流程

```text
POST /api/recording/analyze
        |
        +-- analysis_mode=rules -> RuleBasedRecordingAnalyzer
        |
        +-- analysis_mode=llm
                -> 检查用户是否配置真实 LLM
                -> OpenAICompatibleProvider
                -> LLMRecordingAnalyzer
                -> JSON 解析、字段归一化、分数限制在 0~10
```

LLM 模式必须由用户显式选择。没有真实 LLM 配置时返回明确错误，不会偷偷把请求切换成规则分析；规则模式则不要求模型配置，保持原有本地可运行能力。

## 为什么不能让 LLM 直接返回任意文本

复盘结果会写入画像和复习队列，若直接保存自然语言，后续页面无法稳定读取分数和薄弱点。因此 LLM 只负责生成候选 JSON，后端负责：

1. 去除 Markdown 代码围栏；
2. 解析 JSON 对象；
3. 校验 `summary`；
4. 归一化数组字段；
5. 把分数转换为数字并限制在 0~10；
6. 合并本地可信的转写统计和分段。

解析失败会返回错误，不会把失败伪装成成功复盘。

## 前端变化

录音复盘页增加：

- 本地规则分析 / 真实 LLM 结构化分析选择；
- 本地 TXT 转写导入，文件只在浏览器读取，不上传原文件；
- 复盘页显示本次使用的分析器。

## 面试追问卡

### 为什么 ASR 和复盘分析要拆成两个接口？

转写来源负责提供“对话文本”，分析器负责判断“这段对话表现如何”。前者和后者的生命周期、错误类型和数据结构不同，拆开后可以单独替换和测试。

### 为什么规则分析仍然要保留？

它是无网络时的可运行 fallback，也是回归测试的稳定基线。真实 LLM 的输出有随机性和服务依赖，不能让整个产品只有模型可用时才能启动。

### 为什么不把 OpenAI 调用直接写在录音路由里？

路由只应该负责鉴权、输入校验和编排。HTTP、模型配置和响应错误由 Provider 管理；复盘 JSON 解析由 Analyzer 管理，这样每个模块可以独立测试。

### 真实 LLM 失败时为什么不自动降级？

自动降级可能让用户误以为拿到了模型分析。当前选择显式报错，用户可以重新选择规则版；如果生产环境需要自动降级，应在响应中标记 `fallback_reason`，并在页面上明确告知。

## 当前验证

- 后端测试：`14 passed`；覆盖文本 mock ASR、LLM 结构化解析、LLM 路由选择和无网络 fake provider。
- 前端：`npm run typecheck` 通过；`npm run build` 通过。
- 非交付范围：真实长音频、说话人分离和时间戳对齐；真实外部 ASR/LLM 服务不作为本地验收前提。

## 下一步

在保持当前接口不变的前提下，实现 Copilot 的实时会话边界：先用 JSON/SSE 验证事件协议，再考虑 WebSocket 和多 Agent 并行策略。
