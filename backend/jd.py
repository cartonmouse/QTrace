from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


# This catalog is deliberately small and visible. It is a replaceable seam for
# an LLM extractor or a larger taxonomy later; the first version must remain
# deterministic and easy to explain in an interview.
SKILL_CATALOG: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Python", ("python", "python开发"), "语言与框架"),
    ("FastAPI", ("fastapi",), "语言与框架"),
    ("RAG", ("rag", "检索增强", "检索增强生成"), "LLM 应用"),
    ("Agent", ("agent", "智能体", "多智能体"), "LLM 应用"),
    ("LLM", ("llm", "大模型", "语言模型"), "LLM 应用"),
    ("Prompt", ("prompt", "提示词", "提示工程"), "LLM 应用"),
    ("Embedding", ("embedding", "向量", "向量检索"), "LLM 应用"),
    ("SQL", ("sql", "mysql", "postgresql", "数据库"), "数据与存储"),
    ("Redis", ("redis", "缓存"), "数据与存储"),
    ("Docker", ("docker", "容器化"), "工程化"),
    ("Kubernetes", ("kubernetes", "k8s"), "工程化"),
    ("微服务", ("微服务", "分布式"), "工程化"),
    ("评测", ("评测", "评估", "benchmark", "准确率", "召回率"), "质量与验证"),
    ("性能优化", ("性能优化", "高并发", "吞吐", "延迟", "压测"), "质量与验证"),
)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _contains_skill(text: str, aliases: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(alias.lower() in normalized for alias in aliases)


def _detected_skills(jd_text: str) -> list[tuple[str, str, int]]:
    normalized = jd_text.lower()
    hits: list[tuple[str, str, int]] = []
    for skill, aliases, category in SKILL_CATALOG:
        count = sum(normalized.count(alias.lower()) for alias in aliases)
        if count:
            hits.append((skill, category, count))
    return sorted(hits, key=lambda item: (-item[2], item[0]))


def _focus_areas(skills: list[tuple[str, str, int]]) -> list[dict[str, str]]:
    if not skills:
        return [{
            "area": "岗位通用能力",
            "priority": "high",
            "reason": "JD 没有命中预置技术词，需要通过目标、职责和面试沟通进一步确认岗位重点。",
        }]
    areas: list[dict[str, str]] = []
    for index, (skill, category, count) in enumerate(skills[:6]):
        priority = "high" if index < 2 else "medium" if index < 4 else "normal"
        areas.append({
            "area": skill,
            "priority": priority,
            "reason": f"JD 中出现 {count} 次，属于「{category}」；面试官可能要求你同时说明原理、项目落地和验证方式。",
        })
    return areas


def _question_blueprint(position: str, focus_areas: list[dict[str, str]]) -> list[dict[str, Any]]:
    skills = [item["area"] for item in focus_areas if item["area"] != "岗位通用能力"]
    first = skills[0] if skills else "岗位核心能力"
    second = skills[1] if len(skills) > 1 else first
    return [
        {
            "category": "岗位匹配",
            "focus_area": position or "目标岗位",
            "objective": "确认候选人是否理解岗位目标，并能把经历映射到职责。",
            "question": f"请结合这份 JD 做一个 1 分钟自我介绍，重点说明你为什么适合「{position or '这个岗位'}」。",
        },
        {
            "category": "核心技术",
            "focus_area": first,
            "objective": "验证核心技术的概念、原理和边界。",
            "question": f"请解释你对 {first} 的理解，并结合一个工程场景说明它解决了什么问题。",
        },
        {
            "category": "技术取舍",
            "focus_area": second,
            "objective": "观察候选人能否根据约束做设计决策。",
            "question": f"如果在项目中使用 {second}，你会如何做方案选型？请说明至少一个取舍和验证指标。",
        },
        {
            "category": "项目深挖",
            "focus_area": "项目结果",
            "objective": "确认职责边界、关键设计和可核验结果。",
            "question": "请挑一个最相关的项目，拆解目标、你的职责、关键设计、结果和一次复盘。",
        },
        {
            "category": "工程化场景",
            "focus_area": "可靠性与性能",
            "objective": "验证候选人能否把原型推进到可维护系统。",
            "question": "如果系统请求量增长 10 倍，你会优先检查哪些瓶颈，并如何设计压测和降级方案？",
        },
        {
            "category": "质量验证",
            "focus_area": "评测与观测",
            "objective": "判断候选人是否建立了指标、实验和回归机制。",
            "question": "你会如何验证这个方案有效？请区分离线指标、线上指标和失败样本分析。",
        },
        {
            "category": "协作推进",
            "focus_area": "跨团队沟通",
            "objective": "了解需求不清或意见不一致时的推进方式。",
            "question": "当产品、算法和工程团队对方案意见不一致时，你会如何澄清问题并推动落地？",
        },
        {
            "category": "反问",
            "focus_area": "岗位理解",
            "objective": "观察候选人是否能主动判断岗位和团队匹配度。",
            "question": "基于这份 JD，你会向面试官反问哪两个问题来判断岗位目标和团队工程文化？",
        },
    ]


def analyze_jd(
    jd_text: str,
    *,
    company: str | None = None,
    position: str | None = None,
    resume_text: str = "",
) -> dict[str, Any]:
    clean_jd = _clean(jd_text)
    clean_company = _clean(company)
    clean_position = _clean(position)
    skills = _detected_skills(clean_jd)
    focus_areas = _focus_areas(skills)
    resume_lower = resume_text.lower()
    matching = [skill for skill, aliases, _ in SKILL_CATALOG if _contains_skill(resume_lower, aliases)]
    jd_skills = [skill for skill, _, _ in skills]
    matching = [skill for skill in matching if skill in jd_skills]
    gaps = [skill for skill in jd_skills if skill not in matching]
    resume_used = bool(resume_text.strip())
    if resume_used:
        fit_assessment = (
            f"简历命中 {len(matching)}/{len(jd_skills) or 1} 个预置 JD 技能点；"
            "下一轮应优先准备命中经历和未覆盖要求的解释。"
        )
    else:
        fit_assessment = "当前按 JD 做通用岗位分析，上传或填写简历后可以进一步做经历匹配。"

    recommended_stories = [
        {"project": f"与 {skill} 相关的项目经历", "reason": f"用来证明你在 {skill} 上不仅了解概念，还承担过落地职责。"}
        for skill in matching[:3]
    ]
    blueprint = _question_blueprint(clean_position, focus_areas)
    priorities = [
        f"为 {skill} 准备一个包含背景、行动、结果和指标的项目故事"
        for skill in jd_skills[:4]
    ]
    if not priorities:
        priorities = ["补充岗位职责、技术栈和可量化结果，再进行定向分析"]
    groups = [
        {
            "title": "JD 核心技术",
            "reason": "围绕 JD 出现频率最高的技术点进行原理和边界追问。",
            "sample_questions": [item["question"] for item in blueprint[1:3]],
        },
        {
            "title": "项目与工程化",
            "reason": "验证候选人是否真正做过相关项目，并能解释可靠性、性能和验证。",
            "sample_questions": [item["question"] for item in blueprint[3:6]],
        },
        {
            "title": "岗位匹配与协作",
            "reason": "判断候选人能否把个人经历映射到职责并推动跨团队落地。",
            "sample_questions": [blueprint[0]["question"], blueprint[6]["question"]],
        },
        {
            "title": "反问与双向选择",
            "reason": "帮助候选人在面试末尾确认岗位目标、团队和工程文化。",
            "sample_questions": [blueprint[7]["question"]],
        },
    ]
    return {
        "company": clean_company,
        "position": clean_position,
        "role_summary": (
            f"{clean_company + ' 的' if clean_company else ''}{clean_position or '该岗位'}重点考察 "
            f"{ '、'.join(jd_skills[:4]) if jd_skills else '岗位职责理解、项目表达和工程验证能力'}。"
        ),
        "focus_areas": focus_areas,
        "likely_question_groups": groups,
        "resume_alignment": {
            "resume_used": resume_used,
            "fit_assessment": fit_assessment,
            "matching_evidence": [f"简历中检测到 {skill} 相关关键词" for skill in matching],
            "risk_gaps": [f"JD 要求 {skill}，当前简历未检测到对应关键词" for skill in gaps[:5]],
            "recommended_stories": recommended_stories,
        },
        "prep_priorities": priorities,
        "question_blueprint": blueprint,
        "jd_excerpt": clean_jd[:1500],
        "detected_skills": jd_skills,
    }


def build_jd_question_bank(preview: dict[str, Any], due_points: list[str] | None = None) -> list[str]:
    questions: list[str] = [
        f"复习任务：请优先解释「{point}」，结合目标岗位要求说明原理、取舍和验证方式。"
        for point in (due_points or [])[:5]
    ]
    for item in preview.get("question_blueprint", []):
        if isinstance(item, dict) and str(item.get("question", "")).strip():
            questions.append(str(item["question"]).strip())
    return list(dict.fromkeys(questions))[:12]


def build_jd_context(jd_text: str, preview: dict[str, Any]) -> str:
    return (
        f"岗位 JD：\n{_clean(jd_text)[:8000]}\n\n"
        f"岗位分析：\n{json.dumps(preview, ensure_ascii=False, indent=2)[:8000]}"
    )
