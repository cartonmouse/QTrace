from fastapi.testclient import TestClient

from backend.main import create_app


def _register(client: TestClient, email: str) -> tuple[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password-123", "name": "Graph Learner"},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["access_token"], payload["user"]["id"]


def test_topic_graph_connects_questions_and_sm2_reviews(tmp_path):
    app = create_app(tmp_path / "graph.sqlite3", "test-secret")
    client = TestClient(app)
    token, user_id = _register(client, "graph@example.test")
    headers = {"Authorization": f"Bearer {token}"}

    updated = client.put(
        "/api/knowledge/rag/high_freq",
        headers=headers,
        json={
            "content": (
                "- 如何评估 RAG 的召回率和准确率？\n"
                "- RAG 召回率和准确率如何通过离线评测验证？\n"
                "- Agent 如何设计工具调用？\n"
            )
        },
    )
    assert updated.status_code == 200

    app.state.store.update_profile_after_review(
        user_id,
        {
            "average_score": 4,
            "weak_points": ["RAG 召回率评估"],
            "strengths": [],
            "behavior_signals": [],
            "action_items": [],
        },
        topic="rag",
    )

    response = client.get("/api/graph/rag", headers=headers)
    assert response.status_code == 200
    graph = response.json()
    assert graph["mode"] == "deterministic_question_graph"
    assert graph["summary"]["question_count"] == 3
    assert graph["summary"]["due_review_count"] == 1
    assert graph["summary"]["weak_point_count"] == 1
    assert graph["summary"]["link_count"] == len(graph["links"])
    assert graph["summary"]["link_count"] >= 7
    assert any(node["type"] == "topic" for node in graph["nodes"])
    assert any(node["type"] == "review" and node["status"] == "due" for node in graph["nodes"])
    assert any(link["relation"] == "related" for link in graph["links"])
    assert any(link["relation"] == "revisits" for link in graph["links"])
    assert any(node["status"] == "due" for node in graph["nodes"] if node["type"] == "question")
    question_by_id = {node["id"]: node for node in graph["nodes"] if node["type"] == "question"}
    assert "question:2" in question_by_id["question:1"]["related_question_ids"]
    assert "question:1" in question_by_id["question:2"]["related_question_ids"]
    related_links = [link for link in graph["links"] if link["relation"] == "related"]
    assert all(link["started_count"] == 0 and link["completed_count"] == 0 for link in related_links)
    feedback = client.get("/api/graph/rag/feedback", headers=headers)
    assert feedback.status_code == 200
    assert feedback.json()["summary"]["candidate_edge_count"] == len(related_links)
    assert feedback.json()["summary"]["observed_edge_count"] == 0


def test_topic_graph_is_user_scoped_and_unknown_topic_is_rejected(tmp_path):
    app = create_app(tmp_path / "graph.sqlite3", "test-secret")
    client = TestClient(app)
    first_token, _ = _register(client, "first-graph@example.test")
    second_token, _ = _register(client, "second-graph@example.test")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    custom = client.put(
        "/api/knowledge/rag/high_freq",
        headers=first_headers,
        json={"content": "- 只属于第一个用户的图谱问题\n"},
    )
    assert custom.status_code == 200

    second_graph = client.get("/api/graph/rag", headers=second_headers)
    assert second_graph.status_code == 200
    assert all("只属于第一个用户" not in node["label"] for node in second_graph.json()["nodes"])

    unknown = client.get("/api/graph/not-a-topic", headers=first_headers)
    assert unknown.status_code == 400


def test_graph_question_starts_topic_drill_and_is_audited(tmp_path):
    app = create_app(tmp_path / "graph.sqlite3", "test-secret")
    client = TestClient(app)
    token, _ = _register(client, "graph-drill@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={"mode": "topic_drill", "topic": "rag", "graph_question_id": "question:2"},
    )
    assert started.status_code == 200
    session = started.json()
    assert session["graph_question_id"] == "question:2"
    assert session["graph_question"]

    answered = client.post(
        f"/api/interview/{session['id']}/answer",
        headers=headers,
        json={"answer": "我会先定义召回率、准确率和离线评测集，再做对比实验。"},
    )
    assert answered.status_code == 200
    assert answered.json()["messages"][-1]["content"] == session["graph_question"]

    invalid = client.post(
        "/api/interview/start",
        headers=headers,
        json={"mode": "topic_drill", "topic": "rag", "graph_question_id": "question:999"},
    )
    assert invalid.status_code == 400


def test_graph_related_candidate_source_is_validated_and_counted(tmp_path):
    app = create_app(tmp_path / "graph-feedback.sqlite3", "test-secret")
    client = TestClient(app)
    token, _ = _register(client, "graph-feedback@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    assert client.put(
        "/api/knowledge/rag/high_freq",
        headers=headers,
        json={
            "content": (
                "- 如何评估 RAG 的召回率和准确率？\n"
                "- RAG 召回率和准确率如何通过离线评测验证？\n"
                "- Agent 如何设计工具调用？\n"
            )
        },
    ).status_code == 200

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "rag",
            "graph_question_id": "question:2",
            "graph_entry_source": "related_neighbor",
            "graph_parent_question_id": "question:1",
        },
    )
    assert started.status_code == 200
    session = started.json()
    assert session["graph_entry_source"] == "related_neighbor"
    assert session["graph_parent_question_id"] == "question:1"
    assert session["graph_parent_question"]

    graph_after_start = client.get("/api/graph/rag", headers=headers).json()
    related_link = next(
        link for link in graph_after_start["links"]
        if link["relation"] == "related" and {link["source"], link["target"]} == {"question:1", "question:2"}
    )
    assert related_link["started_count"] == 1
    assert related_link["completed_count"] == 0

    finished = client.post(f"/api/interview/{session['id']}/finish", headers=headers)
    assert finished.status_code == 200
    assert finished.json()["is_finished"] is True
    graph_after_finish = client.get("/api/graph/rag", headers=headers).json()
    related_link = next(
        link for link in graph_after_finish["links"]
        if link["relation"] == "related" and {link["source"], link["target"]} == {"question:1", "question:2"}
    )
    assert related_link["started_count"] == 1
    assert related_link["completed_count"] == 1

    second_started = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "rag",
            "graph_question_id": "question:2",
            "graph_entry_source": "related_neighbor",
            "graph_parent_question_id": "question:1",
        },
    )
    assert second_started.status_code == 200
    assert client.post(f"/api/interview/{second_started.json()['id']}/finish", headers=headers).status_code == 200
    feedback = client.get("/api/graph/rag/feedback", headers=headers)
    assert feedback.status_code == 200
    report = feedback.json()
    assert report["summary"]["started_count"] == 2
    assert report["summary"]["completed_count"] == 2
    report_edge = next(
        edge for edge in report["edges"]
        if {edge["source"], edge["target"]} == {"question:1", "question:2"}
    )
    assert report_edge["completion_rate"] == 1.0
    assert report_edge["average_score"] is not None
    assert report_edge["score_delta"] is not None
    assert report_edge["repeat_rate"] == 0.5

    invalid_parent = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "rag",
            "graph_question_id": "question:2",
            "graph_entry_source": "related_neighbor",
            "graph_parent_question_id": "question:999",
        },
    )
    assert invalid_parent.status_code == 400
