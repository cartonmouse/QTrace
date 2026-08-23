import json
import sqlite3
from datetime import date

import httpx
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.provider import OpenAICompatibleProvider, StubProvider
from backend.recording import LLMRecordingAnalyzer, TextPassthroughASRProvider
from backend.review_schedule import initial_schedule, sm2_update
from backend.store import Store


def _text_pdf(text: str) -> bytes:
    """Build a tiny text PDF without adding a test-only PDF generation dependency."""
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 20 200 Td ({safe_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:])
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    return pdf


def test_auth_provider_gate_and_interview_loop(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))

    registered = client.post(
        "/api/auth/register",
        json={"email": "learner@example.test", "password": "password-123", "name": "Learner"},
    )
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    settings = client.get("/api/settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json()["needs_onboarding"] is True

    blocked = client.post("/api/interview/start", headers=headers, json={"target_role": "后端工程师"})
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "provider_not_configured"

    enabled = client.put("/api/settings", headers=headers, json={"use_stub_provider": True})
    assert enabled.status_code == 200
    assert enabled.json()["needs_onboarding"] is False

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={"target_role": "后端工程师", "resume_text": "我做过一个 RAG 面试助手。"},
    )
    assert started.status_code == 200
    session = started.json()
    assert session["phase"] == "self_intro"
    assert session["messages"][0]["role"] == "assistant"

    for index in range(8):
        if session["is_finished"]:
            break
        response = client.post(
            f"/api/interview/{session['id']}/answer",
            headers=headers,
            json={"answer": f"这是第 {index + 1} 轮回答，结果提升了 20%，我负责设计和验证。"},
        )
        assert response.status_code == 200
        session = response.json()

    finished = client.post(f"/api/interview/{session['id']}/finish", headers=headers)
    assert finished.status_code == 200
    assert finished.json()["review"]["average_score"] > 0

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["completed_sessions"] == 1

    history = client.get("/api/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_user_cannot_read_another_users_session(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))

    first = client.post(
        "/api/auth/register",
        json={"email": "first@example.test", "password": "password-123", "name": "First"},
    ).json()
    second = client.post(
        "/api/auth/register",
        json={"email": "second@example.test", "password": "password-123", "name": "Second"},
    ).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    client.put("/api/settings", headers=first_headers, json={"use_stub_provider": True})
    session = client.post("/api/interview/start", headers=first_headers, json={}).json()

    response = client.get(f"/api/interview/{session['id']}", headers=second_headers)
    assert response.status_code == 404


def test_stub_provider_varies_follow_up_questions():
    provider = StubProvider()
    first = provider.next_question("technical", "后端工程师", "回答", 1)
    second = provider.next_question("technical", "后端工程师", "回答", 2)
    assert first != second


def test_sm2_schedule_is_explainable_and_resets_after_failed_recall():
    today = date(2026, 8, 20)
    initial = initial_schedule(today)
    assert initial["next_review"] == "2026-08-20"

    first_success = sm2_update(initial, 8, today)
    assert first_success["repetitions"] == 1
    assert first_success["interval_days"] == 1
    assert first_success["next_review"] == "2026-08-21"

    second_success = sm2_update(first_success, 8, today)
    assert second_success["repetitions"] == 2
    assert second_success["interval_days"] == 3
    assert second_success["next_review"] == "2026-08-23"

    failed_recall = sm2_update(second_success, 2, today)
    assert failed_recall["repetitions"] == 0
    assert failed_recall["interval_days"] == 1
    assert failed_recall["next_review"] == "2026-08-21"


def test_openai_compatible_provider_uses_chat_completions_contract():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        system = payload["messages"][0]["content"]
        if "JSON 对象" in system:
            content = json.dumps(
                {
                    "summary": "动态复盘",
                    "average_score": 8,
                    "scores": [8],
                    "strengths": ["结构清晰"],
                    "weak_points": [],
                    "action_items": ["继续补充指标"],
                },
                ensure_ascii=False,
            )
        else:
            content = "请说明你会如何验证这个方案的有效性？"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            "https://llm.example.test/v1", "test-key", "test-model", client=client
        )
        assert provider.opening("后端工程师", "RAG 项目")
        assert provider.next_question("technical", "后端工程师", "我做了压测", 2, "RAG 项目")
        review = provider.review([{"role": "user", "content": "回答"}], "后端工程师", "RAG 项目")

    assert review["average_score"] == 8
    assert len(seen) == 3
    assert seen[0]["model"] == "test-model"
    assert seen[0]["messages"][0]["role"] == "system"


