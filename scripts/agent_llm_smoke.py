"""Run a synthetic-only smoke test for the real QTrace Agent model.

The command reads one user's LLM settings through a SQLite read-only URI. It
never reads resume/document tables, never writes the database, and never
prints the API key or the model's answer. It performs the two calls used by
the Agent boundary: structured planning followed by a grounded answer.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.agent import AGENT_TOOLS, build_agent_model
from backend.provider import ProviderError


SYNTHETIC_MESSAGE = (
    "请根据合成训练上下文，给出一条关于 RAG 评估的个性化练习建议；"
    "不要制定学习计划，也不要读取任何个人资料。"
)
SYNTHETIC_CONTEXT = {
    "read_profile": {
        "synthetic": True,
        "topic_mastery": [{"topic": "synthetic-rag", "mastery": 0.4}],
        "weak_points": ["召回率与准确率的区分"],
    },
    "read_due_reviews": [
        {"synthetic": True, "topic": "synthetic-rag", "point": "检索评估指标"}
    ],
    "read_recent_sessions": [],
}


def _read_provider_config(db_path: Path, user_id: str) -> dict[str, str] | None:
    if not db_path.is_file():
        raise FileNotFoundError(f"数据库文件不存在：{db_path}")
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT provider_mode,llm_api_base,llm_model,llm_api_key,use_stub_provider "
            "FROM settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "mode": "stub" if row["use_stub_provider"] else (row["provider_mode"] or "none"),
        "api_base": row["llm_api_base"] or "",
        "model": row["llm_model"] or "",
        "api_key": row["llm_api_key"] or "",
    }


def _endpoint_host(api_base: str) -> str:
    return urlparse(api_base).hostname or "<unknown>"


def _redact(message: str, config: dict[str, str]) -> str:
    """Avoid echoing credentials or the configured endpoint in failures."""

    result = message
    for secret in (config.get("api_key", ""), config.get("api_base", "")):
        if secret:
            result = result.replace(secret, "<redacted>")
    return result.replace("\n", " ")[:240]


def run_smoke(db_path: Path, user_id: str) -> int:
    config = _read_provider_config(db_path, user_id)
    if config is None:
        print("NOT_CONFIGURED: 未找到指定用户；未发起网络请求")
        return 2
    if config["mode"] != "openai":
        print(
            f"NOT_CONFIGURED: provider_mode={config['mode']}；"
            "当前不是真实 LLM 模式，未发起网络请求"
        )
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
        model = build_agent_model(config)
        plan_started = time.perf_counter()
        plan = model.plan(SYNTHETIC_MESSAGE)
        plan_ms = round((time.perf_counter() - plan_started) * 1000, 1)
        tool_names = [str(item.get("name", "")) for item in plan.get("tool_calls", [])]
        if any(name not in AGENT_TOOLS for name in tool_names):
            print("FAIL: Agent 规划返回了未注册工具")
            return 1
        answer_started = time.perf_counter()
        answer = model.answer(SYNTHETIC_MESSAGE, [], SYNTHETIC_CONTEXT)
        answer_ms = round((time.perf_counter() - answer_started) * 1000, 1)
    except ProviderError as exc:
        print(f"FAIL: 真实 LLM/Agent 联调失败：{_redact(str(exc), config)}")
        return 1

    if not isinstance(answer, str) or not answer.strip():
        print("FAIL: Agent 返回了空回答")
        return 1
    print(
        "PASS: synthetic Agent LLM 联调成功 "
        f"model={config['model']} endpoint_host={_endpoint_host(config['api_base'])} "
        f"plan_tools={','.join(tool_names) or '<none>'} "
        f"plan_ms={plan_ms} answer_chars={len(answer)} answer_ms={answer_ms}"
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
