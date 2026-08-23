from scripts.public_demo_preflight import REQUIRED_MARKERS, inspect_public_demo


def _write_fixture(root, *, omit_marker=None, include_api_key=False):
    for relative, markers in REQUIRED_MARKERS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        selected = [marker for marker in markers if marker != omit_marker]
        text = "\n".join(selected)
        if include_api_key and relative == "deploy/demo.env.example":
            text += "\nOPENAI_API_KEY=example-only"
        path.write_text(text, encoding="utf-8")


def test_public_demo_preflight_accepts_complete_fixture(tmp_path):
    _write_fixture(tmp_path)

    report = inspect_public_demo(tmp_path)

    assert report == {"missing_files": [], "missing_markers": [], "secret_hits": []}


def test_public_demo_preflight_reports_missing_proxy_marker(tmp_path):
    _write_fixture(tmp_path, omit_marker="proxy_pass http://api:8000")

    report = inspect_public_demo(tmp_path)

    assert report["missing_files"] == []
    assert "deploy/nginx.conf:proxy_pass http://api:8000" in report["missing_markers"]


def test_public_demo_preflight_rejects_embedded_llm_key(tmp_path):
    _write_fixture(tmp_path, include_api_key=True)

    report = inspect_public_demo(tmp_path)

    assert report["secret_hits"] == ["deploy/demo.env.example:credential assignment"]

