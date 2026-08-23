# 阶段 21：TechSpar 与 QTrace 功能差距审计

## 审计目的

QTrace 的目标是学习并自行搭建一个与 TechSpar 相近的 AI 面试训练系统，而不是只证明当前页面可以运行。本阶段对照冻结参考副本的代码地图、运行记录、页面入口和后端能力文件，区分已经复现、做了可解释替代、以及尚未实现的部分。

参考依据：

- `..\..\reference\docs\FULL_PROJECT_CODE_MAP.md`
- `..\..\reference\docs\REFERENCE_RUN.md`
- 参考副本 `frontend/src/resume/`、`backend/graph.py`、`backend/vector_memory.py`、`backend/personal_agent.py` 和 `backend/copilot/`

## 总体结论

当前 QTrace 已经复现了最值得学习的主链：

```text
用户登录
  -> 模型配置
  -> 简历/主题输入
  -> 面试或专项训练
  -> 结构化复盘
  -> 画像 + SM-2
  -> Personal Agent 读取画像并生成计划
  -> 计划驱动下一轮训练
```

因此它已经不是固定话术 Demo。但它还不是 TechSpar 的功能等价版本，主要缺少三类外围子系统：个人 Agent 文档/向量记忆、简历编辑器、题目关系图谱；实时语音 Copilot 则属于用户已经同意暂不纳入的高成本范围。

## 功能差距矩阵

| 领域 | TechSpar 参考能力 | QTrace 当前状态 | 判断 |
| --- | --- | --- | --- |
| 登录与模型门禁 | JWT、LLM/Embedding 配置引导 | 本地账号、JWT、Stub/OpenAI-compatible 配置 | 已复现；Embedding 仍是 demo 占位 |
| 简历模拟面试 | 显式面试流程、REST + SSE、状态落盘 | `InterviewEngine`、JSON API、会话落盘、复盘 | 核心已复现；普通面试 SSE 尚未实现 |
| 专项训练 | 画像、到期复习、知识库、向量上下文、批量题目 | 画像、简化 SM-2、知识 Markdown、关键词检索、Stub/LLM 动态出题 | 已做可运行替代；向量检索和批量关系图缺失 |
| 画像与复习 | 长期画像、领域历史、SM-2 | 全局画像、领域掌握度/趋势、到期队列、行为信号 | 核心已复现；画像维度更简化 |
| JD 备面 | JD 分析、简历匹配、问题生成和评估 | JD 分析、岗位匹配、问题蓝图和训练 | 已复现核心链路 |
| Copilot Prep | 公司搜索、多 Agent 并行分析、策略树、风险地图 | 确定性 Prep、策略树、风险地图、JSON/SSE | 有替代实现；没有真实搜索和多 Agent 并行 |
| Copilot 实时 | WebSocket、ASR 流、VAD、去重、回答建议 | 未实现 | 明确延后；真实长音频、说话人分离、时间戳也不纳入当前交付 |
| 录音复盘 | 音频上传/转写/说话人处理/复盘 | 文本和 TXT 转写、规则/LLM 复盘 | 有意采用文本优先替代 |
| Personal Agent | 文档库、Embedding 检索、会话和个人 Agent | 画像/复习/历史/简历只读工具、计划写工具、对话恢复 | Agent 主链已复现；文档库和语义检索缺失 |
| 知识图谱 | 题目关系图、向量相似度和图谱页面 | 无 `/graph` 页面和图谱 API | 尚未实现 |
| 简历编辑器 | 结构化字段、模板预览、浏览器 PDF 导出 | 只支持 PDF 上传和文本注入 | 尚未实现，且是较大的独立子系统 |
| 数据迁移/声纹 | 用户数据导入导出、可选声纹注册 | 未实现 | 延后，不影响核心训练学习目标 |

## 与用户目标的相关性排序

### 第一优先：Personal Agent 文档库 + Embedding 检索

这是下一阶段最值得实现的功能。它能把当前“Agent 读取固定工具结果”升级为：

```text
上传项目文档 / 简历补充材料
  -> 文本切分
  -> EmbeddingProvider
  -> 用户隔离的向量记录
  -> Agent 根据问题检索证据
  -> 回答中引用项目事实
```

实现时先保留 `EmbeddingProvider` 接口和本地 deterministic fallback，再接 OpenAI-compatible Embedding；这样没有 Embedding API 时仍然可以运行和测试，不把模型供应商绑定到 Agent 业务。

### 第二优先：题目关系图谱的最小只读版本

等题目或文档已经有稳定的向量/关键词表示后，再生成“相似题、前置知识、薄弱点”的关系数据，并先做只读页面。不要一开始实现完整知识图谱编辑器。

### 第三优先：最小结构化简历编辑器

先支持基本信息、教育经历、项目经历、技能和 Markdown/PDF 预览导出，再考虑参考项目中的多模板、拖拽和移动端适配。它对展示完整产品很有帮助，但不是当前 Agent 学习主线的第一阻塞点。

### 明确暂缓：实时 WebSocket Copilot

参考项目的实时模式同时涉及 WebSocket 生命周期、ASR、VAD、转写去重和回答建议。用户已经同意暂不实现真实长音频、说话人分离和时间戳，因此当前只保留文本 Copilot Prep 和 SSE，避免功能目标漂移。

## 面试中应该如何诚实描述当前完成度

可以这样说：

> 我没有声称完全复刻 TechSpar。当前先独立实现了它最核心的训练闭环：面试状态机、专项动态出题、画像、SM-2、Personal Agent 和计划驱动训练；对实时语音、简历编辑器和知识图谱做了边界拆分。下一步优先补 Personal Agent 文档库和 Embedding 检索，因为它最能体现 Agent 如何基于用户长期材料进行个性化决策。

## 阶段结论

- QTrace 与 TechSpar 的核心训练闭环已经接近，外围功能仍有明显差距；
- “没有 WebSocket”不是当前最大问题，也符合已确认的交付边界；
- 下一阶段进入 Personal Agent 文档库和 EmbeddingProvider 设计，不直接复制参考项目的大型 `resume/` 子系统；
- 本阶段只做审计和路线决策，没有修改运行代码、没有调用真实 LLM、没有进行干净环境复现。
