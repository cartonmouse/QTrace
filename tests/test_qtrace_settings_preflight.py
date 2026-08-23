from scripts.qtrace_settings_preflight import inspect_settings


def _write_fixture(root):
    page = root / "frontend/src/pages/Settings.jsx"
    style = root / "frontend/src/pages/qtrace-settings.css"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "\n".join(
            (
                'import "./qtrace-settings.css";',
                "qtrace-settings-page",
                "qtrace-settings-status-board",
                "qtrace-settings-global-error",
                'data-qtrace-state="testing"',
                'role="alert"',
                "redactSettingsError",
                "testLLMConnection",
                "testEmbeddingConnection",
                "updateSettings",
                "rebuildEmbeddingIndex",
                "qtrace-settings-savebar",
            )
        ),
        encoding="utf-8",
    )
    style.write_text(
        "\n".join(
            (
                ".qtrace-settings-page",
                ".qtrace-settings-status-board",
                ".qtrace-settings-global-error",
                ".qtrace-settings-card",
                ".qtrace-settings-savebar",
                "background-image: none",
                "backdrop-filter: none",
                "@media (prefers-reduced-motion: reduce)",
            )
        ),
        encoding="utf-8",
    )


def test_settings_has_observable_model_feedback_contract(tmp_path):
    _write_fixture(tmp_path)

    assert inspect_settings(tmp_path) == {
        "missing_files": [],
        "missing_page_markers": [],
        "missing_style_markers": [],
    }


def test_preflight_detects_removed_status_board(tmp_path):
    _write_fixture(tmp_path)
    (tmp_path / "frontend/src/pages/qtrace-settings.css").write_text(
        ".qtrace-settings-page", encoding="utf-8"
    )

    report = inspect_settings(tmp_path)

    assert ".qtrace-settings-status-board" in report["missing_style_markers"]
