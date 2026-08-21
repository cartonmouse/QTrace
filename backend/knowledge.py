from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any


MAX_CORE_CHARS = 60_000
MAX_HIGH_FREQ_CHARS = 40_000
DEFAULT_CONTEXT_BUDGET = 8_000
DEFAULT_TOP_K = 6
_KEY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]")


class KnowledgeError(ValueError):
    """Raised when a topic or knowledge file is invalid."""


DEFAULT_TOPICS: list[dict[str, str]] = [
    {
        "key": "python",
        "name": "Python",
        "icon": "⌘",
        "content": """# Python\n\n## 数据模型\n- 需要区分可变对象与不可变对象，理解引用、赋值和拷贝之间的关系。\n- `dict`、`list`、`set` 的选择要结合查找、顺序、去重和内存开销。\n\n## 函数与装饰器\n- 闭包会捕获外层变量；装饰器本质上是接收函数并返回新函数的高阶函数。\n- 面试回答要说明元数据保留、参数传递和副作用边界。\n\n## 异步与并发\n- `asyncio` 适合 IO 等待密集型任务；线程和进程需要结合 GIL、共享状态与进程间通信判断。\n- 生产代码要处理超时、取消、异常传播和资源释放。\n""",
        "questions": """- Python 中 list、tuple、set、dict 的底层特性和适用场景有什么差异？\n- 装饰器、闭包和 `functools.wraps` 分别解决什么问题？\n- GIL 对多线程有什么影响？什么时候选择多进程或 asyncio？\n- 如何定位一个 Python 服务的性能瓶颈和内存泄漏？\n""",
    },
    {
        "key": "rag",
        "name": "RAG",
        "icon": "⌁",
        "content": """# RAG\n\n## 基本链路\n- 文档经过清洗、切分和元数据标注后建立索引；查询阶段完成召回、过滤、重排和上下文拼装。\n- 生成模型不是检索系统本身，应该区分检索质量、上下文质量和答案质量。\n\n## 切分与召回\n- chunk 太大可能带入噪声并浪费上下文，太小则可能丢失语义；要结合文档结构、问题类型和重叠策略验证。\n- 向量检索擅长语义相似，关键词检索擅长专有名词和精确匹配，混合检索可以互补。\n\n## 评估与生产问题\n- 至少分别评估召回率、上下文相关性、答案正确性、延迟和成本。\n- 还要考虑数据更新、权限隔离、缓存、引用、幻觉和失败降级。\n""",
        "questions": """- RAG 为什么需要 chunk？切分过大或过小分别会造成什么问题？\n- 向量检索、BM25 和重排各自解决什么问题？\n- 如何定位“知识库里有答案但模型没有答对”？\n- 如何设计 RAG 的离线评估集和线上观测指标？\n""",
    },
    {
        "key": "agent",
        "name": "Agent",
        "icon": "✦",
        "content": """# Agent\n\n## Agent 与工作流\n- 固定步骤、可预测分支优先使用 workflow；需要根据中间结果选择工具或路径时，Agent 才有价值。\n- 设计时要明确状态、工具权限、终止条件和人工介入点。\n\n## 工具调用与可靠性\n- 工具参数必须校验，执行结果要结构化返回；失败要区分可重试、不可重试和需要人工处理。\n- 重试要考虑幂等、超时、预算和副作用，不能简单无限重试。\n\n## 记忆与评估\n- 短期状态保存当前任务轨迹，长期记忆只保存经过筛选的稳定事实或复盘信号。\n- 评估要关注任务完成率、工具调用正确率、轨迹质量、延迟、成本和安全违规率。\n""",
        "questions": """- 什么问题适合 Agent，什么问题用普通 workflow 更好？\n- 工具调用失败时如何设计重试、超时和幂等？\n- Agent 的短期记忆和长期记忆应该分别存什么？\n- 如何评估一个 Agent 是否真的比固定流程更好？\n""",
    },
]


def _user_root(user_id: str, data_dir: str | Path) -> Path:
    if not user_id or Path(user_id).name != user_id or user_id in {".", ".."}:
        raise KnowledgeError("用户目录无效")
    return Path(data_dir) / "users" / user_id


def _topics_path(user_id: str, data_dir: str) -> Path:
    return _user_root(user_id, data_dir) / "topics.json"


def _knowledge_root(user_id: str, data_dir: str) -> Path:
    return _user_root(user_id, data_dir) / "knowledge"


