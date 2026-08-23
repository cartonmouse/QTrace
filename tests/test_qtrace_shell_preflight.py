from scripts.qtrace_shell_preflight import inspect_shell


def _write_fixture(root):
    app = root / "frontend/src/App.tsx"
    shell = root / "frontend/src/components/QTraceWorkspaceShell.tsx"
    style = root / "frontend/src/components/qtrace-workspace.css"
    app.parent.mkdir(parents=True, exist_ok=True)
    shell.parent.mkdir(parents=True, exist_ok=True)
    app.write_text(
        'import QTraceWorkspaceShell from "./components/QTraceWorkspaceShell";\n'
        "<QTraceWorkspaceShell>",
        encoding="utf-8",
    )
    shell.write_text(
        'import "./qtrace-workspace.css";\n'
        "className={`qtrace-shell is-compact`}\n"
        'className="qtrace-shell-content"\n'
        'aria-label="QTrace 主导航"\n'
        "PERSONAL INTERVIEW OS",
        encoding="utf-8",
    )
    style.write_text(
        ".qtrace-shell .qtrace-shell-sidebar .qtrace-shell-content\n@media",
        encoding="utf-8",
    )


def test_qtrace_shell_is_active_and_self_owned(tmp_path):
    _write_fixture(tmp_path)

    assert inspect_shell(tmp_path) == {
        "missing_files": [],
        "missing_app_markers": [],
        "missing_shell_markers": [],
        "missing_style_markers": [],
        "forbidden_active_imports": [],
    }


def test_preflight_rejects_reference_sidebar_or_landing_as_app_shell(tmp_path):
    _write_fixture(tmp_path)
    app = tmp_path / "frontend/src/App.tsx"
    app.write_text(
        app.read_text(encoding="utf-8")
        + '\nimport Sidebar from "./components/Sidebar";\n'
        + 'import Landing from "./pages/Landing";',
        encoding="utf-8",
    )

    report = inspect_shell(tmp_path)

    assert report["forbidden_active_imports"] == [
        'import Sidebar from "./components/Sidebar";',
        'import Landing from "./pages/Landing";',
    ]


def test_preflight_reports_missing_qtrace_shell_contract(tmp_path):
    _write_fixture(tmp_path)
    (tmp_path / "frontend/src/components/QTraceWorkspaceShell.tsx").write_text(
        "", encoding="utf-8"
    )

    report = inspect_shell(tmp_path)

    assert report["missing_shell_markers"]
