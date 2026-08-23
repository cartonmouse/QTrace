# 阶段 56：简历项目表述与工程证据对齐

本阶段把 QTrace 的公开项目介绍、简历表述和仓库内可验证证据放到同一份材料中。它不读取用户的真实简历，也不代替用户决定最终投递版本；它只提供可根据真实彩排结果修改的草稿。

项目名称：问迹 QTrace

项目仓库：<https://github.com/cartonmouse/QTrace>

项目身份：个人独立重建项目，参考 TechSpar 的产品方向与公开代码结构学习实现。简历中应写“独立重建/复现并扩展”，不要写成 TechSpar 原作者或官方项目。

## 项目定位

QTrace 是一个面向求职训练的个人 Agent 学习系统：用户可以维护结构化简历和个人文档，围绕岗位、主题和项目进行训练；系统通过用户画像、复习状态、知识图谱和受控 Agent 工具把“今天练什么、为什么练、如何继续”串成一条可解释链路。

当前项目的可信核心是“可运行的本地闭环 + 可追溯的工程证据”，不是已经完成生产部署或大规模效果验证的商业系统。

## 简历项目描述（技术版）

```text
问迹 QTrace（个人项目） | React / TypeScript / Vite · FastAPI · SQLite · Personal Agent · RAG · 知识图谱 · SM-2

独立重建面向求职训练的 Personal Agent 系统，围绕结构化简历、个人文档、用户画像和 SM-2 复习状态组装可解释训练上下文，并用确定性知识图谱展示主题、问题与待复习关系。

设计两步 Agent 调用链：先生成受约束的 plan，再执行只读上下文工具和带依赖门禁的学习计划写工具；计划通过 draft / confirm / complete 状态机落库，配合 user_id 隔离、失败降级、显式重试和保留草稿，避免模型直接修改业务状态。

实现本地确定性 Embedding 与 OpenAI-compatible Embedding 适配边界、个人文档分块和 citation；使用合成账号完成注册、简历、追问卡、图谱、Agent 计划确认主链彩排，并以 81 项后端回归、前端 typecheck/build、运行态和交付前置检查支撑当前版本。
```

上面的“81 项”指本阶段暂存工程和正式工程本地实测通过的自动化回归数量；正式投递前仍应重新运行验证命令，确保数字与仓库当前状态一致。

## 简历项目描述（精简版）

```text
问迹 QTrace：独立重建的求职训练 Personal Agent。以结构化简历、个人文档、画像和 SM-2 复习状态为上下文，结合确定性知识图谱生成可解释训练计划；通过 plan → 工具读取 → draft/confirm 写入、用户隔离和失败恢复控制 Agent 行为。当前版本已完成本地合成主链与自动化验证，未声称生产部署、浏览器 E2E 或大规模效果评估。
```

如果简历版面有限，优先保留“Personal Agent、受控工具、draft/confirm、用户隔离、可验证边界”这几个关键词；不要堆叠没有在代码和测试中出现的模型能力。

## 工程证据对照

| 简历中的说法 | 可以展示的证据 | 面试时的准确边界 |
| --- | --- | --- |
| Agent 工具链与受控写入 | `docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md`、`docs/STAGE47_AGENT_FAILURE_CONSISTENCY.md`、`docs/STAGE48_AGENT_TOOL_DEGRADATION.md` | 当前是单 Agent 文本链路；计划写入必须经过依赖检查和用户确认，不是模型直接操作数据库。 |
| RAG 与个人文档 | `docs/STAGE22_PERSONAL_DOCUMENT_MEMORY.md`、`docs/STAGE24_PERSONAL_DOCUMENT_CITATION.md`、`docs/STAGE42_EXTERNAL_EMBEDDING_ADAPTER.md` | 已有本地确定性向量和外部适配边界；真实外部 Embedding 联调、供应商兼容性和效果评估不应写成已完成。 |
| 知识图谱与 SM-2 | `docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md`、`docs/STAGE38_GRAPH_FEEDBACK_EVALUATION.md` | 图谱是按用户/主题生成的可解释读模型，关系使用确定性 token/中文二元片段规则；不等同于向量数据库或能力因果证明。 |
| 可运行与验证 | `docs/STAGE54_FINAL_DELIVERY_PREFLIGHT.md`、`docs/STAGE55_INTERVIEW_DEFENSE_PACK.md`、`scripts/synthetic_demo_smoke.py` | 当前证据是本地测试、构建、运行态检查和合成彩排；浏览器人工彩排、干净目录复现、部署和公开发布仍需单独确认。 |

推荐的证据顺序是：先跑 `python -m pytest -q`，再展示 `scripts/synthetic_demo_smoke.py` 的合成主链，最后打开页面讲 Agent draft/confirm 和图谱入口。这样每个简历关键词都能落到代码、测试或文档，不依赖现场编造结果。

## 面试口述版本

```text
这个项目叫问迹 QTrace，是我参考 TechSpar 的方向独立重建的求职训练 Agent。它不是让模型直接回答一句话，而是先根据用户的简历、个人文档、画像和 SM-2 到期项生成受约束计划，再调用白名单工具读取上下文；如果要创建学习计划，必须先形成 draft，由用户 confirm 后才写入业务状态。

我重点练习的是 Agent 的工程边界：所有读取按 user_id 隔离，工具失败会被归一化并允许部分上下文继续回答，写工具依赖不完整时会安全跳过，模型失败还会恢复输入或保留可确认草稿。图谱目前是确定性可解释读模型，RAG 负责个人文档证据，两者没有混成一个无法解释的相似度分数。当前已经完成本地合成主链和自动化验证，浏览器 E2E、生产部署和大规模效果评估我会明确说明还没有完成。
```

## 不应夸大的表述

以下说法在当前版本中不应直接写入简历或面试回答：

- “完成了 TechSpar 的官方复现”或“参与了 TechSpar 原项目开发”。准确说法是参考其方向进行个人独立重建。
- “生产级多 Agent 系统”“线上稳定运行”“效果提升了 X%”。当前没有生产部署、真实用户规模和对照实验数据。
- “已完成 WebSocket 实时 Copilot、真实长音频、说话人分离、时间戳对齐、PDF 模板导出”。这些属于明确未纳入当前交付范围的能力。
- “已经验证真实 Embedding 检索效果”。当前代码有适配器和配置门禁，但真实网络联调与供应商效果仍需单独验证。
- “Agent 自动维护长期画像”。当前计划确认、训练复盘和画像写回是不同边界，不能把计划完成自动说成能力提升。

## 发布前自检

运行以下只读检查，确认简历材料与仓库证据仍然一致：

```powershell
python scripts\resume_claims_preflight.py
python -m pytest -q
python scripts\final_delivery_preflight.py
```

最后两项浏览器人工彩排和 GitHub 公开发布不是脚本自动完成的结果。用户需要在合成账号下亲自确认页面操作，再决定是否提交和推送；在此之前，仓库链接可以作为目标地址，不能把公开发布写成已完成事实。
