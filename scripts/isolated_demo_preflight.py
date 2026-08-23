"""Check the isolated synthetic-browser demo configuration contract.

This is a read-only source check. It does not create a database, start a
server, open a browser, inspect browser state, read user data, or call an
external API. The check makes it harder to accidentally point a demo frontend
at the normal local backend/database when a separate synthetic database is
intended.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MARKERS = {
    "backend/config.py": ("REBUILD_DATA_DIR", "REBUILD_DB_PATH"),
    "frontend/vite.config.ts": (
        "REBUILD_API_TARGET",
        "http://127.0.0.1:8002",
        "port: 5174",
    ),
    "scripts/seed_synthetic_browser_demo.py": (
        "--db",
        "SQLite",
        "use_stub_provider",
    ),
}


def inspect_isolated_demo(root: Path) -> dict[str, Any]:
    """Return missing source files and markers without changing the checkout."""

    root = root.resolve()
    missing_files: list[str] = []
    missing_markers: list[str] = []
    for relative, markers in REQUIRED_MARKERS.items():
        path = root / relative
        if not path.is_file():
            missing_files.append(relative)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            missing_markers.append(f"{relative}:<unreadable>")
            continue
        missing_markers.extend(
            f"{relative}:{marker}" for marker in markers if marker not in text
        )
    return {
        "missing_files": sorted(missing_files),
        "missing_markers": sorted(missing_markers),
    }


def _print_report(report: dict[str, Any]) -> None:
    if report["missing_files"]:
        print("FAIL isolated demo source files:")
        for item in report["missing_files"]:
            print(f"  - {item}")
    else:
        print("PASS isolated demo source files")

    if report["missing_markers"]:
        print("FAIL isolated demo environment contract:")
        for item in report["missing_markers"]:
            print(f"  - {item}")
    else:
        print("PASS isolated demo environment contract")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=PROJECT_ROOT,
        type=Path,
        help="QTrace repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print("FAIL repository root does not exist")
        return 1

    report = inspect_isolated_demo(root)
    _print_report(report)
    return 1 if report["missing_files"] or report["missing_markers"] else 0


if __name__ == "__main__":
    sys.exit(main())
