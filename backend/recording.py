from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from typing import Any, Protocol


_SPEAKER_PREFIX = re.compile(
    r"^\s*(?P<speaker>面试官|候选人|你|我|interviewer|candidate|question|answer|q|a)\s*[:：]\s*(?P<content>.+)$",
    flags=re.IGNORECASE,
)


class RecordingAnalysisError(RuntimeError):
    """A transcript reached the analyzer but its structured result was unusable."""


class ASRError(RuntimeError):
    """An audio/transcript source could not be converted into a transcript document."""


class ASRProvider(Protocol):
    def transcribe(
        self,
        source: bytes,
        *,
        filename: str = "",
        content_type: str = "",
    ) -> dict[str, Any]: ...


class TextPassthroughASRProvider:
    """A local adapter used to exercise the ASR boundary without network calls.

    It accepts UTF-8 text exports only. An optional external transcription
    service can later return the same document shape without changing analysis.
    """

    max_chars = 40_000

    def transcribe(
        self,
        source: bytes,
        *,
        filename: str = "",
        content_type: str = "",
    ) -> dict[str, Any]:
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if content_type not in {"", "text/plain", "text/markdown"} and suffix not in {"txt", "md"}:
            raise ASRError("本地 mock ASR 只接受 UTF-8 文本转写文件")
        try:
            text = source.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ASRError("转写文件必须是 UTF-8 编码") from exc
        if not text:
            raise ASRError("转写文件内容为空")
        if len(text) > self.max_chars:
            raise ASRError(f"转写文本不能超过 {self.max_chars} 个字符")
        return {
            "text": text,
            "provider": "text_passthrough",
            "filename": filename,
            "content_type": content_type or "text/plain",
            "segments": [],
        }


class RecordingAnalyzer(Protocol):
    def analyze(
        self,
        transcript: str,
        *,
        recording_mode: str = "dual",
        company: str = "",
        position: str = "",
    ) -> tuple[list[dict[str, str]], dict[str, Any]]: ...


def _role(speaker: str) -> str:
    return "assistant" if speaker.lower() in {"面试官", "interviewer", "question", "q"} else "user"


def parse_transcript(transcript: str, recording_mode: str = "dual") -> list[dict[str, str]]:
    """Turn common speaker-labelled text into the message shape used by sessions."""
    clean = transcript.strip()
    if recording_mode == "solo":
        return [{"role": "user", "content": clean}] if clean else []

    messages: list[dict[str, str]] = []
    current_role: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_role and "\n".join(current_lines).strip():
            messages.append({"role": current_role, "content": "\n".join(current_lines).strip()})

    for line in clean.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _SPEAKER_PREFIX.match(stripped)
        if match:
            flush()
            current_role = _role(match.group("speaker"))
            current_lines = [match.group("content").strip()]
        elif current_role:
            current_lines.append(stripped)

    flush()
    if messages:
        return messages
    # A transcript without labels is still useful for solo-style analysis. Do
    # not invent interviewer/candidate boundaries that were not provided.
    return [{"role": "user", "content": clean}] if clean else []


def _answer_messages(messages: list[dict[str, str]]) -> list[str]:
    return [item["content"] for item in messages if item["role"] == "user" and item["content"].strip()]


def _score_answer(answer: str) -> float:
    score = 4.0 + min(2.5, len(answer) / 90)
    if re.search(r"\d+(?:\.\d+)?\s*%?", answer):
        score += 1.0
    if any(token in answer for token in ("结果", "提升", "降低", "指标", "验证", "复盘")):
        score += 1.0
    if any(token in answer for token in ("因为", "所以", "首先", "然后", "最后")):
        score += 0.5
    return min(10.0, round(score, 1))


def _transcript_meta(
    transcript: str,
    messages: list[dict[str, str]],
    recording_mode: str,
    *,
    analysis_mode: str = "rules",
) -> dict[str, Any]:
    return {
        "recording_mode": recording_mode,
        "analysis_mode": analysis_mode,
        "transcript_chars": len(transcript),
        "message_count": len(messages),
        "question_count": sum(1 for item in messages if item["role"] == "assistant"),
        "answer_count": sum(1 for item in messages if item["role"] == "user"),
        "estimated_minutes": round(len(transcript) / 300, 1),
        "speaker_labels_detected": any(_SPEAKER_PREFIX.match(line.strip()) for line in transcript.splitlines()),
    }


