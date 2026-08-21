from __future__ import annotations

from typing import Any

from .jd import analyze_jd


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _build_strategy_tree(preview: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for index, focus in enumerate(preview.get("focus_areas", [])[:6], start=1):
        area = str(focus.get("area", "岗位重点"))
        sample_questions = [
            str(item).strip()
            for item in focus.get("sample_questions", [])
            if str(item).strip()
        ]
        nodes.append(
            {
                "id": f"focus-{index}",
                "label": area,
                "priority": str(focus.get("priority", "normal")),
                "trigger": sample_questions[0] if sample_questions else f"请结合项目说明你的 {area} 经验。",
                "follow_up": sample_questions[1] if len(sample_questions) > 1 else "请说明一个取舍、结果和验证方法。",
            }
        )
    return {
        "root": preview.get("role_summary", "目标岗位面试策略"),
        "nodes": nodes,
    }


def _build_risk_map(preview: dict[str, Any], weak_points: list[str]) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for gap in preview.get("resume_alignment", {}).get("risk_gaps", [])[:4]:
        risks.append(
            {
                "risk": str(gap),
                "severity": "high",
                "evidence": "JD 与简历关键词未形成直接匹配",
                "mitigation": "准备一个可核验的学习、实践或迁移案例，不要把未做过的经验说成已上线。",
            }
        )
    for point in weak_points[:4]:
        risks.append(
            {
                "risk": str(point),
                "severity": "medium",
                "evidence": "历史训练画像中的薄弱点",
                "mitigation": "用背景、行动、结果和指标补齐回答，并准备失败边界。",
            }
        )
    if not risks:
        risks.append(
            {
                "risk": "回答可能停留在技术名词层面",
                "severity": "normal",
                "evidence": "当前没有足够历史薄弱点或简历缺口",
                "mitigation": "每个重点至少准备一个项目例子、一项指标和一种验证方式。",
            }
        )
    return risks


def build_copilot_prep(
    *,
    jd_text: str,
    company: str = "",
    position: str = "",
    resume_text: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, text-only Copilot Prep result.

    The shape intentionally resembles the reference project's prep output,
    while keeping the first implementation explainable and network-free.
    """
    clean_company = company.strip()
    clean_position = position.strip()
    preview = analyze_jd(
        jd_text,
        company=clean_company,
        position=clean_position,
        resume_text=resume_text,
    )
    profile = profile or {}
    weak_points = [
        str(item).strip()
        for item in profile.get("weak_points", [])
        if str(item).strip()
    ]
    strategy_tree = _build_strategy_tree(preview)
    risk_map = _build_risk_map(preview, weak_points)
    prep_hints = _unique(
        [
            *preview.get("prep_priorities", [])[:4],
            *[f"针对薄弱点准备：{point}" for point in weak_points[:3]],
            "每个高频追问都准备一个具体项目例子、结果指标和验证方法。",
        ]
    )[:8]
    return {
        "company": clean_company,
        "position": clean_position,
        "role_summary": preview.get("role_summary", ""),
        "detected_skills": preview.get("detected_skills", []),
        "focus_areas": preview.get("focus_areas", []),
        "resume_alignment": preview.get("resume_alignment", {}),
        "strategy_tree": strategy_tree,
        "risk_map": risk_map,
        "prep_hints": prep_hints,
        "question_blueprint": preview.get("question_blueprint", [])[:8],
        "source": {
            "resume_used": bool(resume_text.strip()),
            "profile_used": bool(weak_points),
            "analysis_mode": "deterministic_text_prep",
        },
    }


def copilot_event_sequence(result: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return the ordered events used by the SSE transport."""
    return [
        (
            "jd_analyzed",
            {
                "stage": "jd_analyzed",
                "message": "JD 已拆解，正在提取岗位重点。",
                "detected_skills": result.get("detected_skills", []),
            },
        ),
        (
            "risk_assessed",
            {
                "stage": "risk_assessed",
                "message": "已结合简历与画像生成风险地图。",
                "risk_count": len(result.get("risk_map", [])),
            },
        ),
        (
            "strategy_ready",
            {
                "stage": "strategy_ready",
                "message": "追问策略树已生成。",
                "node_count": len(result.get("strategy_tree", {}).get("nodes", [])),
            },
        ),
    ]
