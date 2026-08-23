from fastapi.testclient import TestClient
import pytest

from backend.embedding import (
    EmbeddingProviderError,
    LocalSentenceTransformerEmbeddingProvider,
)
from backend.main import create_app


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Local Model Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_sentence_transformer_provider_loads_only_local_model_and_validates_vector(tmp_path):
    model_dir = tmp_path / "synthetic-model"
    model_dir.mkdir()
    loader_calls: list[tuple[str, bool]] = []

    class FakeModel:
        def encode(self, text: str, *, normalize_embeddings: bool, convert_to_numpy: bool):
            assert text == "本地语义检索"
            assert normalize_embeddings is True
            assert convert_to_numpy is True
            return [0.8, 0.6]

    def loader(path: str, *, local_files_only: bool):
        loader_calls.append((path, local_files_only))
        return FakeModel()

    provider = LocalSentenceTransformerEmbeddingProvider(str(model_dir), model_loader=loader)
    vector = provider.embed("本地语义检索")

    assert provider.mode == "local-model"
    assert provider.dimension == 2
    assert vector == [0.8, 0.6]
    assert loader_calls == [(str(model_dir), True)]


def test_sentence_transformer_provider_rejects_dimension_change(tmp_path):
    model_dir = tmp_path / "synthetic-model"
    model_dir.mkdir()

    class FakeModel:
        def __init__(self):
            self.calls = 0

        def encode(self, text: str, **kwargs):
            self.calls += 1
            return [1.0, 0.0] if self.calls == 1 else [1.0, 0.0, 0.0]

    provider = LocalSentenceTransformerEmbeddingProvider(
        str(model_dir), model_loader=lambda path, **kwargs: FakeModel()
    )
    provider.embed("第一次")
    with pytest.raises(EmbeddingProviderError, match="不一致的向量维度"):
        provider.embed("第二次")


def test_local_model_settings_reindex_documents_without_network(tmp_path, monkeypatch):
    model_dir = tmp_path / "synthetic-model"
    model_dir.mkdir()
    app = create_app(tmp_path / "local-model.sqlite3", "test-secret")
    client = TestClient(app)
    headers = _register(client, "local-model@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200

    created = client.post(
        "/api/agent/documents",
        headers=headers,
        json={"title": "合成项目说明", "content": "本地模型负责语义检索，QTrace 只使用合成验收内容。"},
    )
    assert created.status_code == 200
    document_id = created.json()["id"]

    configured = client.put(
        "/api/settings/embedding",
        headers=headers,
        json={"mode": "local-model", "model_path": str(model_dir)},
    )
    assert configured.status_code == 200
    assert configured.json()["embedding_mode"] == "local-model"
    assert configured.json()["embedding_model_path"] == str(model_dir)
    assert configured.json()["embedding_key_configured"] is False

    class FakeProvider:
        mode = "local-model"
        dimension = 3

        def embed(self, text: str) -> list[float]:
            return [0.9, 0.3, 0.1]

    monkeypatch.setattr("backend.main.build_embedding_provider", lambda config: FakeProvider())
    hidden_until_rebuilt = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "本地模型语义检索"},
    )
    assert hidden_until_rebuilt.status_code == 200
    assert hidden_until_rebuilt.json() == []

    rebuilt = client.post("/api/agent/documents/reindex", headers=headers)
    assert rebuilt.status_code == 200
    assert rebuilt.json() == {
        "embedding_mode": "local-model",
        "document_count": 1,
        "chunk_count": 1,
    }
    listed = client.get("/api/agent/documents", headers=headers)
    assert listed.json()[0]["id"] == document_id
    assert listed.json()[0]["embedding_mode"] == "local-model"
    found = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "本地模型语义检索"},
    )
    assert found.status_code == 200
    assert found.json()[0]["embedding_mode"] == "local-model"
