from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .agent import AgentProviderError, build_agent_model, run_personal_agent
from .config import DB_PATH, JWT_SECRET, TOKEN_TTL_SECONDS
from .copilot import build_copilot_prep, copilot_event_sequence
from .graph import build_topic_feedback_report, build_topic_graph, resolve_graph_question_entry
from .interview import InterviewEngine
from .jd import analyze_jd, build_jd_context, build_jd_question_bank
from .document_import import (
    DocumentImportError,
    MAX_PDF_BYTES,
    extract_markdown_text_from_bytes,
    extract_pdf_text_from_bytes,
)
from .embedding import EmbeddingProviderError, build_embedding_provider
from .personal_documents import MAX_DOCUMENT_CHARS, PersonalDocumentError, PersonalDocumentService
from .recording import (
    LLMRecordingAnalyzer,
    RecordingAnalysisError,
    RuleBasedRecordingAnalyzer,
)
from .models import (
    AnswerRequest,
    AgentChatRequest,
    AgentChatView,
    AgentConversationDetailView,
    AgentConversationView,
    EmbeddingSettingsUpdate,
    PersonalDocumentCreateRequest,
    PersonalDocumentUpdateRequest,
    PersonalDocumentSearchResult,
    PersonalDocumentView,
    PersonalDocumentVersionDetailView,
    PersonalDocumentVersionView,
    PersonalDocumentReindexView,
    LearningPlanView,
    AuthResponse,
    CopilotPrepRequest,
    CopilotPrepView,
    DueReviewView,
    JobPrepPreviewRequest,
    JobPrepStartRequest,
    LoginRequest,
    ProfileView,
    RegisterRequest,
    KnowledgeContentRequest,
    KnowledgeFileCreateRequest,
    SessionView,
    SettingsUpdate,
    SettingsView,
    ResumeStatusView,
    ResumeTextView,
    ResumeEditorSaveRequest,
    ResumeEditorVersionDetailView,
    ResumeEditorVersionView,
    ResumeEditorView,
    ResumeQuestionCardView,
    RecordingAnalyzeRequest,
    StartInterviewRequest,
    TopicMasteryView,
    TopicCreateRequest,
    TopicGraphView,
    TopicGraphFeedbackView,
    UserView,
)
from .provider import OpenAICompatibleProvider, ProviderError, StubProvider
from .personalized_drill import build_drill_question_generator
from .knowledge import (
    KnowledgeError,
    create_core_file,
    create_topic,
    delete_core_file,
    delete_topic,
    get_high_freq,
    get_topic_bundle,
    list_core_files,
    list_topics,
    update_core_file,
    update_high_freq,
)
from .resume import ResumeError, delete_resume, get_resume_file, get_resume_status, get_resume_text, save_resume
from .structured_resume import StructuredResumeError, StructuredResumeService
from .security import create_access_token, decode_access_token, verify_password
from .store import Store


bearer = HTTPBearer(auto_error=False)


