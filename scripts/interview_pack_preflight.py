"""Validate that the AI-Agent interview defense pack has its core sections.

The checker reads one Markdown file with explicit UTF-8 and verifies headings
and evidence references. It does not read user documents, call an LLM, or
infer whether a claim is true beyond the required section contract.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "## 1. 90 秒项目介绍",
    "## 2. 架构与数据边界",
    "## 3. Agent 与工具调用",
    "## 4. 记忆、RAG、图谱与 SM-2",
    "## 5. 稳定性、安全与一致性",
    "## 6. 评估与工程取舍",
    "## 7. 高频追问速答",
    "## 8. 不足与诚实边界",
    "## 9. 彩排时的证据顺序",
)


def inspect_interview_pack(root: Path) -> dict[str, Any]:
    """Return interview-pack findings without reading any personal data."""

    root = root.resolve()
    relative_path = "docs/STAGE55_INTERVIEW_DEFENSE_PACK.md"
    path = root / relative_path
    if not path.is_file():
        return {"missing_file": relative_path, "missing_sections": []}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {"missing_file": relative_path, "missing_sections": list(REQUIRED_SECTIONS)}
    return {
        "missing_file": "",
        "missing_sections": [section for section in REQUIRED_SECTIONS if section not in text],
    }


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
    report = inspect_interview_pack(args.root)
    if report["missing_file"]:
        print(f"FAIL interview defense pack missing: {report['missing_file']}")
        return 1
    if report["missing_sections"]:
        print("FAIL interview defense pack sections:")
        for section in report["missing_sections"]:
            print(f"  - {section}")
        return 1
    print("PASS interview defense pack sections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
