from __future__ import annotations

import hashlib
import math
import re
import time
from collections.abc import Mapping
from typing import Any, Callable, Protocol

import httpx


class EmbeddingProviderError(RuntimeError):
    """An embedding service failed or returned an unusable vector."""


class EmbeddingProvider(Protocol):
    """The narrow vectorization seam used by personal document retrieval."""

    mode: str
    dimension: int

    def embed(self, text: str) -> list[float]: ...


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")


def _tokens(text: str) -> list[str]:
    """Extract stable word/character tokens without Python's random hash."""
    base = [item.lower() for item in _TOKEN_PATTERN.findall(text)]
    bigrams: list[str] = []
    for run in _CJK_RUN_PATTERN.findall(text):
        bigrams.extend(f"cjk:{run[index:index + 2]}" for index in range(len(run) - 1))
    return [*base, *bigrams]


def _coerce_vector(raw: Any) -> list[float]:
    """Convert common numpy/torch/list outputs into one validated vector."""
    if hasattr(raw, "detach"):
        raw = raw.detach().cpu()
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    if not isinstance(raw, (list, tuple)) or not raw:
        raise EmbeddingProviderError("本地 Embedding 模型没有返回有效向量")
    if isinstance(raw[0], (list, tuple)):
        raise EmbeddingProviderError("本地 Embedding 模型返回了批量向量，预期是单条文本向量")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw):
        raise EmbeddingProviderError("本地 Embedding 向量包含非数字值")
    values = [float(value) for value in raw]
    if any(not math.isfinite(value) for value in values):
        raise EmbeddingProviderError("本地 Embedding 向量包含非法浮点值")
    return values


class DeterministicEmbeddingProvider:
    """Offline hashed embedding used for a repeatable local retrieval baseline."""

    mode = "local-deterministic"

    def __init__(self, dimension: int = 128):
        self.dimension = max(32, min(int(dimension), 512))

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]


class LocalSentenceTransformerEmbeddingProvider:
    """Load a downloaded Sentence-Transformers model without network access.

    The import and model construction are lazy so the default project install
    remains lightweight. ``local_files_only=True`` is always passed to the
    loader; a missing dependency or incomplete local model becomes an explicit
    ``EmbeddingProviderError`` instead of silently downloading anything.
    """

    mode = "local-model"

    def __init__(
        self,
        model_path: str,
        *,
        model_loader: Callable[..., Any] | None = None,
    ):
        clean_path = model_path.strip()
        if not clean_path:
            raise ValueError("本地 Embedding 需要模型目录")
        self.model_path = clean_path
        self._model_loader = model_loader
        self._model: Any | None = None
        self.dimension = 0

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        loader = self._model_loader
        if loader is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingProviderError(
                    "本地语义 Embedding 需要 sentence-transformers；"
                    "请安装 requirements-local-embedding.txt"
                ) from exc
            loader = SentenceTransformer
        try:
            self._model = loader(self.model_path, local_files_only=True)
        except Exception as exc:  # model libraries expose several exception types
            raise EmbeddingProviderError(f"本地 Embedding 模型加载失败：{exc}") from exc
        return self._model

    def embed(self, text: str) -> list[float]:
        clean_text = text.strip()
        if not clean_text:
            raise EmbeddingProviderError("Embedding 输入文本不能为空")
        model = self._load_model()
        try:
            raw = model.encode(
                clean_text,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:  # model libraries expose several exception types
            raise EmbeddingProviderError(f"本地 Embedding 推理失败：{exc}") from exc
        values = _coerce_vector(raw)
        dimension = len(values)
        if self.dimension and self.dimension != dimension:
            raise EmbeddingProviderError("本地 Embedding 模型返回了不一致的向量维度")
        self.dimension = dimension
        return values


class OpenAICompatibleEmbeddingProvider:
    """Adapter for OpenAI-compatible ``/embeddings`` endpoints.

    The document service only depends on ``EmbeddingProvider``. This class owns
    HTTP, response validation and bounded retries, so a later provider switch
    does not leak network details into chunking or retrieval logic.
    """

    mode = "openai-compatible"

    _RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.25,
    ):
        clean_base = api_base.strip().rstrip("/")
        clean_key = api_key.strip()
        clean_model = model.strip()
        if not clean_base or not clean_key or not clean_model:
            raise ValueError("Embedding 配置需要 API Base、Model 和 API Key")
        self.api_base = clean_base
        self.api_key = clean_key
        self.model = clean_model
        self.timeout_seconds = max(0.1, min(float(timeout_seconds), 120.0))
        self._client = client
        self.max_retries = max(0, min(int(max_retries), 3))
        self.retry_backoff_seconds = max(0.0, min(float(retry_backoff_seconds), 2.0))
        self.dimension = 0

    def _wait_before_retry(self, attempt: int) -> None:
        delay = min(self.retry_backoff_seconds * (2**attempt), 2.0)
        if delay > 0:
            time.sleep(delay)

    def _post(self, text: str) -> httpx.Response:
        payload = {"model": self.model, "input": text}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.api_base}/embeddings"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self._client is not None:
                    response = self._client.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                self._wait_before_retry(attempt)
                continue

            if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                self._wait_before_retry(attempt)
                continue
            return response

        detail = str(last_error) if last_error else "请求多次失败"
        raise EmbeddingProviderError(f"Embedding 请求失败：{detail}") from last_error

    def embed(self, text: str) -> list[float]:
        clean_text = text.strip()
        if not clean_text:
            raise EmbeddingProviderError("Embedding 输入文本不能为空")
        response = self._post(clean_text)
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ")
            raise EmbeddingProviderError(
                f"Embedding 服务返回 HTTP {response.status_code}: {detail}"
            )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError("Embedding 响应不是合法 JSON") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        item = data[0] if isinstance(data, list) and data else None
        vector = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vector, list) or not vector:
            raise EmbeddingProviderError("Embedding 响应缺少有效向量")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector):
            raise EmbeddingProviderError("Embedding 向量包含非数字值")
        values = [float(value) for value in vector]
        if any(not math.isfinite(value) for value in values):
            raise EmbeddingProviderError("Embedding 向量包含非法浮点值")
        dimension = len(values)
        if self.dimension and self.dimension != dimension:
            raise EmbeddingProviderError("Embedding 服务返回了不一致的向量维度")
        self.dimension = dimension
        return values


def build_embedding_provider(config: Mapping[str, str]) -> EmbeddingProvider:
    """Build a user-scoped provider without exposing provider details to callers."""
    if config.get("mode") == "local-model":
        model_path = config.get("model_path", "") or config.get("local_model_path", "")
        return LocalSentenceTransformerEmbeddingProvider(model_path)
    if config.get("mode") == "openai-compatible":
        return OpenAICompatibleEmbeddingProvider(
            api_base=config.get("api_base", ""),
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
    return DeterministicEmbeddingProvider()