def create_app(db_path: str | Path | None = None, jwt_secret: str | None = None) -> FastAPI:
    app = FastAPI(title="问迹 QTrace", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = Store(db_path or DB_PATH)
    app.state.personal_documents = PersonalDocumentService(app.state.store)
    app.state.structured_resume = StructuredResumeService(app.state.store)
    app.state.jwt_secret = jwt_secret or JWT_SECRET
    app.state.data_dir = Path(db_path or DB_PATH).parent

    def personal_documents_for(request: Request, user: dict[str, Any]) -> PersonalDocumentService:
        try:
            provider = build_embedding_provider(request.app.state.store.get_embedding_config(user["id"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PersonalDocumentService(request.app.state.store, provider)

    def settings_view(values: dict[str, Any]) -> SettingsView:
        return SettingsView(
            **values,
            needs_onboarding=not (values["llm_configured"] and values["embedding_configured"]),
        )

    def current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict[str, Any]:
        if not credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录后继续")
        try:
            payload = decode_access_token(credentials.credentials, request.app.state.jwt_secret)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效") from exc
        user = request.app.state.store.get_user(str(payload["sub"]))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
        return user

    def ensure_provider_ready(request: Request, user: dict[str, Any]) -> None:
        settings = request.app.state.store.get_settings(user["id"])
        if not settings["llm_configured"] or not settings["embedding_configured"]:
            raise HTTPException(
                status_code=400,
                detail={"code": "provider_not_configured", "message": "请先配置 LLM 或启用本地演示模型"},
            )

    def engine_for(request: Request, user: dict[str, Any]) -> InterviewEngine:
        ensure_provider_ready(request, user)
        config = request.app.state.store.get_provider_config(user["id"])
        if config["mode"] == "stub":
            return InterviewEngine(StubProvider())
        if config["mode"] == "openai":
            return InterviewEngine(
                OpenAICompatibleProvider(
                    api_base=config["api_base"],
                    api_key=config["api_key"],
                    model=config["model"],
                )
            )
        raise HTTPException(status_code=400, detail={"code": "provider_not_configured", "message": "请先配置模型服务"})

    def recording_analyzer_for(request: Request, user: dict[str, Any], analysis_mode: str):
        if analysis_mode == "rules":
            return RuleBasedRecordingAnalyzer()
        config = request.app.state.store.get_provider_config(user["id"])
        if config["mode"] != "openai":
            raise HTTPException(status_code=400, detail="选择 LLM 复盘前，请先在模型设置中配置真实 LLM")
        provider = OpenAICompatibleProvider(
            api_base=config["api_base"],
            api_key=config["api_key"],
            model=config["model"],
        )
        return LLMRecordingAnalyzer(provider.structured_chat)

    def agent_model_for(request: Request, user: dict[str, Any]):
        return build_agent_model(request.app.state.store.get_provider_config(user["id"]))

    def recent_topic_context(request: Request, user: dict[str, Any], topic: str) -> list[dict[str, Any]]:
        """Keep the question generator grounded in the user's recent topic attempts."""
        result: list[dict[str, Any]] = []
        for session in request.app.state.store.list_sessions(user["id"], topic=topic)[:8]:
            review = session.get("review") or {}
            result.append(
                {
                    "average_score": review.get("average_score", 0),
                    "weak_points": review.get("weak_points", [])[:5],
                    "strengths": review.get("strengths", [])[:3],
                    "action_items": review.get("action_items", [])[:3],
                    "phase": session.get("phase", ""),
                }
            )
        return result

    def user_view(user: dict[str, Any]) -> UserView:
        return UserView(id=user["id"], email=user["email"], name=user["name"])

    def session_view(session: dict[str, Any]) -> SessionView:
        return SessionView(
            id=session["id"],
            target_role=session["target_role"],
            phase=session["phase"],
            phase_question_count=session["phase_question_count"],
            is_finished=session["is_finished"],
            messages=session["messages"],
            question_bank=session.get("question_bank", []),
            review=session["review"],
            mode=session.get("mode", "resume"),
            topic=session.get("topic"),
            company=session.get("company", ""),
            position=session.get("position", ""),
            recording_mode=session.get("recording_mode", ""),
            recording_analysis_mode=session.get(
                "recording_analysis_mode",
                (session.get("recording_meta") or {}).get("analysis_mode", ""),
            ),
            learning_plan_id=session.get("learning_plan_id"),
            learning_plan_item_id=session.get("learning_plan_item_id"),
            question_card_id=session.get("question_card_id"),
            question_card_project=session.get("question_card_project", ""),
            question_card_resume_version=session.get("question_card_resume_version"),
            graph_question_id=session.get("graph_question_id"),
            graph_question=session.get("graph_question", ""),
            graph_entry_source=session.get("graph_entry_source", ""),
            graph_parent_question_id=session.get("graph_parent_question_id"),
            graph_parent_question=session.get("graph_parent_question", ""),
            created_at=session.get("created_at", ""),
            updated_at=session.get("updated_at", ""),
        )

    def copilot_view(prep: dict[str, Any]) -> CopilotPrepView:
        return CopilotPrepView(
            id=prep["id"],
            company=prep["company"],
            position=prep["position"],
            jd_text=prep["jd_text"],
            status=prep["status"],
            result=prep.get("result"),
            error=prep.get("error", ""),
            created_at=prep["created_at"],
            updated_at=prep["updated_at"],
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "qtrace"}

    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(payload: RegisterRequest, request: Request) -> AuthResponse:
        store: Store = request.app.state.store
        if store.get_user_by_email(payload.email):
            raise HTTPException(status_code=409, detail="邮箱已注册")
        user = store.create_user(payload.email, payload.password, payload.name)
        token = create_access_token(user["id"], request.app.state.jwt_secret, TOKEN_TTL_SECONDS)
        return AuthResponse(access_token=token, user=user_view(user))

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, request: Request) -> AuthResponse:
        store: Store = request.app.state.store
        user_record = store.get_user_by_email(payload.email)
        if not user_record or not verify_password(payload.password, user_record["password_hash"]):
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        user = {"id": user_record["id"], "email": user_record["email"], "name": user_record["name"]}
        token = create_access_token(user["id"], request.app.state.jwt_secret, TOKEN_TTL_SECONDS)
        return AuthResponse(access_token=token, user=user_view(user))

    @app.get("/api/me", response_model=UserView)
    def me(user: dict[str, Any] = Depends(current_user)) -> UserView:
        return user_view(user)

    @app.get("/api/settings", response_model=SettingsView)
    def get_settings(request: Request, user: dict[str, Any] = Depends(current_user)) -> SettingsView:
        values = request.app.state.store.get_settings(user["id"])
        return settings_view(values)

    @app.put("/api/settings", response_model=SettingsView)
    def update_settings(payload: SettingsUpdate, request: Request, user: dict[str, Any] = Depends(current_user)) -> SettingsView:
        try:
            if payload.use_stub_provider:
                values = request.app.state.store.set_stub_provider(user["id"], True)
            else:
                values = request.app.state.store.set_openai_provider(
                    user["id"], payload.llm_api_base, payload.llm_model, payload.llm_api_key
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return settings_view(values)

    @app.put("/api/settings/embedding", response_model=SettingsView)
    def update_embedding_settings(
        payload: EmbeddingSettingsUpdate,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> SettingsView:
        try:
            if payload.mode == "demo":
                values = request.app.state.store.set_embedding_demo(user["id"])
            elif payload.mode == "local-model":
                values = request.app.state.store.set_local_embedding(user["id"], payload.model_path)
            else:
                values = request.app.state.store.set_openai_embedding(
                    user["id"], payload.api_base, payload.model, payload.api_key
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return settings_view(values)

    @app.get("/api/resume/status", response_model=ResumeStatusView)
    def resume_status(request: Request, user: dict[str, Any] = Depends(current_user)) -> ResumeStatusView:
        try:
            return ResumeStatusView(**get_resume_status(user["id"], request.app.state.data_dir))
        except ResumeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/resume/text", response_model=ResumeTextView)
    def resume_text(request: Request, user: dict[str, Any] = Depends(current_user)) -> ResumeTextView:
        try:
            text, filename = get_resume_text(user["id"], request.app.state.data_dir)
        except ResumeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ResumeTextView(filename=filename, text=text)

    @app.get("/api/resume/file")
    def resume_file(request: Request, user: dict[str, Any] = Depends(current_user)) -> FileResponse:
        path = get_resume_file(user["id"], request.app.state.data_dir)
        if not path:
            raise HTTPException(status_code=404, detail="还没有上传简历")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/api/resume/upload", response_model=ResumeStatusView)
    async def upload_resume(
        request: Request,
        file: UploadFile = File(...),
        user: dict[str, Any] = Depends(current_user),
    ) -> ResumeStatusView:
        content = await file.read(20 * 1024 * 1024 + 1)
        try:
            values = save_resume(user["id"], file.filename, content, request.app.state.data_dir)
        except ResumeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ResumeStatusView(**values)

    @app.delete("/api/resume")
    def remove_resume(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
        return {"deleted": delete_resume(user["id"], request.app.state.data_dir)}

    @app.get("/api/resume/editor", response_model=ResumeEditorView)
    def get_resume_editor(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> ResumeEditorView:
        return ResumeEditorView(**request.app.state.structured_resume.get_profile(user["id"]))

    @app.put("/api/resume/editor", response_model=ResumeEditorView)
    def save_resume_editor(
        payload: ResumeEditorSaveRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> ResumeEditorView:
        try:
            profile = request.app.state.structured_resume.save_profile(
                user["id"], payload.model_dump()
            )
        except StructuredResumeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ResumeEditorView(**profile)

    @app.get("/api/resume/editor/question-cards", response_model=list[ResumeQuestionCardView])
    def get_resume_question_cards(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[ResumeQuestionCardView]:
        cards = request.app.state.structured_resume.question_cards(user["id"])
        document_service = personal_documents_for(request, user)
        for card in cards:
            card["evidence"] = document_service.search(
                user["id"], str(card["document_query"]), limit=3
            )
        return [ResumeQuestionCardView(**card) for card in cards]

    @app.get("/api/resume/editor/versions", response_model=list[ResumeEditorVersionView])
    def list_resume_editor_versions(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[ResumeEditorVersionView]:
        return [
            ResumeEditorVersionView(**item)
            for item in request.app.state.structured_resume.list_versions(user["id"])
        ]

    @app.get(
        "/api/resume/editor/versions/{version}",
        response_model=ResumeEditorVersionDetailView,
    )
    def get_resume_editor_version(
        version: int,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> ResumeEditorVersionDetailView:
        if version < 1:
            raise HTTPException(status_code=400, detail="简历版本号无效")
        item = request.app.state.structured_resume.get_version(user["id"], version)
        if item is None:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        return ResumeEditorVersionDetailView(**item)

    @app.get("/api/topics")
    def topics(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, dict[str, str]]:
        try:
            return list_topics(user["id"], request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/graph/{topic}", response_model=TopicGraphView)
    def topic_graph(topic: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> TopicGraphView:
        try:
            graph = build_topic_graph(
                user["id"],
                topic,
                request.app.state.data_dir,
                request.app.state.store,
            )
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TopicGraphView(**graph)

    @app.get("/api/graph/{topic}/feedback", response_model=TopicGraphFeedbackView)
    def topic_graph_feedback(
        topic: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> TopicGraphFeedbackView:
        try:
            report = build_topic_feedback_report(
                user["id"],
                topic,
                request.app.state.data_dir,
                request.app.state.store,
            )
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TopicGraphFeedbackView(**report)

    @app.post("/api/topics")
    def add_topic(
        payload: TopicCreateRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        try:
            key = create_topic(user["id"], payload.name, payload.icon, payload.key, request.app.state.data_dir)
        except KnowledgeError as exc:
            status_code = 409 if "已存在" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return {"ok": True, "key": key}

    @app.delete("/api/topics/{topic}")
    def remove_topic(topic: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
        try:
            delete_topic(user["id"], topic, request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/api/knowledge/{topic}/core")
    def core_files(topic: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, str]]:
        try:
            return list_core_files(user["id"], topic, request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/knowledge/{topic}/core")
    def add_core_file(
        topic: str,
        payload: KnowledgeFileCreateRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        try:
            filename = create_core_file(
                user["id"], topic, payload.filename, payload.content, request.app.state.data_dir
            )
        except KnowledgeError as exc:
            status_code = 409 if "已存在" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return {"ok": True, "filename": filename}

    @app.put("/api/knowledge/{topic}/core/{filename}")
    def edit_core_file(
        topic: str,
        filename: str,
        payload: KnowledgeContentRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, bool]:
        try:
            update_core_file(user["id"], topic, filename, payload.content, request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc
        return {"ok": True}

    @app.delete("/api/knowledge/{topic}/core/{filename}")
    def remove_core_file(
        topic: str,
        filename: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, bool]:
        try:
            delete_core_file(user["id"], topic, filename, request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/api/knowledge/{topic}/high_freq")
    def high_freq(topic: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
        try:
            return {"content": get_high_freq(user["id"], topic, request.app.state.data_dir)}
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/knowledge/{topic}/high_freq")
    def edit_high_freq(
        topic: str,
        payload: KnowledgeContentRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, bool]:
        try:
            update_high_freq(user["id"], topic, payload.content, request.app.state.data_dir)
        except KnowledgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/recording/analyze", response_model=SessionView)
    def recording_analyze(
        payload: RecordingAnalyzeRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> SessionView:
        transcript = payload.transcript.strip()
        if len(transcript) < 20:
            raise HTTPException(status_code=400, detail="转写文本太短，至少需要 20 个字符")
        company = (payload.company or "").strip()
        position = (payload.position or "").strip()
        analyzer = recording_analyzer_for(request, user, payload.analysis_mode)
        try:
            messages, review = analyzer.analyze(
                transcript,
                recording_mode=payload.recording_mode,
                company=company,
                position=position,
            )
        except (ProviderError, RecordingAnalysisError) as exc:
            raise HTTPException(status_code=502, detail=f"录音复盘分析失败：{exc}") from exc
        review.setdefault("transcript_meta", {})["analysis_mode"] = payload.analysis_mode
        state = {
            "target_role": position or "录音复盘",
            "resume_text": "",
            "mode": "recording",
            "topic": None,
            "knowledge_context": "",
            "question_bank": [],
            "company": company,
            "position": position,
            "recording_mode": payload.recording_mode,
            "recording_analysis_mode": payload.analysis_mode,
            "source_transcript": transcript,
            "recording_meta": review.get("transcript_meta", {}),
            "phase": "recording",
            "phase_question_count": 1,
            "is_finished": True,
            "messages": messages,
            "review": review,
        }
        session_id = request.app.state.store.create_session(user["id"], state)
        request.app.state.store.update_profile_after_review(user["id"], review, topic=None)
        return session_view({"id": session_id, **state})

    def job_resume_context(request: Request, user: dict[str, Any], use_resume: bool) -> str:
        if not use_resume:
            return ""
        try:
            resume_text, _ = get_resume_text(user["id"], request.app.state.data_dir)
        except ResumeError:
            resume_text = ""
        return resume_text or request.app.state.structured_resume.get_context(user["id"])

    @app.post("/api/job-prep/preview")
    def job_prep_preview(
        payload: JobPrepPreviewRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        jd_text = payload.jd_text.strip()
        if len(jd_text) < 50:
            raise HTTPException(status_code=400, detail="JD 内容太短，至少需要 50 个字符")
        preview = analyze_jd(
            jd_text,
            company=payload.company,
            position=payload.position,
            resume_text=job_resume_context(request, user, payload.use_resume),
            structured_profile=(
                request.app.state.structured_resume.get_profile(user["id"]).get("profile", {})
                if payload.use_resume
                else None
            ),
        )
        return {"preview": preview}

    @app.post("/api/job-prep/start", response_model=SessionView)
    def job_prep_start(
        payload: JobPrepStartRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> SessionView:
        engine = engine_for(request, user)
        jd_text = payload.jd_text.strip()
        if len(jd_text) < 50:
            raise HTTPException(status_code=400, detail="JD 内容太短，至少需要 50 个字符")
        resume_text = job_resume_context(request, user, payload.use_resume)
        incoming_preview = payload.preview
        preview_is_current = bool(
            isinstance(incoming_preview, dict)
            and incoming_preview.get("jd_excerpt") == jd_text[:1500]
            and (incoming_preview.get("company") or "") == (payload.company or "").strip()
            and (incoming_preview.get("position") or "") == (payload.position or "").strip()
        )
        preview = incoming_preview if preview_is_current else analyze_jd(
            jd_text,
            company=payload.company,
            position=payload.position,
            resume_text=resume_text,
            structured_profile=(
                request.app.state.structured_resume.get_profile(user["id"]).get("profile", {})
                if payload.use_resume
                else None
            ),
        )
        company = str(preview.get("company") or payload.company or "").strip()
        position = str(preview.get("position") or payload.position or "").strip()
        due_points = [item["point"] for item in request.app.state.store.list_due_reviews(user["id"])]
        question_bank = build_jd_question_bank(preview, due_points)
        knowledge_context = build_jd_context(jd_text, preview)
        try:
            state = engine.start(
                position or "JD 定向面试",
                resume_text,
                mode="jd_prep",
                knowledge_context=knowledge_context,
                question_bank=question_bank,
                company=company,
                position=position,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        state.update({"company": company, "position": position, "jd_text": jd_text, "jd_preview": preview})
        session_id = request.app.state.store.create_session(user["id"], state)
        session = request.app.state.store.get_session(user["id"], session_id)
        assert session is not None
        return session_view({"id": session_id, **session})

    def copilot_inputs(
        payload: CopilotPrepRequest,
        request: Request,
        user: dict[str, Any],
    ) -> tuple[str, str, str, str, dict[str, Any]]:
        jd_text = payload.jd_text.strip()
        if len(jd_text) < 50:
            raise HTTPException(status_code=400, detail="JD 内容太短，至少需要 50 个字符")
        company = (payload.company or "").strip()
        position = (payload.position or "").strip()
        resume_text = job_resume_context(request, user, payload.use_resume)
        profile = request.app.state.store.get_profile(user["id"])
        return jd_text, company, position, resume_text, profile

    @app.post("/api/copilot/prep", response_model=CopilotPrepView)
    def copilot_prep(
        payload: CopilotPrepRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> CopilotPrepView:
        jd_text, company, position, resume_text, profile = copilot_inputs(payload, request, user)
        prep_id = request.app.state.store.create_copilot_prep(user["id"], company, position, jd_text)
        try:
            result = build_copilot_prep(
                jd_text=jd_text,
                company=company,
                position=position,
                resume_text=resume_text,
                profile=profile,
            )
        except Exception as exc:
            request.app.state.store.update_copilot_prep(
                user["id"], prep_id, status="failed", error=str(exc)
            )
            raise HTTPException(status_code=500, detail="Copilot Prep 生成失败") from exc
        request.app.state.store.update_copilot_prep(
            user["id"], prep_id, status="completed", result=result
        )
        prep = request.app.state.store.get_copilot_prep(user["id"], prep_id)
        assert prep is not None
        return copilot_view(prep)

    @app.get("/api/copilot/prep", response_model=list[CopilotPrepView])
    def copilot_prep_history(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[CopilotPrepView]:
        return [copilot_view(item) for item in request.app.state.store.list_copilot_preps(user["id"])]

    @app.get("/api/copilot/prep/{prep_id}", response_model=CopilotPrepView)
    def get_copilot_prep(
        prep_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> CopilotPrepView:
        prep = request.app.state.store.get_copilot_prep(user["id"], prep_id)
        if not prep:
            raise HTTPException(status_code=404, detail="Copilot Prep 不存在")
        return copilot_view(prep)

    @app.post("/api/copilot/stream")
    async def copilot_stream(
        payload: CopilotPrepRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> StreamingResponse:
        jd_text, company, position, resume_text, profile = copilot_inputs(payload, request, user)
        prep_id = request.app.state.store.create_copilot_prep(user["id"], company, position, jd_text)

        def encode_event(name: str, data: dict[str, Any]) -> str:
            return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        async def event_stream():
            yield encode_event(
                "started",
                {"prep_id": prep_id, "stage": "started", "message": "Copilot Prep 已开始。"},
            )
            await asyncio.sleep(0)
            try:
                result = build_copilot_prep(
                    jd_text=jd_text,
                    company=company,
                    position=position,
                    resume_text=resume_text,
                    profile=profile,
                )
                for name, data in copilot_event_sequence(result):
                    await asyncio.sleep(0)
                    yield encode_event(name, {"prep_id": prep_id, **data})
                request.app.state.store.update_copilot_prep(
                    user["id"], prep_id, status="completed", result=result
                )
                yield encode_event(
                    "completed",
                    {"prep_id": prep_id, "stage": "completed", "result": result},
                )
            except Exception as exc:
                request.app.state.store.update_copilot_prep(
                    user["id"], prep_id, status="failed", error=str(exc)
                )
                yield encode_event(
                    "error",
                    {"prep_id": prep_id, "stage": "error", "message": "Copilot Prep 生成失败。"},
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/agent/chat", response_model=AgentChatView)
    def agent_chat(
        payload: AgentChatRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> AgentChatView:
        clean_topic = (payload.topic or "").strip() or None
        clean_graph_question_id = (payload.graph_question_id or "").strip() or None
        clean_graph_entry_source = (payload.graph_entry_source or "").strip() or None
        clean_graph_parent_question_id = (payload.graph_parent_question_id or "").strip() or None
        if clean_topic:
            try:
                available_topics = list_topics(user["id"], request.app.state.data_dir)
            except KnowledgeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if clean_topic not in available_topics:
                raise HTTPException(status_code=400, detail="Agent 主题不存在")
        graph_entry: dict[str, str] | None = None
        if clean_graph_question_id:
            if not clean_topic:
                raise HTTPException(status_code=400, detail="Agent 图谱问题需要同时提供主题")
            try:
                graph_entry = resolve_graph_question_entry(
                    user["id"],
                    clean_topic,
                    clean_graph_question_id,
                    str(request.app.state.data_dir),
                    request.app.state.store,
                    entry_source=clean_graph_entry_source,
                    parent_question_id=clean_graph_parent_question_id,
                )
            except KnowledgeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if not graph_entry:
                raise HTTPException(status_code=400, detail="Agent 图谱问题不存在或不属于当前主题")
        elif clean_graph_entry_source or clean_graph_parent_question_id:
            raise HTTPException(status_code=400, detail="图谱来源字段需要同时提供图谱问题")
        try:
            document_service = personal_documents_for(request, user)
            result = run_personal_agent(
                message=payload.message,
                user_id=user["id"],
                store=request.app.state.store,
                data_dir=request.app.state.data_dir,
                model=agent_model_for(request, user),
                document_service=document_service,
                structured_resume_service=request.app.state.structured_resume,
                conversation_id=payload.conversation_id,
                question_card_id=payload.question_card_id,
                topic=clean_topic,
                graph_question_id=clean_graph_question_id,
                graph_entry_source=graph_entry["entry_source"] if graph_entry else None,
                graph_parent_question_id=graph_entry["parent_question_id"] if graph_entry else None,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentProviderError as exc:
            stage_label = {"planning": "规划", "answering": "回答"}.get(exc.stage, "处理")
            detail = {
                "code": f"agent_{exc.stage}_failed",
                "stage": exc.stage,
                "message": f"Agent {stage_label}失败，请检查模型设置或稍后重试。",
                "retryable": True,
                "state": exc.state,
            }
            if exc.conversation_id and exc.state == "preserved_draft":
                detail["conversation_id"] = exc.conversation_id
            raise HTTPException(
                status_code=502,
                detail=detail,
            ) from exc
        except ProviderError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "agent_provider_error",
                    "stage": "initialization",
                    "message": "Agent 模型服务未就绪，请检查模型设置。",
                    "retryable": False,
                },
            ) from exc
        except EmbeddingProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return AgentChatView(**result)

    @app.get("/api/agent/documents", response_model=list[PersonalDocumentView])
    def agent_personal_documents(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[PersonalDocumentView]:
        document_service = personal_documents_for(request, user)
        return [
            PersonalDocumentView(**item)
            for item in document_service.list_documents(user["id"])
        ]

    @app.post("/api/agent/documents/reindex", response_model=PersonalDocumentReindexView)
    def reindex_agent_personal_documents(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> PersonalDocumentReindexView:
        try:
            result = personal_documents_for(request, user).reindex_all(user["id"])
        except EmbeddingProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return PersonalDocumentReindexView(**result)

    @app.post("/api/agent/documents", response_model=PersonalDocumentView)
    def add_agent_personal_document(
        payload: PersonalDocumentCreateRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> PersonalDocumentView:
        try:
            document = personal_documents_for(request, user).add_document(
                user["id"],
                title=payload.title,
                content=payload.content,
                source_type=payload.source_type,
            )
        except PersonalDocumentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return PersonalDocumentView(**document)

    @app.post("/api/agent/documents/upload", response_model=PersonalDocumentView)
    async def upload_agent_personal_document(
        request: Request,
        file: UploadFile = File(...),
        user: dict[str, Any] = Depends(current_user),
    ) -> PersonalDocumentView:
        filename = file.filename or ""
        content = await file.read(MAX_PDF_BYTES + 1)
        try:
            suffix = Path(filename).suffix.lower()
            if suffix == ".pdf":
                text = extract_pdf_text_from_bytes(filename, content, max_chars=MAX_DOCUMENT_CHARS)
                source_type = "pdf"
                empty_message = "PDF 中没有可提取的文字；扫描件暂不支持 OCR"
            elif suffix in {".md", ".markdown"}:
                text = extract_markdown_text_from_bytes(filename, content, max_chars=MAX_DOCUMENT_CHARS)
                source_type = "markdown"
                empty_message = "Markdown 文件内容为空"
            else:
                raise DocumentImportError("目前只支持 PDF、.md 或 .markdown 文件")
            if not text:
                raise DocumentImportError(empty_message)
            document = personal_documents_for(request, user).add_document(
                user["id"],
                title=Path(filename).stem,
                content=text,
                source_type=source_type,
            )
        except (DocumentImportError, PersonalDocumentError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return PersonalDocumentView(**document)

    @app.get("/api/agent/documents/search", response_model=list[PersonalDocumentSearchResult])
    def search_agent_personal_documents(
        request: Request,
        q: str = "",
        limit: int = 5,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[PersonalDocumentSearchResult]:
        query = q.strip()
        if len(query) > 2_000:
            raise HTTPException(status_code=400, detail="检索问题不能超过 2000 字")
        if limit < 1 or limit > 8:
            raise HTTPException(status_code=400, detail="检索数量需要在 1 到 8 之间")
        document_service = personal_documents_for(request, user)
        return [
            PersonalDocumentSearchResult(**item)
            for item in document_service.search(
                user["id"], query, limit=limit
            )
        ]

    @app.put("/api/agent/documents/{document_id}", response_model=PersonalDocumentView)
    def update_agent_personal_document(
        document_id: str,
        payload: PersonalDocumentUpdateRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> PersonalDocumentView:
        try:
            document = personal_documents_for(request, user).update_document(
                user["id"],
                document_id,
                title=payload.title,
                content=payload.content,
                source_type=payload.source_type,
            )
        except PersonalDocumentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmbeddingProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if document is None:
            raise HTTPException(status_code=404, detail="个人文档不存在")
        return PersonalDocumentView(**document)

    @app.get(
        "/api/agent/documents/{document_id}/versions",
        response_model=list[PersonalDocumentVersionView],
    )
    def list_agent_personal_document_versions(
        document_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[PersonalDocumentVersionView]:
        versions = personal_documents_for(request, user).list_versions(user["id"], document_id)
        if not versions:
            raise HTTPException(status_code=404, detail="个人文档不存在")
        return [PersonalDocumentVersionView(**item) for item in versions]

    @app.get(
        "/api/agent/documents/{document_id}/versions/{version}",
        response_model=PersonalDocumentVersionDetailView,
    )
    def get_agent_personal_document_version(
        document_id: str,
        version: int,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> PersonalDocumentVersionDetailView:
        if version < 1:
            raise HTTPException(status_code=400, detail="文档版本号无效")
        item = personal_documents_for(request, user).get_version(user["id"], document_id, version)
        if item is None:
            raise HTTPException(status_code=404, detail="个人文档版本不存在")
        return PersonalDocumentVersionDetailView(**item)

    @app.get("/api/agent/plans", response_model=list[LearningPlanView])
    def agent_learning_plans(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[LearningPlanView]:
        return [
            LearningPlanView(**item)
            for item in request.app.state.store.list_learning_plans(user["id"])
        ]

    @app.get("/api/agent/plans/{plan_id}", response_model=LearningPlanView)
    def agent_learning_plan(
        plan_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> LearningPlanView:
        plan = request.app.state.store.get_learning_plan(user["id"], plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="学习计划不存在")
        return LearningPlanView(**plan)

    @app.post("/api/agent/plans/{plan_id}/confirm", response_model=LearningPlanView)
    def confirm_agent_learning_plan(
        plan_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> LearningPlanView:
        try:
            plan = request.app.state.store.confirm_learning_plan(user["id"], plan_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return LearningPlanView(**plan)

    @app.post(
        "/api/agent/plans/{plan_id}/items/{item_id}/complete",
        response_model=LearningPlanView,
    )
    def complete_agent_learning_plan_item(
        plan_id: str,
        item_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> LearningPlanView:
        try:
            plan = request.app.state.store.complete_learning_plan_item(
                user["id"], plan_id, item_id
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return LearningPlanView(**plan)

    @app.get("/api/agent/conversations", response_model=list[AgentConversationView])
    def agent_conversations(
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[AgentConversationView]:
        return [
            AgentConversationView(**item)
            for item in request.app.state.store.list_agent_conversations(user["id"])
        ]

    @app.get("/api/agent/conversations/{conversation_id}", response_model=AgentConversationDetailView)
    def agent_conversation(
        conversation_id: str,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> AgentConversationDetailView:
        conversation = request.app.state.store.get_agent_conversation(user["id"], conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Agent 对话不存在")
        return AgentConversationDetailView(**conversation)

    @app.post("/api/interview/start", response_model=SessionView)
    def start_interview(payload: StartInterviewRequest, request: Request, user: dict[str, Any] = Depends(current_user)) -> SessionView:
        engine = engine_for(request, user)
        plan_id = (payload.plan_id or "").strip() or None
        plan_item_id = (payload.plan_item_id or "").strip() or None
        question_card_id = (payload.question_card_id or "").strip() or None
        graph_question_id = (payload.graph_question_id or "").strip() or None
        graph_entry_source = (payload.graph_entry_source or "").strip() or None
        graph_parent_question_id = (payload.graph_parent_question_id or "").strip() or None
        if bool(plan_id) != bool(plan_item_id):
            raise HTTPException(status_code=400, detail="学习计划关联需要同时提供 plan_id 和 plan_item_id")
        if (plan_id or plan_item_id) and payload.mode != "topic_drill":
            raise HTTPException(status_code=400, detail="学习计划项只能关联专项训练")
        if question_card_id and payload.mode != "topic_drill":
            raise HTTPException(status_code=400, detail="项目追问卡只能关联专项训练")
        if graph_question_id and payload.mode != "topic_drill":
            raise HTTPException(status_code=400, detail="图谱问题只能关联专项训练")
        if graph_question_id and not payload.topic:
            raise HTTPException(status_code=400, detail="图谱问题需要同时提供训练主题")
        if graph_parent_question_id and not graph_question_id:
            raise HTTPException(status_code=400, detail="图谱父节点需要同时提供目标问题")
        if graph_entry_source and not graph_question_id:
            raise HTTPException(status_code=400, detail="图谱来源字段需要同时提供目标问题")
        graph_entry: dict[str, str] | None = None
        if graph_question_id and payload.topic:
            try:
                graph_entry = resolve_graph_question_entry(
                    user["id"],
                    payload.topic,
                    graph_question_id,
                    str(request.app.state.data_dir),
                    request.app.state.store,
                    entry_source=graph_entry_source,
                    parent_question_id=graph_parent_question_id,
                )
            except KnowledgeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if not graph_entry:
                raise HTTPException(status_code=400, detail="图谱问题不存在、父节点不存在或不属于当前训练主题")
        linked_plan_item: dict[str, Any] | None = None
        if plan_id and plan_item_id:
            try:
                linked_plan_item = request.app.state.store.get_learning_plan_item_for_training(
                    user["id"], plan_id, plan_item_id
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if linked_plan_item and graph_entry:
            linked_item = linked_plan_item["item"]
            if str(linked_item.get("graph_question_id", "")) != graph_entry["id"]:
                raise HTTPException(status_code=400, detail="学习计划项与图谱问题来源不一致")
            expected_source = str(linked_item.get("graph_entry_source", "") or "question_node")
            expected_parent_id = str(linked_item.get("graph_parent_question_id", "") or "")
            if expected_source != graph_entry["entry_source"] or expected_parent_id != graph_entry["parent_question_id"]:
                raise HTTPException(status_code=400, detail="学习计划项与图谱候选来源不一致")
        resume_text = payload.resume_text.strip()
        if not resume_text:
            try:
                resume_text, _ = get_resume_text(user["id"], request.app.state.data_dir)
            except ResumeError:
                resume_text = ""
            if not resume_text:
                resume_text = request.app.state.structured_resume.get_context(user["id"])
        topic = None
        knowledge_context = ""
        question_bank: list[str] = []
        focus_parts: list[str] = []
        explicit_focus = (payload.focus or "").strip()
        if explicit_focus:
            focus_parts.append(explicit_focus)
        question_card: dict[str, Any] | None = None
        graph_question: str | None = graph_entry["question"] if graph_entry else None
        if question_card_id:
            question_card = request.app.state.structured_resume.get_question_card(
                user["id"], question_card_id
            )
            if not question_card:
                raise HTTPException(status_code=404, detail="项目追问卡不存在或已不属于当前简历版本")
            card_focus = str(question_card.get("training_focus", question_card["question"])).strip()
            if card_focus:
                focus_parts.append(f"项目追问焦点：{card_focus}")
        if linked_plan_item:
            plan_focus = str(linked_plan_item["item"].get("point", "")).strip()
            if plan_focus:
                focus_parts.append(f"学习计划焦点：{plan_focus}")
        if graph_question:
            focus_parts.append(f"图谱指定问题：{graph_question}")
        requested_focus = "；".join(focus_parts)[:200]
        if payload.mode == "topic_drill":
            if not payload.topic:
                raise HTTPException(status_code=400, detail="专项训练需要选择训练领域")
            try:
                bundle = get_topic_bundle(user["id"], payload.topic, request.app.state.data_dir)
            except KnowledgeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            topic = payload.topic
            knowledge_context = bundle["knowledge_context"]
            due_reviews = request.app.state.store.list_due_reviews(user["id"], topic=topic)
            profile = request.app.state.store.get_profile(user["id"])
            topic_profile = request.app.state.store.get_topic_profile(user["id"], topic)
            try:
                drill_plan = build_drill_question_generator(
                    request.app.state.store.get_provider_config(user["id"])
                ).generate(
                    topic=topic,
                    topic_name=bundle["topic_name"],
                    knowledge_context=knowledge_context,
                    question_bank=bundle["question_bank"],
                    profile=profile,
                    topic_profile=topic_profile,
                    due_reviews=due_reviews,
                    recent_sessions=recent_topic_context(request, user, topic),
                    requested_focus=requested_focus,
                )
            except ProviderError as exc:
                raise HTTPException(status_code=502, detail=f"专项动态出题失败：{exc}") from exc
            question_bank = drill_plan["questions"]
            if graph_question:
                question_bank = [
                    graph_question,
                    *[question for question in question_bank if question != graph_question],
                ][:8]
        try:
            state = engine.start(
                payload.target_role,
                resume_text,
                mode=payload.mode,
                topic=topic,
                knowledge_context=knowledge_context,
                question_bank=question_bank,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        state["learning_plan_id"] = plan_id
        state["learning_plan_item_id"] = plan_item_id
        state["question_card_id"] = question_card["id"] if question_card else None
        state["question_card_project"] = question_card["project_name"] if question_card else ""
        state["question_card_resume_version"] = question_card["resume_version"] if question_card else None
        state["graph_question_id"] = graph_question_id
        state["graph_question"] = graph_question or ""
        state["graph_entry_source"] = graph_entry["entry_source"] if graph_entry else ""
        state["graph_parent_question_id"] = graph_entry["parent_question_id"] if graph_entry else None
        state["graph_parent_question"] = graph_entry["parent_question"] if graph_entry else ""
        session_id = request.app.state.store.create_session(user["id"], state)
        session = request.app.state.store.get_session(user["id"], session_id)
        assert session is not None
        return session_view({"id": session_id, **session})

    @app.get("/api/interview/{session_id}", response_model=SessionView)
    def get_interview(session_id: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> SessionView:
        session = request.app.state.store.get_session(user["id"], session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session_view({"id": session_id, **session})

    @app.post("/api/interview/{session_id}/answer", response_model=SessionView)
    def answer_interview(session_id: str, payload: AnswerRequest, request: Request, user: dict[str, Any] = Depends(current_user)) -> SessionView:
        engine = engine_for(request, user)
        session = request.app.state.store.get_session(user["id"], session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        state = {"id": session_id, **session}
        try:
            engine.answer(state, payload.answer)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        request.app.state.store.update_session(user["id"], session_id, state)
        return session_view(state)

    @app.post("/api/interview/{session_id}/finish", response_model=SessionView)
    def finish_interview(session_id: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> SessionView:
        engine = engine_for(request, user)
        session = request.app.state.store.get_session(user["id"], session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        state = {"id": session_id, **session}
        had_review = bool(state["review"])
        try:
            engine.finish(state)
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        request.app.state.store.update_session(user["id"], session_id, state)
        if not had_review:
            topic = state.get("topic") if state.get("mode") == "topic_drill" else None
            request.app.state.store.update_profile_after_review(user["id"], state["review"] or {}, topic=topic)
        return session_view(state)

    @app.get("/api/history", response_model=list[SessionView])
    def history(request: Request, user: dict[str, Any] = Depends(current_user)) -> list[SessionView]:
        return [session_view({"id": item["id"], **item}) for item in request.app.state.store.list_sessions(user["id"])]

    @app.get("/api/profile/topics", response_model=list[TopicMasteryView])
    def topic_profiles(request: Request, user: dict[str, Any] = Depends(current_user)) -> list[TopicMasteryView]:
        return [TopicMasteryView(**item) for item in request.app.state.store.list_topic_profiles(user["id"])]

    @app.get("/api/profile/topic/{topic}/history", response_model=list[SessionView])
    def topic_history(topic: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> list[SessionView]:
        return [
            session_view({"id": item["id"], **item})
            for item in request.app.state.store.list_sessions(user["id"], topic=topic)
        ]

    @app.get("/api/profile/due-reviews", response_model=list[DueReviewView])
    def due_reviews(
        request: Request,
        topic: str | None = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[DueReviewView]:
        return [
            DueReviewView(**item)
            for item in request.app.state.store.list_due_reviews(user["id"], topic=topic)
        ]

    @app.get("/api/profile", response_model=ProfileView)
    def profile(request: Request, user: dict[str, Any] = Depends(current_user)) -> ProfileView:
        return ProfileView(
            **request.app.state.store.get_profile(user["id"]),
            topic_mastery=request.app.state.store.list_topic_profiles(user["id"]),
            due_reviews=request.app.state.store.list_due_reviews(user["id"]),
        )

    return app


app = create_app()
