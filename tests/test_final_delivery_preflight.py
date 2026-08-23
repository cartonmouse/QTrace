from scripts.final_delivery_preflight import README_EVIDENCE, REQUIRED_FILES, STAGE_DOCS, inspect_delivery


def _write_delivery_fixture(root):
    for relative_path in (*REQUIRED_FILES, *STAGE_DOCS):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("safe", encoding="utf-8")
    (root / "README.md").write_text("\n".join(README_EVIDENCE), encoding="utf-8")


def test_final_delivery_preflight_accepts_complete_synthetic_fixture(tmp_path):
    _write_delivery_fixture(tmp_path)

    report = inspect_delivery(tmp_path)

    assert report["missing_files"] == []
    assert report["missing_stage_docs"] == []
    assert report["missing_readme_evidence"] == []
    assert report["secret_hit_count"] == 0


def test_final_delivery_preflight_reports_missing_stage_and_readme_evidence(tmp_path):
    _write_delivery_fixture(tmp_path)
    (tmp_path / STAGE_DOCS[-1]).unlink()
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    (tmp_path / "README.md").write_text(readme.replace("npm run build", ""), encoding="utf-8")

    report = inspect_delivery(tmp_path)

    assert STAGE_DOCS[-1] in report["missing_stage_docs"]
    assert "npm run build" in report["missing_readme_evidence"]
