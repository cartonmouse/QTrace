from __future__ import annotations

import re
from typing import Any

from .knowledge import get_topic_bundle
from .store import Store


MAX_GRAPH_QUESTIONS = 24
GRAPH_ENTRY_SOURCES = {"question_node", "related_neighbor"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]")


def _tokens(text: str) -> set[str]:
    """Keep the graph deterministic while giving Chinese questions usable overlap."""
    raw = _TOKEN_RE.findall(text.lower())
    tokens = set(raw)
    cjk = "".join(item for item in raw if len(item) == 1 and "\u4e00" <= item <= "\u9fff")
    tokens.update(cjk[index : index + 2] for index in range(max(0, len(cjk) - 1)))
    return {token for token in tokens if token}


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _related(left: str, right: str) -> bool:
    shared = _tokens(left) & _tokens(right)
    return len(shared) >= 2 and _similarity(left, right) >= 0.12


def get_topic_question(
    user_id: str,
    topic: str,
    question_id: str,
    data_dir: str,
) -> str | None:
    """Resolve a graph question id against the current user's current topic bank."""
    match = re.fullmatch(r"question:(\d+)", question_id.strip())
    if not match:
        return None
    bundle = get_topic_bundle(user_id, topic, data_dir)
    questions = [str(item).strip() for item in bundle.get("question_bank", []) if str(item).strip()]
    questions = list(dict.fromkeys(questions))[:MAX_GRAPH_QUESTIONS]
    index = int(match.group(1)) - 1
    if index < 0 or index >= len(questions):
        return None
    return questions[index]


def resolve_graph_question_entry(
    user_id: str,
    topic: str,
    question_id: str,
    data_dir: str,
    store: Store,
    *,
    entry_source: str | None = None,
    parent_question_id: str | None = None,
) -> dict[str, str] | None:
    """Validate a graph question and, for a candidate, its parent relation."""
    clean_question_id = str(question_id or "").strip()
    clean_source = str(entry_source or "").strip() or "question_node"
    clean_parent_id = str(parent_question_id or "").strip()
    if clean_source not in GRAPH_ENTRY_SOURCES:
        raise ValueError("图谱问题来源只能是 question_node 或 related_neighbor")
    if clean_source == "question_node" and clean_parent_id:
        raise ValueError("直接图谱问题不能携带相近题父节点")
    question = get_topic_question(user_id, topic, clean_question_id, data_dir)
    if not question:
        return None
    parent_question = ""
    if clean_source == "related_neighbor":
        if not clean_parent_id:
            raise ValueError("相近题训练需要提供父问题节点")
        if clean_parent_id == clean_question_id:
            raise ValueError("相近题父节点不能与目标问题相同")
        parent_question = get_topic_question(user_id, topic, clean_parent_id, data_dir) or ""
        if not parent_question:
            return None
        graph = build_topic_graph(user_id, topic, data_dir, store)
        parent_node = next(
            (node for node in graph["nodes"] if node.get("id") == clean_parent_id),
            None,
        )
        if not parent_node or clean_question_id not in parent_node.get("related_question_ids", []):
            return None
    return {
        "id": clean_question_id,
        "topic": topic,
        "question": question,
        "entry_source": clean_source,
        "parent_question_id": clean_parent_id,
        "parent_question": parent_question,
    }


