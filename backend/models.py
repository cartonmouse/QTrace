from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)


class RegisterRequest(Credentials):
    name: str = Field(default="Interview Learner", min_length=1, max_length=80)


class LoginRequest(Credentials):
    pass


class UserView(BaseModel):
    id: str
    email: str
    name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserView


class SettingsUpdate(BaseModel):
    use_stub_provider: bool = False
    llm_api_base: str = Field(default="", max_length=500)
    llm_model: str = Field(default="", max_length=200)
    llm_api_key: str = Field(default="", max_length=500)


class SettingsView(BaseModel):
    use_stub_provider: bool
    provider_mode: str
    llm_api_base: str
    llm_model: str
    llm_key_configured: bool
    embedding_mode: str
    llm_configured: bool
    embedding_configured: bool
    needs_onboarding: bool


class ResumeStatusView(BaseModel):
    has_resume: bool
    filename: str
    size: int
    text_chars: int


class ResumeTextView(BaseModel):
    filename: str
    text: str


class TopicCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="📝", max_length=8)
    key: str = Field(default="", max_length=40)


class KnowledgeFileCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=60_000)


class KnowledgeContentRequest(BaseModel):
    content: str = Field(default="", max_length=40_000)


class StartInterviewRequest(BaseModel):
    mode: Literal["resume", "topic_drill"] = "resume"
    topic: str | None = Field(default=None, max_length=40)
    target_role: str = Field(default="AI 应用开发工程师", min_length=1, max_length=120)
    resume_text: str = Field(default="", max_length=20_000)


class JobPrepPreviewRequest(BaseModel):
    jd_text: str = Field(min_length=50, max_length=20_000)
    company: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)
    use_resume: bool = True


class JobPrepStartRequest(JobPrepPreviewRequest):
    preview: dict[str, Any] | None = None


class CopilotPrepRequest(BaseModel):
    jd_text: str = Field(min_length=50, max_length=20_000)
    company: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)
    use_resume: bool = True


class RecordingAnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=20, max_length=40_000)
    recording_mode: Literal["dual", "solo"] = "dual"
    analysis_mode: Literal["rules", "llm"] = "rules"
    company: str | None = Field(default=None, max_length=120)
    position: str | None = Field(default=None, max_length=120)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)


class SessionView(BaseModel):
    id: str
    target_role: str
    phase: str
    phase_question_count: int
    is_finished: bool
    messages: list[dict[str, str]]
    review: dict[str, Any] | None = None
    mode: str = "resume"
    topic: str | None = None
    company: str = ""
    position: str = ""
    recording_mode: str = ""
    recording_analysis_mode: str = ""


class CopilotPrepView(BaseModel):
    id: str
    company: str
    position: str
    jd_text: str
    status: str
    result: dict[str, Any] | None = None
    error: str = ""
    created_at: str
    updated_at: str


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    conversation_id: str | None = Field(default=None, max_length=80)


class AgentConversationView(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class AgentConversationDetailView(BaseModel):
    id: str
    title: str
    messages: list[dict[str, Any]]
    created_at: str
    updated_at: str


class AgentChatView(BaseModel):
    conversation_id: str
    title: str
    message: dict[str, Any]
    plan: dict[str, Any]
    tool_trace: list[dict[str, Any]]


class TopicMasteryView(BaseModel):
    topic: str
    attempts: int
    mastery_score: float
    last_score: float
    weak_points: list[str]
    recent_scores: list[float] = Field(default_factory=list)
    trend: str = "flat"
    updated_at: str


class DueReviewView(BaseModel):
    point: str
    topic: str | None = None
    interval_days: int
    ease_factor: float
    repetitions: int
    next_review: str
    last_score: float | None = None
    updated_at: str


class ProfileView(BaseModel):
    completed_sessions: int
    mastery_score: float
    weak_points: list[str]
    strong_points: list[str] = Field(default_factory=list)
    behavior_signals: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    topic_mastery: list[TopicMasteryView] = Field(default_factory=list)
    due_reviews: list[DueReviewView] = Field(default_factory=list)