def _high_freq_root(user_id: str, data_dir: str) -> Path:
    return _user_root(user_id, data_dir) / "high_freq"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _topic_dir(topic: str, entry: dict[str, Any], data_dir: str) -> Path:
    directory = str(entry.get("dir") or topic)
    if not _KEY_RE.fullmatch(topic) or not _KEY_RE.fullmatch(directory):
        raise KnowledgeError("训练领域存储路径无效")
    root = _knowledge_root(entry["user_id"], data_dir).resolve()
    path = (root / directory).resolve()
    if root not in path.parents and path != root:
        raise KnowledgeError("训练领域存储路径越界")
    return path


def _with_user(topic: str, entry: dict[str, Any], user_id: str) -> dict[str, Any]:
    value = dict(entry)
    value["user_id"] = user_id
    return value


def ensure_topics(user_id: str, data_dir: str | Path) -> dict[str, dict[str, str]]:
    """Seed a small, relevant topic set only on the first access for a user."""
    path = _topics_path(user_id, data_dir)
    existing = _read_json(path, None)
    if existing is None:
        topics = {
            item["key"]: {"name": item["name"], "icon": item["icon"], "dir": item["key"]}
            for item in DEFAULT_TOPICS
        }
        _write_json(path, topics)
        for item in DEFAULT_TOPICS:
            entry = _with_user(item["key"], topics[item["key"]], user_id)
            directory = _topic_dir(item["key"], entry, str(data_dir))
            directory.mkdir(parents=True, exist_ok=True)
            readme = directory / "README.md"
            if not readme.exists():
                readme.write_text(item["content"], encoding="utf-8")
            high_freq = _high_freq_root(user_id, data_dir) / f"{item['key']}.md"
            if not high_freq.exists():
                high_freq.parent.mkdir(parents=True, exist_ok=True)
                high_freq.write_text(item["questions"], encoding="utf-8")
        return topics
    if not isinstance(existing, dict):
        raise KnowledgeError("topics.json 格式无效")
    return {
        str(key): {
            "name": str(value.get("name") or key),
            "icon": str(value.get("icon") or "📝"),
            "dir": str(value.get("dir") or key),
        }
        for key, value in existing.items()
        if isinstance(value, dict)
    }


def save_topics(user_id: str, topics: dict[str, dict[str, str]], data_dir: str | Path) -> None:
    _write_json(_topics_path(user_id, data_dir), topics)


def list_topics(user_id: str, data_dir: str | Path) -> dict[str, dict[str, str]]:
    return ensure_topics(user_id, data_dir)


def _require_topic(user_id: str, topic: str, data_dir: str | Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    if not _KEY_RE.fullmatch(topic):
        raise KnowledgeError("训练领域 key 无效")
    topics = ensure_topics(user_id, data_dir)
    if topic not in topics:
        raise KnowledgeError(f"未知训练领域：{topic}")
    return topics, topics[topic]


def create_topic(user_id: str, name: str, icon: str, key: str, data_dir: str | Path) -> str:
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 80:
        raise KnowledgeError("训练领域名称不能为空且不能超过 80 个字符")
    clean_key = re.sub(r"[^a-zA-Z0-9_-]", "", key.strip()) if key.strip() else uuid.uuid4().hex[:8]
    if not _KEY_RE.fullmatch(clean_key):
        raise KnowledgeError("训练领域 key 只能包含字母、数字、下划线和短横线")
    topics = ensure_topics(user_id, data_dir)
    if clean_key in topics:
        raise KnowledgeError(f"训练领域已存在：{clean_key}")
    topics[clean_key] = {"name": clean_name, "icon": icon.strip() or "📝", "dir": clean_key}
    save_topics(user_id, topics, data_dir)
    entry = _with_user(clean_key, topics[clean_key], user_id)
    directory = _topic_dir(clean_key, entry, str(data_dir))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "README.md").write_text(f"# {clean_name}\n\n请补充这个领域的核心知识。\n", encoding="utf-8")
    return clean_key


def delete_topic(user_id: str, topic: str, data_dir: str | Path) -> None:
    topics, entry = _require_topic(user_id, topic, data_dir)
    directory = _topic_dir(topic, _with_user(topic, entry, user_id), str(data_dir))
    if directory.exists():
        shutil.rmtree(directory)
    high_freq = _high_freq_root(user_id, data_dir) / f"{topic}.md"
    high_freq.unlink(missing_ok=True)
    del topics[topic]
    save_topics(user_id, topics, data_dir)


def _safe_filename(filename: str) -> str:
    clean = filename.strip()
    if not clean or "/" in clean or "\\" in clean or Path(clean).name != clean:
        raise KnowledgeError("知识文件名不能包含路径")
    if not clean.endswith(".md") or len(clean) > 120 or clean in {".", ".."}:
        raise KnowledgeError("知识文件名必须是 120 个字符以内的 .md 文件")
    return clean


