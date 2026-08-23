import sqlite3

from backend.store import Store


def _configured_user(store: Store) -> str:
    return store.create_user(
        "session-byok@example.test",
        "password-123",
        "Session BYOK Learner",
    )["id"]


def test_session_byok_keeps_keys_out_of_sqlite_and_requires_reentry_after_restart(tmp_path):
    db_path = tmp_path / "session-byok.sqlite3"
    store = Store(db_path, secret_storage_mode="session")
    user_id = _configured_user(store)

    store.set_openai_provider(
        user_id,
        "https://synthetic-provider.example/v1",
        "synthetic-model",
        "synthetic-llm-key",
    )
    store.set_openai_embedding(
        user_id,
        "https://synthetic-provider.example/v1",
        "synthetic-embedding-model",
        "synthetic-embedding-key",
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT llm_api_key, embedding_api_key FROM settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
    assert row == ("", "")
    assert store.get_provider_config(user_id)["api_key"] == "synthetic-llm-key"
    assert store.get_embedding_config(user_id)["api_key"] == "synthetic-embedding-key"
    assert store.get_settings(user_id)["llm_configured"] is True
    assert store.get_settings(user_id)["embedding_configured"] is True

    restarted = Store(db_path, secret_storage_mode="session")
    settings = restarted.get_settings(user_id)
    assert settings["llm_configured"] is False
    assert settings["llm_key_configured"] is False
    assert settings["embedding_configured"] is False
    assert settings["embedding_key_configured"] is False
    assert restarted.get_provider_config(user_id)["mode"] == "none"
    assert restarted.get_provider_config(user_id)["api_key"] == ""
    assert restarted.get_embedding_config(user_id)["api_key"] == ""


def test_persisted_byok_mode_keeps_existing_local_behavior(tmp_path):
    db_path = tmp_path / "persisted-byok.sqlite3"
    store = Store(db_path, secret_storage_mode="persisted")
    user_id = _configured_user(store)
    store.set_openai_provider(
        user_id,
        "https://synthetic-provider.example/v1",
        "synthetic-model",
        "synthetic-llm-key",
    )

    restarted = Store(db_path, secret_storage_mode="persisted")
    assert restarted.get_provider_config(user_id)["mode"] == "openai"
    assert restarted.get_provider_config(user_id)["api_key"] == "synthetic-llm-key"
    assert restarted.get_settings(user_id)["llm_configured"] is True


def test_session_embedding_key_is_cleared_when_switching_away_from_remote_mode(tmp_path):
    db_path = tmp_path / "session-embedding-switch.sqlite3"
    store = Store(db_path, secret_storage_mode="session")
    user_id = _configured_user(store)

    store.set_openai_embedding(
        user_id,
        "https://synthetic-provider.example/v1",
        "synthetic-embedding-model",
        "synthetic-embedding-key",
    )
    assert store.get_embedding_config(user_id)["api_key"] == "synthetic-embedding-key"

    store.set_embedding_demo(user_id)
    assert store.get_embedding_config(user_id)["api_key"] == ""
    assert store.get_settings(user_id)["embedding_key_configured"] is False

    store.set_openai_embedding(
        user_id,
        "https://synthetic-provider.example/v1",
        "synthetic-embedding-model",
        "synthetic-embedding-key-2",
    )
    store.set_local_embedding(user_id, str(tmp_path))
    assert store.get_embedding_config(user_id)["api_key"] == ""
    assert store.get_settings(user_id)["embedding_key_configured"] is False
