from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .provider import OpenAICompatibleProvider, ProviderError
from .resume import ResumeError, get_resume_text
from .store import Store


AGENT_TOOLS: dict[str, str] = {
    "read_profile": "读取用户的全局画像、领域掌握度和长期薄弱点",
    "read_due_reviews": "读取今天到期的 SM-2 复习任务",
    "read_recent_sessions": "读取最近几次训练的模式、岗位、分数和复盘薄弱点",
    "read_resume": "读取用户已经上传的简历文本",
}


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
    return calls


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


def _normalize_plan(raw: dict[str, Any], message: str) -> dict[str, Any]:
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
        if name in AGENT_TOOLS and name not in seen:
            calls.append({"name": name, "reason": reason[:160]})
            seen.add(name)
    if not calls:
        calls = _default_tool_calls(message)
    return {
        "intent": str(raw.get("intent", "个性化面试成长建议")).strip()[:120]
        or "个性化面试成长建议",
        "tool_calls": calls[:4],
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
        resume = tool_context.get("read_resume", {})
        weak_points = profile.get("weak_points", [])
        topic_mastery = profile.get("topic_mastery", [])

        lines = [
            "我是问迹 QTrace 个人成长 Agent（本地演示模型）。我先读取了你的长期画像，再根据问题选择了只读工具。",
            f"当前已完成 {profile.get('completed_sessions', 0)} 次训练，整体掌握度为 {profile.get('mastery_score', 0)} / 10。",
        ]
        if topic_mastery:
            topic_text = "、".join(
                f"{item.get('topic', '未命名')} {item.get('mastery_score', 0)}/10"
                for item in topic_mastery[:4]
            )
            lines.append(f"领域掌握度：{topic_text}。")
        if weak_points:
            lines.append(f"当前长期薄弱点：{'；'.join(str(item) for item in weak_points[:4])}。")
        if due:
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
            lines.append(f"已读取简历文本 {resume.get('text_chars', 0)} 字，后续可以用它核对项目回答。")
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
            + '。JSON 格式为 {"intent": string, "tool_calls": [{"name": string, "reason": string}]}。',
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
            "复习队列、训练历史和简历，为用户给出具体、诚实、可执行的中文建议。"
            "只能使用工具结果中的事实；没有读取到的内容要明确说明。"
            "不要声称已经替用户创建任务或修改数据，因为当前工具只有只读能力。"
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


def _resume_context(user_id: str, data_dir: Path) -> dict[str, Any]:
    try:
        text, filename = get_resume_text(user_id, data_dir)
    except ResumeError:
        return {"available": False, "filename": "", "text_chars": 0, "text": ""}
    return {
        "available": bool(text.strip()),
        "filename": filename,
        "text_chars": len(text),
        "text": text[:8000],
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


def _execute_tool(
    name: str,
    *,
    store: Store,
    user_id: str,
    data_dir: Path,
) -> Any:
    if name == "read_profile":
        profile = store.get_profile(user_id)
        return {
            **profile,
            "topic_mastery": store.list_topic_profiles(user_id)[:8],
        }
    if name == "read_due_reviews":
        return store.list_due_reviews(user_id, limit=12)
    if name == "read_recent_sessions":
        return _recent_session_context(store, user_id)
    if name == "read_resume":
        return _resume_context(user_id, data_dir)
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
    return "工具执行完成"


def run_personal_agent(
    *,
    message: str,
    user_id: str,
    store: Store,
    data_dir: Path,
    model: AgentModel,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("消息不能为空")

    conversation = (
        store.get_agent_conversation(user_id, conversation_id)
        if conversation_id
        else None
    )
    if conversation_id and not conversation:
        raise LookupError("Agent 对话不存在")
    if not conversation:
        conversation_id = store.create_agent_conversation(user_id, clean_message[:40])
        conversation = store.get_agent_conversation(user_id, conversation_id)
    assert conversation is not None

    history = conversation["messages"]
    plan = _normalize_plan(model.plan(clean_message), clean_message)
    tool_context: dict[str, Any] = {}
    tool_trace: list[dict[str, Any]] = []
    for call in plan["tool_calls"]:
        name = call["name"]
        try:
            value = _execute_tool(name, store=store, user_id=user_id, data_dir=data_dir)
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
            tool_trace.append(
                {
                    "name": name,
                    "status": "failed",
                    "reason": call["reason"],
                    "summary": str(exc)[:160],
                }
            )

    answer = model.answer(clean_message, history, tool_context).strip()
    if not answer:
        raise ProviderError("Agent 没有返回内容")
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
    }
