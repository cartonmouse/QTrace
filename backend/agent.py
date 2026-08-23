from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from .graph import build_topic_graph, resolve_graph_question_entry
from .knowledge import KnowledgeError
from .provider import OpenAICompatibleProvider, ProviderError
from .personal_documents import PersonalDocumentService
from .resume import ResumeError, get_resume_text
from .store import Store
from .structured_resume import StructuredResumeService


class AgentProviderError(ProviderError):
    """A model failure with the stage of the two-step Agent pipeline."""

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        state: str = "unknown",
        conversation_id: str | None = None,
    ):
        self.stage = stage
        self.state = state
        self.conversation_id = conversation_id
        super().__init__(message)


AGENT_TOOLS: dict[str, str] = {
    "read_profile": "读取用户的全局画像、领域掌握度和长期薄弱点",
    "read_due_reviews": "读取今天到期的 SM-2 复习任务",
    "read_recent_sessions": "读取最近几次训练的模式、岗位、分数和复盘薄弱点",
    "read_resume": "读取用户已经上传的简历文本",
    "read_question_card": "读取当前结构化简历中的指定项目追问卡",
    "read_graph_question": "读取当前主题知识图谱中的指定问题节点",
    "search_personal_documents": "只读检索用户主动保存的项目资料、技术方案和学习笔记",
    "create_learning_plan": "根据已读取的画像和复习上下文生成并保存一份个性化学习计划",
}

AGENT_READ_TOOLS = {
    "read_profile",
    "read_due_reviews",
    "read_recent_sessions",
    "read_resume",
    "read_question_card",
    "read_graph_question",
    "search_personal_documents",
}
AGENT_WRITE_TOOLS = {"create_learning_plan"}
AGENT_WRITE_REQUIREMENTS: dict[str, set[str]] = {
    "create_learning_plan": {"read_profile", "read_due_reviews", "read_recent_sessions"},
}
PERSONAL_DOCUMENT_TERMS = (
    "个人文档",
    "项目文档",
    "技术方案",
    "项目说明",
    "资料库",
    "资料",
    "文档",
    "材料",
    "笔记",
    "个人记忆",
    "personal document",
    "project notes",
)
PLAN_REQUEST_KEYWORDS = (
    "学习计划",
    "复习计划",
    "训练计划",
    "安排学习",
    "安排训练",
    "安排下一轮",
    "制定计划",
    "生成计划",
    "规划今天",
    "学习安排",
)
PLAN_REQUEST_NEGATIONS = (
    "不要",
    "别",
    "不必",
    "无需",
    "不需要",
    "不用",
    "暂不",
    "暂时不要",
    "先不要",
    "先不",
    "不想",
)


class AgentModel(Protocol):
    def plan(self, message: str) -> dict[str, Any]: ...

    def answer(
        self,
        message: str,
        history: list[dict[str, Any]],
        tool_context: dict[str, Any],
    ) -> str: ...


def _default_tool_calls(message: str) -> list[dict[str, str]]:
    """Return a small, deterministic read-only plan for the local provider."""
    lowered = message.lower()
    calls = [
        {"name": "read_profile", "reason": "先确认长期画像和领域掌握度"},
        {"name": "read_due_reviews", "reason": "检查今天是否有应该优先复习的薄弱点"},
    ]
    if any(word in lowered for word in ("历史", "训练", "表现", "进步", "趋势", "复盘")):
        calls.append({"name": "read_recent_sessions", "reason": "补充近期训练轨迹"})
    if any(word in lowered for word in ("简历", "项目", "经历", "岗位匹配")):
        calls.append({"name": "read_resume", "reason": "核对个人简历和项目证据"})
    if _is_document_search_request(message):
        calls.append({"name": "search_personal_documents", "reason": "检索用户自己的项目资料和学习笔记"})
    if _is_plan_request(message):
        if not any(item["name"] == "read_recent_sessions" for item in calls):
            calls.append({"name": "read_recent_sessions", "reason": "补充近期训练轨迹，安排训练优先级"})
        calls.append({"name": "create_learning_plan", "reason": "用户明确请求生成并保存个性化学习计划"})
    return calls


def _is_plan_request(message: str) -> bool:
    lowered = message.lower()
    if _is_negated_plan_request(message):
        return False
    return any(keyword in message for keyword in PLAN_REQUEST_KEYWORDS) or any(
        keyword in lowered for keyword in ("learning plan", "study plan", "make a plan", "schedule")
    )


