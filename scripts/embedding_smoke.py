"""Run a minimal, synthetic-only Embedding connectivity check.

The command reads one user's Embedding settings in SQLite read-only mode. It
never reads personal documents, never writes the database, and never prints an
API key or vector values. A network request is made only when the selected
user explicitly has a complete ``openai-compatible`` Embedding configuration.

Example::

    python scripts/embedding_smoke.py \
        --db-path path/to/rebuild.sqlite3 \
        --user-id USER_ID
"""

from __future__ import annotations

import argparse
import math
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

# Make ``python scripts/embedding_smoke.py`` work from the repository root as
# well as ``python -m scripts.embedding_smoke``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.embedding import EmbeddingProviderError, build_embedding_provider


SYNTHETIC_TEXT = (
    "QTrace synthetic embedding smoke test. "
    "This sentence contains no personal resume content."
)


def _read_embedding_config(db_path: Path, user_id: str) -> dict[str, str] | None:
    """Read only the selected user's Embedding settings from an existing DB."""

    if not db_path.is_file():
        raise FileNotFoundError(f"数据库文件不存在：{db_path}")
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
        model_path_column = ",embedding_model_path" if "embedding_model_path" in columns else ""
        row = conn.execute(
            "SELECT embedding_mode,embedding_api_base,embedding_model"
            f"{model_path_column},embedding_api_key FROM settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "mode": row["embedding_mode"] or "demo",
        "api_base": row["embedding_api_base"] or "",
        "model": row["embedding_model"] or "",
        "model_path": row["embedding_model_path"] if "embedding_model_path" in row.keys() else "",
        "api_key": row["embedding_api_key"] or "",
    }


def _endpoint_host(api_base: str) -> str:
    parsed = urlparse(api_base)
    return parsed.hostname or "<unknown>"


def _redact(message: str, config: dict[str, str]) -> str:
    """Avoid echoing credentials or the full configured endpoint in failures."""

    result = message
    for secret in (config.get("api_key", ""), config.get("api_base", "")):
        if secret:
            result = result.replace(secret, "<redacted>")
    return result.replace("\n", " ")[:240]


def run_smoke(db_path: Path, user_id: str) -> int:
    config = _read_embedding_config(db_path, user_id)
    if config is None:
        print("NOT_CONFIGURED: 未找到指定用户；未发起网络请求")
        return 2
    if config["mode"] == "demo":
        print(
            f"NOT_CONFIGURED: embedding_mode={config['mode']}；"
            "当前为本地模式，未发起网络请求"
        )
        return 2
    if config["mode"] == "local-model":
        if not config["model_path"].strip():
            print("INVALID_CONFIG: 缺少本地模型目录；未发起网络请求")
            return 2
        try:
            provider = build_embedding_provider(config)
            started = time.perf_counter()
            vector = provider.embed(SYNTHETIC_TEXT)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        except (EmbeddingProviderError, ValueError) as exc:
            print(f"FAIL: 本地 Embedding 验收失败：{_redact(str(exc), config)}")
            return 1
        finite = all(isinstance(value, float) and math.isfinite(value) for value in vector)
        if not vector or not finite:
            print("FAIL: 本地模型返回的向量为空或包含非法浮点值")
            return 1
        print(
            "PASS: synthetic 本地 Embedding 验收成功 "
            f"dimension={len(vector)} elapsed_ms={elapsed_ms} "
            "network=disabled model_path_configured=yes"
        )
        return 0
    if config["mode"] != "openai-compatible":
        print(f"INVALID_CONFIG: 不支持的 embedding_mode={config['mode']}；未发起网络请求")
        return 2
    missing = [
        name
        for name, value in (
            ("api_base", config["api_base"]),
            ("model", config["model"]),
            ("api_key", config["api_key"]),
        )
        if not value.strip()
    ]
    if missing:
        print(f"INVALID_CONFIG: 缺少 {', '.join(missing)}；未发起网络请求")
        return 2

    try:
        provider = build_embedding_provider(config)
        started = time.perf_counter()
        vector = provider.embed(SYNTHETIC_TEXT)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    except (EmbeddingProviderError, ValueError) as exc:
        print(f"FAIL: Embedding 联调失败：{_redact(str(exc), config)}")
        return 1

    finite = all(isinstance(value, float) and math.isfinite(value) for value in vector)
    if not vector or not finite:
        print("FAIL: 服务返回的向量为空或包含非法浮点值")
        return 1
    print(
        "PASS: synthetic Embedding 联调成功 "
        f"dimension={len(vector)} elapsed_ms={elapsed_ms} "
        f"endpoint_host={_endpoint_host(config['api_base'])} "
        f"model={config['model']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True, type=Path, help="现有 QTrace SQLite 数据库")
    parser.add_argument("--user-id", required=True, help="要联调的用户 ID")
    args = parser.parse_args(argv)
    try:
        return run_smoke(args.db_path, args.user_id)
    except (OSError, sqlite3.Error) as exc:
        print(f"FAIL: 无法只读读取配置：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
