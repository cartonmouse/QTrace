"""Check that the public QTrace entry goes directly to login.

This is a read-only source contract. It prevents the unused reference landing
page or its startup video from becoming the active root route again.
"""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_APP_MARKERS = (
    "function PublicHome()",
    'return <Navigate to="/login" replace />;',
    "function AuthPage()",
    "return <Login />;",
)
FORBIDDEN_ACTIVE_MARKERS = (
    'import Landing from "./pages/Landing";',
    "return <Landing />;",
    "hero-intro",
)


def inspect_entry(root: Path) -> dict[str, object]:
    """Return missing/forbidden root-entry markers without changing files."""

    app_path = root / "frontend" / "src" / "App.tsx"
    if not app_path.is_file():
        return {
            "missing_file": "frontend/src/App.tsx",
            "missing_markers": list(REQUIRED_APP_MARKERS),
            "forbidden_markers": [],
        }

    text = app_path.read_text(encoding="utf-8")
    return {
        "missing_file": "",
        "missing_markers": [marker for marker in REQUIRED_APP_MARKERS if marker not in text],
        "forbidden_markers": [marker for marker in FORBIDDEN_ACTIVE_MARKERS if marker in text],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = inspect_entry(args.root.resolve())
    if report["missing_file"] or report["missing_markers"] or report["forbidden_markers"]:
        print(f"FAIL {report}")
        return 1
    print("PASS direct-login entry; no active Landing/video markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