def _is_negated_plan_request(message: str) -> bool:
    """Avoid treating a negated plan mention as authorization for a write tool."""
    lowered = message.lower()
    plan_terms = (*PLAN_REQUEST_KEYWORDS, "learning plan", "study plan", "make a plan", "schedule")
    for term in plan_terms:
        for negation in PLAN_REQUEST_NEGATIONS:
            if re.search(rf"{re.escape(negation)}.{{0,12}}{re.escape(term)}", message, flags=re.IGNORECASE):
                return True
            if re.search(rf"{re.escape(term)}.{{0,8}}{re.escape(negation)}", message, flags=re.IGNORECASE):
                return True
    return "do not" in lowered and any(term in lowered for term in plan_terms if term.isascii())


def _is_document_search_request(message: str) -> bool:
    lowered = message.lower()
    if not any(term in lowered for term in PERSONAL_DOCUMENT_TERMS):
        return False
    for negation in ("不要", "别", "无需", "不需要", "不用", "暂不", "先不"):
        if re.search(rf"{re.escape(negation)}.{{0,8}}(?:文档|资料|笔记|记忆|personal document)", message, flags=re.IGNORECASE):
            return False
    return True


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        value = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ProviderError("Agent 规划结果不是合法 JSON") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ProviderError("Agent 规划结果不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("Agent 规划结果必须是 JSON 对象")
    return value


def _normalize_plan(
    raw: dict[str, Any],
    message: str,
    question_card_id: str | None = None,
    graph_question_id: str | None = None,
) -> dict[str, Any]:
    calls: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw.get("tool_calls", []):
        if isinstance(item, str):
            name, reason = item, "根据当前问题读取相关上下文"
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            reason = str(item.get("reason", "根据当前问题读取相关上下文")).strip()
        else:
            continue
        if (
            name in AGENT_TOOLS
            and name not in seen
            and (name not in AGENT_WRITE_TOOLS or _is_plan_request(message))
        ):
            calls.append({"name": name, "reason": reason[:160]})
            seen.add(name)
    if not calls:
        calls = _default_tool_calls(message)
    elif _is_plan_request(message):
        required_reads = (
            ("read_profile", "先确认长期画像和领域掌握度"),
            ("read_due_reviews", "检查今天是否有应该优先复习的薄弱点"),
            ("read_recent_sessions", "补充近期训练轨迹，安排训练优先级"),
        )
        for name, reason in required_reads:
            if name not in seen:
                calls.append({"name": name, "reason": reason})
                seen.add(name)
        if "create_learning_plan" not in seen:
            calls.append({"name": "create_learning_plan", "reason": "用户明确请求生成并保存个性化学习计划"})
            seen.add("create_learning_plan")
    if _is_document_search_request(message) and "search_personal_documents" not in seen:
        calls.append({"name": "search_personal_documents", "reason": "检索用户自己的项目资料和学习笔记"})
        seen.add("search_personal_documents")
    read_calls = [item for item in calls if item["name"] in AGENT_READ_TOOLS]
    if question_card_id and "read_question_card" not in seen:
        read_calls = [
            {"name": "read_question_card", "reason": "核对用户指定的项目追问卡和简历版本"},
            *[item for item in read_calls if item["name"] != "read_question_card"],
        ]
    if graph_question_id and "read_graph_question" not in seen:
        read_calls = [
            {"name": "read_graph_question", "reason": "核对当前主题知识图谱中的指定问题"},
            *[item for item in read_calls if item["name"] != "read_graph_question"],
        ]
    write_calls = [item for item in calls if item["name"] in AGENT_WRITE_TOOLS]
    return {
        "intent": str(raw.get("intent", "个性化面试成长建议")).strip()[:120]
        or "个性化面试成长建议",
        "tool_calls": [*read_calls[:5], *write_calls[:1]],
    }


class StubAgentModel:
    """Offline Agent model used to verify the plan/tool/result contract."""

    def plan(self, message: str) -> dict[str, Any]:
        return _normalize_plan({"intent": "本地个性化训练建议"}, message)

    def answer(
        self,
        message: str,
        history: list[dict[str, Any]],
        tool_context: dict[str, Any],
    ) -> str:
        profile = tool_context.get("read_profile", {})
        due = tool_context.get("read_due_reviews", [])
        recent = tool_context.get("read_recent_sessions", [])
        tool_failures = tool_context.get("tool_failures", [])
        resume = tool_context.get("read_resume", {})
        question_card = tool_context.get("read_question_card", {})
        graph_question = tool_context.get("read_graph_question", {})
        documents = tool_context.get("search_personal_documents", [])
        created_plan = tool_context.get("create_learning_plan")
        weak_points = profile.get("weak_points", [])
        topic_mastery = profile.get("topic_mastery", [])

        lines = [
            "我是问迹 QTrace 个人成长 Agent（本地演示模型）。我先读取了你的长期画像，再根据问题选择了受控工具。",
        ]
        if "read_profile" in tool_context:
            lines.append(
                f"当前已完成 {profile.get('completed_sessions', 0)} 次训练，整体掌握度为 {profile.get('mastery_score', 0)} / 10。"
            )
        else:
            lines.append("长期画像本次未读取成功，因此我不对当前掌握度下结论。")
        if topic_mastery:
            topic_text = "、".join(
                f"{item.get('topic', '未命名')} {item.get('mastery_score', 0)}/10"
                for item in topic_mastery[:4]
            )
            lines.append(f"领域掌握度：{topic_text}。")
        if weak_points:
            lines.append(f"当前长期薄弱点：{'；'.join(str(item) for item in weak_points[:4])}。")
        if "read_due_reviews" not in tool_context:
            lines.append("今日复习队列本次未读取成功，因此我不判断具体到期项。")
        elif due:
            lines.append(
                "今天建议优先复习："
                + "、".join(str(item.get("point", "")) for item in due[:4])
                + "。"
            )
        else:
            lines.append("今天没有到期复习项，可以用一轮专项训练产生新的评估信号。")
        if recent:
            lines.append(f"我还看到了最近 {len(recent)} 次训练记录，可以据此观察分数和薄弱点变化。")
        if resume.get("available"):
            source_label = "结构化简历" if resume.get("source") == "structured-editor" else "简历文本"
            lines.append(f"已读取{source_label} {resume.get('text_chars', 0)} 字，后续可以用它核对项目回答。")
        if question_card:
            lines.append(
                f"已读取项目追问卡：{question_card.get('project_name', '未命名项目')} / "
                f"{question_card.get('category', '未命名类别')}（结构化简历 v{question_card.get('resume_version', 0)}）。"
            )
        if graph_question:
            lines.append(
                f"已读取知识图谱问题：{graph_question.get('topic', '未命名主题')} / "
                f"{graph_question.get('id', '未命名节点')}：{graph_question.get('question', '')}。"
            )
            related_questions = graph_question.get("related_questions", [])
            if related_questions:
                lines.append(
                    "图谱还提供了可选后续练习："
                    + "、".join(
                        f"{str(item.get('question', ''))[:70]}（入口 {int(item.get('started_count', 0) or 0)} 次，完成 {int(item.get('completed_count', 0) or 0)} 次）"
                        for item in related_questions[:3]
                    )
                    + "。"
                )
        if documents:
            lines.append(f"我检索到 {len(documents)} 个个人文档片段，可以用它们核对项目事实：")
            for item in documents[:3]:
                lines.append(
                    f"- [{item.get('citation', item.get('title', '未命名文档'))}]："
                    f"{str(item.get('content', ''))[:220]}"
                )
        if created_plan:
            lines.append(
                f"我已经生成了一份{created_plan.get('title', '个性化学习计划')}草稿，共 {len(created_plan.get('items', []))} 项；确认后才会进入执行状态。"
            )
            for item in created_plan.get("items", [])[:3]:
                lines.append(
                    f"- {item.get('priority', 'P1')}：{item.get('topic', '综合能力')} / "
                    f"{item.get('point', '')}（{item.get('duration_minutes', 0)} 分钟）"
                )
        if tool_failures:
            lines.append(
                f"有 {len(tool_failures)} 个工具未能完成读取或被安全跳过；以上建议只基于成功获得的上下文，不补造缺失数据。"
            )
        lines.extend(
            [
                "下一步建议：先完成一个到期薄弱点的专项回答，再用项目背景、行动、结果和验证方式补齐证据。",
                f"你刚才的问题是：{message[:160]}",
            ]
        )
        return "\n".join(lines)


class OpenAIAgentModel:
    """Two-step Agent model: structured planning, then grounded response."""

    def __init__(self, provider: OpenAICompatibleProvider):
        self.provider = provider

    def plan(self, message: str) -> dict[str, Any]:
        raw = self.provider.structured_chat(
            "你是一个面试成长 Agent 的规划器。只返回 JSON，不要 Markdown。"
            "可用工具只有："
            + json.dumps(AGENT_TOOLS, ensure_ascii=False)
            + '。JSON 格式为 {"intent": string, "tool_calls": [{"name": string, "reason": string}]}。'
            "当用户询问自己的项目资料、技术方案、学习笔记或个人文档时，调用 search_personal_documents；"
            "如果请求带有指定的项目追问卡，先调用 read_question_card 核对卡片；"
            "只有当用户明确要求制定、生成或安排学习计划时，才调用 create_learning_plan；"
            "该工具必须在读取画像和复习队列之后调用。",
            f"用户问题：\n{message[:6000]}",
        )
        return _normalize_plan(_parse_json_object(raw), message)

    def answer(
        self,
        message: str,
        history: list[dict[str, Any]],
        tool_context: dict[str, Any],
    ) -> str:
        history_text = "\n".join(
            f"{item.get('role', 'user')}: {str(item.get('content', ''))[:1600]}"
            for item in history[-8:]
        ) or "暂无历史对话"
        context_text = json.dumps(tool_context, ensure_ascii=False)[:24000]
        return self.provider.structured_chat(
            "你是问迹 QTrace 的个人成长 Agent。你的任务是结合经过工具读取的用户画像、"
            "复习队列、训练历史、简历和个人文档证据，为用户给出具体、诚实、可执行的中文建议。"
            "只能使用工具结果中的事实；没有读取到的内容要明确说明。"
            "如果工具结果中包含 create_learning_plan，说明计划草稿已经生成但仍需用户确认；"
            "只有确认接口返回 active 后，才能说计划进入执行状态。除此之外不要声称修改了任何数据。"
            "引用个人文档时保留工具结果中的 citation，不要编造不存在的来源。"
            "如果工具结果中包含 tool_failures，明确说明对应上下文没有读取成功或写工具被安全跳过，不能补造缺失数据。"
            "先给结论，再给下一步训练建议；必要时给出一道针对性练习题。",
            f"当前用户问题：\n{message[:6000]}\n\n"
            f"近期对话：\n{history_text}\n\n"
            f"工具读取结果：\n{context_text}",
        ).strip()


def build_agent_model(config: dict[str, str]) -> AgentModel:
    if config.get("mode") == "stub":
        return StubAgentModel()
    if config.get("mode") == "openai":
        return OpenAIAgentModel(
            OpenAICompatibleProvider(
                api_base=config.get("api_base", ""),
                api_key=config.get("api_key", ""),
                model=config.get("model", ""),
            )
        )
    raise ProviderError("请先在模型设置中启用本地演示模型或配置真实 LLM")


def _resume_context(
    user_id: str,
    data_dir: Path,
    structured_resume_service: StructuredResumeService | None = None,
) -> dict[str, Any]:
    try:
        text, filename = get_resume_text(user_id, data_dir)
    except ResumeError:
        text, filename = "", ""
    if text.strip():
        return {
            "available": True,
            "filename": filename,
            "text_chars": len(text),
            "text": text[:8000],
            "source": "pdf",
        }
    if structured_resume_service:
        structured = structured_resume_service.get_profile(user_id)
        structured_text = str(structured.get("context_text", ""))
        if structured_text.strip():
            return {
                "available": True,
                "filename": f"结构化简历 v{structured.get('version', 0)}",
                "text_chars": len(structured_text),
                "text": structured_text[:8000],
                "source": "structured-editor",
            }
    return {
        "available": False,
        "filename": "",
        "text_chars": 0,
        "text": "",
        "source": "none",
    }


def _recent_session_context(store: Store, user_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for session in store.list_sessions(user_id)[:8]:
        review = session.get("review") or {}
        result.append(
            {
                "mode": session.get("mode", "resume"),
                "target_role": session.get("target_role", ""),
                "topic": session.get("topic") or "",
                "position": session.get("position") or "",
                "average_score": review.get("average_score", 0),
                "weak_points": review.get("weak_points", [])[:5],
                "action_items": review.get("action_items", [])[:3],
            }
        )
    return result


def _build_learning_plan(
    message: str,
    tool_context: dict[str, Any],
    topic: str | None = None,
) -> dict[str, Any]:
    """Build a small explainable plan from the context already read by the Agent."""
    profile = tool_context.get("read_profile", {}) or {}
    due_reviews = tool_context.get("read_due_reviews", []) or []
    recent_sessions = tool_context.get("read_recent_sessions", []) or []
    question_card = tool_context.get("read_question_card", {}) or {}
    graph_question = tool_context.get("read_graph_question", {}) or {}
    topic_mastery = profile.get("topic_mastery", []) or []
    today = date.today().isoformat()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_item(
        *,
        item_type: str,
        topic: str,
        point: str,
        action: str,
        reason: str,
        duration: int,
        priority: str,
        source: dict[str, Any] | None = None,
    ) -> None:
        clean_topic = topic.strip() or "综合能力"
        clean_point = point.strip()
        key = f"{clean_topic}:{clean_point}"
        if not clean_point or key in seen or len(items) >= 5:
            return
        seen.add(key)
        item = {
                "id": f"task-{len(items) + 1}",
                "type": item_type,
                "topic": clean_topic,
                "point": clean_point[:160],
                "action": action[:240],
                "reason": reason[:240],
                "duration_minutes": max(5, min(int(duration), 90)),
                "priority": priority,
                "scheduled_for": today,
                "status": "pending",
            }
        if source:
            item.update(source)
        items.append(item)

    if graph_question:
        graph_topic = str(graph_question.get("topic", "")).strip() or topic or "综合能力"
        graph_question_text = str(graph_question.get("question", "")).strip()
        related_questions = [
            item for item in graph_question.get("related_questions", [])
            if isinstance(item, dict) and str(item.get("question", "")).strip()
        ][:3]
        add_item(
            item_type="graph_question",
            topic=graph_topic,
            point=graph_question_text,
            action="围绕这道图谱问题完成一次结构化回答，说明原理、工程取舍和一个可验证指标。",
            reason="该训练项由用户从当前主题知识图谱中指定，先回答节点问题，再进入后续主题追问。",
            duration=20,
            priority="P0",
            source={
                "graph_question_id": str(graph_question.get("id", "")),
                "graph_question": graph_question_text,
                "graph_entry_source": str(graph_question.get("entry_source", "question_node")),
                "graph_parent_question_id": str(graph_question.get("parent_question_id", "")),
                "graph_parent_question": str(graph_question.get("parent_question", "")),
                "related_questions": related_questions,
            },
        )

    if question_card:
        card_project = str(question_card.get("project_name", "")).strip() or "未命名项目"
        card_category = str(question_card.get("category", "项目追问")).strip() or "项目追问"
        card_question = str(question_card.get("question", "")).strip()
        card_fields = "、".join(str(item) for item in question_card.get("field_refs", [])[:4])
        add_item(
            item_type="project_followup",
            topic="综合能力",
            point=f"{card_project}：{card_category}",
            action=(
                f"围绕“{card_question}”完成一次项目回答，必须引用 {card_fields or '项目字段'} 中的具体证据，"
                "并说明一个验证方式或工程取舍。"
            ),
            reason="该训练项由用户指定的项目追问卡触发，先补齐项目表达证据，再进入领域专项训练。",
            duration=25,
            priority="P0",
            source={
                "question_card_id": str(question_card.get("id", "")),
                "question_card_project": card_project,
                "question_card_resume_version": question_card.get("resume_version"),
            },
        )

    for review in due_reviews[:3]:
        point = str(review.get("point", "")).strip()
        topic = str(review.get("topic") or "综合能力")
        last_score = review.get("last_score")
        score_text = f"上次得分 {last_score}/10" if last_score is not None else "尚无上次得分"
        add_item(
            item_type="spaced_review",
            topic=topic,
            point=point,
            action="先用 3 分钟口述核心概念，再回答一道追问，并补充具体验证方式。",
            reason=f"该知识点已进入 SM-2 到期队列，{score_text}。",
            duration=20,
            priority="P0",
        )

    lowest_topic = min(
        topic_mastery,
        key=lambda item: float(item.get("mastery_score", 0) or 0),
        default={"topic": "综合能力", "mastery_score": 0},
    )
    for point in profile.get("weak_points", [])[:2]:
        add_item(
            item_type="targeted_drill",
            topic=str(lowest_topic.get("topic") or "综合能力"),
            point=str(point),
            action="完成一轮专项训练，回答时明确背景、行动、结果和验证指标。",
            reason="该问题在长期画像中反复出现，需要通过专项训练形成稳定回答。",
            duration=25,
            priority="P1",
        )

    if not items and topic_mastery:
        add_item(
            item_type="targeted_drill",
            topic=str(lowest_topic.get("topic") or "综合能力"),
            point="围绕当前最低掌握度领域完成一次端到端回答",
            action="完成开场回答、一次追问和复盘，记录一个可量化的改进点。",
            reason=f"当前领域掌握度为 {float(lowest_topic.get('mastery_score', 0) or 0):.1f}/10，优先补齐最低项。",
            duration=30,
            priority="P0",
        )
    if not items:
        add_item(
            item_type="baseline_drill",
            topic="AI 应用开发",
            point="完成一次项目讲解并说明方案验证方式",
            action="用 1 分钟介绍项目，再回答技术难点、取舍和效果验证三个追问。",
            reason="当前画像和到期队列还没有足够信号，先用基线训练建立评估数据。",
            duration=25,
            priority="P1",
        )

    title = "今日个性化学习计划" if today else "个性化学习计划"
    scheduled_due_count = sum(item.get("type") == "spaced_review" for item in items)
    due_summary = (
        f"{scheduled_due_count}/{len(due_reviews)} 个到期复习点"
        if due_reviews
        else "0 个到期复习点"
    )
    summary = (
        f"共 {len(items)} 项：优先处理 {due_summary}，"
        f"再补齐长期薄弱点；计划由 QTrace Agent 根据当前画像生成。"
    )
    plan_source = {
        "generated_by": "qtrace-agent-v1",
        "due_review_count": len(due_reviews),
        "due_review_scheduled": scheduled_due_count,
        "weak_point_count": len(profile.get("weak_points", [])),
        "recent_session_count": len(recent_sessions),
        "mastery_score": float(profile.get("mastery_score", 0) or 0),
        "request": message[:240],
    }
    if topic:
        plan_source["topic"] = topic
    if graph_question:
        plan_source["graph_question"] = {
            "id": graph_question.get("id", ""),
            "topic": graph_question.get("topic", ""),
            "question": graph_question.get("question", ""),
            "entry_source": graph_question.get("entry_source", "question_node"),
            "parent_question_id": graph_question.get("parent_question_id", ""),
            "parent_question": graph_question.get("parent_question", ""),
            "related_questions": graph_question.get("related_questions", [])[:3],
        }
    if question_card:
        plan_source["question_card"] = {
            "id": question_card.get("id", ""),
            "project_name": question_card.get("project_name", ""),
            "category": question_card.get("category", ""),
            "resume_version": question_card.get("resume_version"),
        }
    return {
        "title": title,
        "summary": summary,
        "items": items,
        "source": plan_source,
    }


def _execute_tool(
    name: str,
    *,
    message: str,
    conversation_id: str,
    tool_context: dict[str, Any],
    store: Store,
    document_service: PersonalDocumentService,
    structured_resume_service: StructuredResumeService | None,
    user_id: str,
    data_dir: Path,
    question_card_id: str | None = None,
    topic: str | None = None,
    graph_question_id: str | None = None,
    graph_entry_source: str | None = None,
    graph_parent_question_id: str | None = None,
) -> Any:
    if name == "read_profile":
        profile = store.get_profile(user_id)
        return {
            **profile,
            "topic_mastery": store.list_topic_profiles(user_id)[:8],
        }
    if name == "read_due_reviews":
        return store.list_due_reviews(user_id, topic=topic, limit=12)
    if name == "read_recent_sessions":
        return _recent_session_context(store, user_id)
    if name == "read_resume":
        return _resume_context(user_id, data_dir, structured_resume_service)
    if name == "read_question_card":
        if not question_card_id or not structured_resume_service:
            raise LookupError("当前请求没有可读取的项目追问卡")
        card = structured_resume_service.get_question_card(user_id, question_card_id)
        if not card:
            raise LookupError("项目追问卡不存在或已不属于当前简历版本")
        return card
    if name == "read_graph_question":
        if not graph_question_id or not topic:
            raise LookupError("当前请求没有可读取的主题图谱问题")
        try:
            graph_entry = resolve_graph_question_entry(
                user_id,
                topic,
                graph_question_id,
                str(data_dir),
                store,
                entry_source=graph_entry_source,
                parent_question_id=graph_parent_question_id,
            )
        except KnowledgeError as exc:
            raise LookupError(str(exc)) from exc
        except ValueError as exc:
            raise LookupError(str(exc)) from exc
        if not graph_entry:
            raise LookupError("图谱问题不存在、父节点不存在或已不属于当前训练主题")
        question = graph_entry["question"]
        graph = build_topic_graph(user_id, topic, str(data_dir), store)
        node = next(
            (item for item in graph["nodes"] if item.get("id") == graph_question_id),
            None,
        )
        related_questions: list[dict[str, Any]] = []
        if node:
            for related_id in node.get("related_question_ids", [])[:3]:
                related_node = next(
                    (item for item in graph["nodes"] if item.get("id") == related_id),
                    None,
                )
                if not related_node:
                    continue
                edge = next(
                    (
                        item for item in graph["links"]
                        if item.get("relation") == "related"
                        and {item.get("source"), item.get("target")} == {graph_question_id, related_id}
                    ),
                    None,
                )
                related_questions.append(
                    {
                        "id": related_id,
                        "topic": topic,
                        "question": related_node.get("question", ""),
                        "focus_area": related_node.get("focus_area", "综合能力"),
                        "weight": float((edge or {}).get("weight", 0) or 0),
                        "started_count": int((edge or {}).get("started_count", 0) or 0),
                        "completed_count": int((edge or {}).get("completed_count", 0) or 0),
                        "completion_rate": round(
                            int((edge or {}).get("completed_count", 0) or 0)
                            / int((edge or {}).get("started_count", 0) or 1),
                            3,
                        ) if int((edge or {}).get("started_count", 0) or 0) else 0.0,
                    }
                )
        return {
            "id": graph_question_id,
            "topic": topic,
            "question": question,
            "entry_source": graph_entry["entry_source"],
            "parent_question_id": graph_entry["parent_question_id"],
            "parent_question": graph_entry["parent_question"],
            "related_questions": related_questions,
        }
    if name == "search_personal_documents":
        query = message
        card = tool_context.get("read_question_card") or {}
        if card:
            query = f"{message} {card.get('project_name', '')} {card.get('category', '')}"
        return document_service.search(user_id, query, limit=5)
    if name == "create_learning_plan":
        plan = _build_learning_plan(message, tool_context, topic=topic)
        return store.create_learning_plan(user_id, message, plan, conversation_id)
    raise ProviderError(f"Agent 不允许调用工具：{name}")


def _tool_summary(name: str, value: Any) -> str:
    if name == "read_profile":
        return f"已读取画像：{value.get('completed_sessions', 0)} 次训练，{len(value.get('weak_points', []))} 个长期薄弱点"
    if name == "read_due_reviews":
        return f"已读取今日复习队列：{len(value)} 项"
    if name == "read_recent_sessions":
        return f"已读取最近训练：{len(value)} 次"
    if name == "read_resume":
        return "已读取简历" if value.get("available") else "用户尚未上传简历"
    if name == "read_question_card":
        return f"已读取项目追问卡：{value.get('project_name', '未命名项目')} / {value.get('category', '未命名类别')}"
    if name == "read_graph_question":
        return f"已读取图谱问题：{value.get('topic', '未命名主题')} / {value.get('id', '未命名节点')}"
    if name == "search_personal_documents":
        return f"已检索个人文档：{len(value)} 个相关片段"
    if name == "create_learning_plan":
        return f"已生成学习计划草稿：{value.get('title', '未命名计划')}（{len(value.get('items', []))} 项，等待确认，ID {value.get('id', '')[:8]}）"
    return "工具执行完成"


def _tool_failure_contract(exc: Exception) -> tuple[str, str]:
    """Map internal tool exceptions to safe, stable user-facing diagnostics."""

    if isinstance(exc, ProviderError):
        return "dependency_unavailable", "工具依赖服务暂时不可用，已跳过该工具"
    if isinstance(exc, (LookupError, ValueError)):
        return "context_unavailable", "当前上下文不可用，已跳过该工具"
    return "execution_failed", "工具执行失败，已跳过该工具"


def _blocked_write_contract(
    name: str,
    tool_context: dict[str, Any],
) -> tuple[str, str] | None:
    required = AGENT_WRITE_REQUIREMENTS.get(name)
    if not required:
        return None
    failed_names = {
        str(item.get("name", ""))
        for item in tool_context.get("tool_failures", [])
        if isinstance(item, dict)
    }
    missing = sorted(required & failed_names)
    if not missing:
        return None
    return "write_blocked_by_context", "必要上下文读取失败，暂不创建学习计划草稿"


def run_personal_agent(
    *,
    message: str,
    user_id: str,
    store: Store,
    data_dir: Path,
    model: AgentModel,
    document_service: PersonalDocumentService,
    structured_resume_service: StructuredResumeService | None = None,
    conversation_id: str | None = None,
    question_card_id: str | None = None,
    topic: str | None = None,
    graph_question_id: str | None = None,
    graph_entry_source: str | None = None,
    graph_parent_question_id: str | None = None,
) -> dict[str, Any]:
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("消息不能为空")
    clean_question_card_id = str(question_card_id or "").strip() or None
    clean_topic = str(topic or "").strip() or None
    clean_graph_question_id = str(graph_question_id or "").strip() or None
    clean_graph_entry_source = str(graph_entry_source or "").strip() or None
    clean_graph_parent_question_id = str(graph_parent_question_id or "").strip() or None
    if clean_question_card_id:
        if not structured_resume_service:
            raise LookupError("当前 Agent 未配置结构化简历服务")
        if not structured_resume_service.get_question_card(user_id, clean_question_card_id):
            raise LookupError("项目追问卡不存在或已不属于当前简历版本")
    if clean_graph_question_id:
        if not clean_topic:
            raise LookupError("图谱问题需要同时提供训练主题")
        try:
            graph_entry = resolve_graph_question_entry(
                user_id,
                clean_topic,
                clean_graph_question_id,
                str(data_dir),
                store,
                entry_source=clean_graph_entry_source,
                parent_question_id=clean_graph_parent_question_id,
            )
        except KnowledgeError as exc:
            raise LookupError(str(exc)) from exc
        except ValueError as exc:
            raise LookupError(str(exc)) from exc
        if not graph_entry:
            raise LookupError("图谱问题不存在、父节点不存在或已不属于当前训练主题")
    elif clean_graph_entry_source or clean_graph_parent_question_id:
        raise LookupError("图谱来源字段需要同时提供图谱问题")

    conversation = (
        store.get_agent_conversation(user_id, conversation_id)
        if conversation_id
        else None
    )
    if conversation_id and not conversation:
        raise LookupError("Agent 对话不存在")
    created_conversation = False
    if not conversation:
        conversation_id = store.create_agent_conversation(user_id, clean_message[:40])
        conversation = store.get_agent_conversation(user_id, conversation_id)
        created_conversation = True
    assert conversation is not None

    history = conversation["messages"]
    tool_context: dict[str, Any] = {}
    tool_trace: list[dict[str, Any]] = []

    def failure_state() -> str:
        """Keep durable plans, but remove an empty conversation created for a failed call."""

        if not created_conversation:
            return "preserved_draft" if tool_context.get("create_learning_plan") else "conversation_unchanged"
        if store.delete_empty_agent_conversation(user_id, conversation_id):
            return "rolled_back"
        return "preserved_draft" if tool_context.get("create_learning_plan") else "conversation_unchanged"

    try:
        raw_plan = model.plan(clean_message)
        plan = _normalize_plan(
            raw_plan,
            clean_message,
            question_card_id=clean_question_card_id,
            graph_question_id=clean_graph_question_id,
        )
    except ProviderError as exc:
        raise AgentProviderError(
            "planning",
            str(exc),
            state=failure_state(),
            conversation_id=conversation_id,
        ) from exc

    for call in plan["tool_calls"]:
        name = call["name"]
        blocked = _blocked_write_contract(name, tool_context)
        if blocked:
            code, summary = blocked
            tool_context.setdefault("tool_failures", []).append(
                {"name": name, "code": code, "summary": summary}
            )
            tool_trace.append(
                {
                    "name": name,
                    "status": "skipped",
                    "code": code,
                    "recovery": "continue_with_partial_context",
                    "reason": call["reason"],
                    "summary": summary,
                }
            )
            continue
        try:
            value = _execute_tool(
                name,
                message=clean_message,
                conversation_id=conversation_id,
                tool_context=tool_context,
                store=store,
                document_service=document_service,
                structured_resume_service=structured_resume_service,
                user_id=user_id,
                data_dir=data_dir,
                question_card_id=clean_question_card_id,
                topic=clean_topic,
                graph_question_id=clean_graph_question_id,
                graph_entry_source=clean_graph_entry_source,
                graph_parent_question_id=clean_graph_parent_question_id,
            )
            tool_context[name] = value
            tool_trace.append(
                {
                    "name": name,
                    "status": "completed",
                    "reason": call["reason"],
                    "summary": _tool_summary(name, value),
                }
            )
        except Exception as exc:
            code, summary = _tool_failure_contract(exc)
            tool_context.setdefault("tool_failures", []).append(
                {"name": name, "code": code, "summary": summary}
            )
            tool_trace.append(
                {
                    "name": name,
                    "status": "failed",
                    "code": code,
                    "recovery": "continue_with_partial_context",
                    "reason": call["reason"],
                    "summary": summary,
                }
            )

    try:
        raw_answer = model.answer(clean_message, history, tool_context)
        answer = raw_answer.strip()
    except ProviderError as exc:
        raise AgentProviderError(
            "answering",
            str(exc),
            state=failure_state(),
            conversation_id=conversation_id,
        ) from exc
    except (AttributeError, TypeError) as exc:
        raise AgentProviderError(
            "answering",
            "Agent 返回了不可用内容",
            state=failure_state(),
            conversation_id=conversation_id,
        ) from exc
    if not answer:
        raise AgentProviderError(
            "answering",
            "Agent 没有返回内容",
            state=failure_state(),
            conversation_id=conversation_id,
        )
    now = datetime.now(UTC).isoformat()
    messages = history + [
        {"role": "user", "content": clean_message, "created_at": now},
        {"role": "assistant", "content": answer, "created_at": now},
    ]
    store.update_agent_conversation(user_id, conversation_id, messages)
    return {
        "conversation_id": conversation_id,
        "title": conversation["title"],
        "message": {"role": "assistant", "content": answer, "created_at": now},
        "plan": plan,
        "tool_trace": tool_trace,
        "created_plan": tool_context.get("create_learning_plan"),
    }
