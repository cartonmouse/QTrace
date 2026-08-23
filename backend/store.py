from __future__ import annotations

import hashlib
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

    def __init__(self, db_path: str | Path, *, secret_storage_mode: str = "persisted"):
        if secret_storage_mode not in {"persisted", "session"}:
            raise ValueError("secret_storage_mode must be 'persisted' or 'session'")
        self.db_path = Path(db_path)
        self.secret_storage_mode = secret_storage_mode
        self._session_llm_keys: dict[str, str] = {}
        self._session_embedding_keys: dict[str, str] = {}
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
                    embedding_mode TEXT NOT NULL DEFAULT 'demo',
                    embedding_api_base TEXT NOT NULL DEFAULT '',
                    embedding_model TEXT NOT NULL DEFAULT '',
                    embedding_model_path TEXT NOT NULL DEFAULT '',
                    embedding_api_key TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    target_role TEXT NOT NULL,
                    resume_text TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'resume',
                    topic TEXT,
                    learning_plan_id TEXT,
                    learning_plan_item_id TEXT,
                    question_card_id TEXT,
                    question_card_project TEXT NOT NULL DEFAULT '',
                    question_card_resume_version INTEGER,
                    graph_question_id TEXT,
                    graph_question TEXT NOT NULL DEFAULT '',
                    graph_entry_source TEXT NOT NULL DEFAULT '',
                    graph_parent_question_id TEXT,
                    graph_parent_question TEXT NOT NULL DEFAULT '',
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
                CREATE TABLE IF NOT EXISTS learning_plans (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id TEXT REFERENCES agent_conversations(id) ON DELETE SET NULL,
                    source_message TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL DEFAULT '[]',
                    source_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_plans_user
                    ON learning_plans(user_id, updated_at);
                """
            )
            self._migrate_settings(conn)
            self._migrate_sessions(conn)
            self._migrate_profiles(conn)
            self._migrate_learning_plans(conn)
            self._migrate_personal_documents(conn)
            self._migrate_resume_profiles(conn)
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
            "embedding_api_base": "TEXT NOT NULL DEFAULT ''",
            "embedding_model": "TEXT NOT NULL DEFAULT ''",
            "embedding_model_path": "TEXT NOT NULL DEFAULT ''",
            "embedding_api_key": "TEXT NOT NULL DEFAULT ''",
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
            "learning_plan_id": "TEXT",
            "learning_plan_item_id": "TEXT",
            "question_card_id": "TEXT",
            "question_card_project": "TEXT NOT NULL DEFAULT ''",
            "question_card_resume_version": "INTEGER",
            "graph_question_id": "TEXT",
            "graph_question": "TEXT NOT NULL DEFAULT ''",
            "graph_entry_source": "TEXT NOT NULL DEFAULT ''",
            "graph_parent_question_id": "TEXT",
            "graph_parent_question": "TEXT NOT NULL DEFAULT ''",
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
    def _migrate_learning_plans(conn: sqlite3.Connection) -> None:
        """Link plans to the Agent conversation that created them."""
        current = {row[1] for row in conn.execute("PRAGMA table_info(learning_plans)").fetchall()}
        if "conversation_id" not in current:
            conn.execute(
                "ALTER TABLE learning_plans ADD COLUMN conversation_id TEXT "
                "REFERENCES agent_conversations(id) ON DELETE SET NULL"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_plans_conversation "
            "ON learning_plans(user_id, conversation_id, updated_at)"
        )

    @staticmethod
    def _migrate_personal_documents(conn: sqlite3.Connection) -> None:
        """Create the user-owned document and chunk tables for Personal Agent memory."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS personal_documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                content_chars INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                embedding_mode TEXT NOT NULL DEFAULT 'local-deterministic',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_personal_documents_user
                ON personal_documents(user_id, updated_at);
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES personal_documents(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL DEFAULT '[]',
                embedding_mode TEXT NOT NULL DEFAULT 'local-deterministic',
                created_at TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            );
            CREATE INDEX IF NOT EXISTS idx_document_chunks_user
                ON document_chunks(user_id, document_id, chunk_index);
            CREATE TABLE IF NOT EXISTS personal_document_versions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES personal_documents(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                content_chars INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                embedding_mode TEXT NOT NULL DEFAULT 'local-deterministic',
                created_at TEXT NOT NULL,
                UNIQUE(document_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_personal_document_versions_user
                ON personal_document_versions(user_id, document_id, version DESC);
            """
        )
        current = {row[1] for row in conn.execute("PRAGMA table_info(personal_documents)").fetchall()}
        if "content_hash" not in current:
            conn.execute(
                "ALTER TABLE personal_documents ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''"
            )
        if "version" not in current:
            conn.execute(
                "ALTER TABLE personal_documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
            )
        rows = conn.execute(
            "SELECT id,content FROM personal_documents WHERE content_hash IS NULL OR content_hash=''"
        ).fetchall()
        for row in rows:
            digest = hashlib.sha256(str(row["content"]).encode("utf-8")).hexdigest()
            conn.execute(
                "UPDATE personal_documents SET content_hash=? WHERE id=?",
                (digest, row["id"]),
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_personal_documents_hash "
            "ON personal_documents(user_id, content_hash)"
        )
        rows = conn.execute(
            "SELECT id,user_id,title,source_type,content,content_hash,content_chars,chunk_count,"
            "embedding_mode,created_at,version FROM personal_documents"
        ).fetchall()
        for row in rows:
            version = int(row["version"] or 1)
            exists = conn.execute(
                "SELECT 1 FROM personal_document_versions WHERE document_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO personal_document_versions(
                    id,document_id,user_id,version,title,source_type,content,content_hash,
                    content_chars,chunk_count,embedding_mode,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    row["id"],
                    row["user_id"],
                    version,
                    row["title"],
                    row["source_type"],
                    row["content"],
                    row["content_hash"],
                    int(row["content_chars"] or 0),
                    int(row["chunk_count"] or 0),
                    row["embedding_mode"] or "local-deterministic",
                    row["created_at"],
                ),
            )

    @staticmethod
    def _migrate_resume_profiles(conn: sqlite3.Connection) -> None:
        """Create the current structured resume and immutable version snapshots."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS resume_profiles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                version INTEGER NOT NULL DEFAULT 1,
                profile_json TEXT NOT NULL DEFAULT '{}',
                context_text TEXT NOT NULL DEFAULT '',
                profile_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_resume_profiles_user
                ON resume_profiles(user_id, updated_at);
            CREATE TABLE IF NOT EXISTS resume_profile_versions (
                id TEXT PRIMARY KEY,
                resume_id TEXT NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                profile_json TEXT NOT NULL DEFAULT '{}',
                context_text TEXT NOT NULL DEFAULT '',
                profile_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(resume_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_resume_profile_versions_user
                ON resume_profile_versions(user_id, version DESC);
            """
        )
        rows = conn.execute(
            "SELECT id,user_id,version,profile_json,context_text,profile_hash,created_at FROM resume_profiles"
        ).fetchall()
        for row in rows:
            version = int(row["version"] or 1)
            exists = conn.execute(
                "SELECT 1 FROM resume_profile_versions WHERE resume_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO resume_profile_versions(
                    id,resume_id,user_id,version,profile_json,context_text,profile_hash,created_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    row["id"],
                    row["user_id"],
                    version,
                    row["profile_json"] or "{}",
                    row["context_text"] or "",
                    row["profile_hash"] or "",
                    row["created_at"],
                ),
            )

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

    @staticmethod
    def _personal_document_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "deduplicated": False,
            "version": int(row["version"] or 1),
            "content_chars": int(row["content_chars"] or 0),
            "chunk_count": int(row["chunk_count"] or 0),
            "embedding_mode": row["embedding_mode"] or "local-deterministic",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _personal_document_version_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": row["id"],
            "document_id": row["document_id"],
            "version": int(row["version"] or 1),
            "title": row["title"],
            "source_type": row["source_type"],
            "content": row["content"],
            "content_chars": int(row["content_chars"] or 0),
            "chunk_count": int(row["chunk_count"] or 0),
            "embedding_mode": row["embedding_mode"] or "local-deterministic",
            "created_at": row["created_at"],
        }

    def create_personal_document(
        self,
        user_id: str,
        *,
        title: str,
        source_type: str,
        content: str,
        content_hash: str,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        document_id = str(uuid4())
        now = _now()
        embedding_mode = str(chunks[0].get("embedding_mode", "local-deterministic")) if chunks else "local-deterministic"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM personal_documents WHERE user_id=? AND content_hash=? "
                "ORDER BY updated_at DESC LIMIT 1",
                (user_id, content_hash),
            ).fetchone()
            if existing:
                duplicate = self._personal_document_row(existing) or {}
                duplicate["deduplicated"] = True
                return duplicate
            conn.execute(
                """INSERT INTO personal_documents(
                    id,user_id,title,source_type,content,content_hash,version,content_chars,chunk_count,
                    embedding_mode,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    document_id,
                    user_id,
                    title,
                    source_type,
                    content,
                    content_hash,
                    1,
                    len(content),
                    len(chunks),
                    embedding_mode,
                    now,
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO personal_document_versions(
                    id,document_id,user_id,version,title,source_type,content,content_hash,
                    content_chars,chunk_count,embedding_mode,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    document_id,
                    user_id,
                    1,
                    title,
                    source_type,
                    content,
                    content_hash,
                    len(content),
                    len(chunks),
                    embedding_mode,
                    now,
                ),
            )
            for chunk in chunks:
                conn.execute(
                    """INSERT INTO document_chunks(
                        id,document_id,user_id,chunk_index,content,embedding_json,
                        embedding_mode,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        document_id,
                        user_id,
                        int(chunk["chunk_index"]),
                        str(chunk["content"]),
                        json.dumps(chunk["embedding"], ensure_ascii=False),
                        str(chunk.get("embedding_mode", embedding_mode)),
                        now,
                    ),
                )
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM personal_documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
        return self._personal_document_row(row) or {
            "id": document_id,
            "title": title,
            "source_type": source_type,
            "deduplicated": False,
            "version": 1,
            "content_chars": len(content),
            "chunk_count": len(chunks),
            "embedding_mode": embedding_mode,
            "created_at": now,
            "updated_at": now,
        }

    def list_personal_documents(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM personal_documents WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._personal_document_row(row) for row in rows if row]

    def update_personal_document(
        self,
        user_id: str,
        document_id: str,
        *,
        title: str,
        source_type: str,
        content: str,
        content_hash: str,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Save a changed document as a new immutable version."""
        now = _now()
        embedding_mode = str(chunks[0].get("embedding_mode", "local-deterministic")) if chunks else "local-deterministic"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM personal_documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
            if not current:
                return None
            if current["content_hash"] == content_hash:
                unchanged = self._personal_document_row(current) or {}
                unchanged["unchanged"] = True
                return unchanged

            current_version = int(current["version"] or 1)
            next_version = current_version + 1
            history_exists = conn.execute(
                "SELECT 1 FROM personal_document_versions WHERE document_id=? AND version=?",
                (document_id, current_version),
            ).fetchone()
            if not history_exists:
                conn.execute(
                    """INSERT INTO personal_document_versions(
                        id,document_id,user_id,version,title,source_type,content,content_hash,
                        content_chars,chunk_count,embedding_mode,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        document_id,
                        user_id,
                        current_version,
                        current["title"],
                        current["source_type"],
                        current["content"],
                        current["content_hash"],
                        int(current["content_chars"] or 0),
                        int(current["chunk_count"] or 0),
                        current["embedding_mode"] or "local-deterministic",
                        current["created_at"],
                    ),
                )
            conn.execute(
                """INSERT INTO personal_document_versions(
                    id,document_id,user_id,version,title,source_type,content,content_hash,
                    content_chars,chunk_count,embedding_mode,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    document_id,
                    user_id,
                    next_version,
                    title,
                    source_type,
                    content,
                    content_hash,
                    len(content),
                    len(chunks),
                    embedding_mode,
                    now,
                ),
            )
            conn.execute("DELETE FROM document_chunks WHERE document_id=? AND user_id=?", (document_id, user_id))
            conn.execute(
                """UPDATE personal_documents SET
                    title=?,source_type=?,content=?,content_hash=?,version=?,content_chars=?,
                    chunk_count=?,embedding_mode=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (
                    title,
                    source_type,
                    content,
                    content_hash,
                    next_version,
                    len(content),
                    len(chunks),
                    embedding_mode,
                    now,
                    document_id,
                    user_id,
                ),
            )
            for chunk in chunks:
                conn.execute(
                    """INSERT INTO document_chunks(
                        id,document_id,user_id,chunk_index,content,embedding_json,
                        embedding_mode,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        document_id,
                        user_id,
                        int(chunk["chunk_index"]),
                        str(chunk["content"]),
                        json.dumps(chunk["embedding"], ensure_ascii=False),
                        str(chunk.get("embedding_mode", embedding_mode)),
                        now,
                    ),
                )
            updated = conn.execute(
                "SELECT * FROM personal_documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
        result = self._personal_document_row(updated)
        if result:
            result["unchanged"] = False
        return result

    def list_personal_document_versions(
        self,
        user_id: str,
        document_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id,document_id,version,title,source_type,content,content_chars,
                          chunk_count,embedding_mode,created_at
                   FROM personal_document_versions
                   WHERE user_id=? AND document_id=?
                   ORDER BY version DESC""",
                (user_id, document_id),
            ).fetchall()
        return [self._personal_document_version_row(row) for row in rows if row]

    def reindex_personal_document(
        self,
        user_id: str,
        document_id: str,
        *,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Replace only the current index; do not create a document version."""
        now = _now()
        embedding_mode = str(chunks[0].get("embedding_mode", "local-deterministic")) if chunks else "local-deterministic"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM personal_documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
            if not current:
                return None
            current_version = int(current["version"] or 1)
            conn.execute("DELETE FROM document_chunks WHERE document_id=? AND user_id=?", (document_id, user_id))
            conn.execute(
                "UPDATE personal_documents SET chunk_count=?,embedding_mode=?,updated_at=? "
                "WHERE id=? AND user_id=?",
                (len(chunks), embedding_mode, now, document_id, user_id),
            )
            conn.execute(
                "UPDATE personal_document_versions SET chunk_count=?,embedding_mode=? "
                "WHERE document_id=? AND user_id=? AND version=?",
                (len(chunks), embedding_mode, document_id, user_id, current_version),
            )
            for chunk in chunks:
                conn.execute(
                    """INSERT INTO document_chunks(
                        id,document_id,user_id,chunk_index,content,embedding_json,
                        embedding_mode,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        document_id,
                        user_id,
                        int(chunk["chunk_index"]),
                        str(chunk["content"]),
                        json.dumps(chunk["embedding"], ensure_ascii=False),
                        str(chunk.get("embedding_mode", embedding_mode)),
                        now,
                    ),
                )
            updated = conn.execute(
                "SELECT * FROM personal_documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
        return self._personal_document_row(updated)

    def get_personal_document_version(
        self,
        user_id: str,
        document_id: str,
        version: int,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT id,document_id,version,title,source_type,content,content_chars,
                          chunk_count,embedding_mode,created_at
                   FROM personal_document_versions
                   WHERE user_id=? AND document_id=? AND version=?""",
                (user_id, document_id, int(version)),
            ).fetchone()
        return self._personal_document_version_row(row)

    @staticmethod
    def _decode_resume_profile(raw: str | None) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @classmethod
    def _resume_profile_row(cls, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": row["id"],
            "version": int(row["version"] or 1),
            "profile": cls._decode_resume_profile(row["profile_json"]),
            "context_text": row["context_text"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "exists": True,
            "unchanged": False,
        }

    @classmethod
    def _resume_profile_version_row(cls, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        profile = cls._decode_resume_profile(row["profile_json"])
        return {
            "id": row["id"],
            "version": int(row["version"] or 1),
            "profile": profile,
            "context_text": row["context_text"] or "",
            "created_at": row["created_at"],
            "context_chars": len(row["context_text"] or ""),
            "project_count": len(profile.get("projects", [])) if isinstance(profile.get("projects"), list) else 0,
        }

    def get_resume_profile(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resume_profiles WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return self._resume_profile_row(row)

    def save_resume_profile(
        self,
        user_id: str,
        *,
        profile: dict[str, Any],
        context_text: str,
        profile_hash: str,
    ) -> dict[str, Any]:
        now = _now()
        profile_json = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM resume_profiles WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if current and current["profile_hash"] == profile_hash:
                unchanged = self._resume_profile_row(current) or {}
                unchanged["unchanged"] = True
                return unchanged

            if current:
                resume_id = current["id"]
                version = int(current["version"] or 1) + 1
                created_at = current["created_at"]
                conn.execute(
                    """INSERT INTO resume_profile_versions(
                        id,resume_id,user_id,version,profile_json,context_text,profile_hash,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        resume_id,
                        user_id,
                        version,
                        profile_json,
                        context_text,
                        profile_hash,
                        now,
                    ),
                )
                conn.execute(
                    """UPDATE resume_profiles SET
                        version=?,profile_json=?,context_text=?,profile_hash=?,updated_at=?
                       WHERE id=? AND user_id=?""",
                    (version, profile_json, context_text, profile_hash, now, resume_id, user_id),
                )
            else:
                resume_id = str(uuid4())
                version = 1
                created_at = now
                conn.execute(
                    """INSERT INTO resume_profiles(
                        id,user_id,version,profile_json,context_text,profile_hash,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (resume_id, user_id, version, profile_json, context_text, profile_hash, now, now),
                )
                conn.execute(
                    """INSERT INTO resume_profile_versions(
                        id,resume_id,user_id,version,profile_json,context_text,profile_hash,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid4()),
                        resume_id,
                        user_id,
                        version,
                        profile_json,
                        context_text,
                        profile_hash,
                        now,
                    ),
                )
            saved = conn.execute(
                "SELECT * FROM resume_profiles WHERE id=? AND user_id=?",
                (resume_id, user_id),
            ).fetchone()
        result = self._resume_profile_row(saved) or {
            "id": resume_id,
            "version": version,
            "profile": profile,
            "context_text": context_text,
            "created_at": created_at,
            "updated_at": now,
            "exists": True,
            "unchanged": False,
        }
        result["unchanged"] = False
        return result

    def list_resume_profile_versions(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id,version,profile_json,context_text,created_at
                   FROM resume_profile_versions
                   WHERE user_id=?
                   ORDER BY version DESC""",
                (user_id,),
            ).fetchall()
        return [self._resume_profile_version_row(row) for row in rows if row]

    def get_resume_profile_version(self, user_id: str, version: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT id,version,profile_json,context_text,created_at
                   FROM resume_profile_versions
                   WHERE user_id=? AND version=?""",
                (user_id, int(version)),
            ).fetchone()
        return self._resume_profile_version_row(row)

    def list_personal_document_chunks(self, user_id: str) -> list[dict[str, Any]]:
        """Return only chunks owned by the requested user for local ranking."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT c.document_id,c.chunk_index,c.content,c.embedding_json,c.embedding_mode,
                          d.title,d.source_type,d.version
                   FROM document_chunks c
                   JOIN personal_documents d ON d.id=c.document_id
                   WHERE c.user_id=? AND d.user_id=?
                   ORDER BY d.updated_at DESC,c.chunk_index ASC""",
                (user_id, user_id),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                embedding = json.loads(row["embedding_json"] or "[]")
            except json.JSONDecodeError:
                embedding = []
            if not isinstance(embedding, list):
                embedding = []
            result.append(
                {
                    "document_id": row["document_id"],
                    "chunk_index": int(row["chunk_index"]),
                    "content": row["content"],
                    "embedding": embedding,
                    "embedding_mode": row["embedding_mode"] or "local-deterministic",
                    "title": row["title"],
                    "source_type": row["source_type"],
                    "version": int(row["version"] or 1),
                }
            )
        return result

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
                "embedding_api_base": "",
                "embedding_model": "",
                "embedding_model_path": "",
                "embedding_key_configured": False,
                "llm_configured": False,
                "embedding_configured": False,
            }
        use_stub = bool(row["use_stub_provider"])
        provider_mode = "stub" if use_stub else (row["provider_mode"] or "none")
        llm_key = (
            self._session_llm_keys.get(user_id, "")
            if self.secret_storage_mode == "session"
            else row["llm_api_key"] or ""
        )
        embedding_key = (
            self._session_embedding_keys.get(user_id, "")
            if self.secret_storage_mode == "session"
            else row["embedding_api_key"] or ""
        )
        llm_configured = bool(row["llm_configured"]) and (
            provider_mode != "openai" or bool(llm_key)
        )
        embedding_configured = bool(row["embedding_configured"]) and (
            (row["embedding_mode"] or "demo") != "openai-compatible" or bool(embedding_key)
        )
        return {
            "use_stub_provider": provider_mode == "stub",
            "provider_mode": provider_mode,
            "llm_api_base": row["llm_api_base"] or "",
            "llm_model": row["llm_model"] or "",
            "llm_key_configured": bool(llm_key),
            "embedding_mode": row["embedding_mode"] or "demo",
            "embedding_api_base": row["embedding_api_base"] or "",
            "embedding_model": row["embedding_model"] or "",
            "embedding_model_path": row["embedding_model_path"] or "",
            "embedding_key_configured": bool(embedding_key),
            "llm_configured": llm_configured,
            "embedding_configured": embedding_configured,
        }

    def get_embedding_config(self, user_id: str) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT embedding_mode,embedding_api_base,embedding_model,embedding_model_path,embedding_api_key "
                "FROM settings WHERE user_id=?",
                (user_id,),
            ).fetchone()
        if not row:
            return {"mode": "demo", "api_base": "", "model": "", "model_path": "", "api_key": ""}
        api_key = (
            self._session_embedding_keys.get(user_id, "")
            if self.secret_storage_mode == "session"
            else row["embedding_api_key"] or ""
        )
        return {
            "mode": row["embedding_mode"] or "demo",
            "api_base": row["embedding_api_base"] or "",
            "model": row["embedding_model"] or "",
            "model_path": row["embedding_model_path"] or "",
            "api_key": api_key,
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
        api_key = (
            self._session_llm_keys.get(user_id, "")
            if self.secret_storage_mode == "session"
            else row["llm_api_key"] or ""
        )
        if mode == "openai" and not api_key:
            mode = "none"
        return {
            "mode": mode,
            "api_base": row["llm_api_base"] or "",
            "model": row["llm_model"] or "",
            "api_key": api_key,
        }

    def set_stub_provider(self, user_id: str, enabled: bool) -> dict[str, Any]:
        value = int(enabled)
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET use_stub_provider=?, provider_mode=?, llm_configured=?, "
                "embedding_configured=? WHERE user_id=?",
                (value, "stub" if enabled else "none", value, value, user_id),
            )
        return self.get_settings(user_id)

    def set_embedding_demo(self, user_id: str) -> dict[str, Any]:
        if self.secret_storage_mode == "session":
            self._session_embedding_keys.pop(user_id, None)
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET embedding_configured=1,embedding_mode='demo' WHERE user_id=?",
                (user_id,),
            )
        return self.get_settings(user_id)

    def set_openai_embedding(
        self, user_id: str, api_base: str, model: str, api_key: str
    ) -> dict[str, Any]:
        current = self.get_embedding_config(user_id)
        clean_base = api_base.strip()
        clean_model = model.strip()
        clean_key = api_key.strip() or current["api_key"]
        if not clean_base or not clean_model or not clean_key:
            raise ValueError("真实 Embedding 配置需要 API Base、Model 和 API Key")
        if self.secret_storage_mode == "session":
            self._session_embedding_keys[user_id] = clean_key
        stored_key = "" if self.secret_storage_mode == "session" else clean_key
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET embedding_configured=1,embedding_mode='openai-compatible',"
                "embedding_api_base=?,embedding_model=?,embedding_api_key=? WHERE user_id=?",
                (clean_base, clean_model, stored_key, user_id),
            )
        return self.get_settings(user_id)

    def set_local_embedding(self, user_id: str, model_path: str) -> dict[str, Any]:
        clean_path = model_path.strip()
        if not clean_path:
            raise ValueError("本地 Embedding 需要模型目录")
        if not Path(clean_path).is_dir():
            raise ValueError("本地 Embedding 模型目录不存在")
        if self.secret_storage_mode == "session":
            self._session_embedding_keys.pop(user_id, None)
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET embedding_configured=1,embedding_mode='local-model',"
                "embedding_model_path=? WHERE user_id=?",
                (clean_path, user_id),
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
        existing_embedding = self.get_embedding_config(user_id)
        if self.secret_storage_mode == "session":
            self._session_llm_keys[user_id] = clean_key
        stored_key = "" if self.secret_storage_mode == "session" else clean_key
        with self._connect() as conn:
            conn.execute(
                "UPDATE settings SET use_stub_provider=0, provider_mode='openai', "
                "llm_api_base=?, llm_model=?, llm_api_key=?, llm_configured=1, "
                "embedding_configured=1 WHERE user_id=?",
                (clean_base, clean_model, stored_key, user_id),
            )
            if existing_embedding["mode"] not in {"demo", "local-model", "openai-compatible"}:
                conn.execute(
                    "UPDATE settings SET embedding_mode='demo' WHERE user_id=?",
                    (user_id,),
                )
        return self.get_settings(user_id)

    def create_session(self, user_id: str, state: dict[str, Any]) -> str:
        session_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions(
                    id,user_id,target_role,resume_text,mode,topic,learning_plan_id,learning_plan_item_id,
                    question_card_id,question_card_project,question_card_resume_version,
                    graph_question_id,graph_question,graph_entry_source,graph_parent_question_id,graph_parent_question,
                    knowledge_context,question_bank_json,
                    company,position,jd_text,jd_preview_json,recording_mode,source_transcript,recording_meta_json,
                    phase,phase_question_count,is_finished,messages_json,review_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    user_id,
                    state["target_role"],
                    state["resume_text"],
                    state.get("mode", "resume"),
                    state.get("topic"),
                    state.get("learning_plan_id"),
                    state.get("learning_plan_item_id"),
                    state.get("question_card_id"),
                    state.get("question_card_project", ""),
                    state.get("question_card_resume_version"),
                    state.get("graph_question_id"),
                    state.get("graph_question", ""),
                    state.get("graph_entry_source", ""),
                    state.get("graph_parent_question_id"),
                    state.get("graph_parent_question", ""),
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

    def list_graph_feedback(self, user_id: str, topic: str) -> dict[tuple[str, str], dict[str, int]]:
        """Count candidate-origin sessions by the parent/target question edge."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT graph_parent_question_id,graph_question_id,is_finished
                   FROM sessions
                   WHERE user_id=? AND topic=? AND graph_entry_source='related_neighbor'
                     AND graph_parent_question_id IS NOT NULL AND graph_question_id IS NOT NULL""",
                (user_id, topic),
            ).fetchall()
        result: dict[tuple[str, str], dict[str, int]] = {}
        for row in rows:
            parent_id = str(row["graph_parent_question_id"] or "").strip()
            question_id = str(row["graph_question_id"] or "").strip()
            if not parent_id or not question_id:
                continue
            key = tuple(sorted((parent_id, question_id)))
            stats = result.setdefault(key, {"started_count": 0, "completed_count": 0})
            stats["started_count"] += 1
            if bool(row["is_finished"]):
                stats["completed_count"] += 1
        return result

    def list_graph_feedback_events(self, user_id: str, topic: str) -> list[dict[str, Any]]:
        """Read candidate-origin sessions for descriptive offline evaluation."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT graph_parent_question_id,graph_question_id,is_finished,review_json,updated_at
                   FROM sessions
                   WHERE user_id=? AND topic=? AND graph_entry_source='related_neighbor'
                     AND graph_parent_question_id IS NOT NULL AND graph_question_id IS NOT NULL
                   ORDER BY updated_at ASC""",
                (user_id, topic),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            score: float | None = None
            try:
                review = json.loads(row["review_json"] or "{}")
                raw_score = review.get("average_score") if isinstance(review, dict) else None
                if raw_score is not None:
                    score = round(float(raw_score), 1)
            except (TypeError, ValueError, json.JSONDecodeError):
                score = None
            events.append(
                {
                    "source": str(row["graph_parent_question_id"] or "").strip(),
                    "target": str(row["graph_question_id"] or "").strip(),
                    "is_finished": bool(row["is_finished"]),
                    "score": score,
                    "updated_at": row["updated_at"] or "",
                }
            )
        return events

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

    def delete_empty_agent_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Remove only a just-created empty conversation with no linked plan."""

        with self._connect() as conn:
            row = conn.execute(
                "SELECT messages_json FROM agent_conversations WHERE id=? AND user_id=?",
                (conversation_id, user_id),
            ).fetchone()
            if not row or json.loads(row["messages_json"] or "[]"):
                return False
            linked_plan = conn.execute(
                "SELECT 1 FROM learning_plans WHERE conversation_id=? LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if linked_plan:
                return False
            deleted = conn.execute(
                "DELETE FROM agent_conversations WHERE id=? AND user_id=?",
                (conversation_id, user_id),
            ).rowcount
        return bool(deleted)

    @staticmethod
    def _learning_plan_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "source_message": row["source_message"],
            "title": row["title"],
            "summary": row["summary"],
            "items": json.loads(row["items_json"] or "[]"),
            "source": json.loads(row["source_json"] or "{}"),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_learning_plan(
        self,
        user_id: str,
        source_message: str,
        plan: dict[str, Any],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        plan_id = str(uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO learning_plans(
                    id,user_id,conversation_id,source_message,title,summary,items_json,source_json,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan_id,
                    user_id,
                    conversation_id,
                    source_message.strip()[:1000],
                    str(plan.get("title", "个性化学习计划"))[:120],
                    str(plan.get("summary", ""))[:500],
                    json.dumps(plan.get("items", []), ensure_ascii=False),
                    json.dumps(plan.get("source", {}), ensure_ascii=False),
                    "draft",
                    now,
                    now,
                ),
            )
        return self.get_learning_plan(user_id, plan_id) or {
            "id": plan_id,
            "conversation_id": conversation_id,
            "source_message": source_message.strip()[:1000],
            "title": str(plan.get("title", "个性化学习计划"))[:120],
            "summary": str(plan.get("summary", ""))[:500],
            "items": plan.get("items", []),
            "source": plan.get("source", {}),
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }

    def get_learning_plan(self, user_id: str, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM learning_plans WHERE id=? AND user_id=?",
                (plan_id, user_id),
            ).fetchone()
        return self._learning_plan_row(row)

    def list_learning_plans(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM learning_plans WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, safe_limit),
            ).fetchall()
        return [self._learning_plan_row(row) for row in rows if row]

    def confirm_learning_plan(self, user_id: str, plan_id: str) -> dict[str, Any]:
        plan = self.get_learning_plan(user_id, plan_id)
        if not plan:
            raise LookupError("学习计划不存在")
        if plan["status"] == "draft":
            with self._connect() as conn:
                conn.execute(
                    "UPDATE learning_plans SET status='active',updated_at=? WHERE id=? AND user_id=?",
                    (_now(), plan_id, user_id),
                )
        return self.get_learning_plan(user_id, plan_id) or plan

    def complete_learning_plan_item(
        self,
        user_id: str,
        plan_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        plan = self.get_learning_plan(user_id, plan_id)
        if not plan:
            raise LookupError("学习计划不存在")
        if plan["status"] == "draft":
            raise ValueError("请先确认学习计划，再完成计划项")
        items = list(plan.get("items", []))
        found = False
        for item in items:
            if str(item.get("id", "")) == item_id:
                item["status"] = "completed"
                found = True
                break
        if not found:
            raise LookupError("计划项不存在")
        next_status = "completed" if items and all(item.get("status") == "completed" for item in items) else "active"
        with self._connect() as conn:
            conn.execute(
                "UPDATE learning_plans SET items_json=?,status=?,updated_at=? WHERE id=? AND user_id=?",
                (json.dumps(items, ensure_ascii=False), next_status, _now(), plan_id, user_id),
            )
        return self.get_learning_plan(user_id, plan_id) or plan

    def get_learning_plan_item_for_training(
        self,
        user_id: str,
        plan_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        """Resolve a user-owned, confirmed plan item for a training session."""
        plan = self.get_learning_plan(user_id, plan_id)
        if not plan:
            raise LookupError("学习计划不存在")
        if plan["status"] == "draft":
            raise ValueError("请先确认学习计划，再进入专项训练")
        for item in plan.get("items", []):
            if str(item.get("id", "")) == item_id:
                return {"plan": plan, "item": item}
        raise LookupError("计划项不存在")

    @staticmethod
    def _session_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "target_role": row["target_role"],
            "resume_text": row["resume_text"],
            "mode": row["mode"] or "resume",
            "topic": row["topic"],
            "learning_plan_id": row["learning_plan_id"],
            "learning_plan_item_id": row["learning_plan_item_id"],
            "question_card_id": row["question_card_id"],
            "question_card_project": row["question_card_project"] or "",
            "question_card_resume_version": row["question_card_resume_version"],
            "graph_question_id": row["graph_question_id"],
            "graph_question": row["graph_question"] or "",
            "graph_entry_source": row["graph_entry_source"] or "",
            "graph_parent_question_id": row["graph_parent_question_id"],
            "graph_parent_question": row["graph_parent_question"] or "",
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
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
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
