from fastapi.testclient import TestClient

from backend.main import create_app
from scripts import seed_synthetic_browser_demo
from scripts.seed_synthetic_browser_demo import DemoSeedError, SeededBrowserDemo, seed_browser_demo


def test_seed_synthetic_browser_demo_creates_loginable_context(tmp_path):
    database = tmp_path / "browser-demo.sqlite3"

    seeded = seed_browser_demo(database)

    assert seeded.db_path == database.resolve()
    assert seeded.email.endswith("@example.test")
    assert seeded.password == "qtrace-demo-pass"
    assert seeded.checks[-1] == "knowledge_graph"
    app = create_app(seeded.db_path, "synthetic-browser-demo-secret")
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": seeded.email, "password": seeded.password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/resume/editor", headers=headers).status_code == 200
    assert client.get("/api/agent/documents", headers=headers).status_code == 200
    assert client.get("/api/graph/rag", headers=headers).status_code == 200


def test_seed_synthetic_browser_demo_refuses_existing_database(tmp_path):
    database = tmp_path / "existing.sqlite3"
    database.write_text("do not overwrite", encoding="utf-8")

    try:
        seed_browser_demo(database)
    except DemoSeedError as exc:
        assert str(exc) == "refuse_existing_database"
    else:
        raise AssertionError("existing database must not be overwritten")

    assert database.read_text(encoding="utf-8") == "do not overwrite"


def test_seed_synthetic_browser_demo_prints_isolated_endpoints(tmp_path, monkeypatch, capsys):
    database = tmp_path / "browser-demo.sqlite3"
    seeded = SeededBrowserDemo(
        db_path=database,
        email="qtrace-demo@example.test",
        password="qtrace-demo-pass",
        checks=("synthetic",),
    )
    monkeypatch.setattr(seed_synthetic_browser_demo, "seed_browser_demo", lambda _: seeded)

    assert seed_synthetic_browser_demo.main(["--db", str(database)]) == 0

    output = capsys.readouterr().out
    assert "BACKEND_URL=http://127.0.0.1:8003" in output
    assert "FRONTEND_URL=http://127.0.0.1:5175" in output
    assert "REBUILD_API_TARGET=http://127.0.0.1:8003" in output


def test_seed_synthetic_browser_demo_accepts_available_fallback_ports(tmp_path, monkeypatch, capsys):
    database = tmp_path / "browser-demo.sqlite3"
    seeded = SeededBrowserDemo(
        db_path=database,
        email="qtrace-demo@example.test",
        password="qtrace-demo-pass",
        checks=("synthetic",),
    )
    monkeypatch.setattr(seed_synthetic_browser_demo, "seed_browser_demo", lambda _: seeded)

    assert seed_synthetic_browser_demo.main(
        ["--db", str(database), "--backend-port", "8004", "--frontend-port", "5177"]
    ) == 0

    output = capsys.readouterr().out
    assert "BACKEND_URL=http://127.0.0.1:8004" in output
    assert "FRONTEND_URL=http://127.0.0.1:5177" in output
    assert "REBUILD_API_TARGET=http://127.0.0.1:8004" in output


def test_seed_synthetic_browser_demo_rejects_invalid_port_before_seeding(tmp_path, monkeypatch, capsys):
    def unexpected_seed(_):
        raise AssertionError("invalid ports must be rejected before seeding")

    monkeypatch.setattr(seed_synthetic_browser_demo, "seed_browser_demo", unexpected_seed)

    assert seed_synthetic_browser_demo.main(
        ["--db", str(tmp_path / "should-not-exist.sqlite3"), "--backend-port", "0"]
    ) == 1

    assert capsys.readouterr().out == "FAIL synthetic browser demo seed\n"
