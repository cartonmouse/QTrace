"""Check the source contract for a containerized QTrace interview demo.

This is a read-only check. It does not build images, start containers, read
SQLite data, inspect user documents, call an external API, or deploy anything.
It verifies that the public-demo package keeps the API behind a same-origin
proxy, persists application data in a named volume, and requires a deployment
JWT secret without embedding an LLM credential.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MARKERS = {
    "docker-compose.demo.yml": (
        "deploy/Dockerfile.backend",
        "deploy/Dockerfile.web",
        "REBUILD_JWT_SECRET",
        "service_healthy",
        "qtrace_demo_data",
        "REBUILD_BYOK_STORAGE_MODE: ${REBUILD_BYOK_STORAGE_MODE:-session}",
        "REBUILD_BLOCK_PRIVATE_API_BASE: ${REBUILD_BLOCK_PRIVATE_API_BASE:-true}",
    ),
    "deploy/Dockerfile.backend": (
        "python:3.12-slim",
        "backend.main:app",
        "--host",
        "0.0.0.0",
    ),
    "deploy/Dockerfile.web": (
        "node:22-alpine",
        "nginx:1.27-alpine",
        "npm --prefix frontend run build",
    ),
    "deploy/nginx.conf": (
        "location /api/",
        "proxy_pass http://api:8000",
        "try_files $uri $uri/ /index.html",
    ),
    "deploy/demo.env.example": (
        "REBUILD_JWT_SECRET",
        "Never commit",
        "REBUILD_BYOK_STORAGE_MODE=session",
        "REBUILD_BLOCK_PRIVATE_API_BASE=true",
        "QTRACE_DEMO_PORT",
    ),
    "backend/config.py": (
        "BYOK_STORAGE_MODE",
        "'persisted' or 'session'",
        "BLOCK_PRIVATE_API_BASE",
        "REBUILD_BLOCK_PRIVATE_API_BASE",
    ),
    "backend/network_policy.py": (
        "class APIBasePolicyError",
        "block_private",
        "is_global",
        "DNS rebinding",
    ),
    "backend/store.py": (
        "secret_storage_mode",
        "_session_llm_keys",
        'stored_key = "" if self.secret_storage_mode == "session" else clean_key',
    ),
    ".dockerignore": ("**/node_modules", "*.sqlite3", "qtrace_*/"),
}

REQUIRED_FILES = tuple(REQUIRED_MARKERS)
SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:OPENAI|DEEPSEEK|LLM|EMBEDDING)_?(?:API_)?KEY\s*="
)


def inspect_public_demo(root: Path) -> dict[str, Any]:
    """Return missing files, markers, and obvious embedded LLM credentials."""

    root = root.resolve()
    missing_files: list[str] = []
    missing_markers: list[str] = []
    secret_hits: list[str] = []
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
        if relative == "deploy/demo.env.example" and SECRET_ASSIGNMENT.search(text):
            secret_hits.append(f"{relative}:credential assignment")
    return {
        "missing_files": sorted(missing_files),
        "missing_markers": sorted(missing_markers),
        "secret_hits": sorted(secret_hits),
    }


def _print_report(report: dict[str, Any]) -> None:
    if report["missing_files"]:
        print("FAIL public demo files:")
        for item in report["missing_files"]:
            print(f"  - {item}")
    else:
        print("PASS public demo files")

    if report["missing_markers"]:
        print("FAIL public demo deployment contract:")
        for item in report["missing_markers"]:
            print(f"  - {item}")
    else:
        print("PASS public demo deployment contract")

    if report["secret_hits"]:
        print("FAIL public demo example contains credential assignments:")
        for item in report["secret_hits"]:
            print(f"  - {item}")
    else:
        print("PASS no LLM credential assignment in demo example")


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

    report = inspect_public_demo(root)
    _print_report(report)
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