def test_openai_settings_are_user_scoped_and_key_is_not_returned(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "provider@example.test", "password": "password-123", "name": "Provider Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    saved = client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "https://llm.example.test/v1",
            "llm_model": "test-model",
            "llm_api_key": "synthetic-test-key",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["provider_mode"] == "openai"
    assert saved.json()["llm_key_configured"] is True
    assert "synthetic-test-key" not in saved.text

    read_back = client.get("/api/settings", headers=headers)
    assert read_back.json()["llm_key_configured"] is True
    assert "synthetic-test-key" not in read_back.text


def test_stage1_stub_setting_is_migrated_to_provider_mode(tmp_path):
    db_path = tmp_path / "old-stage1.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, password_hash TEXT, name TEXT, created_at TEXT);
            CREATE TABLE settings (
                user_id TEXT PRIMARY KEY,
                use_stub_provider INTEGER NOT NULL DEFAULT 0,
                llm_configured INTEGER NOT NULL DEFAULT 0,
                embedding_configured INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO settings(user_id,use_stub_provider,llm_configured,embedding_configured)
            VALUES('legacy-user',1,1,1);
            """
        )
    values = Store(db_path).get_settings("legacy-user")
    assert values["provider_mode"] == "stub"


def test_resume_upload_parses_pdf_and_is_injected_when_starting(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"email": "resume@example.test", "password": "password-123", "name": "Resume Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    client.put("/api/settings", headers=headers, json={"use_stub_provider": True})

    pdf = _text_pdf("RAG project: local resume context")
    uploaded = client.post(
        "/api/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["has_resume"] is True
    assert uploaded.json()["filename"] == "resume.pdf"

    text = client.get("/api/resume/text", headers=headers)
    assert text.status_code == 200
    assert "RAG project" in text.json()["text"]

    started = client.post("/api/interview/start", headers=headers, json={"target_role": "AI 工程师"})
    assert started.status_code == 200
    session_id = started.json()["id"]
    stored = app.state.store.get_session(registered["user"]["id"], session_id)
    assert stored is not None
    assert "RAG project" in stored["resume_text"]

    downloaded = client.get("/api/resume/file", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")

    removed = client.delete("/api/resume", headers=headers)
    assert removed.status_code == 200
    assert removed.json() == {"deleted": True}
    assert client.get("/api/resume/status", headers=headers).json()["has_resume"] is False


def test_resume_upload_rejects_non_pdf_and_path_like_filename(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "resume-validation@example.test", "password": "password-123", "name": "Validator"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    fake_pdf = b"not a pdf"

    wrong_type = client.post(
        "/api/resume/upload",
        headers=headers,
        files={"file": ("resume.txt", fake_pdf, "text/plain")},
    )
    assert wrong_type.status_code == 400
    assert "PDF" in wrong_type.json()["detail"]

    path_like = client.post(
        "/api/resume/upload",
        headers=headers,
        files={"file": ("../resume.pdf", _text_pdf("safe"), "application/pdf")},
    )
    assert path_like.status_code == 400
    assert "路径" in path_like.json()["detail"]


def test_topics_knowledge_crud_and_topic_drill_context(tmp_path):
    app = create_app(tmp_path / "rebuild.sqlite3", "test-secret")
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"email": "topic@example.test", "password": "password-123", "name": "Topic Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    client.put("/api/settings", headers=headers, json={"use_stub_provider": True})

    topics = client.get("/api/topics", headers=headers)
    assert topics.status_code == 200
    assert {"python", "rag", "agent"}.issubset(topics.json())
    core = client.get("/api/knowledge/rag/core", headers=headers)
    assert core.status_code == 200
    assert "RAG" in core.json()[0]["content"]

    created = client.post(
        "/api/topics",
        headers=headers,
        json={"key": "testing", "name": "测试领域", "icon": "✓"},
    )
    assert created.status_code == 200
    created_file = client.post(
        "/api/knowledge/testing/core",
        headers=headers,
        json={"filename": "notes.md", "content": "测试知识：先定义指标，再做压测。"},
    )
    assert created_file.status_code == 200
    updated = client.put(
        "/api/knowledge/testing/high_freq",
        headers=headers,
        json={"content": "- 为什么要先定义指标再做压测？\n- 如何判断压测结果可信？"},
    )
    assert updated.status_code == 200

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={"mode": "topic_drill", "topic": "testing", "target_role": "AI 工程师"},
    )
    assert started.status_code == 200
    session = started.json()
    assert session["mode"] == "topic_drill"
    assert session["topic"] == "testing"
    assert "专项训练" in session["messages"][0]["content"]

    answered = client.post(
        f"/api/interview/{session['id']}/answer",
        headers=headers,
        json={"answer": "我会先定义延迟、吞吐和错误率指标，再设计压测场景并对比基线。"},
    )
    assert answered.status_code == 200
    assert "为什么要先定义指标" in answered.json()["messages"][-1]["content"]

    finished = client.post(f"/api/interview/{session['id']}/finish", headers=headers)
    assert finished.status_code == 200
    assert "testing" in finished.json()["review"]["summary"]

    mastery = client.get("/api/profile/topics", headers=headers)
    assert mastery.status_code == 200
    assert mastery.json()[0]["topic"] == "testing"
    assert mastery.json()[0]["attempts"] == 1
    assert mastery.json()[0]["mastery_score"] > 0
    topic_history = client.get("/api/profile/topic/testing/history", headers=headers)
    assert topic_history.status_code == 200
    assert len(topic_history.json()) == 1
    assert topic_history.json()[0]["topic"] == "testing"

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["topic_mastery"][0]["topic"] == "testing"
    assert profile.json()["due_reviews"]
    due_reviews = client.get("/api/profile/due-reviews?topic=testing", headers=headers)
    assert due_reviews.status_code == 200
    assert due_reviews.json()[0]["topic"] == "testing"

    next_started = client.post(
        "/api/interview/start",
        headers=headers,
        json={"mode": "topic_drill", "topic": "testing", "target_role": "AI 工程师"},
    )
    assert next_started.status_code == 200
    next_answered = client.post(
        f"/api/interview/{next_started.json()['id']}/answer",
        headers=headers,
        json={"answer": "我会先复述问题、给出假设，再用指标和实验验证结论。"},
    )
    assert next_answered.status_code == 200
    assert "复习任务：" in next_answered.json()["messages"][-1]["content"]

    unsafe = client.post(
        "/api/knowledge/testing/core",
        headers=headers,
        json={"filename": "../escape.md", "content": "x"},
    )
    assert unsafe.status_code == 400

    deleted = client.delete("/api/topics/testing", headers=headers)
    assert deleted.status_code == 200
    assert "testing" not in client.get("/api/topics", headers=headers).json()


def test_jd_preview_and_targeted_training(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "jd@example.test", "password": "password-123", "name": "JD Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    client.put("/api/settings", headers=headers, json={"use_stub_provider": True})
    jd_text = (
        "我们正在招聘大模型应用开发工程师，负责 Python、FastAPI、RAG 和 Agent 服务建设；"
        "需要关注向量检索、SQL、Docker、性能优化，并建立评测和监控体系。"
    )

    preview_response = client.post(
        "/api/job-prep/preview",
        headers=headers,
        json={
            "company": "QTrace Labs",
            "position": "大模型应用开发工程师",
            "jd_text": jd_text,
            "use_resume": False,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["preview"]
    assert preview["position"] == "大模型应用开发工程师"
    assert {"Python", "RAG", "Agent"}.issubset(preview["detected_skills"])
    assert preview["likely_question_groups"]
    assert len(preview["question_blueprint"]) == 8

    started = client.post(
        "/api/job-prep/start",
        headers=headers,
        json={
            "company": "QTrace Labs",
            "position": "大模型应用开发工程师",
            "jd_text": jd_text,
            "use_resume": False,
            "preview": preview,
        },
    )
    assert started.status_code == 200
    session = started.json()
    assert session["mode"] == "jd_prep"
    assert session["company"] == "QTrace Labs"
    assert "定向备面" in session["messages"][0]["content"]

    answered = client.post(
        f"/api/interview/{session['id']}/answer",
        headers=headers,
        json={"answer": "我会结合岗位要求介绍一个 Python 服务项目，并说明结果和指标。"},
    )
    assert answered.status_code == 200
    assert "JD" in answered.json()["messages"][-1]["content"]

    finished = client.post(f"/api/interview/{session['id']}/finish", headers=headers)
    assert finished.status_code == 200
    assert "大模型应用开发工程师" in finished.json()["review"]["summary"]

    history = client.get("/api/history", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["company"] == "QTrace Labs"


def test_jd_preview_maps_structured_projects_to_question_cards(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "jd-project-map@example.test", "password": "password-123", "name": "JD Project Mapper"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    assert client.put("/api/settings", headers=headers, json={"use_stub_provider": True}).status_code == 200
    resume = {
        "name": "Project Mapper",
        "headline": "AI 应用开发工程师",
        "summary": "负责 AI Agent 应用工程化。",
        "skills": ["Python", "Agent"],
        "projects": [
            {
                "name": "问迹 QTrace",
                "role": "负责 Agent 编排和后端实现",
                "description": "把面试训练、画像和复习队列连接成可追踪的成长系统。",
                "technologies": ["Python", "FastAPI", "Agent"],
                "highlights": ["通过结构化复盘和测试验证训练链路"],
            }
        ],
    }
    assert client.put("/api/resume/editor", headers=headers, json=resume).status_code == 200
    jd_text = "招聘 AI 应用开发工程师，负责 Python、FastAPI 和 Agent 系统建设，要求具备工程验证和项目落地能力。"

    mapped = client.post(
        "/api/job-prep/preview",
        headers=headers,
        json={"position": "AI 应用开发工程师", "jd_text": jd_text, "use_resume": True},
    )
    assert mapped.status_code == 200
    matches = mapped.json()["preview"]["project_matches"]
    assert matches
    qtrace_match = next(item for item in matches if item["project_name"] == "问迹 QTrace")
    assert {"Python", "FastAPI", "Agent"}.issubset(qtrace_match["matched_skills"])
    assert "technologies" in qtrace_match["evidence_fields"]
    assert qtrace_match["priority"] == "high"
    assert qtrace_match["score"] > 0
    assert qtrace_match["question_card_id"] == "project-1-question-3"

    without_resume = client.post(
        "/api/job-prep/preview",
        headers=headers,
        json={"position": "AI 应用开发工程师", "jd_text": jd_text, "use_resume": False},
    )
    assert without_resume.status_code == 200
    assert without_resume.json()["preview"]["project_matches"] == []


def test_recording_transcript_analysis_is_persisted_and_updates_profile(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "recording@example.test", "password": "password-123", "name": "Recording Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    transcript = (
        "面试官：请介绍一下你做过的 RAG 项目。\n"
        "你：我负责文档清洗、切分和召回链路，先定义召回率和延迟指标，再用离线数据集验证，最终召回率提升 20%。\n"
        "面试官：如果请求量增长十倍，你会怎么处理？\n"
        "你：我会先看缓存命中率、数据库和模型延迟，然后设计压测，必要时增加降级和限流。"
    )
    analyzed = client.post(
        "/api/recording/analyze",
        headers=headers,
        json={
            "recording_mode": "dual",
            "company": "QTrace Labs",
            "position": "RAG 工程师",
            "transcript": transcript,
        },
    )
    assert analyzed.status_code == 200
    session = analyzed.json()
    assert session["mode"] == "recording"
    assert session["recording_mode"] == "dual"
    assert session["company"] == "QTrace Labs"
    assert [message["role"] for message in session["messages"]] == ["assistant", "user", "assistant", "user"]
    assert session["review"]["transcript_meta"]["answer_count"] == 2
    assert session["review"]["average_score"] > 0

    stored = client.get(f"/api/interview/{session['id']}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["recording_mode"] == "dual"
    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["completed_sessions"] == 1

    solo = client.post(
        "/api/recording/analyze",
        headers=headers,
        json={"recording_mode": "solo", "transcript": "我复盘今天的项目回答，先说明背景，再说明行动和结果。"},
    )
    assert solo.status_code == 200
    assert solo.json()["review"]["transcript_meta"]["recording_mode"] == "solo"


def test_recording_adapter_contract_parses_structured_llm_result_and_text_source():
    document = TextPassthroughASRProvider().transcribe(
        "面试官：请介绍项目。\n你：我负责检索链路并通过指标验证。".encode("utf-8"),
        filename="practice.txt",
        content_type="text/plain",
    )
    assert document["provider"] == "text_passthrough"
    assert "面试官" in document["text"]

    analyzer = LLMRecordingAnalyzer(
        lambda _system, _user: json.dumps(
            {
                "summary": "模型复盘",
                "average_score": 8.6,
                "scores": [8.6],
                "strengths": ["有验证意识"],
                "weak_points": ["可以补充失败边界"],
                "action_items": ["准备一个失败案例"],
            },
            ensure_ascii=False,
        )
    )
    messages, review = analyzer.analyze(document["text"], recording_mode="dual", position="AI 工程师")
    assert [message["role"] for message in messages] == ["assistant", "user"]
    assert review["average_score"] == 8.6
    assert review["transcript_meta"]["analysis_mode"] == "llm"


def test_recording_llm_mode_uses_configured_provider_without_network(monkeypatch, tmp_path):
    class FakeProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, _system, _user):
            return json.dumps(
                {
                    "summary": "定向模型复盘",
                    "average_score": 7.5,
                    "scores": [7.5],
                    "strengths": ["回答完整"],
                    "weak_points": [],
                    "action_items": ["补充量化结果"],
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", FakeProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "recording-llm@example.test", "password": "password-123", "name": "LLM Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    client.put(
        "/api/settings",
        headers=headers,
        json={
            "use_stub_provider": False,
            "llm_api_base": "https://llm.example.test/v1",
            "llm_model": "test-model",
            "llm_api_key": "synthetic-test-key",
        },
    )
    response = client.post(
        "/api/recording/analyze",
        headers=headers,
        json={
            "analysis_mode": "llm",
            "recording_mode": "solo",
            "position": "AI 工程师",
            "transcript": "我负责一个检索项目，使用离线指标验证方案并补充失败案例。",
        },
    )
    assert response.status_code == 200
    assert response.json()["recording_analysis_mode"] == "llm"
    assert response.json()["review"]["summary"] == "定向模型复盘"


def test_copilot_text_prep_streams_ordered_events_and_persists_result(tmp_path):
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "copilot@example.test", "password": "password-123", "name": "Copilot Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    jd_text = (
        "招聘大模型应用开发工程师，负责 Python、FastAPI、RAG 和 Agent 服务建设；"
        "需要关注向量检索、SQL、Docker、性能优化，并建立评测和监控体系。"
    )

    streamed = client.post(
        "/api/copilot/stream",
        headers=headers,
        json={
            "company": "QTrace Labs",
            "position": "大模型应用开发工程师",
            "jd_text": jd_text,
            "use_resume": False,
        },
    )
    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    blocks = [block for block in streamed.text.split("\n\n") if block.strip()]
    event_names = [block.split("\n", 1)[0].split(":", 1)[1].strip() for block in blocks]
    assert event_names == ["started", "jd_analyzed", "risk_assessed", "strategy_ready", "completed"]
    completed_data = json.loads(next(line[6:] for line in blocks[-1].splitlines() if line.startswith("data:")))
    prep_id = completed_data["prep_id"]
    assert completed_data["result"]["strategy_tree"]["nodes"]

    stored = client.get(f"/api/copilot/prep/{prep_id}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["jd_text"] == jd_text
    assert stored.json()["status"] == "completed"
    assert stored.json()["result"]["source"]["analysis_mode"] == "deterministic_text_prep"
    history = client.get("/api/copilot/prep", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["id"] == prep_id
