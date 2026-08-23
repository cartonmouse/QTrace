import hashlib
import sqlite3

from fastapi.testclient import TestClient

from backend.main import create_app
import httpx

from backend.personal_documents import (
    DeterministicEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    split_document_text,
)
from backend.store import Store


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Document Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_local_embedding_and_chunking_are_deterministic():
    text = ("QTrace 使用个人文档保存项目证据，并通过 Embedding 检索相关片段。\n\n" * 40).strip()
    chunks = split_document_text(text, max_chars=180, overlap=30)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 180 for chunk in chunks)

    provider = DeterministicEmbeddingProvider(dimension=64)
    assert provider.embed("向量检索") == provider.embed("向量检索")
    assert len(provider.embed("向量检索")) == 64


def test_openai_compatible_embedding_provider_validates_response_contract():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((str(request.url), request.headers.get("authorization"), request.read()))
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleEmbeddingProvider(
            "https://embedding.example/v1",
            "test-key",
            "embedding-demo",
            client=client,
            retry_backoff_seconds=0,
        )
        vector = provider.embed("QTrace 文档检索")

    assert vector == [0.1, 0.2, 0.3]
    assert provider.mode == "openai-compatible"
    assert provider.dimension == 3
    assert calls[0][0] == "https://embedding.example/v1/embeddings"
    assert calls[0][1] == "Bearer test-key"
    assert b'"model":"embedding-demo"' in calls[0][2]


def test_openai_compatible_embedding_provider_retries_transient_status_and_rejects_dimension_change():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "busy"}, request=request)
        vector = [1.0, 2.0] if attempts == 2 else [1.0, 2.0, 3.0]
        return httpx.Response(200, json={"data": [{"embedding": vector}]}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleEmbeddingProvider(
            "https://embedding.example/v1",
            "test-key",
            "embedding-demo",
            client=client,
            retry_backoff_seconds=0,
        )
        assert provider.embed("first") == [1.0, 2.0]
        try:
            provider.embed("second")
        except RuntimeError as exc:
            assert "不一致的向量维度" in str(exc)
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("expected dimension mismatch")

    assert attempts == 3


def test_personal_document_api_is_user_scoped_and_searchable(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    owner_headers = _register(client, "document-owner@example.test")
    other_headers = _register(client, "document-other@example.test")

    created = client.post(
        "/api/agent/documents",
        headers=owner_headers,
        json={
            "title": "QTrace 检索设计",
            "source_type": "markdown",
            "content": "QTrace 使用本地确定性 Embedding 保存项目证据，并用余弦相似度检索文档块。",
        },
    )
    assert created.status_code == 200
    document = created.json()
    assert document["chunk_count"] == 1
    assert document["embedding_mode"] == "local-deterministic"

    owner_documents = client.get("/api/agent/documents", headers=owner_headers)
    assert owner_documents.status_code == 200
    assert [item["id"] for item in owner_documents.json()] == [document["id"]]
    assert client.get("/api/agent/documents", headers=other_headers).json() == []

    found = client.get(
        "/api/agent/documents/search",
        headers=owner_headers,
        params={"q": "确定性 Embedding 检索"},
    )
    assert found.status_code == 200
    assert found.json()[0]["document_id"] == document["id"]
    assert "余弦相似度" in found.json()[0]["content"]
    assert found.json()[0]["citation"].startswith("QTrace 检索设计#v1-chunk-1")

    hidden = client.get(
        "/api/agent/documents/search",
        headers=other_headers,
        params={"q": "确定性 Embedding 检索"},
    )
    assert hidden.status_code == 200
    assert hidden.json() == []


def test_embedding_settings_are_user_scoped_and_never_return_api_key(tmp_path):
    client = TestClient(create_app(tmp_path / "embedding-settings.sqlite3", "test-secret"))
    owner_headers = _register(client, "embedding-owner@example.test")
    other_headers = _register(client, "embedding-other@example.test")

    saved = client.put(
        "/api/settings/embedding",
        headers=owner_headers,
        json={
            "mode": "openai-compatible",
            "api_base": "https://embedding.example/v1",
            "model": "embedding-demo",
            "api_key": "synthetic-embedding-key",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["embedding_mode"] == "openai-compatible"
    assert saved.json()["embedding_key_configured"] is True
    assert "synthetic-embedding-key" not in saved.text

    owner_settings = client.get("/api/settings", headers=owner_headers)
    other_settings = client.get("/api/settings", headers=other_headers)
    assert owner_settings.json()["embedding_model"] == "embedding-demo"
    assert owner_settings.json()["embedding_key_configured"] is True
    assert other_settings.json()["embedding_mode"] == "demo"
    assert other_settings.json()["embedding_key_configured"] is False
    assert "synthetic-embedding-key" not in owner_settings.text


def test_external_embedding_reindex_is_explicit_and_hides_old_mode_until_rebuilt(tmp_path, monkeypatch):
    class FakeEmbeddingProvider:
        mode = "openai-compatible"
        dimension = 4

        def embed(self, text: str) -> list[float]:
            return [1.0, 0.5, 0.25, 0.125]

    app = create_app(tmp_path / "embedding-reindex.sqlite3", "test-secret")
    client = TestClient(app)
    headers = _register(client, "embedding-reindex@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    created = client.post(
        "/api/agent/documents",
        headers=headers,
        json={"title": "待重建文档", "content": "QTrace 外部 Embedding 重建索引测试。"},
    )
    assert created.status_code == 200
    document_id = created.json()["id"]

    configured = client.put(
        "/api/settings/embedding",
        headers=headers,
        json={
            "mode": "openai-compatible",
            "api_base": "https://embedding.example/v1",
            "model": "embedding-demo",
            "api_key": "synthetic-embedding-key",
        },
    )
    assert configured.status_code == 200
    monkeypatch.setattr("backend.main.build_embedding_provider", lambda config: FakeEmbeddingProvider())

    hidden_until_rebuilt = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "外部 Embedding"},
    )
    assert hidden_until_rebuilt.status_code == 200
    assert hidden_until_rebuilt.json() == []

    rebuilt = client.post("/api/agent/documents/reindex", headers=headers)
    assert rebuilt.status_code == 200
    assert rebuilt.json() == {
        "embedding_mode": "openai-compatible",
        "document_count": 1,
        "chunk_count": 1,
    }
    listed = client.get("/api/agent/documents", headers=headers)
    assert listed.json()[0]["id"] == document_id
    assert listed.json()[0]["embedding_mode"] == "openai-compatible"
    found = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "外部 Embedding"},
    )
    assert found.status_code == 200
    assert found.json()[0]["embedding_mode"] == "openai-compatible"


