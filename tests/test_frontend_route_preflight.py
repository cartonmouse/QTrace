from scripts.frontend_route_preflight import (
    REQUIRED_APP_MARKERS,
    REQUIRED_AUTH_MARKERS,
    REQUIRED_AUTH_CLIENT_MARKERS,
    REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS,
    REQUIRED_AUTH_EXPIRY_STATE_MARKERS,
    REQUIRED_AUTH_STATE_MARKERS,
    REQUIRED_LOCAL_EMBEDDING_MARKERS,
    REQUIRED_PROFILE_RECOVERY_MARKERS,
    REQUIRED_PRODUCT_UX_MARKERS,
    REQUIRED_PRODUCT_STYLE_MARKERS,
    REQUIRED_PRODUCT_WORKSPACE_MARKERS,
    REQUIRED_PERSONAL_DOCUMENT_IMPORT_MARKERS,
    REQUIRED_REVIEW_FLOW_MARKERS,
    REQUIRED_ROUTES,
    REQUIRED_SETTINGS_FEEDBACK_MARKERS,
    REQUIRED_STYLE_MARKERS,
    REQUIRED_THEME_MARKERS,
    REQUIRED_TELEMETRY_MARKERS,
    REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS,
    inspect_frontend,
)


def _write_frontend_fixture(root):
    app_path = root / "frontend" / "src" / "App.tsx"
    api_path = root / "frontend" / "src" / "api.ts"
    styles_path = root / "frontend" / "src" / "styles.css"
    product_styles_path = root / "frontend" / "src" / "product.css"
    product_ui_path = root / "frontend" / "src" / "components" / "ProductUI.tsx"
    app_path.parent.mkdir(parents=True, exist_ok=True)
    styles_path.parent.mkdir(parents=True, exist_ok=True)
    product_styles_path.parent.mkdir(parents=True, exist_ok=True)
    product_ui_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.write_text(
        "\n".join(
            [
                *(f'<Route path="{route}" />' for route in REQUIRED_ROUTES),
                *REQUIRED_APP_MARKERS,
                *REQUIRED_AUTH_MARKERS,
                *REQUIRED_AUTH_STATE_MARKERS,
                *REQUIRED_AUTH_EXPIRY_STATE_MARKERS,
                *REQUIRED_REVIEW_FLOW_MARKERS,
                *REQUIRED_PROFILE_RECOVERY_MARKERS,
                *REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS,
                *REQUIRED_LOCAL_EMBEDDING_MARKERS,
                *REQUIRED_SETTINGS_FEEDBACK_MARKERS,
                *REQUIRED_TELEMETRY_MARKERS,
                *REQUIRED_THEME_MARKERS,
                *REQUIRED_PRODUCT_UX_MARKERS,
                *REQUIRED_PERSONAL_DOCUMENT_IMPORT_MARKERS,
            ]
        ),
        encoding="utf-8",
    )
    api_path.write_text(
        "\n".join((*REQUIRED_AUTH_CLIENT_MARKERS, *REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS)),
        encoding="utf-8",
    )
    styles_path.write_text("\n".join(REQUIRED_STYLE_MARKERS), encoding="utf-8")
    product_styles_path.write_text("\n".join(REQUIRED_PRODUCT_STYLE_MARKERS), encoding="utf-8")
    product_ui_path.write_text("\n".join(REQUIRED_PRODUCT_WORKSPACE_MARKERS), encoding="utf-8")


def test_frontend_route_preflight_accepts_complete_synthetic_fixture(tmp_path):
    _write_frontend_fixture(tmp_path)

    report = inspect_frontend(tmp_path)

    assert report == {
        "missing_files": [],
        "missing_routes": [],
        "missing_app_markers": [],
        "missing_auth_markers": [],
        "missing_auth_client_markers": [],
        "missing_auth_expiry_client_markers": [],
        "missing_auth_state_markers": [],
        "missing_auth_expiry_state_markers": [],
        "missing_review_flow_markers": [],
        "missing_profile_recovery_markers": [],
        "missing_topic_drill_recovery_markers": [],
        "missing_local_embedding_markers": [],
        "missing_settings_feedback_markers": [],
        "missing_telemetry_markers": [],
        "missing_theme_markers": [],
        "missing_product_ux_markers": [],
        "missing_product_workspace_markers": [],
        "missing_product_style_markers": [],
        "missing_personal_document_import_markers": [],
        "missing_style_markers": [],
    }


