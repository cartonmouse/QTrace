"""Check the QTrace-owned profile landing surface without running the app."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "frontend/src/pages/Profile.jsx",
    "frontend/src/pages/qtrace-profile.css",
)

REQUIRED_PAGE_MARKERS = (
    'import "./qtrace-profile.css";',
    'className={cn(PAGE_CLASS, "qtrace-profile-page")}',
    'qtrace-profile-heading',
    'qtrace-profile-empty',
    'qtrace-profile-route-card',
    'qtrace-profile-stat-grid',
    "getProfile()",
    'navigate("/topic-drill")',
)

REQUIRED_STYLE_MARKERS = (
    ".qtrace-profile-page",
    ".qtrace-profile-heading",
    ".qtrace-profile-surface",
    ".qtrace-profile-route-card",
    ".qtrace-profile-stat-grid",
    "prefers-reduced-motion",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def inspect_profile(root: Path) -> dict[str, Any]:
    root = root.resolve()
    page_text = _read(root / "frontend/src/pages/Profile.jsx")
    style_text = _read(root / "frontend/src/pages/qtrace-profile.css")
    return {
        "missing_files": [
            relative for relative in REQUIRED_FILES if not (root / relative).is_file()
        ],
        "missing_page_markers": [
            marker for marker in REQUIRED_PAGE_MARKERS if marker not in page_text
        ],
        "missing_style_markers": [
            marker for marker in REQUIRED_STYLE_MARKERS if marker not in style_text
        ],
    }


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
    report = inspect_profile(args.root)
    _print_report(report)
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
