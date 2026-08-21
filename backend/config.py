from __future__ import annotations

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name, "").strip()
    return Path(value) if value else default


DATA_DIR = _path_from_env("REBUILD_DATA_DIR", PROJECT_DIR / "data")
DB_PATH = _path_from_env("REBUILD_DB_PATH", DATA_DIR / "rebuild.sqlite3")
JWT_SECRET = os.getenv("REBUILD_JWT_SECRET", "local-rebuild-only-change-me")
TOKEN_TTL_SECONDS = int(os.getenv("REBUILD_TOKEN_TTL_SECONDS", "86400"))

