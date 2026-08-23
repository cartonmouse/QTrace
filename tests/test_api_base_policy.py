import socket

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.network_policy import APIBasePolicyError, validate_api_base


def _public_resolver(host: str, port: int, **_kwargs) -> list[tuple]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


@pytest.mark.parametrize(
    "api_base",
    [
        "http://127.0.0.1:8000/v1",
        "http://10.0.0.8/v1",
        "http://169.254.169.254/latest",
        "http://[::1]/v1",
        "http://localhost/v1",
        "http://model.internal/v1",
        "ftp://provider.example/v1",
        "https://user:password@provider.example/v1",
    ],
)
def test_public_policy_rejects_local_or_unsafe_api_base(api_base):
    with pytest.raises(APIBasePolicyError):
        validate_api_base(api_base, block_private=True, resolver=_public_resolver)


def test_public_policy_accepts_a_hostname_that_resolves_only_to_public_ips():
    assert (
        validate_api_base(
            "https://synthetic-provider.example/v1/",
            block_private=True,
            resolver=_public_resolver,
        )
        == "https://synthetic-provider.example/v1"
    )


def test_public_policy_rejects_private_dns_result():
    def private_resolver(host: str, port: int, **_kwargs) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.8", port))]

    with pytest.raises(APIBasePolicyError, match="公网地址"):
        validate_api_base(
            "https://synthetic-provider.example/v1",
            block_private=True,
            resolver=private_resolver,
        )


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "network-policy@example.test",
            "password": "password-123",
            "name": "Synthetic Network Policy Learner",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_public_app_rejects_private_llm_and_embedding_settings(tmp_path):
    client = TestClient(
        create_app(
            tmp_path / "network-policy.sqlite3",
            "test-secret",
            block_private_api_base=True,
        )
    )
    headers = _register(client)

    llm_response = client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "http://127.0.0.1:11434/v1",
            "llm_model": "synthetic-model",
            "llm_api_key": "synthetic-key",
        },
    )
    assert llm_response.status_code == 400
    assert "公开 Demo" in llm_response.json()["detail"]

    embedding_response = client.put(
        "/api/settings/embedding",
        headers=headers,
        json={
            "mode": "openai-compatible",
            "api_base": "http://10.0.0.8:8080/v1",
            "model": "synthetic-embedding-model",
            "api_key": "synthetic-key",
            "model_path": "",
        },
    )
    assert embedding_response.status_code == 400
    assert "公开 Demo" in embedding_response.json()["detail"]


def test_public_app_rejects_private_probe_before_provider_call(monkeypatch, tmp_path):
    class UnexpectedProvider:
        def __init__(self, **_kwargs):
            raise AssertionError("private API Base must be rejected before provider construction")

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", UnexpectedProvider)
    client = TestClient(
        create_app(
            tmp_path / "network-policy-probe.sqlite3",
            "test-secret",
            block_private_api_base=True,
        )
    )
    headers = _register(client)
    response = client.post(
        "/api/settings/test-llm",
        headers=headers,
        json={
            "api_base": "http://127.0.0.1:11434/v1",
            "model": "synthetic-model",
            "api_key": "synthetic-key",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "公开 Demo" in response.json()["error"]
