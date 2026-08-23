"""Validate the resume-facing project entry and its engineering evidence.

This is a read-only documentation check. It reads only the repository's
synthetic project-entry document and verifies that every major claim points to
an existing stage document. It never opens a resume, personal document,
database, browser storage, or external service.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ENTRY_PATH = "docs/STAGE56_RESUME_PROJECT_ENTRY.md"

REQUIRED_SECTIONS = (
    "## 项目定位",
    "## 简历项目描述（技术版）",
    "## 简历项目描述（精简版）",
    "## 工程证据对照",
    "## 面试口述版本",
    "## 不应夸大的表述",
)

CLAIM_EVIDENCE = {
    "Agent工具链": (
        "docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md",
        "docs/STAGE47_AGENT_FAILURE_CONSISTENCY.md",
        "docs/STAGE48_AGENT_TOOL_DEGRADATION.md",
    ),
    "RAG与个人文档": (
        "docs/STAGE22_PERSONAL_DOCUMENT_MEMORY.md",
        "docs/STAGE24_PERSONAL_DOCUMENT_CITATION.md",
        "docs/STAGE42_EXTERNAL_EMBEDDING_ADAPTER.md",
    ),
    "知识图谱与SM-2": (
        "docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md",
        "docs/STAGE38_GRAPH_FEEDBACK_EVALUATION.md",
    ),
    "验证证据": (
        "docs/STAGE54_FINAL_DELIVERY_PREFLIGHT.md",
        "docs/STAGE55_INTERVIEW_DEFENSE_PACK.md",
    ),
}


def inspect_resume_entry(root: Path) -> dict[str, Any]:
    """Return project-entry findings without reading personal documents."""

    root = root.resolve()
    path = root / ENTRY_PATH
    if not path.is_file():
        return {
            "missing_file": ENTRY_PATH,
            "missing_sections": [],
            "missing_evidence": {claim: list(paths) for claim, paths in CLAIM_EVIDENCE.items()},
        }
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {
            "missing_file": "",
            "missing_sections": list(REQUIRED_SECTIONS),
            "missing_evidence": {claim: list(paths) for claim, paths in CLAIM_EVIDENCE.items()},
        }

    missing_evidence = {
        claim: [relative for relative in paths if not (root / relative).is_file()]
        for claim, paths in CLAIM_EVIDENCE.items()
    }
    return {
        "missing_file": "",
        "missing_sections": [section for section in REQUIRED_SECTIONS if section not in text],
        "missing_evidence": {claim: paths for claim, paths in missing_evidence.items() if paths},
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
    report = inspect_resume_entry(args.root)
    if report["missing_file"]:
        print(f"FAIL resume project entry missing: {report['missing_file']}")
        return 1
    if report["missing_sections"]:
        print("FAIL resume project entry sections:")
        for section in report["missing_sections"]:
            print(f"  - {section}")
        return 1
    if report["missing_evidence"]:
        print("FAIL resume project entry evidence:")
        for claim, paths in report["missing_evidence"].items():
            print(f"  - {claim}: {', '.join(paths)}")
        return 1
    print("PASS resume project entry and evidence references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
