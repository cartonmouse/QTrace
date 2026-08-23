import json

from scripts.reproduction_preflight import REQUIRED_FILES, inspect_reproduction


def _write_valid_fixture(root):
    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("safe", encoding="utf-8")
    package_path = root / "frontend" / "package.json"
    package_path.write_text(
        json.dumps(
            {"scripts": {"dev": "vite", "typecheck": "tsc --noEmit", "build": "vite build"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        ".env\ndata/\nfrontend/node_modules/\nfrontend/dist/\n"
        "qtrace_stage*_pytest_tmp/\nqtrace_stage*_formal_pytest_tmp/\n",
        encoding="utf-8",
    )


def test_reproduction_preflight_accepts_complete_synthetic_fixture(tmp_path, monkeypatch):
    _write_valid_fixture(tmp_path)
    monkeypatch.setattr("scripts.reproduction_preflight.shutil.which", lambda name: f"/fake/{name}")

    report = inspect_reproduction(tmp_path)

    assert report["missing"] == []
    assert report["config_errors"] == []
    assert report["tooling"] == {"python": True, "node": True, "npm": True}


def test_reproduction_preflight_reports_missing_file_and_script(tmp_path, monkeypatch):
    _write_valid_fixture(tmp_path)
    (tmp_path / "scripts" / "local_runtime_smoke.py").unlink()
    package_path = tmp_path / "frontend" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["scripts"].pop("build")
    package_path.write_text(json.dumps(package), encoding="utf-8")
    monkeypatch.setattr("scripts.reproduction_preflight.shutil.which", lambda name: None)

    report = inspect_reproduction(tmp_path)

    assert report["missing"] == ["scripts/local_runtime_smoke.py"]
    assert "frontend/package.json is missing script: build" in report["config_errors"]


def test_reproduction_preflight_reports_invalid_package_and_ignore_rules(tmp_path, monkeypatch):
    _write_valid_fixture(tmp_path)
    (tmp_path / "frontend" / "package.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    monkeypatch.setattr("scripts.reproduction_preflight.shutil.which", lambda name: None)

    report = inspect_reproduction(tmp_path)

    assert report["missing"] == []
    assert "frontend/package.json is not valid UTF-8 JSON" in report["config_errors"]
    assert ".gitignore is missing rule: data/" in report["config_errors"]
