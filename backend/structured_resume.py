from __future__ import annotations

import hashlib
import json
from typing import Any

from .store import Store


MAX_RESUME_PROFILE_CHARS = 20_000
MAX_PROJECTS = 8
MAX_SKILLS = 30


class StructuredResumeError(ValueError):
    """A structured resume profile is not usable as interview context."""


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _clean_multiline(value: Any, limit: int) -> str:
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [" ".join(line.split()).strip() for line in raw.split("\n")]
    return "\n".join(line for line in lines if line)[:limit]


def _clean_list(value: Any, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = _clean_text(item, item_limit)
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
        if len(result) >= limit:
            break
    return result


def normalize_resume_profile(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StructuredResumeError("结构化简历必须是对象")
    projects: list[dict[str, Any]] = []
    raw_projects = payload.get("projects", [])
    if not isinstance(raw_projects, list):
        raise StructuredResumeError("项目经历必须是数组")
    for raw_project in raw_projects[:MAX_PROJECTS]:
        if not isinstance(raw_project, dict):
            continue
        project = {
            "name": _clean_text(raw_project.get("name"), 120),
            "role": _clean_text(raw_project.get("role"), 120),
            "description": _clean_multiline(raw_project.get("description"), 2_000),
            "technologies": _clean_list(raw_project.get("technologies"), limit=20, item_limit=60),
            "highlights": _clean_list(raw_project.get("highlights"), limit=8, item_limit=240),
        }
        if any(project.values()):
            if not project["name"]:
                raise StructuredResumeError("每个项目都需要填写项目名称")
            projects.append(project)

    normalized = {
        "name": _clean_text(payload.get("name"), 80),
        "headline": _clean_text(payload.get("headline"), 160),
        "email": _clean_text(payload.get("email"), 160),
        "location": _clean_text(payload.get("location"), 120),
        "summary": _clean_multiline(payload.get("summary"), 3_000),
        "skills": _clean_list(payload.get("skills"), limit=MAX_SKILLS, item_limit=60),
        "projects": projects,
    }
    if not any((normalized["summary"], normalized["skills"], normalized["projects"])):
        raise StructuredResumeError("至少填写个人概述、技能或一个项目经历")
    serialized = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > MAX_RESUME_PROFILE_CHARS:
        raise StructuredResumeError(f"结构化简历不能超过 {MAX_RESUME_PROFILE_CHARS} 字")
    return normalized


def render_resume_context(profile: dict[str, Any]) -> str:
    """Render stable structured fields into the text contract used by interview flows."""
    lines: list[str] = []
    if profile.get("name"):
        lines.append(f"姓名：{profile['name']}")
    if profile.get("headline"):
        lines.append(f"目标方向：{profile['headline']}")
    if profile.get("email"):
        lines.append(f"联系方式：{profile['email']}")
    if profile.get("location"):
        lines.append(f"所在地：{profile['location']}")
    if profile.get("summary"):
        lines.extend(["个人概述：", str(profile["summary"])])
    if profile.get("skills"):
        lines.append(f"技能：{'、'.join(profile['skills'])}")
    projects = profile.get("projects") or []
    if projects:
        lines.append("项目经历：")
        for project in projects:
            role = f"（{project['role']}）" if project.get("role") else ""
            lines.append(f"- {project['name']}{role}")
            if project.get("description"):
                lines.append(f"  项目概述：{project['description']}")
            if project.get("technologies"):
                lines.append(f"  技术栈：{'、'.join(project['technologies'])}")
            for highlight in project.get("highlights") or []:
                lines.append(f"  关键工作：{highlight}")
    return "\n".join(lines)[:MAX_RESUME_PROFILE_CHARS]


def resume_profile_hash(profile: dict[str, Any]) -> str:
    serialized = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_project_question_cards(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Build explainable follow-up cards from fields, without asking an LLM."""
    cards: list[dict[str, Any]] = []
    templates = (
        (
            "背景与目标",
            "这个项目要解决什么问题？用户为什么需要它？",
            "先把项目价值和边界讲清楚，再进入技术细节。",
            ["description"],
        ),
        (
            "个人职责",
            "你在这个项目中具体负责哪些模块？哪些工作是你亲自完成的？",
            "避免把团队成果泛化成个人经历，准备能落到代码和决策的证据。",
            ["role", "highlights"],
        ),
        (
            "关键设计",
            "为什么选择这套技术和架构？如果换一种方案，代价是什么？",
            "面试官通常会从技术栈继续追问取舍，而不是只听技术名词。",
            ["technologies", "highlights"],
        ),
        (
            "效果验证",
            "你如何证明这个方案有效？用了什么指标、基线或故障验证？",
            "把项目描述从‘做过’推进到‘验证过’，准备量化或可复现的结果。",
            ["highlights", "description"],
        ),
        (
            "复盘取舍",
            "这个项目中最难的工程取舍是什么？如果再做一次，你会改什么？",
            "准备一个真实限制和改进方向，体现工程判断而不是只背成功故事。",
            ["description", "technologies", "highlights"],
        ),
    )
    for project_index, project in enumerate(profile.get("projects", []) or []):
        if not isinstance(project, dict) or not project.get("name"):
            continue
        project_name = str(project["name"])
        for card_index, (category, question, purpose, field_refs) in enumerate(templates):
            cards.append(
                {
                    "id": f"project-{project_index + 1}-question-{card_index + 1}",
                    "project_name": project_name,
                    "category": category,
                    "question": question,
                    "training_focus": question,
                    "purpose": purpose,
                    "field_refs": field_refs,
                    "document_query": f"{project_name} {category}",
                    "evidence": [],
                }
            )
    return cards


class StructuredResumeService:
    """Validate, version and render the user's structured resume profile."""

    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def empty_profile() -> dict[str, Any]:
        return {
            "name": "",
            "headline": "",
            "email": "",
            "location": "",
            "summary": "",
            "skills": [],
            "projects": [],
        }

    def get_profile(self, user_id: str) -> dict[str, Any]:
        current = self.store.get_resume_profile(user_id)
        if current:
            return current
        return {
            "id": "",
            "version": 0,
            "profile": self.empty_profile(),
            "context_text": "",
            "created_at": "",
            "updated_at": "",
            "exists": False,
            "unchanged": False,
        }

    def save_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile = normalize_resume_profile(payload)
        return self.store.save_resume_profile(
            user_id,
            profile=profile,
            context_text=render_resume_context(profile),
            profile_hash=resume_profile_hash(profile),
        )

    def list_versions(self, user_id: str) -> list[dict[str, Any]]:
        return self.store.list_resume_profile_versions(user_id)

    def get_version(self, user_id: str, version: int) -> dict[str, Any] | None:
        return self.store.get_resume_profile_version(user_id, version)

    def get_context(self, user_id: str) -> str:
        current = self.store.get_resume_profile(user_id)
        return str(current.get("context_text", "")) if current else ""

    def question_cards(self, user_id: str) -> list[dict[str, Any]]:
        current = self.store.get_resume_profile(user_id)
        if not current:
            return []
        cards = build_project_question_cards(current.get("profile", {}))
        for card in cards:
            card["resume_version"] = int(current.get("version", 0))
        return cards

    def get_question_card(self, user_id: str, card_id: str) -> dict[str, Any] | None:
        """Resolve a current-user card before attaching it to a training session."""
        clean_id = str(card_id or "").strip()
        if not clean_id:
            return None
        return next((card for card in self.question_cards(user_id) if card["id"] == clean_id), None)