def test_agent_reads_personal_document_evidence_without_write_access(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "document-agent@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    assert client.post(
        "/api/agent/documents",
        headers=headers,
        json={
            "title": "Agent 项目复盘",
            "content": "个人 Agent 通过受控工具读取文档证据，再由回答模型生成建议。",
        },
    ).status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请根据我的个人文档说明 Agent 的检索设计。"},
    )
    assert response.status_code == 200
    result = response.json()
    names = {item["name"] for item in result["tool_trace"]}
    assert "search_personal_documents" in names
    assert result["created_plan"] is None
    assert "个人文档片段" in result["message"]["content"]
    assert "受控工具读取文档证据" in result["message"]["content"]
    assert "#v1-chunk-1" in result["message"]["content"]


def test_same_normalized_content_is_not_saved_twice(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "document-dedup@example.test")
    content = "QTrace 文档去重使用规范化正文指纹，避免同一份资料重复进入长期记忆。"

    first = client.post(
        "/api/agent/documents",
        headers=headers,
        json={"title": "第一份资料", "source_type": "text", "content": content},
    )
    second = client.post(
        "/api/agent/documents",
        headers=headers,
        json={"title": "同内容的 PDF 资料", "source_type": "pdf", "content": content},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["deduplicated"] is True
    assert len(client.get("/api/agent/documents", headers=headers).json()) == 1


def test_document_update_creates_version_history_and_current_search_uses_latest(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "document-version@example.test")
    created = client.post(
        "/api/agent/documents",
        headers=headers,
        json={
            "title": "QTrace 版本设计",
            "source_type": "text",
            "content": "第一版内容用于说明文档版本管理。",
        },
    )
    assert created.status_code == 200
    document_id = created.json()["id"]
    assert created.json()["version"] == 1

    updated = client.put(
        f"/api/agent/documents/{document_id}",
        headers=headers,
        json={
            "title": "QTrace 版本设计（更新）",
            "source_type": "markdown",
            "content": "第二版内容加入引用版本号，检索只读取最新版本。",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["unchanged"] is False

    versions = client.get(
        f"/api/agent/documents/{document_id}/versions",
        headers=headers,
    )
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]
    assert all("content" not in item for item in versions.json())

    first_version = client.get(
        f"/api/agent/documents/{document_id}/versions/1",
        headers=headers,
    )
    latest_version = client.get(
        f"/api/agent/documents/{document_id}/versions/2",
        headers=headers,
    )
    assert first_version.status_code == 200
    assert latest_version.status_code == 200
    assert "第一版内容" in first_version.json()["content"]
    assert "第二版内容" in latest_version.json()["content"]

    found = client.get(
        "/api/agent/documents/search",
        headers=headers,
        params={"q": "引用版本号 最新版本"},
    )
    assert found.status_code == 200
    assert found.json()[0]["version"] == 2
    assert "#v2-chunk-1" in found.json()[0]["citation"]

    unchanged = client.put(
        f"/api/agent/documents/{document_id}",
        headers=headers,
        json={
            "title": "改一个标题也不改变正文版本",
            "source_type": "markdown",
            "content": "第二版内容加入引用版本号，检索只读取最新版本。",
        },
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["version"] == 2
    assert unchanged.json()["unchanged"] is True


def test_legacy_personal_document_table_gets_content_hash_on_startup(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    content = "旧版本个人文档需要在启动时补齐内容指纹。"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """CREATE TABLE personal_documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                content_chars INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                embedding_mode TEXT NOT NULL DEFAULT 'local-deterministic',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO personal_documents(
                id,user_id,title,source_type,content,content_chars,chunk_count,
                embedding_mode,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            ("legacy-doc", "legacy-user", "旧文档", "text", content, len(content), 1, "local-deterministic", "now", "now"),
        )

    Store(db_path)
    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(personal_documents)").fetchall()}
        value = connection.execute(
            "SELECT content_hash,version FROM personal_documents WHERE id=?", ("legacy-doc",)
        ).fetchone()
        history = connection.execute(
            "SELECT version,content FROM personal_document_versions WHERE document_id=?",
            ("legacy-doc",),
        ).fetchone()
    assert "content_hash" in columns
    assert "version" in columns
    assert value[0] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert value[1] == 1
    assert history == (1, content)