def test_frontend_route_preflight_reports_missing_recovery_contract(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    styles_path = tmp_path / "frontend" / "src" / "styles.css"
    app_path.write_text('<Route path="agent" />\nrole="alert"', encoding="utf-8")
    styles_path.write_text(".agent-tool", encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert "resume-editor" in report["missing_routes"]
    assert "重新发送" in report["missing_app_markers"]
    assert ".agent-error-actions" in report["missing_style_markers"]


def test_frontend_route_preflight_reports_missing_auth_entry(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text('\n'.join(f'<Route path="{route}" />' for route in REQUIRED_ROUTES), encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_auth_markers"] == list(REQUIRED_AUTH_MARKERS)


def test_frontend_route_preflight_reports_missing_auth_client_boundary(tmp_path):
    _write_frontend_fixture(tmp_path)
    api_path = tmp_path / "frontend" / "src" / "api.ts"
    api_path.write_text(REQUIRED_AUTH_CLIENT_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_auth_client_markers"] == list(REQUIRED_AUTH_CLIENT_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_auth_state_lifecycle(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_AUTH_STATE_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_auth_state_markers"] == list(REQUIRED_AUTH_STATE_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_auth_expiry_recovery(tmp_path):
    _write_frontend_fixture(tmp_path)
    api_path = tmp_path / "frontend" / "src" / "api.ts"
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    api_path.write_text(REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS[0], encoding="utf-8")
    app_path.write_text(REQUIRED_AUTH_EXPIRY_STATE_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_auth_expiry_client_markers"] == list(REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS[1:])
    assert report["missing_auth_expiry_state_markers"] == list(REQUIRED_AUTH_EXPIRY_STATE_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_review_flow(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_REVIEW_FLOW_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_review_flow_markers"] == list(REQUIRED_REVIEW_FLOW_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_profile_recovery(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_PROFILE_RECOVERY_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_profile_recovery_markers"] == list(REQUIRED_PROFILE_RECOVERY_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_topic_drill_recovery(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_topic_drill_recovery_markers"] == list(REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_local_embedding_contract(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_LOCAL_EMBEDDING_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_local_embedding_markers"] == list(REQUIRED_LOCAL_EMBEDDING_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_settings_feedback_contract(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_SETTINGS_FEEDBACK_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_settings_feedback_markers"] == list(REQUIRED_SETTINGS_FEEDBACK_MARKERS[1:])


def test_frontend_route_preflight_covers_settings_load_recovery(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    app_path.write_text(REQUIRED_SETTINGS_FEEDBACK_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert "loadKey" in report["missing_settings_feedback_markers"]
    assert "重新读取模型设置" in report["missing_settings_feedback_markers"]


def test_frontend_route_preflight_reports_missing_telemetry_redesign(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    styles_path = tmp_path / "frontend" / "src" / "styles.css"
    app_path.write_text(REQUIRED_TELEMETRY_MARKERS[0], encoding="utf-8")
    styles_path.write_text(REQUIRED_STYLE_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_telemetry_markers"] == list(REQUIRED_TELEMETRY_MARKERS[1:])


def test_frontend_route_preflight_reports_missing_theme_selection(tmp_path):
    _write_frontend_fixture(tmp_path)
    app_path = tmp_path / "frontend" / "src" / "App.tsx"
    styles_path = tmp_path / "frontend" / "src" / "styles.css"
    app_path.write_text(REQUIRED_THEME_MARKERS[0], encoding="utf-8")
    styles_path.write_text(REQUIRED_STYLE_MARKERS[0], encoding="utf-8")

    report = inspect_frontend(tmp_path)

    assert report["missing_theme_markers"] == list(REQUIRED_THEME_MARKERS[1:])
