from fastapi.testclient import TestClient

from backend.main import create_app


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Resume Editor"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _profile_payload(summary: str = "负责 AI 应用和个人 Agent 的工程化落地") -> dict[str, object]:
    return {
        "name": "QTrace Learner",
        "headline": "AI 应用开发工程师",
        "email": "resume-editor@example.test",
        "location": "北京",
        "summary": summary,
        "skills": ["Python", "FastAPI", "RAG", "Agent"],
        "projects": [
            {
                "name": "问迹 QTrace",
                "role": "独立负责后端与 Agent 编排",
                "description": "为面试训练建立画像、复习队列和个人文档检索闭环。",
                "technologies": ["FastAPI", "SQLite", "React"],
                "highlights": [
                    "设计两步 Agent：规划 -> 工具执行 -> 回答",
                    "用版本快照保留结构化简历历史",
                ],
            }
        ],
    }


def test_structured_resume_editor_versions_and_interview_context(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    headers = _register(client, "structured-resume@example.test")

    empty = client.get("/api/resume/editor", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["exists"] is False
    assert empty.json()["version"] == 0
    assert client.get("/api/resume/editor/versions", headers=headers).json() == []

    first = client.put("/api/resume/editor", headers=headers, json=_profile_payload())
    assert first.status_code == 200
    assert first.json()["version"] == 1
    assert first.json()["unchanged"] is False
    assert "项目经历" in first.json()["context_text"]
    assert "两步 Agent" in first.json()["context_text"]

    document = client.post(
        "/api/agent/documents",
        headers=headers,
        json={
            "title": "QTrace 项目复盘证据",
            "content": "问迹 QTrace 项目背景与目标是把面试训练变成可追踪的成长链。项目中我负责 Agent 编排和版本管理。",
        },
    )
    assert document.status_code == 200
    cards = client.get("/api/resume/editor/question-cards", headers=headers)
    assert cards.status_code == 200
    assert len(cards.json()) == 5
    assert {item["category"] for item in cards.json()} == {"背景与目标", "个人职责", "关键设计", "效果验证", "复盘取舍"}
    assert any(item["evidence"] for item in cards.json())

    unchanged = client.put("/api/resume/editor", headers=headers, json=_profile_payload())
    assert unchanged.status_code == 200
    assert unchanged.json()["version"] == 1
    assert unchanged.json()["unchanged"] is True

    second = client.put(
        "/api/resume/editor",
        headers=headers,
        json=_profile_payload("第二版补充了结构化简历版本管理和面试上下文生成。"),
    )
    assert second.status_code == 200
    assert second.json()["version"] == 2
    latest_cards = client.get("/api/resume/editor/question-cards", headers=headers)
    assert latest_cards.status_code == 200
    assert {item["resume_version"] for item in latest_cards.json()} == {2}

    topic = client.post(
        "/api/topics",
        headers=headers,
        json={"name": "Stage28 RAG", "key": "stage28-rag", "icon": "◈"},
    )
    assert topic.status_code == 200

    versions = client.get("/api/resume/editor/versions", headers=headers)
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]
    assert versions.json()[0]["project_count"] == 1

    first_detail = client.get("/api/resume/editor/versions/1", headers=headers)
    latest_detail = client.get("/api/resume/editor/versions/2", headers=headers)
    assert first_detail.status_code == 200
    assert latest_detail.status_code == 200
    assert "负责 AI 应用" in first_detail.json()["profile"]["summary"]
    assert "第二版补充" in latest_detail.json()["profile"]["summary"]

    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    card = latest_cards.json()[0]
    drill_started = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "stage28-rag",
            "target_role": "RAG 工程师",
            "question_card_id": card["id"],
        },
    )
    assert drill_started.status_code == 200
    assert drill_started.json()["question_card_id"] == card["id"]
    assert drill_started.json()["question_card_project"] == "问迹 QTrace"
    assert drill_started.json()["question_card_resume_version"] == 2
    drill_answered = client.post(
        f"/api/interview/{drill_started.json()['id']}/answer",
        headers=headers,
        json={"answer": "我会先说明问题边界，再用离线数据和线上指标验证方案。"},
    )
    assert drill_answered.status_code == 200
    assert card["training_focus"] in drill_answered.json()["messages"][-1]["content"]

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={"target_role": "AI 应用开发工程师", "resume_text": ""},
    )
    assert started.status_code == 200
    stored_session = app.state.store.get_session(
        client.get("/api/me", headers=headers).json()["id"],
        started.json()["id"],
    )
    assert stored_session is not None
    assert "结构化简历版本管理" in stored_session["resume_text"]

    invalid_card = client.post(
        "/api/interview/start",
        headers=headers,
        json={"question_card_id": card["id"], "target_role": "AI 应用开发工程师"},
    )
    assert invalid_card.status_code == 400


def test_structured_resume_and_agent_are_user_scoped(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    owner_headers = _register(client, "structured-owner@example.test")
    other_headers = _register(client, "structured-other@example.test")

    assert client.put("/api/resume/editor", headers=owner_headers, json=_profile_payload()).status_code == 200
    assert client.get("/api/resume/editor/versions/1", headers=other_headers).status_code == 404
    assert client.get("/api/resume/editor", headers=other_headers).json()["exists"] is False

    assert client.put("/api/settings", headers=owner_headers, json={"use_stub_provider": True}).status_code == 200
    response = client.post(
        "/api/agent/chat",
        headers=owner_headers,
        json={"message": "请读取我的简历，指出 QTrace 项目最值得准备的追问。"},
    )
    assert response.status_code == 200
    assert "read_resume" in {item["name"] for item in response.json()["tool_trace"]}
    assert "已读取结构化简历" in response.json()["message"]["content"]