def build_topic_graph(user_id: str, topic: str, data_dir: str, store: Store) -> dict[str, Any]:
    """Build a small user-scoped question graph from existing knowledge and SM-2 data.

    This is intentionally a rebuildable read model, not a second source of truth:
    topic files and review_items remain authoritative.
    """
    bundle = get_topic_bundle(user_id, topic, data_dir)
    due_reviews = store.list_due_reviews(user_id, topic=topic, limit=12)
    topic_profile = store.get_topic_profile(user_id, topic) or {}
    feedback_by_edge = store.list_graph_feedback(user_id, topic)
    due_points = [str(item.get("point", "")).strip() for item in due_reviews if item.get("point")]
    weak_points = [str(item).strip() for item in topic_profile.get("weak_points", []) if str(item).strip()]

    root_id = f"topic:{topic}"
    nodes: list[dict[str, Any]] = [
        {
            "id": root_id,
            "type": "topic",
            "label": bundle["topic_name"],
            "status": "root",
            "topic": topic,
        }
    ]
    links: list[dict[str, Any]] = []
    questions = [str(item).strip() for item in bundle.get("question_bank", []) if str(item).strip()]
    questions = list(dict.fromkeys(questions))[:MAX_GRAPH_QUESTIONS]
    for index, question in enumerate(questions):
        question_id = f"question:{index + 1}"
        related_due = next((point for point in due_points if _similarity(question, point) >= 0.12), "")
        related_weak = next((point for point in weak_points if _similarity(question, point) >= 0.12), "")
        status = "due" if related_due else "weak" if related_weak else "ready"
        nodes.append(
            {
                "id": question_id,
                "type": "question",
                "label": question[:100],
                "question": question,
                "status": status,
                "focus_area": related_due or related_weak or "综合能力",
                "topic": topic,
                "related_question_ids": [],
            }
        )
        links.append({"source": root_id, "target": question_id, "relation": "contains", "weight": 1.0})

    for index, point in enumerate(due_points):
        review_id = f"review:{index + 1}"
        nodes.append(
            {
                "id": review_id,
                "type": "review",
                "label": point[:100],
                "status": "due",
                "focus_area": point,
                "topic": topic,
            }
        )
        links.append({"source": root_id, "target": review_id, "relation": "reviews", "weight": 1.0})

    question_nodes = [node for node in nodes if node["type"] == "question"]
    for index, left in enumerate(question_nodes):
        for right in question_nodes[index + 1 :]:
            similarity = _similarity(left["question"], right["question"])
            if _related(left["question"], right["question"]):
                feedback = feedback_by_edge.get(tuple(sorted((left["id"], right["id"]))), {})
                links.append(
                    {
                        "source": left["id"],
                        "target": right["id"],
                        "relation": "related",
                        "weight": round(similarity, 3),
                        "started_count": int(feedback.get("started_count", 0)),
                        "completed_count": int(feedback.get("completed_count", 0)),
                    }
                )

    for node in question_nodes:
        for review_index, point in enumerate(due_points):
            similarity = _similarity(node["question"], point)
            if similarity >= 0.12:
                links.append(
                    {
                        "source": node["id"],
                        "target": f"review:{review_index + 1}",
                        "relation": "revisits",
                        "weight": round(similarity, 3),
                    }
                )

    related_by_id: dict[str, set[str]] = {node["id"]: set() for node in question_nodes}
    for link in links:
        if link["relation"] != "related":
            continue
        related_by_id.setdefault(link["source"], set()).add(link["target"])
        related_by_id.setdefault(link["target"], set()).add(link["source"])
    for node in question_nodes:
        node["related_question_ids"] = sorted(related_by_id.get(node["id"], set()))

    return {
        "topic": topic,
        "topic_name": bundle["topic_name"],
        "mode": "deterministic_question_graph",
        "nodes": nodes,
        "links": links,
        "summary": {
            "question_count": len(question_nodes),
            "due_review_count": len(due_points),
            "weak_point_count": len(weak_points),
            "link_count": len(links),
        },
    }


def build_topic_feedback_report(
    user_id: str,
    topic: str,
    data_dir: str,
    store: Store,
) -> dict[str, Any]:
    """Build descriptive candidate metrics without writing back to learning facts."""
    graph = build_topic_graph(user_id, topic, data_dir, store)
    events_by_edge: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in store.list_graph_feedback_events(user_id, topic):
        source = str(event.get("source", "")).strip()
        target = str(event.get("target", "")).strip()
        if source and target:
            events_by_edge.setdefault(tuple(sorted((source, target))), []).append(event)

    related_links = [link for link in graph["links"] if link.get("relation") == "related"]
    feedback_edges: list[dict[str, Any]] = []
    total_started = 0
    total_completed = 0
    observed_edge_count = 0
    for link in related_links:
        key = tuple(sorted((str(link["source"]), str(link["target"]))))
        events = events_by_edge.get(key, [])
        started_count = len(events)
        completed_count = sum(1 for event in events if event.get("is_finished"))
        total_started += started_count
        total_completed += completed_count
        if started_count:
            observed_edge_count += 1
        scores = [float(event["score"]) for event in events if event.get("is_finished") and event.get("score") is not None]
        score_delta = round(scores[-1] - scores[0], 1) if len(scores) >= 2 else None
        feedback_edges.append(
            {
                "source": link["source"],
                "target": link["target"],
                "weight": float(link.get("weight", 0) or 0),
                "started_count": started_count,
                "completed_count": completed_count,
                "completion_rate": round(completed_count / started_count, 3) if started_count else 0.0,
                "average_score": round(sum(scores) / len(scores), 1) if scores else None,
                "score_delta": score_delta,
                "repeat_rate": round(max(started_count - 1, 0) / started_count, 3) if started_count else 0.0,
            }
        )
    feedback_edges.sort(key=lambda item: (-item["started_count"], -item["completed_count"], item["source"], item["target"]))
    return {
        "topic": graph["topic"],
        "topic_name": graph["topic_name"],
        "edges": feedback_edges,
        "summary": {
            "candidate_edge_count": len(related_links),
            "observed_edge_count": observed_edge_count,
            "started_count": total_started,
            "completed_count": total_completed,
        },
    }
