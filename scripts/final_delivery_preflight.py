"""Run a read-only final handoff checklist for the QTrace repository.

This check verifies that the public-facing entrypoints, stage documentation,
validation scripts, and README evidence are present. It does not commit,
push, deploy, install dependencies, read the database, or inspect personal
documents. Local-only artifacts are reported as warnings, not deleted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.repository_preflight import inspect_repository


REQUIRED_FILES = (
    "README.md",
    "requirements.txt",
    "requirements-local-embedding.txt",
    "pyproject.toml",
    "backend/main.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/App.tsx",
    "frontend/src/api/interview.ts",
    "frontend/src/api/personalAgent.ts",
    "frontend/src/components/QTraceWorkspaceShell.tsx",
    "frontend/src/components/qtrace-workspace.css",
    "frontend/src/pages/Settings.jsx",
    "frontend/src/pages/qtrace-settings.css",
    "docs/STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md",
    "frontend/src/components/Sidebar.tsx",
    "frontend/public/qtrace-icon.png",
    "docs/QTRACE_ENGINEERING_NOTE.md",
    "docker-compose.demo.yml",
    "deploy/Dockerfile.backend",
    "deploy/Dockerfile.web",
    "deploy/nginx.conf",
    "deploy/demo.env.example",
    "scripts/repository_preflight.py",
    "scripts/reproduction_preflight.py",
    "scripts/local_runtime_smoke.py",
    "scripts/synthetic_demo_smoke.py",
    "scripts/agent_llm_smoke.py",
    "scripts/embedding_smoke.py",
    "scripts/embedding_eval.py",
    "scripts/frontend_route_preflight.py",
    "scripts/techspar_frontend_preflight.py",
    "scripts/qtrace_shell_preflight.py",
    "scripts/qtrace_interview_preflight.py",
    "scripts/qtrace_profile_preflight.py",
    "scripts/qtrace_settings_preflight.py",
    "scripts/qtrace_byok_preflight.py",
    "scripts/qtrace_entry_preflight.py",
    "scripts/resume_claims_preflight.py",
    "scripts/seed_synthetic_browser_demo.py",
    "scripts/isolated_demo_preflight.py",
    "scripts/public_demo_preflight.py",
)

STAGE_DOCS = (
    "docs/STAGE40_INTERVIEW_QA_GRAPH_AGENT_SM2.md",
    "docs/STAGE41_REPOSITORY_PREFLIGHT.md",
    "docs/STAGE42_EXTERNAL_EMBEDDING_ADAPTER.md",
    "docs/STAGE43_EMBEDDING_CONFIG_REINDEX.md",
    "docs/STAGE44_EMBEDDING_SMOKE_GATE.md",
    "docs/STAGE45_REAL_LLM_AGENT_SMOKE.md",
    "docs/STAGE46_AGENT_ERROR_OBSERVABILITY.md",
    "docs/STAGE47_AGENT_FAILURE_CONSISTENCY.md",
    "docs/STAGE48_AGENT_TOOL_DEGRADATION.md",
    "docs/STAGE49_AGENT_RECOVERY_UI.md",
    "docs/STAGE50_LOCAL_RUNTIME_SMOKE.md",
    "docs/STAGE51_REPRODUCTION_DEMO_RUNBOOK.md",
    "docs/STAGE52_SYNTHETIC_DEMO_REHEARSAL.md",
    "docs/STAGE53_BROWSER_REHEARSAL_PREP.md",
    "docs/STAGE54_FINAL_DELIVERY_PREFLIGHT.md",
    "docs/STAGE55_INTERVIEW_DEFENSE_PACK.md",
    "docs/STAGE56_RESUME_PROJECT_ENTRY.md",
    "docs/STAGE57_SYNTHETIC_BROWSER_DEMO_SEED.md",
    "docs/STAGE58_AGENT_SMOKE_REDACTION.md",
    "docs/STAGE59_REPOSITORY_ARTIFACT_IGNORES.md",
    "docs/STAGE60_ISOLATED_BROWSER_REHEARSAL.md",
    "docs/STAGE61_SYNTHETIC_DEMO_ENDPOINT_OUTPUT.md",
    "docs/STAGE62_ISOLATED_RUNTIME_SMOKE.md",
    "docs/STAGE63_PORT_VALIDATION_BEFORE_SEED.md",
    "docs/STAGE64_SYNTHETIC_BROWSER_ENTRY_CHECK.md",
    "docs/STAGE65_AUTH_CLIENT_BOUNDARY.md",
    "docs/STAGE66_AUTH_STATE_LIFECYCLE.md",
    "docs/STAGE67_AUTH_EXPIRY_RECOVERY.md",
    "docs/STAGE68_REVIEW_QUEUE_ENTRY.md",
    "docs/STAGE69_PROFILE_RECOVERY.md",
    "docs/STAGE70_TOPIC_DRILL_RECOVERY.md",
    "docs/STAGE71_LOCAL_SEMANTIC_EMBEDDING.md",
    "docs/STAGE74_EMBEDDING_RETRIEVAL_EVAL.md",
    "docs/STAGE75_FRONTEND_TELEMETRY_REDESIGN.md",
    "docs/STAGE76_FRONTEND_MINIMALIST_THEME.md",
    "docs/STAGE77_TECHSPAR_INFORMED_PRODUCT_UX.md",
    "docs/STAGE79_LIGHT_PRODUCT_WORKSPACE.md",
    "docs/STAGE80_PERSONAL_DOCUMENT_FILE_IMPORT.md",
    "docs/STAGE81_BRAND_ICON_IN_WORKSPACE.md",
    "docs/STAGE82_TECHSPAR_FRONTEND_MIGRATION.md",
    "docs/STAGE83_VITE_DEV_RENDER_RECOVERY.md",
    "docs/STAGE84_DIRECT_LOGIN_ENTRY.md",
    "docs/STAGE85_QTRACE_WORKSPACE_SHELL.md",
    "docs/STAGE86_QTRACE_INTERVIEW_WORKSPACE.md",
    "docs/STAGE87_QTRACE_PROFILE_WORKSPACE.md",
    "docs/STAGE88_QTRACE_SETTINGS_FEEDBACK.md",
    "docs/STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md",
    "docs/STAGE90_PUBLIC_DEMO_DEPLOYMENT_CONTRACT.md",
    "docs/STAGE91_BYOK_LLM_CONNECTION_PROBE.md",
    "docs/STAGE92_SESSION_BYOK_STORAGE.md",
    "docs/STAGE93_LOCAL_RUNTIME_HANDOFF.md",
    "docs/STAGE94_PUBLIC_API_BASE_POLICY.md",
    "THIRD_PARTY_NOTICES.md",
)

README_EVIDENCE = (
    "python -m pytest -q",
    "python -m compileall -q backend tests",
    "npm run typecheck",
    "npm run build",
    "python scripts\\repository_preflight.py",
    "python scripts\\qtrace_settings_preflight.py",
    "python scripts\\qtrace_byok_preflight.py",
    "python scripts\\resume_claims_preflight.py",
    "docs\\STAGE89_LOCAL_ACCEPTANCE_CHECKLIST.md",
)


def inspect_delivery(root: Path) -> dict[str, Any]:
    """Return handoff findings without changing the repository."""

    root = root.resolve()
    missing_files = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    missing_stage_docs = [relative for relative in STAGE_DOCS if not (root / relative).is_file()]
    readme_text = ""
    readme_path = root / "README.md"
    if readme_path.is_file():
        try:
            readme_text = readme_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            readme_text = ""
    missing_readme_evidence = [marker for marker in README_EVIDENCE if marker not in readme_text]
    repository_report = inspect_repository(root)
    return {
        "missing_files": sorted(missing_files),
        "missing_stage_docs": sorted(missing_stage_docs),
        "missing_readme_evidence": sorted(missing_readme_evidence),
        "secret_hit_count": len(repository_report["secret_hits"]),
        "local_artifact_count": len(repository_report["local_artifacts"]),
    }


def _print_report(report: dict[str, Any]) -> None:
    checks = (
        ("core handoff files", report["missing_files"]),
        ("stage documentation", report["missing_stage_docs"]),
        ("README validation evidence", report["missing_readme_evidence"]),
    )
    for label, missing in checks:
        if missing:
            print(f"FAIL {label}:")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"PASS {label}")

    if report["secret_hit_count"]:
        print(f"FAIL obvious secret patterns={report['secret_hit_count']}")
    else:
        print("PASS no obvious secret pattern")
    if report["local_artifact_count"]:
        print(f"WARN local-only artifacts={report['local_artifact_count']} (review, do not delete automatically)")
    else:
        print("PASS no local-only artifact")


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

    report = inspect_delivery(root)
    _print_report(report)
    blocking_keys = ("missing_files", "missing_stage_docs", "missing_readme_evidence")
    return 1 if any(report[key] for key in blocking_keys) or report["secret_hit_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
