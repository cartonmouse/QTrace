"""Check the local frontend route, auth-client, and recovery-UI contract without a browser.

This read-only check is a safe substitute when a browser session has an
unknown account state. It inspects only source files for expected route, auth
client, and UI markers; it never opens a page, reads browser storage, starts a
service, or loads user data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_ROUTES = (
    "resume-editor",
    "topic-drill",
    "job-prep",
    "copilot",
    "agent",
    "recording",
    "knowledge",
    "graph",
    "history",
    "profile",
    "settings",
)

REQUIRED_APP_MARKERS = (
    "重新发送",
    "加载保留草稿",
    'role="alert"',
)

REQUIRED_AUTH_MARKERS = ("进入学习工程", "创建本地账户")

REQUIRED_AUTH_CLIENT_MARKERS = (
    'const API_BASE = "/api";',
    'if (token) headers.set("Authorization", `Bearer ${token}`);',
    "export async function authenticate(",
    "return apiFetch<{ access_token: string; user: User }>(`/auth/${mode}`",
)

REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS = (
    'export const AUTH_EXPIRED_EVENT = "qtrace:auth-expired";',
    'if (response.status === 401 && token && typeof window !== "undefined") {',
    "window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));",
)

REQUIRED_AUTH_STATE_MARKERS = (
    'const TOKEN_KEY = "rebuild_access_token";',
    "useState(() => localStorage.getItem(TOKEN_KEY))",
    "localStorage.setItem(TOKEN_KEY, nextToken);",
    "localStorage.removeItem(TOKEN_KEY);",
    "if (!token || !user) return <LoginPage",
)

REQUIRED_AUTH_EXPIRY_STATE_MARKERS = (
    "function clearAuthState()",
    "window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);",
    "window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);",
)

REQUIRED_STYLE_MARKERS = (".agent-error-actions", ".agent-tool")

REQUIRED_REVIEW_FLOW_MARKERS = (
    "TODAY&apos;S REVIEW QUEUE",
    "function buildDueReviewPath(item: DueReview)",
    "if (item.topic) params.set(\"topic\", item.topic);",
    "return `/topic-drill?${params.toString()}`;",
    "立即复习 ↗",
)

REQUIRED_PROFILE_RECOVERY_MARKERS = ("画像加载失败", "重新加载画像")

REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS = ("训练领域加载失败", "重新加载训练领域")

REQUIRED_LOCAL_EMBEDDING_MARKERS = (
    '"local-model"',
    "本地语义模型",
    "embeddingModelPath",
    "model_path: embeddingModelPath",
    "sentence-transformers",
)

REQUIRED_SETTINGS_FEEDBACK_MARKERS = (
    "settings-page",
    "const [llmMessage",
    "const [embeddingMessage",
    "settings-feedback--error",
    "settings-feedback--success",
    "formatApiErrorDetail",
    "loadKey",
    "重新读取模型设置",
    "settings-load-card",
)

REQUIRED_TELEMETRY_MARKERS = (
    "telemetry-shell",
    "workspace-command-bar",
    "sidebar-signal",
    "dashboard-display-title",
    "status-dot active",
    "--q-yellow",
    "body::before",
)

REQUIRED_THEME_MARKERS = (
    'const THEME_KEY = "qtrace_theme";',
    'type Theme = "dark" | "minimalist";',
    "document.documentElement.dataset.theme = theme;",
    'data-theme-option="minimalist"',
    "theme-toggle",
    ':root[data-theme="minimalist"]',
    "--q-editorial",
)

REQUIRED_PRODUCT_UX_MARKERS = (
  "qtrace-workspace-shell",
  "sidebar-collapse-button",
  "workspace-mobile-bar",
  "training-mode-grid",
    "data-dashboard-mode",
    "dashboard-action-panel",
    "dashboard-skeleton-line",
  "qtrace-skeleton",
)

REQUIRED_PRODUCT_WORKSPACE_MARKERS = (
    "product-workspace-shell",
    "data-product-shell=\"true\"",
    'src=\"/qtrace-icon.png\"',
    "<PageHeader",
    "<StatePanel",
    "<StatusBadge",
)

REQUIRED_PRODUCT_STYLE_MARKERS = (
    ".product-page-header",
    ".product-surface",
    ".training-mode-card",
    ".product-agent-layout",
)

REQUIRED_PERSONAL_DOCUMENT_IMPORT_MARKERS = (
    "导入 PDF",
    "导入 Markdown",
    'accept=".md,.markdown,text/markdown"',
    "importDocumentFile(file, \"Markdown\")",
)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def inspect_frontend(root: Path) -> dict[str, Any]:
    """Return route and recovery UI findings without executing frontend code."""

    root = root.resolve()
    app_path = root / "frontend" / "src" / "App.tsx"
    api_path = root / "frontend" / "src" / "api.ts"
    styles_path = root / "frontend" / "src" / "styles.css"
    product_styles_path = root / "frontend" / "src" / "product.css"
    product_ui_path = root / "frontend" / "src" / "components" / "ProductUI.tsx"
    missing_files = [
        relative
        for relative, path in (
            ("frontend/src/App.tsx", app_path),
            ("frontend/src/api.ts", api_path),
            ("frontend/src/styles.css", styles_path),
            ("frontend/src/product.css", product_styles_path),
            ("frontend/src/components/ProductUI.tsx", product_ui_path),
        )
        if not path.is_file()
    ]
    app_text = _read_text(app_path) or ""
    api_text = _read_text(api_path) or ""
    styles_text = _read_text(styles_path) or ""
    product_styles_text = _read_text(product_styles_path) or ""
    product_ui_text = _read_text(product_ui_path) or ""
    return {
        "missing_files": missing_files,
        "missing_routes": [route for route in REQUIRED_ROUTES if f'path="{route}"' not in app_text],
        "missing_app_markers": [marker for marker in REQUIRED_APP_MARKERS if marker not in app_text],
        "missing_auth_markers": [marker for marker in REQUIRED_AUTH_MARKERS if marker not in app_text],
        "missing_auth_client_markers": [marker for marker in REQUIRED_AUTH_CLIENT_MARKERS if marker not in api_text],
        "missing_auth_expiry_client_markers": [marker for marker in REQUIRED_AUTH_EXPIRY_CLIENT_MARKERS if marker not in api_text],
        "missing_auth_state_markers": [marker for marker in REQUIRED_AUTH_STATE_MARKERS if marker not in app_text],
        "missing_auth_expiry_state_markers": [marker for marker in REQUIRED_AUTH_EXPIRY_STATE_MARKERS if marker not in app_text],
        "missing_review_flow_markers": [marker for marker in REQUIRED_REVIEW_FLOW_MARKERS if marker not in app_text],
        "missing_profile_recovery_markers": [marker for marker in REQUIRED_PROFILE_RECOVERY_MARKERS if marker not in app_text],
        "missing_topic_drill_recovery_markers": [marker for marker in REQUIRED_TOPIC_DRILL_RECOVERY_MARKERS if marker not in app_text],
        "missing_local_embedding_markers": [
            marker
            for marker in REQUIRED_LOCAL_EMBEDDING_MARKERS
            if marker not in (app_text + api_text + styles_text)
        ],
        "missing_settings_feedback_markers": [
            marker
            for marker in REQUIRED_SETTINGS_FEEDBACK_MARKERS
            if marker not in (app_text + api_text + styles_text)
        ],
        "missing_telemetry_markers": [
            marker
            for marker in REQUIRED_TELEMETRY_MARKERS
            if marker not in (app_text + styles_text)
        ],
        "missing_theme_markers": [
            marker
            for marker in REQUIRED_THEME_MARKERS
            if marker not in (app_text + styles_text)
        ],
        "missing_product_ux_markers": [
            marker
            for marker in REQUIRED_PRODUCT_UX_MARKERS
            if marker not in (app_text + styles_text)
        ],
        "missing_product_workspace_markers": [
            marker
            for marker in REQUIRED_PRODUCT_WORKSPACE_MARKERS
            if marker not in (app_text + product_ui_text)
        ],
        "missing_product_style_markers": [
            marker
            for marker in REQUIRED_PRODUCT_STYLE_MARKERS
            if marker not in product_styles_text
        ],
        "missing_personal_document_import_markers": [
            marker
            for marker in REQUIRED_PERSONAL_DOCUMENT_IMPORT_MARKERS
            if marker not in app_text
        ],
        "missing_style_markers": [marker for marker in REQUIRED_STYLE_MARKERS if marker not in styles_text],
    }


def _print_report(report: dict[str, Any]) -> None:
    if report["missing_files"]:
        print("FAIL frontend source files:")
        for item in report["missing_files"]:
            print(f"  - {item}")
    else:
        print("PASS frontend source files")

    findings = (
        ("routes", report["missing_routes"]),
        ("recovery UI markers", report["missing_app_markers"]),
        ("auth entry markers", report["missing_auth_markers"]),
        ("auth client markers", report["missing_auth_client_markers"]),
        ("auth expiry client markers", report["missing_auth_expiry_client_markers"]),
        ("auth state markers", report["missing_auth_state_markers"]),
        ("auth expiry state markers", report["missing_auth_expiry_state_markers"]),
        ("review flow markers", report["missing_review_flow_markers"]),
        ("profile recovery markers", report["missing_profile_recovery_markers"]),
        ("topic drill recovery markers", report["missing_topic_drill_recovery_markers"]),
        ("local embedding markers", report["missing_local_embedding_markers"]),
        ("settings feedback markers", report["missing_settings_feedback_markers"]),
        ("telemetry redesign markers", report["missing_telemetry_markers"]),
        ("theme selection markers", report["missing_theme_markers"]),
        ("product UX markers", report["missing_product_ux_markers"]),
        ("product workspace markers", report["missing_product_workspace_markers"]),
        ("product style markers", report["missing_product_style_markers"]),
        ("personal document import markers", report["missing_personal_document_import_markers"]),
        ("recovery UI styles", report["missing_style_markers"]),
    )
    for label, missing in findings:
        if missing:
            print(f"FAIL frontend {label}:")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"PASS frontend {label}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="QTrace repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print("FAIL repository root does not exist")
        return 1

    report = inspect_frontend(root)
    _print_report(report)
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
