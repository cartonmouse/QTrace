from __future__ import annotations

import hashlib
import math
import re

from .embedding import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from .store import Store


MAX_DOCUMENT_CHARS = 100_000
MAX_SEARCH_RESULTS = 8
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120
class PersonalDocumentError(ValueError):
    """A user document cannot be accepted or searched safely."""


def _tokens(text: str) -> list[str]:
    """Keep token overlap as a small exact-match signal beside vector scores."""
    base = [item.lower() for item in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)]
    bigrams: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        bigrams.extend(f"cjk:{run[index:index + 2]}" for index in range(len(run) - 1))
    return [*base, *bigrams]


def normalize_document_text(text: str) -> str:
    clean = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"[ \t]+\n", "\n", clean)


def split_document_text(
    text: str,
    *,
    max_chars: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split long text while preferring paragraph and sentence boundaries."""
    clean = normalize_document_text(text)
    if not clean:
        return []
    if max_chars <= 0 or overlap < 0 or overlap >= max_chars:
        raise ValueError("文档分块参数无效")
    if len(clean) <= max_chars:
        return [clean]

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        hard_end = min(start + max_chars, len(clean))
        end = hard_end
        if hard_end < len(clean):
            boundary_floor = start + max_chars // 2
            candidates = [
                (clean.rfind("\n\n", boundary_floor, hard_end), 2),
                (clean.rfind("\n", boundary_floor, hard_end), 1),
                (clean.rfind("。", boundary_floor, hard_end), 1),
                (clean.rfind("！", boundary_floor, hard_end), 1),
                (clean.rfind("？", boundary_floor, hard_end), 1),
                (clean.rfind("; ", boundary_floor, hard_end), 2),
                (clean.rfind("；", boundary_floor, hard_end), 1),
                (clean.rfind(". ", boundary_floor, hard_end), 2),
            ]
            boundary, width = max(candidates, key=lambda item: item[0])
            if boundary >= boundary_floor:
                end = boundary + width

        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("向量维度不一致")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


class PersonalDocumentService:
    """Deep module for user-owned document ingestion and evidence retrieval."""

    def __init__(self, store: Store, embedding_provider: EmbeddingProvider | None = None):
        self.store = store
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()

    @property
    def embedding_mode(self) -> str:
        return self.embedding_provider.mode

    def _prepare_document(
        self,
        *,
        title: str,
        content: str,
        source_type: str,
    ) -> tuple[str, str, str, list[dict[str, object]]]:
        clean_title = " ".join(title.strip().split())[:160]
        clean_content = normalize_document_text(content)
        if not clean_title:
            raise PersonalDocumentError("文档标题不能为空")
        if not clean_content:
            raise PersonalDocumentError("文档内容不能为空")
        if len(clean_content) > MAX_DOCUMENT_CHARS:
            raise PersonalDocumentError(f"文档内容不能超过 {MAX_DOCUMENT_CHARS} 字")
        if source_type not in {"text", "markdown", "pdf"}:
            raise PersonalDocumentError("当前只支持 text、markdown 或 pdf 文档")

        content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()
        chunks = split_document_text(clean_content)
        chunk_records = [
            {
                "chunk_index": index,
                "content": chunk,
                "embedding": self.embedding_provider.embed(chunk),
                "embedding_mode": self.embedding_mode,
            }
            for index, chunk in enumerate(chunks)
        ]
        return clean_title, clean_content, content_hash, chunk_records

    def add_document(
        self,
        user_id: str,
        *,
        title: str,
        content: str,
        source_type: str = "text",
    ) -> dict[str, object]:
        clean_title, clean_content, content_hash, chunk_records = self._prepare_document(
            title=title,
            content=content,
            source_type=source_type,
        )
        return self.store.create_personal_document(
            user_id,
            title=clean_title,
            source_type=source_type,
            content=clean_content,
            content_hash=content_hash,
            chunks=chunk_records,
        )

    def update_document(
        self,
        user_id: str,
        document_id: str,
        *,
        title: str,
        content: str,
        source_type: str = "text",
    ) -> dict[str, object] | None:
        clean_title, clean_content, content_hash, chunk_records = self._prepare_document(
            title=title,
            content=content,
            source_type=source_type,
        )
        return self.store.update_personal_document(
            user_id,
            document_id,
            title=clean_title,
            source_type=source_type,
            content=clean_content,
            content_hash=content_hash,
            chunks=chunk_records,
        )

    def list_documents(self, user_id: str) -> list[dict[str, object]]:
        return self.store.list_personal_documents(user_id)

    def list_versions(self, user_id: str, document_id: str) -> list[dict[str, object]]:
        return self.store.list_personal_document_versions(user_id, document_id)

    def get_version(
        self,
        user_id: str,
        document_id: str,
        version: int,
    ) -> dict[str, object] | None:
        return self.store.get_personal_document_version(user_id, document_id, version)

    def reindex_document(self, user_id: str, document_id: str) -> dict[str, object] | None:
        versions = self.store.list_personal_document_versions(user_id, document_id)
        if not versions:
            return None
        current = versions[0]
        _, _, _, chunk_records = self._prepare_document(
            title=str(current["title"]),
            content=str(current["content"]),
            source_type=str(current["source_type"]),
        )
        return self.store.reindex_personal_document(
            user_id,
            document_id,
            chunks=chunk_records,
        )

    def reindex_all(self, user_id: str) -> dict[str, int | str]:
        documents = self.store.list_personal_documents(user_id)
        chunk_count = 0
        reindexed_count = 0
        for document in documents:
            result = self.reindex_document(user_id, str(document["id"]))
            if result is not None:
                reindexed_count += 1
                chunk_count += int(result.get("chunk_count", 0))
        return {
            "embedding_mode": self.embedding_mode,
            "document_count": reindexed_count,
            "chunk_count": chunk_count,
        }

    def search(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        clean_query = normalize_document_text(query)
        if not clean_query:
            return []
        safe_limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
        query_vector = self.embedding_provider.embed(clean_query)
        query_tokens = set(_tokens(clean_query))
        scored: list[dict[str, object]] = []
        for chunk in self.store.list_personal_document_chunks(user_id):
            if str(chunk.get("embedding_mode", "")) != self.embedding_mode:
                continue
            content = str(chunk["content"])
            try:
                similarity = cosine_similarity(query_vector, list(chunk["embedding"]))
            except ValueError:
                # A provider/model switch can leave an old index until explicit reindex.
                continue
            overlap_count = len(query_tokens.intersection(_tokens(content)))
            if overlap_count == 0 and similarity < 0.18:
                continue
            score = min(1.0, similarity + min(0.25, overlap_count * 0.05))
            scored.append(
                {
                    "document_id": chunk["document_id"],
                    "title": chunk["title"],
                    "source_type": chunk["source_type"],
                    "chunk_index": chunk["chunk_index"],
                    "content": content,
                    "score": round(score, 4),
                    "embedding_mode": chunk["embedding_mode"],
                    "version": int(chunk.get("version", 1)),
                    "citation": (
                        f"{chunk['title']}#v{int(chunk.get('version', 1))}-chunk-"
                        f"{int(chunk['chunk_index']) + 1} "
                        f"({str(chunk['document_id'])[:8]})"
                    ),
                }
            )
        scored.sort(key=lambda item: (-float(item["score"]), int(item["chunk_index"])))
        return scored[:safe_limit]
