import json

from fastapi.testclient import TestClient

from backend.main import create_app


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Agent Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_personal_agent_stub_runs_plan_tools_and_persists_conversation(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "根据我的训练历史，今天最应该复习什么？"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["conversation_id"]
    assert result["plan"]["tool_calls"]
    assert {item["name"] for item in result["tool_trace"]} >= {
        "read_profile",
        "read_due_reviews",
        "read_recent_sessions",
    }
    assert "个人成长 Agent" in result["message"]["content"]

    history = client.get("/api/agent/conversations", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["message_count"] == 2

    detail = client.get(
        f"/api/agent/conversations/{result['conversation_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant"]

    continued = client.post(
        "/api/agent/chat",
        headers=headers,
        json={
            "conversation_id": result["conversation_id"],
            "message": "再给我一个下一轮训练建议。",
        },
    )
    assert continued.status_code == 200
    assert continued.json()["conversation_id"] == result["conversation_id"]
    assert client.get(
        f"/api/agent/conversations/{result['conversation_id']}",
        headers=headers,
    ).json()["messages"][-2]["role"] == "user"


def test_agent_conversation_is_user_scoped(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    first_headers = _register(client, "agent-owner@example.test")
    second_headers = _register(client, "agent-other@example.test")
    client.put("/api/settings", headers=first_headers, json={"use_stub_provider": True})
    client.put("/api/settings", headers=second_headers, json={"use_stub_provider": True})

    created = client.post(
        "/api/agent/chat",
        headers=first_headers,
        json={"message": "读取我的画像。"},
    ).json()
    forbidden = client.get(
        f"/api/agent/conversations/{created['conversation_id']}",
        headers=second_headers,
    )
    assert forbidden.status_code == 404


def test_personal_agent_openai_path_uses_structured_plan_and_response(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []

    class FakeProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, user_prompt: str) -> str:
            calls.append((system_prompt, user_prompt))
            if "规划器" in system_prompt:
                return json.dumps(
                    {
                        "intent": "读取薄弱点",
                        "tool_calls": [
                            {"name": "read_profile", "reason": "确认画像"},
                            {"name": "read_due_reviews", "reason": "确认到期项"},
                        ],
                    },
                    ensure_ascii=False,
                )
            return "根据当前画像，建议先完成到期薄弱点的专项训练，再补充一个项目验证案例。"

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", FakeProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-llm@example.test")
    configured = client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "https://llm.example.test/v1",
            "llm_model": "test-model",
            "llm_api_key": "synthetic-test-key",
        },
    )
    assert configured.status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "我下一轮应该练什么？"},
    )
    assert response.status_code == 200
    assert response.json()["plan"]["intent"] == "读取薄弱点"
    assert "到期薄弱点" in response.json()["message"]["content"]
    assert len(calls) == 2
