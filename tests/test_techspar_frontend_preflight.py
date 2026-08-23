from scripts.techspar_frontend_preflight import inspect_frontend


def _write_fixture(root, *, complete=True):
    frontend = root / "frontend"
    for relative in (
        "src/App.tsx",
        "src/components/QTraceWorkspaceShell.tsx",
        "src/components/qtrace-workspace.css",
        "src/components/Logo.jsx",
        "src/components/TaskNotification.jsx",
        "src/pages/Landing.jsx",
        "src/pages/Home.jsx",
        "src/pages/Settings.jsx",
        "src/pages/PersonalAgent.tsx",
        "src/api/interview.ts",
        "src/api/personalAgent.ts",
        "src/contexts/AuthContext.tsx",
    ):
        path = frontend / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    (frontend / "src" / "App.tsx").write_text(
        "\n".join(
            (
                'path="/interview/:sessionId"',
                'path="/review/:sessionId"',
                'path="/profile"',
                'path="/personal-agent"',
                'path="/knowledge"',
                'path="/graph"',
                'path="/recording"',
                'path="/mock-interview"',
                'path="/job-prep"',
                'path="/copilot"',
                'path="/topic-drill"',
                'path="/resume-manager"',
                'path="/settings"',
                'import QTraceWorkspaceShell from "./components/QTraceWorkspaceShell";',
                '<QTraceWorkspaceShell>',
            )
        ),
        encoding="utf-8",
    )
    (frontend / "src" / "components" / "Sidebar.tsx").write_text(
        "问迹", encoding="utf-8"
    )
    (frontend / "src" / "components" / "QTraceWorkspaceShell.tsx").write_text(
        'import "./qtrace-workspace.css";\nclassName="qtrace-shell-content"\n<QTraceWorkspaceShell>',
        encoding="utf-8",
    )
    (frontend / "src" / "components" / "qtrace-workspace.css").write_text(
        ".qtrace-shell .qtrace-shell-sidebar .qtrace-shell-content", encoding="utf-8"
    )
    (frontend / "src" / "components" / "Logo.jsx").write_text(
        'QTrace src="/qtrace-icon.png"', encoding="utf-8"
    )
    (frontend / "src" / "pages" / "Landing.jsx").write_text(
        "QTrace", encoding="utf-8"
    )
    (frontend / "src" / "pages" / "Home.jsx").write_text(
        "QTrace", encoding="utf-8"
    )
    (frontend / "src" / "api" / "interview.ts").write_text(
        '"/api/interview/start"\n`${API_BASE}/interview/${encodeURIComponent(sessionId)}/answer`\n`${API_BASE}/interview/${encodeURIComponent(sessionId)}/finish`\n`${API_BASE}/settings/embedding`',
        encoding="utf-8",
    )
    (frontend / "src" / "api" / "personalAgent.ts").write_text(
        '`${API_BASE}/agent/documents`\n`${API_BASE}/agent/chat`', encoding="utf-8"
    )
    (frontend / "public").mkdir(parents=True, exist_ok=True)
    (frontend / "public" / "qtrace-icon.png").write_bytes(b"synthetic")
    (frontend / "index.html").write_text(
        'href="/qtrace-icon.png"', encoding="utf-8"
    )

    if not complete:
        (frontend / "src" / "api.ts").write_text("legacy", encoding="utf-8")


def test_active_frontend_matches_migration_contract(tmp_path):
    _write_fixture(tmp_path)
    report = inspect_frontend(tmp_path)

    assert report == {
        "missing_source_files": [],
        "missing_routes": [],
        "missing_qtrace_shell_markers": [],
        "missing_qtrace_shell_styles": [],
        "legacy_sidebar_import": False,
        "legacy_active_files": [],
        "missing_brand_markers": [],
        "forbidden_visible_techspar_markers": [],
        "missing_qtrace_adapter_markers": [],
        "missing_icon": False,
        "reference_source_audit": {
            "missing_from_reference": [],
            "qtrace_owned_files": [],
        },
    }


def test_preflight_rejects_legacy_qtrace_ui_in_active_source(tmp_path):
    _write_fixture(tmp_path, complete=False)
    report = inspect_frontend(tmp_path)

    assert report["legacy_active_files"] == ["src/api.ts"]
