import json

from fastapi.testclient import TestClient

from backend.agent import _build_learning_plan, _normalize_plan
from backend.main import create_app


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Agent Learner"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_learning_plan_explains_due_review_capacity():
    plan = _build_learning_plan(
        "请生成今天的学习计划。",
        {
            "read_profile": {"weak_points": ["缺少验证指标"]},
            "read_due_reviews": [
                {"topic": "rag", "point": "切分策略"},
                {"topic": "rag", "point": "召回率"},
                {"topic": "rag", "point": "重排"},
                {"topic": "rag", "point": "评估阈值"},
            ],
            "read_recent_sessions": [],
        },
    )
    assert plan["source"]["due_review_count"] == 4
    assert plan["source"]["due_review_scheduled"] == 3
    assert "3/4 个到期复习点" in plan["summary"]


def test_learning_plan_can_be_grounded_in_a_project_question_card(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    owner_headers = _register(client, "card-plan-owner@example.test")
    other_headers = _register(client, "card-plan-other@example.test")
    assert client.put("/api/settings", headers=owner_headers, json={"use_stub_provider": True}).status_code == 200
    assert client.put("/api/settings", headers=other_headers, json={"use_stub_provider": True}).status_code == 200
    profile = {
        "name": "Card Plan Learner",
        "headline": "AI 应用开发工程师",
        "summary": "负责个人 Agent 和面试训练工程化。",
        "skills": ["Python", "Agent"],
        "projects": [
            {
                "name": "问迹 QTrace",
                "role": "负责 Agent 编排",
                "description": "把训练、画像和复习队列连接起来。",
                "technologies": ["FastAPI", "SQLite"],
                "highlights": ["实现受控学习计划工具"],
            }
        ],
    }
    assert client.put("/api/resume/editor", headers=owner_headers, json=profile).status_code == 200
    cards = client.get("/api/resume/editor/question-cards", headers=owner_headers).json()
    card = next(item for item in cards if item["category"] == "关键设计")

    response = client.post(
        "/api/agent/chat",
        headers=owner_headers,
        json={
            "message": "请基于这张项目追问卡，生成今天的项目训练计划。",
            "question_card_id": card["id"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    tool_names = {item["name"] for item in result["tool_trace"]}
    assert {"read_question_card", "create_learning_plan"} <= tool_names
    created_plan = result["created_plan"]
    assert created_plan["status"] == "draft"
    assert created_plan["source"]["question_card"]["id"] == card["id"]
    card_item = created_plan["items"][0]
    assert card_item["type"] == "project_followup"
    assert card_item["question_card_id"] == card["id"]
    assert "项目追问卡" in result["message"]["content"]

    forbidden = client.post(
        "/api/agent/chat",
        headers=other_headers,
        json={
            "message": "请基于这张项目追问卡生成计划。",
            "question_card_id": card["id"],
        },
    )
    assert forbidden.status_code == 404


def test_plan_normalization_requires_recent_context_and_respects_negation():
    normalized = _normalize_plan(
        {
            "tool_calls": [
                {"name": "read_profile"},
                {"name": "read_due_reviews"},
            ]
        },
        "请生成今天的学习计划。",
    )
    names = [item["name"] for item in normalized["tool_calls"]]
    assert names[:3] == ["read_profile", "read_due_reviews", "read_recent_sessions"]
    assert names[-1] == "create_learning_plan"

    denied = _normalize_plan(
        {"tool_calls": [{"name": "create_learning_plan"}]},
        "暂时不要生成学习计划，只给我解释当前薄弱点。",
    )
    assert "create_learning_plan" not in {item["name"] for item in denied["tool_calls"]}


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


def test_agent_topic_scope_turns_graph_context_into_a_review_plan(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    headers = _register(client, "graph-agent@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    user_id = client.get("/api/me", headers=headers).json()["id"]

    app.state.store.update_profile_after_review(
        user_id,
        {"average_score": 4, "weak_points": ["RAG 召回率"], "strengths": [], "action_items": []},
        topic="rag",
    )
    app.state.store.update_profile_after_review(
        user_id,
        {"average_score": 4, "weak_points": ["Python 异步"], "strengths": [], "action_items": []},
        topic="python",
    )

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请根据知识图谱生成今天的专项复习计划。", "topic": "rag"},
    )
    assert response.status_code == 200
    result = response.json()
    created_plan = result["created_plan"]
    assert created_plan["source"]["topic"] == "rag"
    assert created_plan["source"]["due_review_count"] == 1
    spaced_reviews = [item for item in created_plan["items"] if item["type"] == "spaced_review"]
    assert spaced_reviews
    assert all(item["topic"] == "rag" for item in spaced_reviews)

    invalid_topic = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请生成复习计划。", "topic": "not-a-topic"},
    )
    assert invalid_topic.status_code == 400


def test_agent_graph_question_is_preserved_in_plan_and_training_entry(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    headers = _register(client, "graph-question-plan@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    assert client.put(
        "/api/knowledge/rag/high_freq",
        headers=headers,
        json={
            "content": "- 如何评估 RAG 的召回率和准确率？\n- RAG 召回率和准确率如何通过离线评测验证？\n"
        },
    ).status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={
            "message": "请围绕这道图谱问题制定一份可确认的专项训练计划。",
            "topic": "rag",
            "graph_question_id": "question:1",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "read_graph_question" in {item["name"] for item in result["tool_trace"]}
    created_plan = result["created_plan"]
    assert created_plan["source"]["graph_question"]["id"] == "question:1"
    assert created_plan["source"]["graph_question"]["related_questions"]
    graph_item = created_plan["items"][0]
    assert graph_item["type"] == "graph_question"
    assert graph_item["topic"] == "rag"
    assert graph_item["graph_question_id"] == "question:1"
    assert graph_item["graph_question"] == created_plan["source"]["graph_question"]["question"]
    assert graph_item["related_questions"][0]["id"] == "question:2"
    assert graph_item["related_questions"][0]["started_count"] == 0
    assert graph_item["related_questions"][0]["completed_count"] == 0
    assert graph_item["related_questions"][0]["completion_rate"] == 0.0
    assert graph_item["graph_entry_source"] == "question_node"
    assert created_plan["source"]["graph_question"]["entry_source"] == "question_node"
    assert "知识图谱问题" in result["message"]["content"]

    related_response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={
            "message": "请把这道相近问题作为候选来源，制定一份可确认的专项训练计划。",
            "topic": "rag",
            "graph_question_id": "question:2",
            "graph_entry_source": "related_neighbor",
            "graph_parent_question_id": "question:1",
        },
    )
    assert related_response.status_code == 200
    related_plan = related_response.json()["created_plan"]
    assert related_plan["source"]["graph_question"]["entry_source"] == "related_neighbor"
    assert related_plan["source"]["graph_question"]["parent_question_id"] == "question:1"
    assert related_plan["items"][0]["graph_entry_source"] == "related_neighbor"
    assert related_plan["items"][0]["graph_parent_question"]

    confirmed = client.post(
        f"/api/agent/plans/{related_plan['id']}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200
    related_item = related_plan["items"][0]
    training = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "rag",
            "focus": related_item["point"],
            "plan_id": related_plan["id"],
            "plan_item_id": related_item["id"],
            "graph_question_id": related_item["graph_question_id"],
            "graph_entry_source": related_item["graph_entry_source"],
            "graph_parent_question_id": related_item["graph_parent_question_id"],
        },
    )
    assert training.status_code == 200
    assert training.json()["graph_entry_source"] == "related_neighbor"
    assert training.json()["graph_parent_question_id"] == "question:1"

    refreshed = client.post(
        "/api/agent/chat",
        headers=headers,
        json={
            "message": "请重新读取这道图谱问题，并结合相近候选的历史训练情况制定一份可确认的专项训练计划。",
            "topic": "rag",
            "graph_question_id": "question:1",
        },
    )
    assert refreshed.status_code == 200
    refreshed_related = refreshed.json()["created_plan"]["items"][0]["related_questions"][0]
    assert refreshed_related["started_count"] == 1
    assert refreshed_related["completed_count"] == 0
    assert refreshed_related["completion_rate"] == 0.0

    missing_topic = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请围绕图谱问题制定计划。", "graph_question_id": "question:1"},
    )
    assert missing_topic.status_code == 400

    invalid_question = client.post(
        "/api/agent/chat",
        headers=headers,
        json={
            "message": "请围绕图谱问题制定计划。",
            "topic": "rag",
            "graph_question_id": "question:999",
        },
    )
    assert invalid_question.status_code == 400


def test_personal_agent_does_not_write_plan_for_negated_request(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "agent-no-plan@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "暂时不要生成学习计划，只解释我当前的薄弱点。"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["created_plan"] is None
    assert "create_learning_plan" not in {item["name"] for item in result["tool_trace"]}


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


def test_personal_agent_creates_user_scoped_learning_plan(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    owner_headers = _register(client, "plan-owner@example.test")
    other_headers = _register(client, "plan-other@example.test")
    assert client.put("/api/settings", headers=owner_headers, json={"use_stub_provider": True}).status_code == 200
    assert client.put("/api/settings", headers=other_headers, json={"use_stub_provider": True}).status_code == 200

    response = client.post(
        "/api/agent/chat",
        headers=owner_headers,
        json={"message": "请帮我生成今天的个性化学习计划。"},
    )
    assert response.status_code == 200
    result = response.json()
    created_plan = result["created_plan"]
    assert created_plan["id"]
    assert created_plan["conversation_id"] == result["conversation_id"]
    assert created_plan["status"] == "draft"
    assert created_plan["items"]
    assert any(item["name"] == "create_learning_plan" for item in result["tool_trace"])
    assert "计划草稿" in result["message"]["content"]

    blocked = client.post(
        f"/api/agent/plans/{created_plan['id']}/items/{created_plan['items'][0]['id']}/complete",
        headers=owner_headers,
    )
    assert blocked.status_code == 409
    confirmed = client.post(
        f"/api/agent/plans/{created_plan['id']}/confirm",
        headers=owner_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
    assert client.post(
        f"/api/agent/plans/{created_plan['id']}/confirm",
        headers=owner_headers,
    ).json()["status"] == "active"
    for item in created_plan["items"]:
        completed = client.post(
            f"/api/agent/plans/{created_plan['id']}/items/{item['id']}/complete",
            headers=owner_headers,
        )
        assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    plans = client.get("/api/agent/plans", headers=owner_headers)
    assert plans.status_code == 200
    assert plans.json()[0]["id"] == created_plan["id"]
    assert plans.json()[0]["conversation_id"] == result["conversation_id"]
    assert client.post(
        f"/api/agent/plans/{created_plan['id']}/confirm", headers=other_headers
    ).status_code == 404
    assert client.get(
        f"/api/agent/plans/{created_plan['id']}", headers=other_headers
    ).status_code == 404


def test_learning_plan_item_is_audited_by_topic_session(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    headers = _register(client, "plan-session@example.test")
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200

    created = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请帮我生成今天的个性化学习计划。"},
    ).json()["created_plan"]
    item = created["items"][0]
    start_payload = {
        "mode": "topic_drill",
        "topic": "rag",
        "target_role": "AI 应用开发工程师",
        "plan_id": created["id"],
        "plan_item_id": item["id"],
    }
    incomplete_link = client.post(
        "/api/interview/start",
        headers=headers,
        json={**start_payload, "plan_item_id": None},
    )
    assert incomplete_link.status_code == 400

    draft_start = client.post("/api/interview/start", headers=headers, json=start_payload)
    assert draft_start.status_code == 409

    confirmed = client.post(
        f"/api/agent/plans/{created['id']}/confirm", headers=headers
    )
    assert confirmed.status_code == 200

    started = client.post("/api/interview/start", headers=headers, json=start_payload)
    assert started.status_code == 200
    session = started.json()
    assert session["learning_plan_id"] == created["id"]
    assert session["learning_plan_item_id"] == item["id"]
    assert session["mode"] == "topic_drill"

    persisted = client.get(f"/api/interview/{session['id']}", headers=headers)
    assert persisted.status_code == 200
    assert persisted.json()["learning_plan_item_id"] == item["id"]
    assert client.get(f"/api/agent/plans/{created['id']}", headers=headers).json()["items"][0]["status"] == "pending"

    finished = client.post(f"/api/interview/{session['id']}/finish", headers=headers)
    assert finished.status_code == 200
    assert client.get(f"/api/agent/plans/{created['id']}", headers=headers).json()["items"][0]["status"] == "pending"

    completed = client.post(
        f"/api/agent/plans/{created['id']}/items/{item['id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["items"][0]["status"] == "completed"


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
