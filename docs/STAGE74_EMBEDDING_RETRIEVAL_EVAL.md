# 阶段 74：Embedding 离线检索评估

## 目标

阶段 71 已经证明本地 Sentence-Transformers 模型可以在当前机器离线加载并返回向量，但“能返回向量”还不等于“检索质量可解释”。本阶段建立一个固定、可重复、不会触碰真实资料的最小评估闭环，对默认的 local-deterministic Provider 和本地语义模型使用同一套合成文档、查询和人工相关性标注。

## 合成评估集

评估集固定包含四份短文档和四个查询，每个查询对应一个相关文档：

- Python 异步服务、FastAPI、asyncio 和并发请求；
- RAG 文档切分、Embedding、余弦相似度和证据召回；
- 个人 Agent、用户画像、知识图谱和 SM-2 复习队列；
- React、Vite 代理、FastAPI 后端以及前端请求状态。

这些内容只描述 QTrace 的公开技术主题，不来自用户简历、个人文档、SQLite 或浏览器存储。相关文档 ID 直接写在脚本中，避免评估过程中产生隐含的标注读取依赖。

## 指标与实现

scripts/embedding_eval.py 先用 Provider 为四份文档生成向量，再为每个查询生成向量并按余弦相似度排序。排序出现相同分数时使用文档 ID 做稳定的第二排序键。

- Recall@K：前 K 个结果中命中的相关文档数，除以该查询的相关文档数，再对所有查询取平均；
- MRR：每个查询第一个相关文档排名的倒数，再对所有查询取平均；
- dimension：Provider 实际返回的向量维度，用于确认本地模型不是空向量或错误维度。

脚本默认只跑 local-deterministic，传入 model-path 后才额外加载本地模型。LocalSentenceTransformerEmbeddingProvider 内部强制 local_files_only=True，因此该比较不调用远程 Embedding API。评估脚本没有数据库参数，不会读取既有索引，也不会把评估结果写回系统。

## 验收结果

暂存工程上使用固定的合成评估集运行：

    python scripts/embedding_eval.py
    provider=local-deterministic dimension=128 recall@2=1.000 mrr=1.000 queries=4

使用已下载的中文本地模型运行：

    python scripts/embedding_eval.py --model-path <本地模型目录> --top-k 2
    provider=local-deterministic dimension=128 recall@2=1.000 mrr=1.000 queries=4
    provider=local-model dimension=768 recall@2=1.000 mrr=1.000 queries=4
    PASS: synthetic retrieval evaluation network=disabled

该结果证明的是：两种 Provider 在当前四个合成查询上都把相关文档排进前 2，并且第一个结果就是相关文档。它不证明真实简历、长文档、跨领域问题或更大规模语料上的质量，也不替代用户对个人文档重建索引后的人工检索验收。

## 测试

新增 tests/test_embedding_eval.py，覆盖：

- Recall@K、MRR 和 Provider 维度的计算；
- 排序分数与稳定 ID 排序；
- CLI 默认只执行确定性本地基线；
- 缺少本地模型目录时直接失败且不发起远程请求。

本阶段不新增第三方依赖，不修改个人文档服务的检索协议，也不改变模型切换后必须显式重建索引的边界。

## 面试讲法

> 我没有把本地模型能加载直接当成语义效果证明，而是先固定一组人工标注的合成查询和相关文档，用同样的文档向量、查询向量和余弦排序比较两个 Provider。Recall@K 关注相关证据有没有进入候选集，MRR 关注第一个相关证据的位置。当前四条合成查询上两个 Provider 的 Recall@2 和 MRR 都是 1.0，但样本很小，所以我会把它表述为离线契约和回归基线，不会声称真实简历语料上的泛化质量。

## 未完成边界

- 还没有使用用户真实简历或个人文档做质量评估；
- 没有引入大规模标注集、nDCG、人工双标注或线上点击反馈；
- 浏览器中设置保存、显式重建索引和检索证据仍需用户用合成账号人工验收；
- 本阶段没有调用外部 API、读取或输出 API Key、删除文件、部署或提交推送 GitHub。
