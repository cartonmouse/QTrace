"""Check whether a QTrace checkout is ready for a future clean reproduction.

This is a read-only preparation check. It does not install dependencies, start
servers, inspect the database, read personal documents, call external APIs, or
change the worktree. It reports missing project files, frontend script drift,
and missing ignore rules before a clean-environment run is attempted.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    ".gitignore",
    "backend/main.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/App.tsx",
    "scripts/repository_preflight.py",
    "scripts/local_runtime_smoke.py",
)

REQUIRED_FRONTEND_SCRIPTS = ("dev", "typecheck", "build")
REQUIRED_IGNORE_RULES = (
    ".env",
    "data/",
    "frontend/node_modules/",
    "frontend/dist/",
    "qtrace_stage*_pytest_tmp/",
    "qtrace_stage*_formal_pytest_tmp/",
)


def inspect_reproduction(root: Path) -> dict[str, Any]:
    """Return preparation findings without changing or inspecting user data."""

    root = root.resolve()
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    config_errors: list[str] = []

    package_path = root / "frontend" / "package.json"
    if package_path.is_file():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            config_errors.append("frontend/package.json is not valid UTF-8 JSON")
        else:
            scripts = package.get("scripts") if isinstance(package, dict) else None
            if not isinstance(scripts, dict):
                config_errors.append("frontend/package.json has no scripts object")
            else:
                for script_name in REQUIRED_FRONTEND_SCRIPTS:
                    if not scripts.get(script_name):
                        config_errors.append(f"frontend/package.json is missing script: {script_name}")

    gitignore_path = root / ".gitignore"
    if gitignore_path.is_file():
        try:
            ignore_text = gitignore_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            config_errors.append(".gitignore is not readable as UTF-8")
        else:
            ignore_rules = {line.strip() for line in ignore_text.splitlines() if line.strip()}
            for rule in REQUIRED_IGNORE_RULES:
                if rule not in ignore_rules:
                    config_errors.append(f".gitignore is missing rule: {rule}")

    tooling = {name: bool(shutil.which(name)) for name in ("python", "node", "npm")}
    return {"missing": sorted(missing), "config_errors": sorted(config_errors), "tooling": tooling}


def _print_report(report: dict[str, Any]) -> None:
    if report["missing"]:
        print("FAIL required reproduction files:")
        for item in report["missing"]:
            print(f"  - {item}")
    else:
        print("PASS required reproduction files")

    if report["config_errors"]:
        print("FAIL reproduction configuration:")
        for item in report["config_errors"]:
            print(f"  - {item}")
    else:
        print("PASS frontend scripts and local-data ignore rules")

    for name, available in report["tooling"].items():
        print(f"INFO {name} available={available}")


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

    report = inspect_reproduction(root)
    _print_report(report)
    return 1 if report["missing"] or report["config_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
