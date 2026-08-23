from scripts.isolated_demo_preflight import REQUIRED_MARKERS, inspect_isolated_demo


def _write_fixture(root, *, omit_marker=None):
    for relative, markers in REQUIRED_MARKERS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        selected = [marker for marker in markers if marker != omit_marker]
        path.write_text("\n".join(selected), encoding="utf-8")


def test_isolated_demo_preflight_accepts_complete_synthetic_fixture(tmp_path):
    _write_fixture(tmp_path)

    report = inspect_isolated_demo(tmp_path)

    assert report == {"missing_files": [], "missing_markers": []}


def test_isolated_demo_preflight_reports_missing_environment_marker(tmp_path):
    _write_fixture(tmp_path, omit_marker="REBUILD_DB_PATH")

    report = inspect_isolated_demo(tmp_path)

    assert report["missing_files"] == []
    assert "backend/config.py:REBUILD_DB_PATH" in report["missing_markers"]
