from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend import agent as agent_module
from backend.main import create_app
from backend.provider import ProviderError


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Agent Error Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _configure_real_llm(client: TestClient, headers: dict[str, str]) -> None:
    response = client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "https://llm.example.test/v1",
            "llm_model": "synthetic-model",
            "llm_api_key": "synthetic-test-key",
        },
    )
    assert response.status_code == 200


def test_agent_planning_failure_has_stable_error_envelope(monkeypatch, tmp_path):
    class PlanningFailureProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, _user_prompt: str) -> str:
            if "规划器" in system_prompt:
                raise ProviderError("synthetic planning failure")
            return "不应执行回答阶段"

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", PlanningFailureProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-planning-error@example.test")
    _configure_real_llm(client, headers)

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "给我一条合成训练建议。"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "agent_planning_failed",
        "stage": "planning",
        "message": "Agent 规划失败，请检查模型设置或稍后重试。",
        "retryable": True,
        "state": "rolled_back",
    }
    assert client.get("/api/agent/conversations", headers=headers).json() == []


def test_agent_answer_failure_has_stable_error_envelope(monkeypatch, tmp_path):
    class AnswerFailureProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, _user_prompt: str) -> str:
            if "规划器" in system_prompt:
                return json.dumps(
                    {"intent": "合成训练建议", "tool_calls": [{"name": "read_profile"}]},
                    ensure_ascii=False,
                )
            raise ProviderError("synthetic answer failure")

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", AnswerFailureProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-answer-error@example.test")
    _configure_real_llm(client, headers)

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "给我一条合成训练建议。"},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "agent_answering_failed"
    assert detail["stage"] == "answering"
    assert detail["retryable"] is True
    assert detail["state"] == "rolled_back"
    assert "synthetic" not in detail["message"]
    assert client.get("/api/agent/conversations", headers=headers).json() == []


def test_agent_answer_failure_preserves_learning_plan_draft(monkeypatch, tmp_path):
    class PlanThenAnswerFailureProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, _user_prompt: str) -> str:
            if "规划器" in system_prompt:
                return json.dumps(
                    {
                        "intent": "个性化学习计划",
                        "tool_calls": [
                            {"name": "read_profile"},
                            {"name": "read_due_reviews"},
                            {"name": "read_recent_sessions"},
                            {"name": "create_learning_plan"},
                        ],
                    },
                    ensure_ascii=False,
                )
            raise ProviderError("synthetic answer failure after plan draft")

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", PlanThenAnswerFailureProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-preserved-draft@example.test")
    _configure_real_llm(client, headers)

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请生成我的学习计划。"},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["state"] == "preserved_draft"
    assert detail["conversation_id"]
    plans = client.get("/api/agent/plans", headers=headers)
    assert plans.status_code == 200
    assert len(plans.json()) == 1
    assert plans.json()[0]["status"] == "draft"
    assert len(client.get("/api/agent/conversations", headers=headers).json()) == 1


def test_agent_tool_failure_is_sanitized_and_answer_continues(monkeypatch, tmp_path):
    answer_prompts: list[str] = []

    class ToolFailureProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, user_prompt: str) -> str:
            if "规划器" in system_prompt:
                return json.dumps(
                    {
                        "intent": "读取薄弱点",
                        "tool_calls": [{"name": "read_profile"}],
                    },
                    ensure_ascii=False,
                )
            answer_prompts.append(user_prompt)
            return "我会只根据当前成功读取到的上下文继续回答。"

    original_execute_tool = agent_module._execute_tool

    def fail_profile(name: str, **kwargs):
        if name == "read_profile":
            raise ProviderError("synthetic internal provider detail")
        return original_execute_tool(name, **kwargs)

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", ToolFailureProvider)
    monkeypatch.setattr(agent_module, "_execute_tool", fail_profile)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-tool-failure@example.test")
    _configure_real_llm(client, headers)

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "我当前最薄弱的知识点是什么？"},
    )

    assert response.status_code == 200
    result = response.json()
    failed = result["tool_trace"][0]
    assert failed["name"] == "read_profile"
    assert failed["status"] == "failed"
    assert failed["code"] == "dependency_unavailable"
    assert failed["recovery"] == "continue_with_partial_context"
    assert failed["summary"] == "工具依赖服务暂时不可用，已跳过该工具"
    assert "synthetic internal provider detail" not in json.dumps(result, ensure_ascii=False)
    assert answer_prompts and "tool_failures" in answer_prompts[0]


def test_agent_write_tool_is_blocked_when_required_context_fails(monkeypatch, tmp_path):
    class WriteBlockedProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, _user_prompt: str) -> str:
            if "规划器" in system_prompt:
                return json.dumps(
                    {
                        "intent": "生成个性化学习计划",
                        "tool_calls": [
                            {"name": "read_profile"},
                            {"name": "read_due_reviews"},
                            {"name": "read_recent_sessions"},
                            {"name": "create_learning_plan"},
                        ],
                    },
                    ensure_ascii=False,
                )
            return "必要画像没有读取成功，本次先不创建计划。"

    original_execute_tool = agent_module._execute_tool

    def fail_profile(name: str, **kwargs):
        if name == "read_profile":
            raise ProviderError("synthetic profile provider detail")
        return original_execute_tool(name, **kwargs)

    monkeypatch.setattr("backend.agent.OpenAICompatibleProvider", WriteBlockedProvider)
    monkeypatch.setattr(agent_module, "_execute_tool", fail_profile)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-write-blocked@example.test")
    _configure_real_llm(client, headers)

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请生成我的个性化学习计划。"},
    )

    assert response.status_code == 200
    result = response.json()
    trace = {item["name"]: item for item in result["tool_trace"]}
    assert trace["create_learning_plan"]["status"] == "skipped"
    assert trace["create_learning_plan"]["code"] == "write_blocked_by_context"
    assert result["created_plan"] is None
    assert client.get("/api/agent/plans", headers=headers).json() == []
