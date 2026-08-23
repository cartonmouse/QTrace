from fastapi.testclient import TestClient

from backend.main import create_app
from backend.provider import ProviderError


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "llm-probe@example.test",
            "password": "password-123",
            "name": "Synthetic Probe Learner",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_llm_probe_uses_unsaved_values_and_does_not_persist(monkeypatch, tmp_path):
    seen: list[dict[str, str]] = []

    class FakeProvider:
        def __init__(self, *, api_base, api_key, model, **_kwargs):
            seen.append({"api_base": api_base, "api_key": api_key, "model": model})

        def probe(self):
            return None

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", FakeProvider)
    client = TestClient(create_app(tmp_path / "probe.sqlite3", "test-secret"))
    headers = _register(client)

    response = client.post(
        "/api/settings/test-llm",
        headers=headers,
        json={
            "api_base": "https://synthetic-provider.example/v1",
            "model": "synthetic-model",
            "api_key": "synthetic-key",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "LLM 连接成功"}
    assert seen == [
        {
            "api_base": "https://synthetic-provider.example/v1",
            "api_key": "synthetic-key",
            "model": "synthetic-model",
        }
    ]
    assert client.get("/api/settings", headers=headers).json()["llm_configured"] is False
    assert "synthetic-key" not in response.text


def test_llm_probe_can_reuse_saved_key_without_returning_it(monkeypatch, tmp_path):
    seen: list[dict[str, str]] = []

    class FakeProvider:
        def __init__(self, *, api_base, api_key, model, **_kwargs):
            seen.append({"api_base": api_base, "api_key": api_key, "model": model})

        def probe(self):
            return None

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", FakeProvider)
    client = TestClient(create_app(tmp_path / "saved-probe.sqlite3", "test-secret"))
    headers = _register(client)
    saved = client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "https://synthetic-provider.example/v1",
            "llm_model": "synthetic-model",
            "llm_api_key": "synthetic-key",
        },
    )
    assert saved.status_code == 200

    response = client.post(
        "/api/settings/test-llm",
        headers=headers,
        json={"api_base": "", "model": "", "api_key": ""},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert seen[-1]["api_key"] == "synthetic-key"
    assert "synthetic-key" not in response.text


def test_llm_probe_returns_safe_provider_error(monkeypatch, tmp_path):
    class FailingProvider:
        def __init__(self, **_kwargs):
            pass

        def probe(self):
            raise ProviderError("LLM 网络连接失败，请检查 API Base 和网络设置")

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", FailingProvider)
    client = TestClient(create_app(tmp_path / "failed-probe.sqlite3", "test-secret"))
    headers = _register(client)

    response = client.post(
        "/api/settings/test-llm",
        headers=headers,
        json={
            "api_base": "https://synthetic-provider.example/v1",
            "model": "synthetic-model",
            "api_key": "synthetic-key",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "LLM 网络连接失败，请检查 API Base 和网络设置",
    }
    assert "synthetic-key" not in response.text
