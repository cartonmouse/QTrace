"""Read-only checks for a QTrace repository before a public release.

The checker intentionally does not install dependencies, call external services,
modify the worktree, or inspect real user data. It only reports local artifacts
that should stay outside a public repository and fails on missing core files or
obvious secret material.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


REQUIRED_FILES = (
    "README.md",
    "requirements.txt",
    "requirements-local-embedding.txt",
    "pyproject.toml",
    "backend/main.py",
    "backend/models.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/App.tsx",
    "docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md",
)

SKIP_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
}

TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA|PRIVATE) KEY-----"),
)


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        yield path


def _is_local_artifact(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env":
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    return path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log"}


def _secret_hits(path: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def inspect_repository(root: Path) -> dict[str, list[str]]:
    """Return findings without changing the repository."""

    root = root.resolve()
    missing = [item for item in REQUIRED_FILES if not (root / item).is_file()]
    local_artifacts = [
        path.relative_to(root).as_posix()
        for path in _iter_files(root)
        if _is_local_artifact(path)
    ]
    if (root / "data").is_dir():
        local_artifacts.append("data/")
    secret_hits = []
    for path in _iter_files(root):
        patterns = _secret_hits(path)
        if patterns:
            secret_hits.append(f"{path.relative_to(root).as_posix()}: {', '.join(patterns)}")
    return {
        "missing": sorted(missing),
        "local_artifacts": sorted(local_artifacts),
        "secret_hits": sorted(secret_hits),
    }


def _git_status(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip()


def _print_findings(report: dict[str, list[str]], root: Path) -> None:
    if report["missing"]:
        print("FAIL missing required files:")
        for item in report["missing"]:
            print(f"  - {item}")
    else:
        print("PASS required project files")

    if report["secret_hits"]:
        print("FAIL obvious secret material detected:")
        for item in report["secret_hits"]:
            print(f"  - {item}")
    else:
        print("PASS no obvious secret pattern in tracked-style text files")

    if report["local_artifacts"]:
        print("WARN local-only artifacts found (keep them ignored/uncommitted):")
        for item in report["local_artifacts"]:
            print(f"  - {item}")
    else:
        print("PASS no local-only artifact found")

    status = _git_status(root)
    if status:
        changed_count = len(status.splitlines())
        print(f"INFO worktree has {changed_count} changed/untracked path(s); review before release")
    else:
        print("INFO worktree status is clean or Git is unavailable")


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
        print(f"FAIL repository root does not exist: {root}")
        return 1
    report = inspect_repository(root)
    _print_findings(report, root)
    return 1 if report["missing"] or report["secret_hits"] else 0


if __name__ == "__main__":
    sys.exit(main())
