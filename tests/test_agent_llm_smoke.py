from __future__ import annotations

from pathlib import Path

from backend.store import Store
from backend.provider import ProviderError
from scripts import agent_llm_smoke


def test_demo_mode_does_not_build_or_call_real_agent(tmp_path: Path, monkeypatch, capsys):
    store = Store(tmp_path / "agent-smoke.sqlite3")
    user = store.create_user("agent-smoke@example.test", "password-123", "Agent Smoke")

    def fail_if_called(_config):
        raise AssertionError("demo mode must not build a real Agent model")

    monkeypatch.setattr(agent_llm_smoke, "build_agent_model", fail_if_called)
    result = agent_llm_smoke.run_smoke(store.db_path, user["id"])

    assert result == 2
    assert "未发起网络请求" in capsys.readouterr().out


def test_missing_user_does_not_create_or_modify_database(tmp_path: Path, capsys):
    db_path = tmp_path / "agent-smoke.sqlite3"
    Store(db_path)
    before = db_path.stat().st_mtime_ns

    result = agent_llm_smoke.run_smoke(db_path, "missing-user")

    assert result == 2
    assert "未发起网络请求" in capsys.readouterr().out
    assert db_path.stat().st_mtime_ns == before


def test_configured_agent_failure_redacts_key_and_endpoint(tmp_path: Path, monkeypatch, capsys):
    store = Store(tmp_path / "agent-smoke-configured.sqlite3")
    user = store.create_user("agent-smoke-configured@example.test", "password-123", "Agent Smoke")
    api_base = "https://synthetic-provider.example/v1"
    api_key = "synthetic-agent-key"
    store.set_openai_provider(user["id"], api_base, "synthetic-model", api_key)

    def fail_if_called(_config):
        raise ProviderError(f"provider detail key={api_key} base={api_base}")

    monkeypatch.setattr(agent_llm_smoke, "build_agent_model", fail_if_called)

    result = agent_llm_smoke.run_smoke(store.db_path, user["id"])

    output = capsys.readouterr().out
    assert result == 1
    assert api_key not in output
    assert api_base not in output
    assert "<redacted>" in output
