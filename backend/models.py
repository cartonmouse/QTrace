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


class EmbeddingSettingsUpdate(BaseModel):
    mode: Literal["demo", "local-model", "openai-compatible"] = "demo"
    api_base: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    model_path: str = Field(default="", max_length=1000)
    api_key: str = Field(default="", max_length=500)


class SettingsView(BaseModel):
    use_stub_provider: bool
    provider_mode: str
    llm_api_base: str
    llm_model: str
    llm_key_configured: bool
    embedding_mode: str
    embedding_api_base: str
    embedding_model: str
    embedding_model_path: str
    embedding_key_configured: bool
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


class ResumeProjectPayload(BaseModel):
    name: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2_000)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    highlights: list[str] = Field(default_factory=list, max_length=8)


class StructuredResumePayload(BaseModel):
    name: str = Field(default="", max_length=80)
    headline: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=160)
    location: str = Field(default="", max_length=120)
    summary: str = Field(default="", max_length=3_000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    projects: list[ResumeProjectPayload] = Field(default_factory=list, max_length=8)


class ResumeEditorSaveRequest(StructuredResumePayload):
    pass


class ResumeEditorView(BaseModel):
    id: str
    version: int
    profile: StructuredResumePayload
    context_text: str
    exists: bool = False
    unchanged: bool = False
    created_at: str = ""
    updated_at: str = ""


class ResumeEditorVersionView(BaseModel):
    id: str
    version: int
    context_chars: int
    project_count: int
    created_at: str


class ResumeEditorVersionDetailView(BaseModel):
    id: str
    version: int
    profile: StructuredResumePayload
    context_text: str
    created_at: str


class ResumeQuestionCardView(BaseModel):
    id: str
    resume_version: int
    project_name: str
    category: str
    question: str
    training_focus: str
    purpose: str
    field_refs: list[str]
    document_query: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class TopicCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="📝", max_length=8)
    key: str = Field(default="", max_length=40)


class TopicGraphNodeView(BaseModel):
    id: str
    type: str
    label: str
    status: str
    question: str = ""
    focus_area: str = ""
    topic: str = ""
    related_question_ids: list[str] = Field(default_factory=list)


class TopicGraphLinkView(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0
    started_count: int = 0
    completed_count: int = 0


class TopicGraphSummaryView(BaseModel):
    question_count: int
    due_review_count: int
    weak_point_count: int
    link_count: int


class TopicGraphView(BaseModel):
    topic: str
    topic_name: str
    mode: str
    nodes: list[TopicGraphNodeView] = Field(default_factory=list)
    links: list[TopicGraphLinkView] = Field(default_factory=list)
    summary: TopicGraphSummaryView


class TopicGraphFeedbackEdgeView(BaseModel):
    source: str
    target: str
    weight: float = 0.0
    started_count: int = 0
    completed_count: int = 0
    completion_rate: float = 0.0
    average_score: float | None = None
    score_delta: float | None = None
    repeat_rate: float = 0.0


class TopicGraphFeedbackSummaryView(BaseModel):
    candidate_edge_count: int = 0
    observed_edge_count: int = 0
    started_count: int = 0
    completed_count: int = 0


class TopicGraphFeedbackView(BaseModel):
    topic: str
    topic_name: str
    edges: list[TopicGraphFeedbackEdgeView] = Field(default_factory=list)
    summary: TopicGraphFeedbackSummaryView


class KnowledgeFileCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=60_000)


class KnowledgeContentRequest(BaseModel):
    content: str = Field(default="", max_length=40_000)


class StartInterviewRequest(BaseModel):
    mode: Literal["resume", "topic_drill"] = "resume"
    topic: str | None = Field(default=None, max_length=40)
    focus: str | None = Field(default=None, max_length=200)
    plan_id: str | None = Field(default=None, max_length=80)
    plan_item_id: str | None = Field(default=None, max_length=80)
    question_card_id: str | None = Field(default=None, max_length=120)
    graph_question_id: str | None = Field(default=None, max_length=40)
    graph_entry_source: str | None = Field(default=None, max_length=40)
    graph_parent_question_id: str | None = Field(default=None, max_length=40)
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
    question_bank: list[str] = Field(default_factory=list)
    review: dict[str, Any] | None = None
    mode: str = "resume"
    topic: str | None = None
    company: str = ""
    position: str = ""
    recording_mode: str = ""
    recording_analysis_mode: str = ""
    learning_plan_id: str | None = None
    learning_plan_item_id: str | None = None
    question_card_id: str | None = None
    question_card_project: str = ""
    question_card_resume_version: int | None = None
    graph_question_id: str | None = None
    graph_question: str = ""
    graph_entry_source: str = ""
    graph_parent_question_id: str | None = None
    graph_parent_question: str = ""
    created_at: str = ""
    updated_at: str = ""


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
    question_card_id: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=40)
    graph_question_id: str | None = Field(default=None, max_length=40)
    graph_entry_source: str | None = Field(default=None, max_length=40)
    graph_parent_question_id: str | None = Field(default=None, max_length=40)


class PersonalDocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=100_000)
    source_type: Literal["text", "markdown", "pdf"] = "text"


class PersonalDocumentUpdateRequest(PersonalDocumentCreateRequest):
    pass


class PersonalDocumentView(BaseModel):
    id: str
    title: str
    source_type: str
    version: int
    content_chars: int
    chunk_count: int
    embedding_mode: str
    created_at: str
    updated_at: str
    deduplicated: bool = False
    unchanged: bool = False


class PersonalDocumentVersionView(BaseModel):
    id: str
    document_id: str
    version: int
    title: str
    source_type: str
    content_chars: int
    chunk_count: int
    embedding_mode: str
    created_at: str


class PersonalDocumentVersionDetailView(PersonalDocumentVersionView):
    content: str


class PersonalDocumentSearchResult(BaseModel):
    document_id: str
    title: str
    source_type: str
    version: int
    chunk_index: int
    content: str
    score: float
    embedding_mode: str
    citation: str


class PersonalDocumentReindexView(BaseModel):
    embedding_mode: str
    document_count: int
    chunk_count: int


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
    created_plan: dict[str, Any] | None = None


class LearningPlanView(BaseModel):
    id: str
    conversation_id: str | None = None
    source_message: str
    title: str
    summary: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: str
    updated_at: str


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
