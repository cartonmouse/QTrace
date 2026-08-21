from __future__ import annotations

from typing import Any

from .provider import InterviewProvider


PHASE_ORDER = ["self_intro", "technical", "project_deep_dive", "behavioral", "reverse_qa"]
PHASE_LIMITS = {
    "self_intro": 1,
    "technical": 2,
    "project_deep_dive": 2,
    "behavioral": 2,
    "reverse_qa": 1,
}


class InterviewEngine:
    def __init__(self, provider: InterviewProvider):
        self.provider = provider

    def start(
        self,
        target_role: str,
        resume_text: str,
        *,
        mode: str = "resume",
        topic: str | None = None,
        knowledge_context: str = "",
        question_bank: list[str] | None = None,
        company: str = "",
        position: str = "",
    ) -> dict[str, Any]:
        return {
            "target_role": target_role.strip(),
            "resume_text": resume_text,
            "mode": mode,
            "topic": topic,
            "knowledge_context": knowledge_context,
            "question_bank": question_bank or [],
            "company": company,
            "position": position,
            "phase": "self_intro",
            "phase_question_count": 1,
            "is_finished": False,
            "messages": [{
                "role": "assistant",
                "content": self.provider.opening(
                    target_role,
                    resume_text,
                    topic or "",
                    knowledge_context,
                    question_bank or [],
                    mode=mode,
                    company=company,
                    position=position,
                ),
            }],
            "review": None,
        }

    def answer(self, state: dict[str, Any], answer: str) -> dict[str, Any]:
        if state["is_finished"]:
            raise ValueError("session already finished")
        clean_answer = answer.strip()
        if not clean_answer:
            raise ValueError("answer cannot be empty")
        state["messages"].append({"role": "user", "content": clean_answer})

        phase = state["phase"]
        if state["phase_question_count"] >= PHASE_LIMITS[phase]:
            phase_index = PHASE_ORDER.index(phase)
            if phase_index == len(PHASE_ORDER) - 1:
                state["is_finished"] = True
                return state
            state["phase"] = PHASE_ORDER[phase_index + 1]
            state["phase_question_count"] = 0

        next_question = self.provider.next_question(
            state["phase"],
            state["target_role"],
            clean_answer,
            state["phase_question_count"] + 1,
            state.get("resume_text", ""),
            state.get("topic") or "",
            state.get("knowledge_context", ""),
            state.get("question_bank", []),
            mode=state.get("mode", "resume"),
            company=state.get("company", ""),
            position=state.get("position", ""),
        )
        state["messages"].append({"role": "assistant", "content": next_question})
        state["phase_question_count"] += 1
        return state

    def finish(self, state: dict[str, Any]) -> dict[str, Any]:
        if not state["review"]:
            state["review"] = self.provider.review(
                state["messages"],
                state["target_role"],
                state.get("resume_text", ""),
                state.get("topic") or "",
                state.get("knowledge_context", ""),
                mode=state.get("mode", "resume"),
                company=state.get("company", ""),
                position=state.get("position", ""),
            )
        state["is_finished"] = True
        return state
