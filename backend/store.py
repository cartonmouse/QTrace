from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .review_schedule import initial_schedule, sm2_update
from .security import hash_password


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_list(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = str(item).strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def _json_scores(raw: str | None) -> list[float]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    scores: list[float] = []
    for item in value:
        try:
            scores.append(round(max(0.0, min(10.0, float(item))), 1))
        except (TypeError, ValueError):
            continue
    return scores[-8:]


def _review_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("signal") or item.get("name") or item.get("text") or item.get("point")
        clean = str(item or "").strip()
        if clean:
            result.append(clean)
    return list(dict.fromkeys(result))


def _merge_values(previous: list[str], incoming: list[str], limit: int = 8) -> list[str]:
    return list(dict.fromkeys([*previous, *incoming]))[:limit]


def _score_trend(scores: list[float]) -> str:
    if len(scores) < 2:
        return "new" if scores else "flat"
    delta = scores[-1] - scores[-2]
    if delta >= 0.5:
        return "improving"
    if delta <= -0.5:
        return "declining"
    return "stable"


class Store:
    """Small SQLite boundary used by the first vertical slice.

    The store owns persistence details. Routers and the interview engine receive
    plain dictionaries so the data flow stays visible while we learn the system.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    use_stub_provider INTEGER NOT NULL DEFAULT 0,
                    llm_configured INTEGER NOT NULL DEFAULT 0,
                    embedding_configured INTEGER NOT NULL DEFAULT 0,
                    provider_mode TEXT NOT NULL DEFAULT 'none',
                    llm_api_base TEXT NOT NULL DEFAULT '',
                    llm_model TEXT NOT NULL DEFAULT '',
                    llm_api_key TEXT NOT NULL DEFAULT '',
                    embedding_mode TEXT NOT NULL DEFAULT 'demo'
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    target_role TEXT NOT NULL,
                    resume_text TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'resume',
                    topic TEXT,
                    knowledge_context TEXT NOT NULL DEFAULT '',
                    question_bank_json TEXT NOT NULL DEFAULT '[]',
                    company TEXT NOT NULL DEFAULT '',
                    position TEXT NOT NULL DEFAULT '',
                    jd_text TEXT NOT NULL DEFAULT '',
                    jd_preview_json TEXT NOT NULL DEFAULT '{}',
                    recording_mode TEXT NOT NULL DEFAULT '',
                    source_transcript TEXT NOT NULL DEFAULT '',
                    recording_meta_json TEXT NOT NULL DEFAULT '{}',
                    phase TEXT NOT NULL,
                    phase_question_count INTEGER NOT NULL,
                    is_finished INTEGER NOT NULL,
                    messages_json TEXT NOT NULL,
                    review_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    completed_sessions INTEGER NOT NULL DEFAULT 0,
                    mastery_score REAL NOT NULL DEFAULT 0,
                    weak_points_json TEXT NOT NULL DEFAULT '[]',
                    strong_points_json TEXT NOT NULL DEFAULT '[]',
                    behavior_signals_json TEXT NOT NULL DEFAULT '[]',
                    action_items_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS topic_profiles (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    topic TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    mastery_score REAL NOT NULL DEFAULT 0,
                    last_score REAL NOT NULL DEFAULT 0,
                    weak_points_json TEXT NOT NULL DEFAULT '[]',
                    recent_scores_json TEXT NOT NULL DEFAULT '[]',
                    trend TEXT NOT NULL DEFAULT 'flat',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, topic)
                );
                CREATE TABLE IF NOT EXISTS review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    topic TEXT NOT NULL DEFAULT '',
                    point TEXT NOT NULL,
                    interval_days INTEGER NOT NULL DEFAULT 1,
                    ease_factor REAL NOT NULL DEFAULT 2.5,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    next_review TEXT NOT NULL,
                    last_score REAL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, topic, point)
                );
                CREATE TABLE IF NOT EXISTS copilot_preps (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    company TEXT NOT NULL DEFAULT '',
                    position TEXT NOT NULL DEFAULT '',
                    jd_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    result_json TEXT,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT '新的成长对话',
                    messages_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_conversations_user
                    ON agent_conversations(user_id, updated_at);
                """
            )
            self._migrate_settings(conn)
            self._migrate_sessions(conn)
            self._migrate_profiles(conn)
            self._backfill_review_items(conn)

    @staticmethod
    def _migrate_settings(conn: sqlite3.Connection) -> None:
        """Add provider columns when an earlier stage-1 database already exists."""
        current = {row[1] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
        additions = {
            "provider_mode": "TEXT NOT NULL DEFAULT 'none'",
            "llm_api_base": "TEXT NOT NULL DEFAULT ''",
            "llm_model": "TEXT NOT NULL DEFAULT ''",
            "llm_api_key": "TEXT NOT NULL DEFAULT ''",
            "embedding_mode": "TEXT NOT NULL DEFAULT 'demo'",
        }
        for column, definition in additions.items():
            if column not in current:
                conn.execute(f"ALTER TABLE settings ADD COLUMN {column} {definition}")
        conn.execute(
            "UPDATE settings SET provider_mode='stub' "
            "WHERE use_stub_provider=1 AND (provider_mode IS NULL OR provider_mode='none')"
        )

    @staticmethod
    def _migrate_sessions(conn: sqlite3.Connection) -> None:
        current = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        additions = {
            "mode": "TEXT NOT NULL DEFAULT 'resume'",
            "topic": "TEXT",
            "knowledge_context": "TEXT NOT NULL DEFAULT ''",
            "question_bank_json": "TEXT NOT NULL DEFAULT '[]'",
            "company": "TEXT NOT NULL DEFAULT ''",
            "position": "TEXT NOT NULL DEFAULT ''",
            "jd_text": "TEXT NOT NULL DEFAULT ''",
            "jd_preview_json": "TEXT NOT NULL DEFAULT '{}'",
            "recording_mode": "TEXT NOT NULL DEFAULT ''",
            "source_transcript": "TEXT NOT NULL DEFAULT ''",
            "recording_meta_json": "TEXT NOT NULL DEFAULT '{}'",
        }
        for column, definition in additions.items():
            if column not in current:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")

    @staticmethod
    def _migrate_profiles(conn: sqlite3.Connection) -> None:
        """Add the long-term signals introduced by personalized drill v1."""
        profile_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()
        }
        profile_additions = {
            "strong_points_json": "TEXT NOT NULL DEFAULT '[]'",
            "behavior_signals_json": "TEXT NOT NULL DEFAULT '[]'",
            "action_items_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, definition in profile_additions.items():
            if column not in profile_columns:
                conn.execute(f"ALTER TABLE profiles ADD COLUMN {column} {definition}")

        topic_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(topic_profiles)").fetchall()
        }
        topic_additions = {
            "recent_scores_json": "TEXT NOT NULL DEFAULT '[]'",
            "trend": "TEXT NOT NULL DEFAULT 'flat'",
        }
        for column, definition in topic_additions.items():
            if column not in topic_columns:
                conn.execute(f"ALTER TABLE topic_profiles ADD COLUMN {column} {definition}")

    @staticmethod
    def _backfill_review_items(conn: sqlite3.Connection) -> None:
        """Make weak points from earlier stages visible to the new scheduler."""
        initial = initial_schedule()

        def points_from(raw: str | None) -> list[str]:
            try:
                values = json.loads(raw or "[]")
            except json.JSONDecodeError:
                return []
            return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

        profile_rows = conn.execute("SELECT user_id,weak_points_json FROM profiles").fetchall()
        for row in profile_rows:
            for point in points_from(row["weak_points_json"]):
                conn.execute(
                    """INSERT OR IGNORE INTO review_items(
                        user_id,topic,point,interval_days,ease_factor,repetitions,
                        next_review,last_score,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (row["user_id"], "", point, initial["interval_days"], initial["ease_factor"],
                     initial["repetitions"], initial["next_review"], initial["last_score"], _now()),
                )

        topic_rows = conn.execute(
            "SELECT user_id,topic,weak_points_json FROM topic_profiles"
        ).fetchall()
        for row in topic_rows:
            for point in points_from(row["weak_points_json"]):
                conn.execute(
                    """INSERT OR IGNORE INTO review_items(
                        user_id,topic,point,interval_days,ease_factor,repetitions,
                        next_review,last_score,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (row["user_id"], row["topic"], point, initial["interval_days"], initial["ease_factor"],
                     initial["repetitions"], initial["next_review"], initial["last_score"], _now()),
                )

    def create_user(self, email: str, password: str, name: str) -> dict[str, str]:
        user_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(id,email,password_hash,name,created_at) VALUES(?,?,?,?,?)",
                (user_id, email.lower().strip(), hash_password(password), name.strip(), _now()),
            )
            conn.execute("INSERT INTO settings(user_id) VALUES(?)", (user_id,))
            conn.execute("INSERT INTO profiles(user_id) VALUES(?)", (user_id,))
        return {"id": user_id, "email": email.lower().strip(), "name": name.strip()}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT id,email,name FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_settings(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {
                "use_stub_provider": False,
                "provider_mode": "none",
                "llm_api_base": "",
                "llm_model": "",
                "llm_key_configured": False,
                "embedding_mode": "demo",
                "llm_configured": False,
                "embedding_configured": False,
            }
        use_stub = bool(row["use_stub_provider"])
        provider_mode = "stub" if use_stub else (row["provider_mode"] or "none")
        return {
            "use_stub_provider": provider_mode == "stub",
            "provider_mode": provider_mode,
            "llm_api_base": row["llm_api_base"] or "",
            "llm_model": row["llm_model"] or "",
            "llm_key_configured": bool(row["llm_api_key"]),
            "embedding_mode": row["embedding_mode"] or "demo",
            "llm_configured": bool(row["llm_configured"]),
            "embedding_configured": bool(row["embedding_configured"]),
        }

    def get_provider_config(self, user_id: str) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provider_mode,llm_api_base,llm_model,llm_api_key,use_stub_provider "
                "FROM settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return {"mode": "none", "api_base": "", "model": "", "api_key": ""}
        mode = "stub" if row["use_stub_provider"] else (row["provider_mode"] or "none")
        return {
            "mode": mode,
            "api_base": row["llm_api_base"] or "",
            "model": row["llm_model"] or "",
            "api_key": row["llm_api_key"] or "",
        }

    def set_stub_provider(self, user_id: str, enabled: bool) -> dict[str, Any]:
        value = int(enabled)
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET use_stub_provider=?, provider_mode=?, llm_configured=?, "
                "embedding_configured=?, embedding_mode=? WHERE user_id=?",
                (value, "stub" if enabled else "none", value, value, "demo", user_id),
            )
        return self.get_settings(user_id)

    def set_openai_provider(
        self, user_id: str, api_base: str, model: str, api_key: str
    ) -> dict[str, Any]:
        current = self.get_provider_config(user_id)
        clean_base = api_base.strip()
        clean_model = model.strip() or current["model"]
        clean_key = api_key.strip() or current["api_key"]
        if not clean_base or not clean_model or not clean_key:
            raise ValueError("真实 LLM 配置需要 API Base、Model 和 API Key")
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET use_stub_provider=0, provider_mode='openai', "
                "llm_api_base=?, llm_model=?, llm_api_key=?, llm_configured=1, "
                "embedding_configured=1, embedding_mode='demo' WHERE user_id=?",
                (clean_base, clean_model, clean_key, user_id),
            )
        return self.get_settings(user_id)

    def create_session(self, user_id: str, state: dict[str, Any]) -> str:
        session_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions(
                    id,user_id,target_role,resume_text,mode,topic,knowledge_context,question_bank_json,
                    company,position,jd_text,jd_preview_json,recording_mode,source_transcript,recording_meta_json,
                    phase,phase_question_count,is_finished,messages_json,review_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    user_id,
                    state["target_role"],
                    state["resume_text"],
                    state.get("mode", "resume"),
                    state.get("topic"),
                    state.get("knowledge_context", ""),
                    json.dumps(state.get("question_bank", []), ensure_ascii=False),
                    state.get("company", ""),
                    state.get("position", ""),
                    state.get("jd_text", ""),
                    json.dumps(state.get("jd_preview", {}), ensure_ascii=False),
                    state.get("recording_mode", ""),
                    state.get("source_transcript", ""),
                    json.dumps(state.get("recording_meta", {}), ensure_ascii=False),
                    state["phase"],
                    state["phase_question_count"],
                    int(state["is_finished"]),
                    json.dumps(state["messages"], ensure_ascii=False),
                    json.dumps(state.get("review"), ensure_ascii=False) if state.get("review") else None,
                    _now(),
                    _now(),
                ),
            )
        return session_id

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id=? AND user_id=?", (session_id, user_id)
            ).fetchone()
        return self._session_row(row) if row else None

    def update_session(self, user_id: str, session_id: str, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE sessions SET phase=?,phase_question_count=?,is_finished=?,
                   messages_json=?,review_json=?,updated_at=? WHERE id=? AND user_id=?""",
                (
                    state["phase"],
                    state["phase_question_count"],
                    int(state["is_finished"]),
                    json.dumps(state["messages"], ensure_ascii=False),
                    json.dumps(state.get("review"), ensure_ascii=False) if state.get("review") else None,
                    _now(),
                    session_id,
                    user_id,
                ),
            )

    def list_sessions(self, user_id: str, topic: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if topic:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id=? AND topic=? ORDER BY updated_at DESC",
                    (user_id, topic),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
                ).fetchall()
        return [self._session_row(row) for row in rows]

    def create_copilot_prep(self, user_id: str, company: str, position: str, jd_text: str) -> str:
        prep_id = str(uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO copilot_preps(
                    id,user_id,company,position,jd_text,status,result_json,error,created_at,updated_at
                ) VALUES(?,?,?,?,?,'running',NULL,'',?,?)""",
                (prep_id, user_id, company, position, jd_text, now, now),
            )
        return prep_id

    def update_copilot_prep(
        self,
        user_id: str,
        prep_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE copilot_preps SET status=?,result_json=?,error=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    _now(),
                    prep_id,
                    user_id,
                ),
            )

    @staticmethod
    def _copilot_prep_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "company": row["company"] or "",
            "position": row["position"] or "",
            "jd_text": row["jd_text"] or "",
            "status": row["status"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_copilot_prep(self, user_id: str, prep_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM copilot_preps WHERE id=? AND user_id=?",
                (prep_id, user_id),
            ).fetchone()
        return self._copilot_prep_row(row) if row else None

    def list_copilot_preps(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM copilot_preps WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._copilot_prep_row(row) for row in rows]

    @staticmethod
    def _agent_conversation_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "messages": json.loads(row["messages_json"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_agent_conversation(self, user_id: str, title: str) -> str:
        conversation_id = str(uuid4())
        clean_title = " ".join(title.strip().split())[:40] or "新的成长对话"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_conversations(id,user_id,title,messages_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (conversation_id, user_id, clean_title, "[]", now, now),
            )
        return conversation_id

    def get_agent_conversation(self, user_id: str, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE id=? AND user_id=?",
                (conversation_id, user_id),
            ).fetchone()
        return self._agent_conversation_row(row)

    def list_agent_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id,title,messages_json,created_at,updated_at FROM agent_conversations "
                "WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "message_count": len(json.loads(row["messages_json"] or "[]")),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def update_agent_conversation(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE agent_conversations SET messages_json=?,updated_at=? "
                "WHERE id=? AND user_id=?",
                (json.dumps(messages[-40:], ensure_ascii=False), _now(), conversation_id, user_id),
            )

    @staticmethod
    def _session_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "target_role": row["target_role"],
            "resume_text": row["resume_text"],
            "mode": row["mode"] or "resume",
            "topic": row["topic"],
            "knowledge_context": row["knowledge_context"] or "",
            "question_bank": json.loads(row["question_bank_json"] or "[]"),
            "company": row["company"] or "",
            "position": row["position"] or "",
            "jd_text": row["jd_text"] or "",
            "jd_preview": json.loads(row["jd_preview_json"] or "{}"),
            "recording_mode": row["recording_mode"] or "",
            "source_transcript": row["source_transcript"] or "",
            "recording_meta": json.loads(row["recording_meta_json"] or "{}"),
            "phase": row["phase"],
            "phase_question_count": row["phase_question_count"],
            "is_finished": bool(row["is_finished"]),
            "messages": json.loads(row["messages_json"]),
            "review": json.loads(row["review_json"]) if row["review_json"] else None,
        }

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return {
                "completed_sessions": 0,
                "mastery_score": 0.0,
                "weak_points": [],
                "strong_points": [],
                "behavior_signals": [],
                "action_items": [],
            }
        return {
            "completed_sessions": int(row["completed_sessions"]),
            "mastery_score": float(row["mastery_score"]),
            "weak_points": _json_list(row["weak_points_json"]),
            "strong_points": _json_list(row["strong_points_json"]),
            "behavior_signals": _json_list(row["behavior_signals_json"]),
            "action_items": _json_list(row["action_items_json"]),
        }

    def list_topic_profiles(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM topic_profiles WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
            ).fetchall()
        return [
            {
                "topic": row["topic"],
                "attempts": int(row["attempts"]),
                "mastery_score": float(row["mastery_score"]),
                "last_score": float(row["last_score"]),
                "weak_points": _json_list(row["weak_points_json"]),
                "recent_scores": _json_scores(row["recent_scores_json"]),
                "trend": row["trend"] or "flat",
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def get_topic_profile(self, user_id: str, topic: str) -> dict[str, Any] | None:
        return next((item for item in self.list_topic_profiles(user_id) if item["topic"] == topic), None)

    @staticmethod
    def _review_item_view(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "point": row["point"],
            "topic": row["topic"] or None,
            "interval_days": int(row["interval_days"]),
            "ease_factor": float(row["ease_factor"]),
            "repetitions": int(row["repetitions"]),
            "next_review": row["next_review"],
            "last_score": float(row["last_score"]) if row["last_score"] is not None else None,
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _upsert_review_items(
        conn: sqlite3.Connection,
        user_id: str,
        weak_points: list[str],
        score: float,
        topic: str | None,
    ) -> None:
        """Persist weak points and advance their scheduling state atomically."""
        normalized_topic = (topic or "").strip()
        unique_points = list(dict.fromkeys(item.strip() for item in weak_points if item.strip()))
        for point in unique_points:
            row = conn.execute(
                "SELECT * FROM review_items WHERE user_id=? AND topic=? AND point=?",
                (user_id, normalized_topic, point),
            ).fetchone()
            schedule = sm2_update(dict(row), score) if row else initial_schedule()
            conn.execute(
                """INSERT INTO review_items(
                    user_id,topic,point,interval_days,ease_factor,repetitions,
                    next_review,last_score,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id,topic,point) DO UPDATE SET
                    interval_days=excluded.interval_days,
                    ease_factor=excluded.ease_factor,
                    repetitions=excluded.repetitions,
                    next_review=excluded.next_review,
                    last_score=excluded.last_score,
                    updated_at=excluded.updated_at""",
                (
                    user_id,
                    normalized_topic,
                    point,
                    schedule["interval_days"],
                    schedule["ease_factor"],
                    schedule["repetitions"],
                    schedule["next_review"],
                    schedule["last_score"],
                    _now(),
                ),
            )

    def list_due_reviews(
        self,
        user_id: str,
        topic: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return weak points due today, with the hardest items first."""
        clean_topic = (topic or "").strip()
        safe_limit = max(1, min(int(limit), 100))
        today = date.today().isoformat()
        with self._connect() as conn:
            if clean_topic:
                rows = conn.execute(
                    """SELECT * FROM review_items
                       WHERE user_id=? AND topic=? AND next_review<=?
                       ORDER BY next_review ASC, ease_factor ASC, updated_at ASC LIMIT ?""",
                    (user_id, clean_topic, today, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM review_items
                       WHERE user_id=? AND next_review<=?
                       ORDER BY next_review ASC, ease_factor ASC, updated_at ASC LIMIT ?""",
                    (user_id, today, safe_limit),
                ).fetchall()
        return [self._review_item_view(row) for row in rows]

    def update_profile_after_review(
        self,
        user_id: str,
        review: dict[str, Any],
        topic: str | None = None,
    ) -> dict[str, Any]:
        previous = self.get_profile(user_id)
        score = max(0.0, min(10.0, float(review.get("average_score", 0) or 0)))
        review_weak_points = _review_values(review.get("weak_points", []))
        review_strengths = _review_values(review.get("strengths", []))
        review_signals = _review_values(review.get("behavior_signals", []))
        review_actions = _review_values(review.get("action_items", []))
        weak_points = _merge_values(previous["weak_points"], review_weak_points)
        strong_points = _merge_values(previous["strong_points"], review_strengths)
        behavior_signals = _merge_values(previous["behavior_signals"], review_signals)
        action_items = _merge_values(previous["action_items"], review_actions)
        mastery = round((previous["mastery_score"] * previous["completed_sessions"] + score) / (previous["completed_sessions"] + 1), 1)
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET completed_sessions=?, mastery_score=?, weak_points_json=?, "
                "strong_points_json=?, behavior_signals_json=?, action_items_json=? WHERE user_id=?",
                (
                    previous["completed_sessions"] + 1,
                    mastery,
                    json.dumps(weak_points, ensure_ascii=False),
                    json.dumps(strong_points, ensure_ascii=False),
                    json.dumps(behavior_signals, ensure_ascii=False),
                    json.dumps(action_items, ensure_ascii=False),
                    user_id,
                ),
            )
            if topic:
                row = conn.execute(
                    "SELECT * FROM topic_profiles WHERE user_id=? AND topic=?", (user_id, topic)
                ).fetchone()
                attempts = int(row["attempts"]) if row else 0
                previous_score = float(row["mastery_score"]) if row else 0.0
                topic_weak_points = _json_list(row["weak_points_json"]) if row else []
                topic_weak_points = _merge_values(topic_weak_points, review_weak_points)
                recent_scores = _json_scores(row["recent_scores_json"]) if row else []
                recent_scores = [*recent_scores, score][-8:]
                trend = _score_trend(recent_scores)
                topic_mastery = round((previous_score * attempts + score) / (attempts + 1), 1)
                conn.execute(
                    """INSERT INTO topic_profiles(
                        user_id,topic,attempts,mastery_score,last_score,weak_points_json,
                        recent_scores_json,trend,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(user_id,topic) DO UPDATE SET
                        attempts=excluded.attempts,
                        mastery_score=excluded.mastery_score,
                        last_score=excluded.last_score,
                        weak_points_json=excluded.weak_points_json,
                        recent_scores_json=excluded.recent_scores_json,
                        trend=excluded.trend,
                        updated_at=excluded.updated_at""",
                    (
                        user_id,
                        topic,
                        attempts + 1,
                        topic_mastery,
                        score,
                        json.dumps(topic_weak_points, ensure_ascii=False),
                        json.dumps(recent_scores, ensure_ascii=False),
                        trend,
                        _now(),
                    ),
                )
            self._upsert_review_items(conn, user_id, review_weak_points, score, topic)
        return self.get_profile(user_id)
