"""Run read-only smoke checks against the local QTrace runtime.

The check intentionally stays inside the local project boundary. It does not
read the database, inspect user documents, call an external service, or modify
the worktree. It only probes the local health/page endpoints and verifies that
the frontend production entrypoint references files that exist in ``dist``.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ASSET_REFERENCE = re.compile(r"(?:src|href)=[\"']([^\"']*assets/[^\"']+)[\"']")


@dataclass(frozen=True)
class ProbeResult:
    name: str
    status: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def _probe_url(name: str, url: str, timeout: float) -> ProbeResult:
    request = Request(url, headers={"Accept": "application/json,text/html"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            response.read(4096)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return ProbeResult(name, "FAIL", "unreachable or invalid response")

    if not 200 <= status < 300:
        return ProbeResult(name, "FAIL", f"status={status}")
    return ProbeResult(name, "PASS", f"status={status}")


def _probe_frontend_dist(root: Path) -> ProbeResult:
    index_path = root / "frontend" / "dist" / "index.html"
    if not index_path.is_file():
        return ProbeResult("frontend_dist", "FAIL", "frontend/dist/index.html is missing")

    try:
        html = index_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ProbeResult("frontend_dist", "FAIL", "frontend/dist/index.html is unreadable")

    references = ASSET_REFERENCE.findall(html)
    if not references:
        return ProbeResult("frontend_dist", "FAIL", "no bundled asset reference found")

    missing = 0
    for reference in references:
        relative_path = reference.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if not relative_path or not (index_path.parent / relative_path).is_file():
            missing += 1
    if missing:
        return ProbeResult("frontend_dist", "FAIL", f"missing referenced assets={missing}")

    return ProbeResult(
        "frontend_dist",
        "PASS",
        f"index_bytes={index_path.stat().st_size} assets={len(references)}",
    )


def check_runtime(
    root: Path,
    backend_url: str,
    frontend_url: str,
    timeout: float,
) -> list[ProbeResult]:
    """Return local runtime findings without printing response content."""

    return [
        _probe_url("backend_health", backend_url, timeout),
        _probe_url("frontend_dev", frontend_url, timeout),
        _probe_frontend_dist(root.resolve()),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="QTrace repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:8002/api/health",
        help="local backend health URL",
    )
    parser.add_argument(
        "--frontend-url",
        default="http://127.0.0.1:5174/",
        help="local frontend URL",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="per-request timeout in seconds")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print("FAIL repository root does not exist")
        return 1

    results = check_runtime(root, args.backend_url, args.frontend_url, args.timeout)
    print("QTrace local runtime smoke")
    for result in results:
        print(f"{result.status} {result.name}: {result.detail}")
    if all(result.passed for result in results):
        print("PASS local runtime smoke")
        return 0
    print("FAIL local runtime smoke")
    return 2


if __name__ == "__main__":
    sys.exit(main())
