"""Read-only contract for QTrace's TechSpar-informed frontend boundary.

TechSpar is a product and interaction reference, not QTrace's active source
tree. The check keeps the migrated routes, QTrace API adapters, brand
markers, and the current QTrace-owned app shell observable while allowing
QTrace-specific source files to diverge from the reference repository. It
does not run a browser, call an API, or read user data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_FILES = (
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
)

REQUIRED_QTRACE_SHELL_MARKERS = (
    'import QTraceWorkspaceShell from "./components/QTraceWorkspaceShell";',
    "<QTraceWorkspaceShell>",
    'import "./qtrace-workspace.css";',
    'className="qtrace-shell-content"',
)

REQUIRED_ROUTES = (
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
)

LEGACY_ACTIVE_FILES = (
    "src/api.ts",
    "src/styles.css",
    "src/product.css",
    "src/components/ProductUI.tsx",
)

REQUIRED_BRAND_MARKERS = (
    "问迹",
    "QTrace",
    'src="/qtrace-icon.png"',
    'href="/qtrace-icon.png"',
)

FORBIDDEN_VISIBLE_TECHSPAR_MARKERS = (
    ">TechSpar<",
    "aria-label=\"Star TechSpar",
    "github.com/AnnaSuSu/TechSpar",
    "为什么 TechSpar",
)

REQUIRED_QTRACE_ADAPTER_MARKERS = (
    '"/api/interview/start"',
    '`${API_BASE}/interview/${encodeURIComponent(sessionId)}/answer`',
    '`${API_BASE}/interview/${encodeURIComponent(sessionId)}/finish`',
    '`${API_BASE}/agent/documents`',
    '`${API_BASE}/agent/chat`',
    '`${API_BASE}/settings/embedding`',
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _relative_files(root: Path) -> set[str]:
    source = root / "frontend" / "src"
    if not source.is_dir():
        return set()
    return {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
    }


def inspect_frontend(root: Path, reference: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    frontend = root / "frontend"
    app_text = _read(frontend / "src" / "App.tsx")
    index_text = _read(frontend / "index.html")
    sidebar_text = _read(frontend / "src" / "components" / "Sidebar.tsx")
    shell_text = _read(frontend / "src" / "components" / "QTraceWorkspaceShell.tsx")
    shell_style_text = _read(
        frontend / "src" / "components" / "qtrace-workspace.css"
    )
    logo_text = _read(frontend / "src" / "components" / "Logo.jsx")
    landing_text = _read(frontend / "src" / "pages" / "Landing.jsx")
    home_text = _read(frontend / "src" / "pages" / "Home.jsx")
    adapter_text = "\n".join(
        (
            _read(frontend / "src" / "api" / "interview.ts"),
            _read(frontend / "src" / "api" / "personalAgent.ts"),
        )
    )
    visible_brand_text = "\n".join(
        (sidebar_text, shell_text, logo_text, landing_text, home_text, index_text)
    )
    report: dict[str, Any] = {
        "missing_source_files": [
            relative
            for relative in REQUIRED_SOURCE_FILES
            if not (frontend / relative).is_file()
        ],
        "missing_routes": [marker for marker in REQUIRED_ROUTES if marker not in app_text],
        "missing_qtrace_shell_markers": [
            marker
            for marker in REQUIRED_QTRACE_SHELL_MARKERS
            if marker not in (app_text + "\n" + shell_text)
        ],
        "missing_qtrace_shell_styles": [
            marker
            for marker in (".qtrace-shell", ".qtrace-shell-sidebar", ".qtrace-shell-content")
            if marker not in shell_style_text
        ],
        "legacy_sidebar_import": (
            'import Sidebar from "./components/Sidebar";' in app_text
        ),
        "legacy_active_files": [
            relative
            for relative in LEGACY_ACTIVE_FILES
            if (frontend / relative).exists()
        ],
        "missing_brand_markers": [
            marker
            for marker in REQUIRED_BRAND_MARKERS
            if marker not in visible_brand_text
        ],
        "forbidden_visible_techspar_markers": [
            marker
            for marker in FORBIDDEN_VISIBLE_TECHSPAR_MARKERS
            if marker in visible_brand_text
        ],
        "missing_qtrace_adapter_markers": [
            marker
            for marker in REQUIRED_QTRACE_ADAPTER_MARKERS
            if marker not in adapter_text
        ],
        "missing_icon": not (frontend / "public" / "qtrace-icon.png").is_file(),
    }

    if reference is not None:
        reference_files = _relative_files(reference.resolve())
        active_files = _relative_files(root)
        report["reference_source_audit"] = {
            "missing_from_reference": sorted(reference_files - active_files),
            "qtrace_owned_files": sorted(active_files - reference_files),
        }
    else:
        report["reference_source_audit"] = {
            "missing_from_reference": [],
            "qtrace_owned_files": [],
        }

    return report


def _print_report(report: dict[str, Any]) -> None:
    for key, value in report.items():
        if key == "reference_source_audit":
            print(f"INFO {key}: {value}")
        elif value:
            print(f"FAIL {key}: {value}")
        else:
            print(f"PASS {key}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="QTrace repository root",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="Optional TechSpar repository root used for source-set parity",
    )
    args = parser.parse_args(argv)
    report = inspect_frontend(args.root, args.reference)
    _print_report(report)
    blocking_keys = [key for key in report if key != "reference_source_audit"]
    return 1 if any(report[key] for key in blocking_keys) else 0


if __name__ == "__main__":
    sys.exit(main())
