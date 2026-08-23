import json

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.personalized_drill import (
    LLMDrillQuestionGenerator,
    StubDrillQuestionGenerator,
    normalize_drill_plan,
)
from backend.store import Store


def test_stub_drill_prioritizes_due_points_and_profile_focus():
    plan = StubDrillQuestionGenerator().generate(
        topic="rag",
        topic_name="RAG",
        knowledge_context="召回、重排和评估",
        question_bank=["如何定位 RAG 的召回问题？"],
        profile={"weak_points": ["缺少量化指标"]},
        topic_profile={
            "mastery_score": 5.2,
            "trend": "stable",
            "weak_points": ["召回评估"],
        },
        due_reviews=[{"point": "chunk 切分策略"}],
        recent_sessions=[{"average_score": 5.0}],
        requested_focus="离线评估",
    )

    assert plan["source"] == "stub_profile_driven"
    assert "学习计划焦点" in plan["questions"][0]
    assert any(question.startswith("复习任务：") for question in plan["questions"])
    assert "离线评估" in plan["items"][0]["focus"]
    assert any("召回评估" in question for question in plan["questions"])
    assert len(plan["questions"]) <= 8


def test_llm_drill_generator_validates_structured_json():
    calls: list[tuple[str, str]] = []

    def fake_chat(system_prompt: str, user_prompt: str) -> str:
        calls.append((system_prompt, user_prompt))
        return json.dumps(
            {
                "questions": [
                    {
                        "question": "请说明混合检索如何验证召回质量？",
                        "focus": "RAG 评估",
                        "difficulty": 4,
                        "reason": "当前掌握度已经进入工程验证阶段",
                    }
                ]
            },
            ensure_ascii=False,
        )

    plan = LLMDrillQuestionGenerator(fake_chat).generate(
        topic="rag",
        topic_name="RAG",
        knowledge_context="混合检索和离线评估",
        question_bank=["向量检索和 BM25 有什么差异？"],
        profile={"weak_points": ["召回评估"]},
        topic_profile={"mastery_score": 7.5, "trend": "improving"},
        due_reviews=[{"point": "重排"}],
        recent_sessions=[],
        requested_focus="评估工具选型",
    )

    assert plan["source"] == "llm_profile_driven"
    assert plan["items"][0]["difficulty"] == 4
    assert "due_reviews" in calls[0][1]
    assert "评估工具选型" in calls[0][1]


def test_drill_plan_rejects_empty_or_malformed_questions():
    try:
        normalize_drill_plan({"questions": []}, topic="agent", source="test")
    except Exception as exc:
        assert "没有可用题目" in str(exc)
    else:
        raise AssertionError("empty questions should be rejected")


def test_profile_migration_and_signal_writeback(tmp_path):
    store = Store(tmp_path / "rebuild.sqlite3")
    user = store.create_user("profile@example.test", "password-123", "Profile Learner")
    store.update_profile_after_review(
        user["id"],
        {
            "average_score": 6.5,
            "strengths": ["能完成结构化回答"],
            "weak_points": ["缺少量化指标"],
            "behavior_signals": ["回答有清晰的行动线索"],
            "action_items": ["补充一次压测数据"],
        },
        topic="rag",
    )
    profile = store.get_profile(user["id"])
    topic = store.get_topic_profile(user["id"], "rag")

    assert profile["strong_points"] == ["能完成结构化回答"]
    assert profile["behavior_signals"] == ["回答有清晰的行动线索"]
    assert profile["action_items"] == ["补充一次压测数据"]
    assert topic is not None
    assert topic["recent_scores"] == [6.5]
    assert topic["trend"] == "new"


def test_topic_start_uses_llm_question_generator_before_interview(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []

    class FakeProvider:
        def __init__(self, **_kwargs):
            pass

        def structured_chat(self, system_prompt: str, user_prompt: str) -> str:
            calls.append((system_prompt, user_prompt))
            return json.dumps(
                {
                    "questions": [
                        {
                            "question": "请说明你会如何验证 RAG 的召回质量？",
                            "focus": "RAG 评估",
                            "difficulty": 4,
                            "reason": "根据本轮画像安排工程验证问题",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        def opening(self, *args, **kwargs) -> str:
            return "请先介绍你对这个领域的理解。"

        def next_question(
            self,
            phase,
            target_role,
            last_answer,
            question_number=1,
            resume_text="",
            topic="",
            knowledge_context="",
            question_bank=None,
            **kwargs,
        ) -> str:
            return (question_bank or ["默认问题"])[0]

    monkeypatch.setattr("backend.main.OpenAICompatibleProvider", FakeProvider)
    monkeypatch.setattr("backend.personalized_drill.OpenAICompatibleProvider", FakeProvider)
    client = TestClient(create_app(tmp_path / "rebuild.sqlite3", "test-secret"))
    registered = client.post(
        "/api/auth/register",
        json={"email": "drill-llm@example.test", "password": "password-123", "name": "Drill Learner"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
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

    started = client.post(
        "/api/interview/start",
        headers=headers,
        json={
            "mode": "topic_drill",
            "topic": "rag",
            "focus": "离线评估数据集",
            "target_role": "AI 工程师",
        },
    )
    assert started.status_code == 200
    answered = client.post(
        f"/api/interview/{started.json()['id']}/answer",
        headers=headers,
        json={"answer": "我会先定义召回率和上下文相关性，再用离线数据集验证。"},
    )
    assert answered.status_code == 200
    assert "验证 RAG 的召回质量" in answered.json()["messages"][-1]["content"]
    assert calls and "profile" in calls[0][1] and "topic_profile" in calls[0][1]
    assert "离线评估数据集" in calls[0][1]
