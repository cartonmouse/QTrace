from scripts.qtrace_interview_preflight import inspect_interview


def _write_fixture(root):
    page = root / "frontend/src/pages/MockInterview.tsx"
    style = root / "frontend/src/pages/qtrace-interview.css"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        '\n'.join(
            (
                'import "./qtrace-interview.css";',
                'className="qtrace-interview-page"',
                'className="qtrace-interview-intro"',
                'className="qtrace-interview-tabs"',
                'role="tablist"',
                'role="tabpanel"',
                'to="/topic-drill"',
            )
        ),
        encoding="utf-8",
    )
    style.write_text(
        ".qtrace-interview-page .qtrace-interview-intro "
        ".qtrace-interview-tab .qtrace-interview-panel\n"
        "@media (prefers-reduced-motion: reduce)",
        encoding="utf-8",
    )


def test_start_training_view_has_qtrace_owned_contract(tmp_path):
    _write_fixture(tmp_path)

    assert inspect_interview(tmp_path) == {
        "missing_files": [],
        "missing_markers": [],
        "missing_style_markers": [],
    }


def test_preflight_detects_removed_training_panel(tmp_path):
    _write_fixture(tmp_path)
    (tmp_path / "frontend/src/pages/qtrace-interview.css").write_text(
        ".qtrace-interview-page", encoding="utf-8"
    )

    report = inspect_interview(tmp_path)

    assert ".qtrace-interview-panel" in report["missing_style_markers"]
