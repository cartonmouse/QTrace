"""Evaluate synthetic retrieval quality for the deterministic and local providers.

This command intentionally uses a fixed four-document corpus and four queries.
It does not read SQLite, personal documents, resumes, or API keys. When
--model-path is supplied, Sentence-Transformers is forced into local-files-only
mode by the local provider, so this comparison does not call a remote
Embedding service.

Examples:

    python scripts/embedding_eval.py
    python scripts/embedding_eval.py --model-path C:\\models\\text2vec --top-k 2
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# Make this script work from the repository root as well as module execution.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.embedding import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingProviderError,
    LocalSentenceTransformerEmbeddingProvider,
)


@dataclass(frozen=True)
class SyntheticDocument:
    """A labeled document in the evaluation-only corpus."""

    document_id: str
    text: str


@dataclass(frozen=True)
class SyntheticQuery:
    """A query with manually assigned relevant document IDs."""

    query_id: str
    text: str
    relevant_document_ids: frozenset[str]


@dataclass(frozen=True)
class RetrievalEvaluation:
    """Aggregate ranking metrics for one provider."""

    provider_mode: str
    dimension: int
    top_k: int
    recall_at_k: float
    mrr: float
    query_count: int
    rankings: tuple[tuple[str, ...], ...]


SYNTHETIC_DOCUMENTS: tuple[SyntheticDocument, ...] = (
    SyntheticDocument(
        "python-async",
        "Python 异步服务使用 FastAPI、asyncio 和非阻塞 I/O 处理并发请求。",
    ),
    SyntheticDocument(
        "rag-retrieval",
        "RAG 检索先切分文档，再生成 Embedding，并用余弦相似度召回相关证据。",
    ),
    SyntheticDocument(
        "agent-sm2",
        "个人 Agent 读取用户画像、知识图谱和 SM-2 到期队列，再生成个性化复习计划。",
    ),
    SyntheticDocument(
        "frontend-api",
        "React 前端通过 Vite 代理访问 FastAPI 后端，并展示请求的 loading、成功和失败状态。",
    ),
)

SYNTHETIC_QUERIES: tuple[SyntheticQuery, ...] = (
    SyntheticQuery(
        "q-python",
        "Python 异步接口如何处理并发请求？",
        frozenset({"python-async"}),
    ),
    SyntheticQuery(
        "q-rag",
        "Embedding 如何帮助 RAG 找到相关文档证据？",
        frozenset({"rag-retrieval"}),
    ),
    SyntheticQuery(
        "q-agent",
        "Agent 如何结合用户画像和 SM-2 安排复习？",
        frozenset({"agent-sm2"}),
    ),
    SyntheticQuery(
        "q-frontend",
        "React 和 Vite 前端如何访问 FastAPI 后端？",
        frozenset({"frontend-api"}),
    ),
)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("评估向量维度不一致")
    if not left:
        raise ValueError("评估向量不能为空")
    if any(not math.isfinite(value) for value in [*left, *right]):
        raise ValueError("评估向量包含非法浮点值")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _rank_embedded(
    query_vector: list[float],
    documents: Sequence[SyntheticDocument],
    document_vectors: Sequence[list[float]],
) -> tuple[str, ...]:
    scored = [
        (
            _cosine_similarity(query_vector, vector),
            document.document_id,
        )
        for document, vector in zip(documents, document_vectors, strict=True)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(document_id for _, document_id in scored)


def rank_documents(
    provider: EmbeddingProvider,
    query: str,
    documents: Sequence[SyntheticDocument] = SYNTHETIC_DOCUMENTS,
) -> tuple[str, ...]:
    """Return all synthetic document IDs in descending cosine-score order."""

    query_vector = provider.embed(query)
    document_vectors = [provider.embed(document.text) for document in documents]
    return _rank_embedded(query_vector, documents, document_vectors)


def evaluate_provider(
    provider: EmbeddingProvider,
    *,
    documents: Sequence[SyntheticDocument] = SYNTHETIC_DOCUMENTS,
    queries: Sequence[SyntheticQuery] = SYNTHETIC_QUERIES,
    top_k: int = 2,
) -> RetrievalEvaluation:
    """Calculate mean Recall@K and mean reciprocal rank on synthetic data."""

    if not documents:
        raise ValueError("评估文档集不能为空")
    if not queries:
        raise ValueError("评估查询集不能为空")
    document_ids = {document.document_id for document in documents}
    if len(document_ids) != len(documents):
        raise ValueError("评估文档 ID 必须唯一")
    if any(not query.relevant_document_ids for query in queries):
        raise ValueError("每个评估查询至少需要一个相关文档")
    if any(not query.relevant_document_ids <= document_ids for query in queries):
        raise ValueError("评估查询引用了不存在的文档")

    safe_top_k = max(1, min(int(top_k), len(documents)))
    document_vectors = [provider.embed(document.text) for document in documents]
    rankings: list[tuple[str, ...]] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []

    for query in queries:
        ranking = _rank_embedded(
            provider.embed(query.text),
            documents,
            document_vectors,
        )
        rankings.append(ranking)
        retrieved = set(ranking[:safe_top_k])
        relevant = set(query.relevant_document_ids)
        recalls.append(len(retrieved & relevant) / len(relevant))
        first_relevant_rank = next(
            (index + 1 for index, document_id in enumerate(ranking) if document_id in relevant),
            None,
        )
        reciprocal_ranks.append(1.0 / first_relevant_rank if first_relevant_rank else 0.0)

    return RetrievalEvaluation(
        provider_mode=str(provider.mode),
        dimension=int(getattr(provider, "dimension", 0)),
        top_k=safe_top_k,
        recall_at_k=sum(recalls) / len(recalls),
        mrr=sum(reciprocal_ranks) / len(reciprocal_ranks),
        query_count=len(queries),
        rankings=tuple(rankings),
    )


def _format_result(result: RetrievalEvaluation) -> str:
    return (
        f"provider={result.provider_mode} dimension={result.dimension} "
        f"recall@{result.top_k}={result.recall_at_k:.3f} "
        f"mrr={result.mrr:.3f} queries={result.query_count}"
    )


def _evaluate_local_model(model_path: Path, top_k: int) -> RetrievalEvaluation:
    if not model_path.is_dir():
        raise ValueError("本地模型目录不存在")
    provider = LocalSentenceTransformerEmbeddingProvider(str(model_path))
    return evaluate_provider(provider, top_k=top_k)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-path",
        type=Path,
        help="可选的已下载本地 Sentence-Transformers 模型目录",
    )
    parser.add_argument("--top-k", type=int, default=2, help="计算 Recall@K 的 K，默认 2")
    args = parser.parse_args(argv)

    print("QTrace synthetic embedding retrieval evaluation")
    try:
        deterministic = evaluate_provider(
            DeterministicEmbeddingProvider(),
            top_k=args.top_k,
        )
        print(_format_result(deterministic))
        if args.model_path is None:
            print("SKIP: 未提供本地模型目录；只评估 local-deterministic")
        else:
            local_model = _evaluate_local_model(args.model_path, args.top_k)
            print(_format_result(local_model))
    except (EmbeddingProviderError, OSError, ValueError):
        print("FAIL: synthetic Embedding 检索评估失败；未发起远程网络请求")
        return 1

    print("PASS: synthetic retrieval evaluation network=disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
