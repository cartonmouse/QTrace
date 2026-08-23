from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Protocol

from .provider import OpenAICompatibleProvider, ProviderError


MAX_DRILL_QUESTIONS = 8


class DrillQuestionGenerator(Protocol):
    def generate(
        self,
        *,
        topic: str,
        topic_name: str,
        knowledge_context: str,
        question_bank: list[str],
        profile: Mapping[str, Any],
        topic_profile: Mapping[str, Any] | None,
        due_reviews: list[Mapping[str, Any]],
        recent_sessions: list[Mapping[str, Any]],
        requested_focus: str = "",
    ) -> dict[str, Any]: ...


def _unique_strings(values: Any, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("text") or value.get("point") or value.get("question")
        clean = str(value or "").strip()
        if clean and clean not in seen:
            result.append(clean[:500])
            seen.add(clean)
        if len(result) >= limit:
            break
    return result


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(raw)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ProviderError("动态出题结果不是合法 JSON") from None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ProviderError("动态出题结果不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("动态出题结果必须是 JSON 对象")
    return value


def normalize_drill_plan(
    raw: Mapping[str, Any],
    *,
    topic: str,
    source: str,
) -> dict[str, Any]:
    """Validate the model boundary and return the engine's simple question list."""
    raw_items = raw.get("questions")
    if not isinstance(raw_items, list):
        raise ProviderError("动态出题结果缺少 questions 数组")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        if isinstance(raw_item, str):
            question = raw_item.strip()
            focus = "综合能力"
            reason = "根据当前专项训练上下文生成"
            difficulty = 3
        elif isinstance(raw_item, dict):
            question = str(raw_item.get("question", "")).strip()
            focus = str(raw_item.get("focus", "综合能力")).strip() or "综合能力"
            reason = str(raw_item.get("reason", "根据当前专项训练上下文生成")).strip()
            try:
                difficulty = max(1, min(5, int(raw_item.get("difficulty", 3))))
            except (TypeError, ValueError):
                difficulty = 3
        else:
            continue
        if not question or question in seen:
            continue
        seen.add(question)
        items.append(
            {
                "question": question[:1_000],
                "focus": focus[:120],
                "difficulty": difficulty,
                "reason": reason[:240] or "根据当前专项训练上下文生成",
            }
        )
        if len(items) >= MAX_DRILL_QUESTIONS:
            break

    if not items:
        raise ProviderError("动态出题结果没有可用题目")
    return {
        "topic": topic,
        "source": source,
        "questions": [item["question"] for item in items],
        "items": items,
    }


def _focus_for_profile(topic_profile: Mapping[str, Any] | None) -> tuple[str, str]:
    if not topic_profile:
        return "基础概念与工程应用", "还没有该领域的历史训练记录，先建立基线。"
    mastery = float(topic_profile.get("mastery_score", 0) or 0)
    trend = str(topic_profile.get("trend", "new") or "new")
    if mastery < 6:
        return "概念、原理与边界", "当前领域掌握度较低，优先补齐概念和适用边界。"
    if trend == "declining" or mastery < 8:
        return "方案取舍、验证与故障排查", "已有基础，但需要把知识转化为可验证的工程判断。"
    return "系统设计、规模变化与追问", "掌握度较好，增加开放式场景来验证迁移能力。"


class StubDrillQuestionGenerator:
    """Offline generator: deterministic, but still follows the profile-driven contract."""

    def generate(
        self,
        *,
        topic: str,
        topic_name: str,
        knowledge_context: str,
        question_bank: list[str],
        profile: Mapping[str, Any],
        topic_profile: Mapping[str, Any] | None,
        due_reviews: list[Mapping[str, Any]],
        recent_sessions: list[Mapping[str, Any]],
        requested_focus: str = "",
    ) -> dict[str, Any]:
        del knowledge_context, recent_sessions
        focus, reason = _focus_for_profile(topic_profile)
        requested_focus = requested_focus.strip()[:200]
        due_items: list[dict[str, Any]] = []
        if requested_focus:
            due_items.append(
                {
                    "question": f"请围绕学习计划焦点「{requested_focus}」回答一个专项问题，说明原理、工程取舍和验证方式。",
                    "focus": requested_focus,
                    "difficulty": 3,
                    "reason": "该问题由当前学习计划项指定，作为本轮专项训练的首要关注点。",
                }
            )
        for item in due_reviews[:5]:
            point = str(item.get("point", "")).strip()
            if not point:
                continue
            due_items.append(
                {
                    "question": f"复习任务：请优先解释「{point}」，结合一个工程例子说明原理、取舍和验证方式。",
                    "focus": point,
                    "difficulty": 3,
                    "reason": "该薄弱点已经进入今天的 SM-2 到期复习队列。",
                }
            )

        weak_points = _unique_strings(
            (topic_profile or {}).get("weak_points") or profile.get("weak_points", []),
            limit=4,
        )
        personalized = [
            {
                "question": f"请围绕「{point}」说明你会如何验证自己的理解，并指出一个常见误区。",
                "focus": point,
                "difficulty": 2,
                "reason": "该主题在长期画像中被记录为待补强点。",
            }
            for point in weak_points
            if not any(point in item["question"] for item in due_items)
        ]

        generated = due_items + personalized
        for question in question_bank:
            clean = str(question).strip()
            if clean and not any(clean == item["question"] for item in generated):
                generated.append(
                    {
                        "question": clean,
                        "focus": focus,
                        "difficulty": 3 if topic_profile else 2,
                        "reason": reason,
                    }
                )
        if not generated:
            generated.append(
                {
                    "question": f"请解释「{topic_name or topic}」中的一个核心概念，说明原理、适用边界和验证方式。",
                    "focus": focus,
                    "difficulty": 2,
                    "reason": "题库暂无内容，使用领域基线问题建立第一次训练信号。",
                }
            )
        return normalize_drill_plan(
            {"questions": generated}, topic=topic, source="stub_profile_driven"
        )


class LLMDrillQuestionGenerator:
    """Generate a small, structured question set grounded in local user signals."""

    def __init__(self, structured_chat: Callable[[str, str], str]):
        self.structured_chat = structured_chat

    def generate(
        self,
        *,
        topic: str,
        topic_name: str,
        knowledge_context: str,
        question_bank: list[str],
        profile: Mapping[str, Any],
        topic_profile: Mapping[str, Any] | None,
        due_reviews: list[Mapping[str, Any]],
        recent_sessions: list[Mapping[str, Any]],
        requested_focus: str = "",
    ) -> dict[str, Any]:
        system_prompt = (
            "你是问迹 QTrace 的专项面试出题器。只返回 JSON 对象，不要 Markdown。"
            '格式必须是 {"questions":[{"question":string,"focus":string,'
            '"difficulty":number,"reason":string}]}。'
            "生成 4 到 8 道互不重复的中文面试题；difficulty 为 1 到 5。"
            "必须优先覆盖 due_reviews 中的到期薄弱点，再结合画像掌握度、趋势、长期薄弱点、"
            "最近训练和本地知识上下文安排难度。题目应能追问原理、工程取舍、验证或故障排查，"
            "不要编造用户没有提供的经历；如果 plan_focus 非空，至少有一道题要直接覆盖这个计划焦点。"
        )
        payload = {
            "topic": topic,
            "topic_name": topic_name,
            "profile": dict(profile),
            "topic_profile": dict(topic_profile or {}),
            "due_reviews": [dict(item) for item in due_reviews[:12]],
            "recent_sessions": [dict(item) for item in recent_sessions[:8]],
            "plan_focus": requested_focus[:200],
            "knowledge_context": knowledge_context[:8_000],
            "high_frequency_questions": question_bank[:12],
        }
        raw = self.structured_chat(
            system_prompt,
            "请根据以下 JSON 输入生成本轮专项题目：\n" + json.dumps(payload, ensure_ascii=False),
        )
        return normalize_drill_plan(
            _parse_json_object(raw), topic=topic, source="llm_profile_driven"
        )


def build_drill_question_generator(config: Mapping[str, str]) -> DrillQuestionGenerator:
    if config.get("mode") == "stub":
        return StubDrillQuestionGenerator()
    if config.get("mode") == "openai":
        provider = OpenAICompatibleProvider(
            api_base=config.get("api_base", ""),
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
        return LLMDrillQuestionGenerator(provider.structured_chat)
    raise ProviderError("请先在模型设置中启用本地演示模型或配置真实 LLM")
