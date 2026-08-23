"""Check the non-persistent BYOK LLM probe contract without running the app."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "backend/main.py",
    "backend/models.py",
    "backend/provider.py",
    "backend/network_policy.py",
    "frontend/src/api/interview.ts",
)

REQUIRED_MARKERS = {
    "backend/main.py": (
        '@app.post("/api/settings/test-llm")',
        "LLMConnectionRequest",
        ".probe()",
        '"ok": False',
    ),
    "backend/models.py": (
        "class LLMConnectionRequest",
        "api_base: str",
        "api_key: str",
    ),
    "backend/provider.py": (
        "def probe(self)",
        '"max_tokens"',
        "max(1, min(int(max_tokens), 16))",
    ),
    "backend/network_policy.py": (
        "class APIBasePolicyError",
        "validate_api_base",
        "is_global",
    ),
    "frontend/src/api/interview.ts": (
        "`${API_BASE}/settings/test-llm`",
        'method: "POST"',
        "await readJson<AnyRecord>(res)",
    ),
}

FORBIDDEN_FRONTEND_MARKERS = (
    "当前 QTrace 尚未提供独立 LLM 连接测试接口",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def inspect_byok(root: Path) -> dict[str, Any]:
    root = root.resolve()
    texts = {relative: _read(root / relative) for relative in REQUIRED_FILES}
    missing_files = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    missing_markers = {
        relative: [marker for marker in markers if marker not in texts[relative]]
        for relative, markers in REQUIRED_MARKERS.items()
    }
    missing_markers = {relative: markers for relative, markers in missing_markers.items() if markers}
    forbidden = [marker for marker in FORBIDDEN_FRONTEND_MARKERS if marker in texts["frontend/src/api/interview.ts"]]
    return {
        "missing_files": missing_files,
        "missing_markers": missing_markers,
        "forbidden_frontend_markers": forbidden,
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
    report = inspect_byok(args.root)
    _print_report(report)
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
