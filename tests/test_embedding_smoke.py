from __future__ import annotations

from pathlib import Path

from backend.store import Store
from scripts import embedding_smoke


def test_demo_mode_does_not_build_or_call_external_provider(tmp_path: Path, monkeypatch, capsys):
    store = Store(tmp_path / "smoke.sqlite3")
    user = store.create_user("smoke@example.test", "password-123", "Smoke Learner")

    def fail_if_called(_config):
        raise AssertionError("demo mode must not build an external provider")

    monkeypatch.setattr(embedding_smoke, "build_embedding_provider", fail_if_called)
    result = embedding_smoke.run_smoke(store.db_path, user["id"])

    assert result == 2
    assert "未发起网络请求" in capsys.readouterr().out


def test_missing_user_does_not_create_or_modify_database(tmp_path: Path, capsys):
    db_path = tmp_path / "smoke.sqlite3"
    store = Store(db_path)
    before = db_path.stat().st_mtime_ns

    result = embedding_smoke.run_smoke(db_path, "missing-user")

    assert result == 2
    assert "未发起网络请求" in capsys.readouterr().out
    assert db_path.stat().st_mtime_ns == before


def test_local_model_smoke_uses_synthetic_text_without_network(tmp_path: Path, monkeypatch, capsys):
    db_path = tmp_path / "local-smoke.sqlite3"
    store = Store(db_path)
    user = store.create_user("local-smoke@example.test", "password-123", "Local Smoke")
    model_dir = tmp_path / "synthetic-model"
    model_dir.mkdir()
    store.set_local_embedding(user["id"], str(model_dir))

    class FakeProvider:
        mode = "local-model"
        dimension = 3

        def embed(self, text: str) -> list[float]:
            assert text.startswith("QTrace synthetic embedding smoke test")
            return [0.8, 0.4, 0.1]

    monkeypatch.setattr(embedding_smoke, "build_embedding_provider", lambda config: FakeProvider())
    result = embedding_smoke.run_smoke(db_path, user["id"])

    assert result == 0
    output = capsys.readouterr().out
    assert "PASS: synthetic 本地 Embedding 验收成功" in output
    assert "network=disabled" in output
