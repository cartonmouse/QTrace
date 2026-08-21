from __future__ import annotations

import json
import re
import time
from typing import Any, Protocol

import httpx


class ProviderError(RuntimeError):
    """A model provider failed or returned an unusable response."""


class InterviewProvider(Protocol):
    def opening(
        self,
        target_role: str,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str: ...

    def next_question(
        self,
        phase: str,
        target_role: str,
        last_answer: str,
        question_number: int = 1,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str: ...

    def review(
        self,
        messages: list[dict[str, str]],
        target_role: str = "",
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> dict[str, Any]: ...


class StubProvider:
    """Deterministic local provider: same boundary as an LLM, no network needed."""

    def opening(
        self,
        target_role: str,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str:
        if mode == "jd_prep":
            return f"你好，今天围绕「{company or '目标公司'}」的「{position or target_role}」岗位进行定向备面。请先结合岗位要求做一个 1 分钟自我介绍。"
        if topic:
            return f"你好，今天我们进行「{topic}」专项训练，目标是检查你对概念、原理和工程取舍的理解。请先说明你对这个领域的整体认识。"
        return f"你好，今天我们围绕「{target_role}」进行模拟面试。请先做一个 1 分钟左右的自我介绍。"

    def next_question(
        self,
        phase: str,
        target_role: str,
        last_answer: str,
        question_number: int = 1,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str:
        if mode == "jd_prep":
            bank = question_bank or []
            offsets = {"technical": 0, "project_deep_dive": 2, "behavioral": 4, "reverse_qa": 6}
            index = offsets.get(phase, 0) + max(question_number, 1) - 1
            if bank:
                return bank[min(index, len(bank) - 1)]
            return f"请结合「{position or target_role}」岗位 JD，说明你会如何证明自己的项目经验与岗位要求匹配。"
        if topic:
            bank = question_bank or []
            offsets = {"technical": 0, "project_deep_dive": 2, "behavioral": 4, "reverse_qa": 6}
            index = offsets.get(phase, 0) + max(question_number, 1) - 1
            if bank:
                return bank[min(index, len(bank) - 1)]
            return f"请围绕「{topic}」解释一个核心概念，说明它的工作原理、适用边界，以及你会如何验证自己的理解。"
        questions = {
            "technical": [
                f"请结合一个项目，解释你在 {target_role} 相关工作中解决过的一个技术难点。你会如何验证方案有效？",
                "如果这个技术方案的请求量增长 10 倍，你会优先检查哪些瓶颈，并如何设计压测？",
            ],
            "project_deep_dive": [
                "请把刚才提到的项目拆成目标、你的职责、关键设计、结果和复盘，并说明一个具体取舍。",
                "如果重新做一次这个项目，你会保留什么、重构什么？为什么？",
            ],
            "behavioral": [
                "遇到需求不清或方案意见不一致时，你通常如何推进？请讲一个真实或模拟的例子。",
                "请举例说明一次失败或延期经历，以及你如何定位原因、沟通并改进。",
            ],
            "reverse_qa": [
                "最后，请你向面试官提一个能帮助判断岗位和团队是否匹配的问题。",
            ],
        }
        variants = questions.get(phase, ["请继续补充一个具体例子，并说明你从中学到了什么。"])
        return variants[min(max(question_number, 1) - 1, len(variants) - 1)]

    def review(
        self,
        messages: list[dict[str, str]],
        target_role: str = "",
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> dict[str, Any]:
        answers = [m["content"] for m in messages if m["role"] == "user"]
        scores = [min(10.0, round(4 + len(answer) / 45, 1)) for answer in answers]
        average = round(sum(scores) / len(scores), 1) if scores else 0.0
        weak_points = []
        if any(len(answer) < 50 for answer in answers):
            weak_points.append("回答缺少足够的事实细节")
        if any("结果" not in answer and "提升" not in answer for answer in answers):
            weak_points.append("回答中缺少结果或量化指标")
        return {
            "summary": (
            f"本地演示专项评估已完成，训练领域：{topic}。"
                if topic
                else f"本地演示 JD 定向评估已完成，目标岗位：{position or target_role}。"
                if mode == "jd_prep"
                else "本地演示评估已完成。真实模型接入后，这里会替换为结构化的逐题评估和复盘建议。"
            ),
            "average_score": average,
            "scores": scores,
            "strengths": ["能够完成一轮结构化回答"] if answers else [],
            "weak_points": weak_points,
            "behavior_signals": [
                "能够围绕问题给出连续回答" if answers else "尚未形成回答信号",
                "需要继续积累可核验的项目证据",
            ],
            "action_items": ["用 STAR 结构补充背景、行动和结果", "为项目回答准备可核验的数字"],
        }


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_review(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ProviderError("LLM 复盘结果不是合法 JSON") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ProviderError("LLM 复盘结果不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ProviderError("LLM 复盘结果必须是 JSON 对象")
    return {
        "summary": str(data.get("summary", "")),
        "average_score": float(data.get("average_score", 0) or 0),
        "scores": data.get("scores") if isinstance(data.get("scores"), list) else [],
        "strengths": data.get("strengths") if isinstance(data.get("strengths"), list) else [],
        "weak_points": data.get("weak_points") if isinstance(data.get("weak_points"), list) else [],
        "behavior_signals": data.get("behavior_signals") if isinstance(data.get("behavior_signals"), list) else [],
        "action_items": data.get("action_items") if isinstance(data.get("action_items"), list) else [],
    }


class OpenAICompatibleProvider:
    """Provider for any OpenAI-compatible /chat/completions endpoint.

    The interview state machine depends only on InterviewProvider. This adapter
    owns HTTP, prompt construction, response validation and JSON normalization.
    """

    _RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.25,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = client
        self.max_retries = max(0, min(int(max_retries), 3))
        self.retry_backoff_seconds = max(0.0, min(float(retry_backoff_seconds), 2.0))

    def _wait_before_retry(self, attempt: int) -> None:
        delay = min(self.retry_backoff_seconds * (2**attempt), 2.0)
        if delay > 0:
            time.sleep(delay)

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.api_base}/chat/completions"
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self._client is not None:
                    response = self._client.post(url, json=payload, headers=headers)
                else:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    self._wait_before_retry(attempt)
                    continue
                raise ProviderError("LLM 请求超时，请检查网络或增大超时配置") from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    self._wait_before_retry(attempt)
                    continue
                raise ProviderError("LLM 网络连接失败，请检查 API Base 和网络设置") from exc

            if response.status_code < 400:
                break
            if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                self._wait_before_retry(attempt)
                continue
            raise ProviderError(f"LLM 请求失败，HTTP {response.status_code}")

        if response is None:
            raise ProviderError("LLM 请求没有返回响应")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("LLM 返回缺少 choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("LLM 返回了空内容")
        return content.strip()

    def structured_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Expose the validated chat boundary for non-interview analyzers."""
        return self._chat(system_prompt, user_prompt)

    @staticmethod
    def _resume_context(resume_text: str) -> str:
        return resume_text.strip()[:6000] or "未提供简历摘要"

    @staticmethod
    def _topic_context(topic: str, knowledge_context: str, question_bank: list[str] | None = None) -> str:
        if not topic:
            return "未指定专项训练领域"
        bank = "\n".join(f"- {item}" for item in (question_bank or [])[:12]) or "未维护高频题目"
        return f"训练领域：{topic}\n核心知识上下文：{knowledge_context.strip()[:8000] or '暂无'}\n高频题目参考：\n{bank}"

    @staticmethod
    def _job_context(
        company: str,
        position: str,
        knowledge_context: str,
        question_bank: list[str] | None = None,
    ) -> str:
        bank = "\n".join(f"- {item}" for item in (question_bank or [])[:12]) or "暂无定向问题"
        return (
            f"公司：{company or '未提供'}\n岗位：{position or '未提供'}\n"
            f"JD 与岗位分析上下文：{knowledge_context.strip()[:10000] or '暂无'}\n"
            f"定向问题参考：\n{bank}"
        )

    def opening(
        self,
        target_role: str,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str:
        context = self._job_context(company, position, knowledge_context, question_bank) if mode == "jd_prep" else self._topic_context(topic, knowledge_context, question_bank)
        return self._chat(
            "你是一名严谨、友好的技术面试官。只输出给候选人的开场话术，不要输出分析。",
            f"目标岗位：{target_role}\n简历摘要：{self._resume_context(resume_text)}\n"
            f"{context}\n"
            + (
                "请围绕 JD 岗位要求开场，并让候选人说明自己与岗位的匹配点。"
                if mode == "jd_prep"
                else "请围绕专项领域开场，并让候选人先说明对该领域的整体认识。"
                if topic
                else "请开场并让候选人做 1 分钟自我介绍。"
            ),
        )

    def next_question(
        self,
        phase: str,
        target_role: str,
        last_answer: str,
        question_number: int = 1,
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> str:
        context = self._job_context(company, position, knowledge_context, question_bank) if mode == "jd_prep" else self._topic_context(topic, knowledge_context, question_bank)
        return self._chat(
            "你是技术面试官。只输出一个下一步面试问题，不要评价、不要输出问题编号。"
            "问题必须结合候选人的上一轮回答，避免重复原问题。",
            f"岗位：{target_role}\n阶段：{phase}\n阶段内第 {question_number} 个问题\n"
            f"简历摘要：{self._resume_context(resume_text)}\n"
            f"{context}\n"
            f"上一轮回答：{last_answer[:4000]}",
        )

    def review(
        self,
        messages: list[dict[str, str]],
        target_role: str = "",
        resume_text: str = "",
        topic: str = "",
        knowledge_context: str = "",
        mode: str = "resume",
        company: str = "",
        position: str = "",
    ) -> dict[str, Any]:
        context = self._job_context(company, position, knowledge_context) if mode == "jd_prep" else self._topic_context(topic, knowledge_context)
        transcript = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
        raw = self._chat(
            "你是技术面试复盘引擎。只返回 JSON 对象，不要 Markdown 代码块。字段必须包含："
            "summary(string), average_score(number 0-10), scores(array), strengths(array), "
            "weak_points(array), behavior_signals(array), action_items(array)。"
            "behavior_signals 用简短句子描述候选人的稳定表达或行为信号，不能编造经历。",
            f"岗位：{target_role}\n简历摘要：{self._resume_context(resume_text)}\n"
            f"{context}\n面试记录：\n{transcript[:12000]}",
        )
        return _parse_review(raw)
