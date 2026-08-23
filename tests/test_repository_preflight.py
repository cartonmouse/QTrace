from scripts.repository_preflight import REQUIRED_FILES, inspect_repository


def test_repository_fixture_has_required_files_and_no_obvious_secrets(tmp_path):
    for relative_path in REQUIRED_FILES:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("safe", encoding="utf-8")

    report = inspect_repository(tmp_path)

    assert report["missing"] == []
    assert report["secret_hits"] == []


def test_local_artifacts_are_reported_but_do_not_become_secret_hits(tmp_path):
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    (tmp_path / ".env.local").write_text("REBUILD_API_KEY=local", encoding="utf-8")
    (tmp_path / "run.log").write_text("server output", encoding="utf-8")

    report = inspect_repository(tmp_path)

    assert ".env.local" in report["local_artifacts"]
    assert "run.log" in report["local_artifacts"]
    assert report["secret_hits"] == []
