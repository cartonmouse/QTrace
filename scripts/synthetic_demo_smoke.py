"""Run a local synthetic rehearsal of QTrace's main learning loop.

The rehearsal uses FastAPI's in-process TestClient, a temporary synthetic
SQLite path, and the StubProvider. It never reads the user's database or
documents, never calls an external API, and never deletes its generated
database. The output is limited to step names and counts so it can be used as
evidence before a manual browser demo.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

# Make both ``python scripts/synthetic_demo_smoke.py`` and
# ``python -m scripts.synthetic_demo_smoke`` resolve the project package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import create_app


@dataclass(frozen=True)
class DemoStep:
    name: str
    detail: str


class DemoCheckError(RuntimeError):
    """A stable, non-sensitive failure raised by the rehearsal."""


def _require(response, expected_status: int, step: str) -> None:
    if response.status_code != expected_status:
        raise DemoCheckError(step)


def _synthetic_profile() -> dict[str, object]:
    return {
        "name": "QTrace Synthetic Learner",
        "headline": "AI 应用开发工程师",
        "email": "synthetic-demo@example.test",
        "summary": "用合成资料演示简历、知识图谱、复习队列和 Personal Agent 的连接。",
        "skills": ["Python", "FastAPI", "RAG", "Agent"],
        "projects": [
            {
                "name": "合成 QTrace 项目",
                "role": "负责 Agent 编排与训练链路",
                "description": "把画像、复习队列和个人文档检索连接到面试训练。",
                "technologies": ["FastAPI", "SQLite", "React"],
                "highlights": [
                    "实现规划、工具执行和回答的两步 Agent",
                    "用 draft/confirm 控制学习计划写入",
                ],
            }
        ],
    }


def run_demo(db_path: Path | None = None) -> list[DemoStep]:
    """Run the synthetic API rehearsal and return stable evidence steps."""

    if db_path is None:
        db_path = Path(tempfile.gettempdir()) / f"qtrace-synthetic-demo-{uuid4().hex}.sqlite3"

    app = create_app(db_path, "synthetic-demo-secret")
    client = TestClient(app)
    steps: list[DemoStep] = []

    registered = client.post(
        "/api/auth/register",
        json={
            "email": f"synthetic-{uuid4().hex[:8]}@example.test",
            "password": "password-123",
            "name": "QTrace Synthetic Learner",
        },
    )
    _require(registered, 200, "register")
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    steps.append(DemoStep("register", "status=200 synthetic_user"))

    settings = client.put("/api/settings", headers=headers, json={"use_stub_provider": True})
    _require(settings, 200, "settings")
    steps.append(DemoStep("stub_provider", "status=200 offline"))

    resume = client.put("/api/resume/editor", headers=headers, json=_synthetic_profile())
    _require(resume, 200, "resume_editor")
    if resume.json().get("version") != 1:
        raise DemoCheckError("resume_editor_version")
    steps.append(DemoStep("resume_editor", "version=1"))

    document = client.post(
        "/api/agent/documents",
        headers=headers,
        json={
            "title": "合成项目证据",
            "content": "合成项目用于说明 Agent 编排、计划确认和训练复盘，不包含真实个人经历。",
        },
    )
    _require(document, 200, "personal_document")
    cards = client.get("/api/resume/editor/question-cards", headers=headers)
    _require(cards, 200, "question_cards")
    if len(cards.json()) != 5:
        raise DemoCheckError("question_card_count")
    steps.append(DemoStep("question_cards", "count=5"))

    knowledge = client.put(
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
    _require(knowledge, 200, "knowledge")

    user = client.get("/api/me", headers=headers)
    _require(user, 200, "current_user")
    app.state.store.update_profile_after_review(
        user.json()["id"],
        {
            "average_score": 4,
            "weak_points": ["RAG 召回率评估"],
            "strengths": [],
            "behavior_signals": [],
            "action_items": [],
        },
        topic="rag",
    )
    graph = client.get("/api/graph/rag", headers=headers)
    _require(graph, 200, "knowledge_graph")
    graph_summary = graph.json().get("summary", {})
    if graph_summary.get("question_count") != 3:
        raise DemoCheckError("knowledge_graph_question_count")
    if not any(link.get("relation") == "related" for link in graph.json().get("links", [])):
        raise DemoCheckError("knowledge_graph_related_edge")
    steps.append(DemoStep("knowledge_graph", "questions=3 related_edge=true"))

    agent = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "请帮我生成今天的个性化学习计划。", "topic": "rag"},
    )
    _require(agent, 200, "agent_chat")
    result = agent.json()
    created_plan = result.get("created_plan")
    if not isinstance(created_plan, dict) or created_plan.get("status") != "draft":
        raise DemoCheckError("agent_draft")
    tool_names = {item.get("name") for item in result.get("tool_trace", [])}
    required_tools = {"read_profile", "read_due_reviews", "read_recent_sessions", "create_learning_plan"}
    if not required_tools <= tool_names:
        raise DemoCheckError("agent_tool_trace")
    steps.append(DemoStep("agent_draft", f"status=draft items={len(created_plan.get('items', []))}"))

    confirmed = client.post(
        f"/api/agent/plans/{created_plan['id']}/confirm",
        headers=headers,
    )
    _require(confirmed, 200, "plan_confirm")
    if confirmed.json().get("status") != "active":
        raise DemoCheckError("plan_active")
    steps.append(DemoStep("plan_confirm", "status=active"))

    items = created_plan.get("items", [])
    if not items:
        raise DemoCheckError("plan_items")
    final_plan = confirmed.json()
    for item in items:
        completed = client.post(
            f"/api/agent/plans/{created_plan['id']}/items/{item['id']}/complete",
            headers=headers,
        )
        _require(completed, 200, "plan_item_complete")
        final_plan = completed.json()
    if final_plan.get("status") != "completed":
        raise DemoCheckError("plan_completed")
    steps.append(DemoStep("plan_complete", f"status=completed items={len(items)}"))
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        help="optional synthetic SQLite path; defaults to a unique path in the OS temp directory",
    )
    args = parser.parse_args(argv)
    try:
        steps = run_demo(args.db)
    except DemoCheckError:
        print("FAIL synthetic demo rehearsal")
        return 1

    print("QTrace synthetic demo rehearsal")
    for step in steps:
        print(f"PASS {step.name}: {step.detail}")
    print("PASS synthetic demo rehearsal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