def analyze_transcript(
    transcript: str,
    *,
    recording_mode: str = "dual",
    company: str = "",
    position: str = "",
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Backward-compatible local rules analyzer."""
    clean = transcript.strip()
    messages = parse_transcript(clean, recording_mode)
    answers = _answer_messages(messages)
    scores = [_score_answer(answer) for answer in answers]
    average = round(sum(scores) / len(scores), 1) if scores else 0.0
    meta = _transcript_meta(clean, messages, recording_mode, analysis_mode="rules")

    weak_points: list[str] = []
    strengths: list[str] = []
    if not answers:
        weak_points.append("没有识别到候选人回答")
    elif any(len(answer) < 45 for answer in answers):
        weak_points.append("回答缺少足够的事实细节")
    if answers and not any(re.search(r"\d+(?:\.\d+)?\s*%?", answer) for answer in answers):
        weak_points.append("回答中缺少结果或量化指标")
    if answers and any(any(token in answer for token in ("结果", "提升", "指标", "验证")) for answer in answers):
        strengths.append("回答中出现了结果、指标或验证意识")
    if answers and any(len(answer) >= 80 for answer in answers):
        strengths.append("能够展开说明背景和行动")
    if recording_mode == "dual" and not meta["speaker_labels_detected"]:
        weak_points.append("双人转写缺少说话人标签，问答边界可能不准确")
    if recording_mode == "solo":
        strengths.append("完成了一次独立口述复盘")

    summary_prefix = f"{company + ' · ' if company else ''}{position or '面试'}"
    review = {
        "summary": f"本地文本录音复盘已完成：{summary_prefix}，识别 {meta['answer_count']} 个回答，估算时长 {meta['estimated_minutes']} 分钟。",
        "average_score": average,
        "scores": scores,
        "strengths": strengths or ["完成了一次可分析的转写复盘"],
        "weak_points": list(dict.fromkeys(weak_points)),
        "action_items": [
            "把每个回答补成背景、行动、结果和指标四段",
            "对最重要的技术结论补充验证方法和失败边界",
        ],
        "transcript_meta": meta,
        "segments": messages,
    }
    return messages, review


class RuleBasedRecordingAnalyzer:
    """Stable, explainable fallback that never calls an external service."""

    def analyze(
        self,
        transcript: str,
        *,
        recording_mode: str = "dual",
        company: str = "",
        position: str = "",
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        return analyze_transcript(
            transcript,
            recording_mode=recording_mode,
            company=company,
            position=position,
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:12]


def _parse_structured_review(raw: str) -> dict[str, Any]:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
    try:
        data = json.loads(clean.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        if not match:
            raise RecordingAnalysisError("LLM 复盘结果不是合法 JSON") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RecordingAnalysisError("LLM 复盘结果不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise RecordingAnalysisError("LLM 复盘结果必须是 JSON 对象")

    raw_scores = data.get("scores") if isinstance(data.get("scores"), list) else []
    scores: list[float] = []
    for value in raw_scores:
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(score):
            scores.append(round(min(10.0, max(0.0, score)), 1))
    try:
        average = float(data.get("average_score", 0) or 0)
    except (TypeError, ValueError):
        average = sum(scores) / len(scores) if scores else 0.0
    if not math.isfinite(average):
        average = sum(scores) / len(scores) if scores else 0.0
    summary = str(data.get("summary", "")).strip()
    if not summary:
        raise RecordingAnalysisError("LLM 复盘结果缺少 summary")
    return {
        "summary": summary,
        "average_score": round(min(10.0, max(0.0, average)), 1),
        "scores": scores,
        "strengths": _string_list(data.get("strengths")),
        "weak_points": _string_list(data.get("weak_points")),
        "action_items": _string_list(data.get("action_items")),
    }


class LLMRecordingAnalyzer:
    """Structured LLM analyzer behind a small callable chat boundary."""

    def __init__(self, chat: Callable[[str, str], str]):
        self._chat = chat

    def analyze(
        self,
        transcript: str,
        *,
        recording_mode: str = "dual",
        company: str = "",
        position: str = "",
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        clean = transcript.strip()
        messages = parse_transcript(clean, recording_mode)
        meta = _transcript_meta(clean, messages, recording_mode, analysis_mode="llm")
        transcript_view = "\n".join(
            f"{item['role']}: {item['content']}" for item in messages
        )[:16_000]
        raw = self._chat(
            "你是技术面试复盘引擎。只返回一个 JSON 对象，不要 Markdown 代码块。"
            "字段必须包含 summary(string)、average_score(number 0-10)、scores(array number)、"
            "strengths(array string)、weak_points(array string)、action_items(array string)。",
            f"公司：{company or '未提供'}\n岗位：{position or '未提供'}\n"
            f"转写模式：{recording_mode}\n面试记录：\n{transcript_view}\n"
            "请基于候选人的回答给出事实、结构、技术深度和验证意识方面的复盘，"
            "不要编造转写中没有出现的项目指标。",
        )
        review = _parse_structured_review(raw)
        review["transcript_meta"] = meta
        review["segments"] = messages
        return messages, review
