"""Check that QTrace's own app shell is the active workspace boundary.

This is a read-only static check. It does not run a browser, call an API, or
read user data. TechSpar remains a reference for proven interaction patterns;
the active shell must be owned by QTrace so the product can evolve without
shipping the reference app shell unchanged.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "frontend/src/App.tsx",
    "frontend/src/components/QTraceWorkspaceShell.tsx",
    "frontend/src/components/qtrace-workspace.css",
)

REQUIRED_APP_MARKERS = (
    'import QTraceWorkspaceShell from "./components/QTraceWorkspaceShell";',
    "<QTraceWorkspaceShell>",
)

REQUIRED_SHELL_MARKERS = (
    'import "./qtrace-workspace.css";',
    "className={`qtrace-shell",
    'className="qtrace-shell-content"',
    'aria-label="QTrace 主导航"',
    "PERSONAL INTERVIEW OS",
)

REQUIRED_STYLE_MARKERS = (
    ".qtrace-shell",
    ".qtrace-shell-sidebar",
    ".qtrace-shell-content",
    "@media",
)

FORBIDDEN_ACTIVE_IMPORTS = (
    'import Sidebar from "./components/Sidebar";',
    'import Landing from "./pages/Landing";',
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def inspect_shell(root: Path) -> dict[str, Any]:
    root = root.resolve()
    app_text = _read(root / "frontend/src/App.tsx")
    shell_text = _read(root / "frontend/src/components/QTraceWorkspaceShell.tsx")
    style_text = _read(root / "frontend/src/components/qtrace-workspace.css")
    report: dict[str, Any] = {
        "missing_files": [
            relative for relative in REQUIRED_FILES if not (root / relative).is_file()
        ],
        "missing_app_markers": [
            marker for marker in REQUIRED_APP_MARKERS if marker not in app_text
        ],
        "missing_shell_markers": [
            marker for marker in REQUIRED_SHELL_MARKERS if marker not in shell_text
        ],
        "missing_style_markers": [
            marker for marker in REQUIRED_STYLE_MARKERS if marker not in style_text
        ],
        "forbidden_active_imports": [
            marker
            for marker in FORBIDDEN_ACTIVE_IMPORTS
            if marker in app_text
        ],
    }
    return report


def _print_report(report: dict[str, Any]) -> None:
    for key, value in report.items():
        if value:
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
    args = parser.parse_args(argv)
    report = inspect_shell(args.root)
    _print_report(report)
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
