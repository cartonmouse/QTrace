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
BYOK_STORAGE_MODE = os.getenv("REBUILD_BYOK_STORAGE_MODE", "persisted").strip().lower()
if BYOK_STORAGE_MODE not in {"persisted", "session"}:
    raise ValueError("REBUILD_BYOK_STORAGE_MODE must be 'persisted' or 'session'")


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


# Local development keeps localhost-compatible providers available. The public
# Compose contract overrides this to block private and link-local destinations.
BLOCK_PRIVATE_API_BASE = _bool_from_env("REBUILD_BLOCK_PRIVATE_API_BASE", False)


def _origins_from_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip()) or default


ALLOWED_ORIGINS = _origins_from_env(
    "REBUILD_ALLOWED_ORIGINS",
    ("http://127.0.0.1:5173", "http://localhost:5173"),
)
