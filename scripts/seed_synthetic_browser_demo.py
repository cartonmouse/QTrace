"""Create a fresh, synthetic QTrace database for a manual browser rehearsal.

The command only creates a new SQLite path. It refuses an existing database
or SQLite sidecar, never deletes files, never reads the user's database or
documents, and never calls an external model. The printed credentials are
synthetic and intended only for a local demo account.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import create_app
from scripts.synthetic_demo_smoke import _synthetic_profile


DEMO_PASSWORD = "qtrace-demo-pass"
DEMO_BACKEND_PORT = 8003
DEMO_FRONTEND_PORT = 5175


@dataclass(frozen=True)
class SeededBrowserDemo:
    db_path: Path
    email: str
    password: str
    checks: tuple[str, ...]


class DemoSeedError(RuntimeError):
    """A stable, non-sensitive error raised before an unsafe seed."""


def _validate_demo_port(value: int, label: str) -> int:
    if not 1 <= value <= 65535:
        raise DemoSeedError(f"invalid_{label}_port")
    return value


def _require(response, expected_status: int, step: str) -> None:
    if response.status_code != expected_status:
        raise DemoSeedError(step)


def _new_database_path(db_path: Path | None) -> Path:
    if db_path is None:
        candidate = Path(tempfile.gettempdir()) / f"qtrace-browser-demo-{uuid4().hex}.sqlite3"
    else:
        candidate = db_path.expanduser()
    candidate = candidate.resolve()
    sidecars = (
        candidate,
        candidate.with_name(candidate.name + "-wal"),
        candidate.with_name(candidate.name + "-shm"),
        candidate.with_name(candidate.name + "-journal"),
    )
    if any(path.exists() for path in sidecars):
        raise DemoSeedError("refuse_existing_database")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def seed_browser_demo(db_path: Path | None = None) -> SeededBrowserDemo:
    """Create a fresh synthetic account and its browser-rehearsal context."""

    database = _new_database_path(db_path)
    email = f"qtrace-demo-{uuid4().hex[:8]}@example.test"
    app = create_app(database, "synthetic-browser-demo-secret")
    client = TestClient(app)

    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": DEMO_PASSWORD, "name": "QTrace Synthetic Learner"},
    )
    _require(registered, 200, "register")
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    settings = client.put("/api/settings", headers=headers, json={"use_stub_provider": True})
    _require(settings, 200, "stub_provider")

    profile = _synthetic_profile()
    profile["email"] = email
    resume = client.put("/api/resume/editor", headers=headers, json=profile)
    _require(resume, 200, "resume_editor")

    document = client.post(
        "/api/agent/documents",
        headers=headers,
        json={
            "title": "合成项目证据",
            "content": "合成资料用于浏览器彩排，说明 Agent 编排、计划确认和训练复盘，不包含真实个人经历。",
        },
    )
    _require(document, 200, "personal_document")

    knowledge = client.put(
        "/api/knowledge/rag/high_freq",
        headers=headers,
        json={
            "content": (
                "- 如何评估 RAG 的召回率和准确率？\n"
                "- Agent 如何设计工具调用？\n"
                "- 如何验证一个学习计划是否有效？\n"
            )
        },
    )
    _require(knowledge, 200, "knowledge")

    cards = client.get("/api/resume/editor/question-cards", headers=headers)
    _require(cards, 200, "question_cards")
    if len(cards.json()) != 5:
        raise DemoSeedError("question_card_count")
    graph = client.get("/api/graph/rag", headers=headers)
    _require(graph, 200, "knowledge_graph")

    return SeededBrowserDemo(
        db_path=database,
        email=email,
        password=DEMO_PASSWORD,
        checks=("register", "stub_provider", "resume_editor", "personal_document", "knowledge", "question_cards", "knowledge_graph"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        help="new SQLite path; defaults to a unique OS temporary path and refuses existing files",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=DEMO_BACKEND_PORT,
        help=f"recommended local backend port (default: {DEMO_BACKEND_PORT})",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=DEMO_FRONTEND_PORT,
        help=f"recommended local frontend port (default: {DEMO_FRONTEND_PORT})",
    )
    args = parser.parse_args(argv)
    try:
        backend_port = _validate_demo_port(args.backend_port, "backend")
        frontend_port = _validate_demo_port(args.frontend_port, "frontend")
        demo = seed_browser_demo(args.db)
    except DemoSeedError:
        print("FAIL synthetic browser demo seed")
        return 1

    print("QTrace synthetic browser demo seed")
    print(f"PASS database_created: {demo.db_path}")
    print(f"EMAIL={demo.email}")
    print(f"PASSWORD={demo.password}")
    print(f"REBUILD_DB_PATH={demo.db_path}")
    print(f"REBUILD_DATA_DIR={demo.db_path.parent}")
    print(f"BACKEND_URL=http://127.0.0.1:{backend_port}")
    print(f"FRONTEND_URL=http://127.0.0.1:{frontend_port}")
    print(f"REBUILD_API_TARGET=http://127.0.0.1:{backend_port}")
    print("PASS synthetic browser demo seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