def _core_directory(user_id: str, topic: str, data_dir: str | Path) -> Path:
    _, entry = _require_topic(user_id, topic, data_dir)
    directory = _topic_dir(topic, _with_user(topic, entry, user_id), str(data_dir))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_core_files(user_id: str, topic: str, data_dir: str | Path) -> list[dict[str, str]]:
    directory = _core_directory(user_id, topic, data_dir)
    return [
        {"filename": path.name, "content": path.read_text(encoding="utf-8")}
        for path in sorted(directory.glob("*.md"))
        if path.is_file()
    ]


def create_core_file(user_id: str, topic: str, filename: str, content: str, data_dir: str | Path) -> str:
    path = _core_directory(user_id, topic, data_dir) / _safe_filename(filename)
    if path.exists():
        raise KnowledgeError(f"知识文件已存在：{path.name}")
    if len(content) > MAX_CORE_CHARS:
        raise KnowledgeError("知识文件不能超过 60,000 个字符")
    path.write_text(content, encoding="utf-8")
    return path.name


def update_core_file(user_id: str, topic: str, filename: str, content: str, data_dir: str | Path) -> None:
    path = _core_directory(user_id, topic, data_dir) / _safe_filename(filename)
    if not path.exists():
        raise KnowledgeError(f"知识文件不存在：{path.name}")
    if len(content) > MAX_CORE_CHARS:
        raise KnowledgeError("知识文件不能超过 60,000 个字符")
    path.write_text(content, encoding="utf-8")


def delete_core_file(user_id: str, topic: str, filename: str, data_dir: str | Path) -> None:
    path = _core_directory(user_id, topic, data_dir) / _safe_filename(filename)
    if not path.exists():
        raise KnowledgeError(f"知识文件不存在：{path.name}")
    path.unlink()


def get_high_freq(user_id: str, topic: str, data_dir: str | Path) -> str:
    _require_topic(user_id, topic, data_dir)
    path = _high_freq_root(user_id, data_dir) / f"{topic}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def update_high_freq(user_id: str, topic: str, content: str, data_dir: str | Path) -> None:
    _require_topic(user_id, topic, data_dir)
    if len(content) > MAX_HIGH_FREQ_CHARS:
        raise KnowledgeError("高频题库不能超过 40,000 个字符")
    path = _high_freq_root(user_id, data_dir) / f"{topic}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _chunk_text(text: str, chunk_size: int = 1_000, overlap: int = 120) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > chunk_size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _all_core_chunks(user_id: str, topic: str, data_dir: str | Path) -> list[tuple[str, str]]:
    files = list_core_files(user_id, topic, data_dir)
    chunks: list[tuple[str, str]] = []
    for file in files:
        chunks.extend((chunk, file["filename"]) for chunk in _chunk_text(file["content"]))
    return chunks


def retrieve_topic_context(
    user_id: str,
    topic: str,
    queries: list[str],
    data_dir: str | Path,
    *,
    top_k: int = DEFAULT_TOP_K,
    char_budget: int = DEFAULT_CONTEXT_BUDGET,
) -> str:
    """Small local keyword retriever with the same seam a vector retriever can replace."""
    chunks = _all_core_chunks(user_id, topic, data_dir)
    if not chunks:
        return ""
    full = "\n\n---\n\n".join(chunk for chunk, _ in chunks)
    if len(full) <= char_budget:
        return full

    query_tokens = _tokens(" ".join(queries))
    scored: list[tuple[float, int, str]] = []
    for index, (chunk, source) in enumerate(chunks):
        chunk_tokens = _tokens(chunk)
        overlap = len(query_tokens & chunk_tokens)
        exact_bonus = sum(1 for query in queries if query.strip() and query.strip().lower() in chunk.lower())
        score = overlap + exact_bonus * 2
        scored.append((score, -index, f"[{source}]\n{chunk}"))
    selected = [item[2] for item in sorted(scored, reverse=True)[:max(1, top_k)]]
    return "\n\n---\n\n".join(selected)[:char_budget]


def parse_question_bank(content: str) -> list[str]:
    questions: list[str] = []
    for line in content.splitlines():
        clean = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if clean and not clean.startswith("#") and len(clean) >= 8:
            questions.append(clean)
    return questions


def get_topic_bundle(user_id: str, topic: str, data_dir: str | Path) -> dict[str, Any]:
    topics, entry = _require_topic(user_id, topic, data_dir)
    high_freq = get_high_freq(user_id, topic, data_dir)
    context = retrieve_topic_context(
        user_id,
        topic,
        [entry.get("name", topic), *parse_question_bank(high_freq)[:6]],
        data_dir,
    )
    return {
        "topic": topic,
        "topic_name": entry.get("name", topic),
        "topics": topics,
        "knowledge_context": context,
        "question_bank": parse_question_bank(high_freq),
    }
