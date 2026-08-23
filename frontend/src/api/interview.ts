import { API_BASE, authFetch, type ApiResponse } from "./client";

// 兼容旧引用:authFetch 历史上从本模块导出
export { authFetch } from "./client";

type AnyRecord = Record<string, any>;

async function readJson<T = AnyRecord>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as AnyRecord)?.detail;
    throw new Error(
      typeof detail === "string" ? detail : detail?.message || "请求失败"
    );
  }
  return data as T;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function qtraceQuestions(session: AnyRecord): Array<{ id: string; question: string }> {
  const bank = Array.isArray(session.question_bank) ? session.question_bank : [];
  const assistantMessages = Array.isArray(session.messages)
    ? session.messages.filter((item: AnyRecord) => item?.role === "assistant")
    : [];
  const source = bank.length ? bank : assistantMessages.map((item: AnyRecord) => item.content);
  return source
    .map((item: unknown, index: number) => {
      if (typeof item === "string") {
        return { id: `q${index + 1}`, question: item };
      }
      const record = (item || {}) as AnyRecord;
      return {
        id: asText(record.id || record.question_id || `q${index + 1}`),
        question: asText(record.question || record.content || record.text),
      };
    })
    .filter((item) => item.question.trim());
}

function qtraceAnswers(
  questions: Array<{ id: string; question: string }>,
  messages: AnyRecord[] = []
): Array<{ question_id: string; answer: string }> {
  return questions.map((question) => {
    const index = messages.findIndex(
      (item) => item?.role === "assistant" && item?.content === question.question
    );
    const answer = index >= 0 && messages[index + 1]?.role === "user"
      ? asText(messages[index + 1].content)
      : "";
    return { question_id: question.id, answer };
  });
}

function qtraceReview(session: AnyRecord): AnyRecord {
  const raw = (session.review || {}) as AnyRecord;
  const questions = qtraceQuestions(session);
  const messages = Array.isArray(session.messages) ? session.messages : [];
  const answers = qtraceAnswers(questions, messages);
  const rawScores = Array.isArray(raw.scores) ? raw.scores : [];
  const scores = questions.map((question, index) => {
    const value = rawScores[index];
    if (value && typeof value === "object") {
      const score = Number(value.score ?? value.value ?? 0);
      return { ...value, question_id: value.question_id || question.id, score };
    }
    return {
      question_id: question.id,
      score: Number(value ?? 0),
      feedback: "",
    };
  });
  const average = Number(raw.average_score ?? 0);
  const strengths = Array.isArray(raw.strengths) ? raw.strengths : [];
  const weakPoints = Array.isArray(raw.weak_points) ? raw.weak_points : [];
  const actionItems = Array.isArray(raw.action_items) ? raw.action_items : [];
  const behaviorSignals = Array.isArray(raw.behavior_signals) ? raw.behavior_signals : [];
  const summary = asText(raw.summary);
  const markdown = [
    summary,
    strengths.length ? `\n### 表现亮点\n${strengths.map((item: unknown) => `- ${asText(item)}`).join("\n")}` : "",
    weakPoints.length ? `\n### 薄弱点\n${weakPoints.map((item: unknown) => `- ${asText(item)}`).join("\n")}` : "",
    actionItems.length ? `\n### 下一步\n${actionItems.map((item: unknown) => `- ${asText(item)}`).join("\n")}` : "",
  ].filter(Boolean).join("\n");

  return {
    review: markdown,
    raw_review: raw,
    summary,
    scores,
    questions,
    answers,
    transcript: messages,
    mode: session.mode || "resume",
    topic: session.topic || null,
    meta: {
      company: session.company || "",
      position: session.position || "",
      jd_text: session.jd_text || "",
      preview: session.jd_preview || {},
      recording_mode: session.recording_mode || "",
    },
    overall: {
      avg_score: average,
      summary,
      new_weak_points: weakPoints,
      new_strong_points: strengths,
      action_items: actionItems,
      behavior_signals: behaviorSignals,
      dimension_scores: raw.dimension_scores || null,
    },
    avg_score: average,
    weak_points: weakPoints,
    strong_points: strengths,
    action_items: actionItems,
    behavior_signals: behaviorSignals,
    dimension_scores: raw.dimension_scores || null,
    topics_covered: raw.topics_covered || [],
  };
}

function qtraceSession(session: AnyRecord): AnyRecord {
  const normalized = qtraceReview(session);
  const hasReview = Boolean(session.review);
  return {
    ...normalized,
    session_id: asText(session.id || session.session_id),
    target_role: session.target_role || "",
    status: hasReview ? "reviewed" : session.is_finished ? "ended" : "ongoing",
    is_finished: Boolean(session.is_finished),
    can_continue: !session.is_finished,
    review_error: "",
    created_at: session.created_at || "",
    updated_at: session.updated_at || "",
    progress: session.phase || "",
  };
}

function qtraceHistory(sessions: AnyRecord[], mode: string | null, topic: string | null): AnyRecord[] {
  return sessions
    .filter((session) => !mode || session.mode === mode)
    .filter((session) => !topic || session.topic === topic)
    .map((session) => qtraceSession(session));
}

async function getQTraceSession(sessionId: string): Promise<AnyRecord> {
  return readJson(await authFetch(`${API_BASE}/interview/${encodeURIComponent(sessionId)}`));
}

// ── Speech-to-text ──

export async function transcribeAudio(
  audioBlob: Blob
): Promise<ApiResponse<"/api/transcribe", "post">> {
  const form = new FormData();
  form.append("file", audioBlob, "recording.webm");
  const res = await authFetch(`${API_BASE}/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTopics(): Promise<ApiResponse<"/api/topics", "get">> {
  const res = await authFetch(`${API_BASE}/topics`);
  return res.json();
}

export async function createTopic(
  name: string,
  icon = "📝"
): Promise<ApiResponse<"/api/topics", "post">> {
  const res = await authFetch(`${API_BASE}/topics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, icon }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteTopic(
  key: string
): Promise<ApiResponse<"/api/topics/{key}", "delete">> {
  const res = await authFetch(`${API_BASE}/topics/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Resume ──

export async function getResumeStatus(): Promise<
  ApiResponse<"/api/resume/status", "get">
> {
  const res = await authFetch(`${API_BASE}/resume/status`);
  const data = await readJson<AnyRecord>(res);
  // TechSpar calls this field `exists`; QTrace keeps the more explicit
  // `has_resume`. Keep both so the original pages remain usable.
  return { ...data, exists: Boolean(data.exists ?? data.has_resume) } as any;
}

export async function uploadResume(
  file: File
): Promise<ApiResponse<"/api/resume/upload", "post">> {
  const form = new FormData();
  form.append("file", file);
  const res = await authFetch(`${API_BASE}/resume/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getResumePdfBlob(): Promise<Blob> {
  const res = await authFetch(`${API_BASE}/resume/file`);
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function deleteUploadedResume(): Promise<
  ApiResponse<"/api/resume", "delete">
> {
  const res = await authFetch(`${API_BASE}/resume`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function parseUploadedResume(): Promise<
  ApiResponse<"/api/resume/parse", "post">
> {
  const res = await authFetch(`${API_BASE}/resume/parse`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Interview ──

interface StartInterviewOptions {
  numQuestions?: number;
  divergence?: number;
  targetRole?: string;
  jobDescription?: string;
}

export async function startInterview(
  mode: string,
  topic: string | null = null,
  { numQuestions, divergence, targetRole, jobDescription }: StartInterviewOptions = {}
): Promise<ApiResponse<"/api/interview/start", "post">> {
  const body: Record<string, unknown> = { mode, topic };
  if (targetRole != null) body.target_role = targetRole;
  // QTrace owns question generation and reads the saved resume/context. The
  // remaining TechSpar tuning knobs are intentionally not sent to avoid a
  // misleading request contract.
  void numQuestions;
  void divergence;
  void jobDescription;
  const res = await authFetch(`${API_BASE}/interview/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const session = await readJson<AnyRecord>(res);
  return qtraceSession(session) as any;
}

export async function inferTargetRole(): Promise<
  ApiResponse<"/api/profile/infer-target-role", "post">
> {
  const res = await authFetch(`${API_BASE}/profile/infer-target-role`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function previewJobPrep(
  payload: Record<string, unknown>
): Promise<ApiResponse<"/api/job-prep/preview", "post">> {
  const res = await authFetch(`${API_BASE}/job-prep/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startJobPrep(
  payload: Record<string, unknown>
): Promise<ApiResponse<"/api/job-prep/start", "post">> {
  const normalizedPayload = {
    jd_text: payload.jd_text || payload.job_description || "",
    company: payload.company || "",
    position: payload.position || "",
    use_resume: payload.use_resume !== false,
    preview: payload.preview || payload.preview_data || null,
  };
  const res = await authFetch(`${API_BASE}/job-prep/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(normalizedPayload),
  });
  const session = await readJson<AnyRecord>(res);
  return qtraceSession(session) as any;
}

export async function sendMessage(
  sessionId: string,
  message: string
): Promise<ApiResponse<"/api/interview/chat", "post">> {
  const res = await authFetch(`${API_BASE}/interview/${encodeURIComponent(sessionId)}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer: message }),
  });
  const session = await readJson<AnyRecord>(res);
  const normalized = qtraceSession(session);
  const assistantMessages = (session.messages || []).filter(
    (item: AnyRecord) => item?.role === "assistant"
  );
  return {
    ...normalized,
    message: asText(assistantMessages.at(-1)?.content),
    is_finished: Boolean(session.is_finished),
  } as any;
}

interface ChatStreamCallbacks {
  onToken?: (token: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}

export async function sendMessageStream(
  sessionId: string,
  message: string,
  { onToken, onDone, onError }: ChatStreamCallbacks
): Promise<void> {
  // QTrace currently exposes a synchronous answer endpoint. Keep TechSpar's
  // callback contract so its chat UI remains unchanged; the whole assistant
  // message is delivered as one token rather than pretending to stream.
  try {
    const data = await sendMessage(sessionId, message) as any;
    if (data.message) onToken?.(String(data.message));
    onDone?.(data);
  } catch (error) {
    const normalized = error instanceof Error ? error : new Error(String(error));
    onError?.(normalized);
    throw normalized;
  }
}

export async function endInterview(
  sessionId: string,
  answers: any = null
): Promise<ApiResponse<"/api/interview/end/{session_id}", "post">> {
  // Batch pages collect answers locally. Feed each non-empty answer through
  // QTrace's real state machine before finishing; no review data is invented.
  if (Array.isArray(answers)) {
    for (const item of answers) {
      if (!item?.answer?.trim()) continue;
      await sendMessage(sessionId, String(item.answer));
    }
  }
  const res = await authFetch(`${API_BASE}/interview/${encodeURIComponent(sessionId)}/finish`, {
    method: "POST",
  });
  return qtraceSession(await readJson<AnyRecord>(res)) as any;
}

export async function saveDraftAnswers(
  sessionId: string,
  answers: Record<string, unknown>
): Promise<any> {
  // QTrace persists every answer immediately. The TechSpar batch page calls
  // this as a fire-and-forget autosave, so acknowledge it without issuing a
  // request to a non-existent endpoint.
  void sessionId;
  void answers;
  return { ok: true, persisted_by_answer_endpoint: true };
}

export async function getReview(
  sessionId: string
): Promise<ApiResponse<"/api/interview/review/{session_id}", "get">> {
  return qtraceReview(await getQTraceSession(sessionId)) as any;
}

export async function retryReview(
  sessionId: string
): Promise<ApiResponse<"/api/interview/review/{session_id}/generate", "post">> {
  const res = await authFetch(`${API_BASE}/interview/${encodeURIComponent(sessionId)}/finish`, {
    method: "POST",
  });
  return qtraceSession(await readJson<AnyRecord>(res)) as any;
}

export async function getResumableSession(
  sessionId: string
): Promise<ApiResponse<"/api/interview/session/{session_id}/resume", "get">> {
  const session = await getQTraceSession(sessionId);
  return {
    ...qtraceSession(session),
    questions: qtraceQuestions(session),
    transcript: session.messages || [],
  } as any;
}

export async function getTaskStatus(
  taskId: string
): Promise<ApiResponse<"/api/tasks/{task_id}", "get">> {
  const session = await getQTraceSession(taskId);
  return {
    status: session.review ? "done" : session.is_finished ? "error" : "pending",
    result: session.review ? qtraceReview(session) : null,
  } as any;
}

export async function getReferenceAnswer(
  sessionId: string,
  questionId: string
): Promise<ApiResponse<"/api/interview/reference-answer", "post">> {
  void sessionId;
  void questionId;
  throw new Error("当前 QTrace 尚未提供独立参考答案接口");
}

export async function getHistory(
  limit = 20,
  offset = 0,
  mode: string | null = null,
  topic: string | null = null
): Promise<ApiResponse<"/api/interview/history", "get">> {
  const sessions = await readJson<AnyRecord[]>(await authFetch(`${API_BASE}/history`));
  const filtered = qtraceHistory(sessions, mode, topic);
  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
  } as any;
}

export async function deleteSession(
  sessionId: string
): Promise<ApiResponse<"/api/interview/session/{session_id}", "delete">> {
  void sessionId;
  throw new Error("当前 QTrace 尚未开放历史记录删除接口");
}

export async function getInterviewTopics(): Promise<
  ApiResponse<"/api/interview/topics", "get">
> {
  const topics = await readJson<AnyRecord>(await authFetch(`${API_BASE}/topics`));
  return Object.keys(topics).sort() as any;
}

// ── Graph ──

export async function getGraphData(
  topic: string
): Promise<ApiResponse<"/api/graph/{topic}", "get">> {
  const res = await authFetch(`${API_BASE}/graph/${topic}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Profile & Retrospective ──

export async function getProfile(): Promise<ApiResponse<"/api/profile", "get">> {
  const profile = await readJson<AnyRecord>(await authFetch(`${API_BASE}/profile`));
  let history: AnyRecord[] = [];
  try {
    const sessions = await readJson<AnyRecord[]>(await authFetch(`${API_BASE}/history`));
    history = qtraceHistory(sessions, null, null);
  } catch {
    // The profile page can still render its stable profile fields when the
    // optional history request is unavailable.
  }
  const scored = history.filter((item) => item.avg_score != null && item.avg_score > 0);
  const totalAnswers = history.reduce(
    (sum, item) => sum + (item.transcript || []).filter((message: AnyRecord) => message.role === "user").length,
    0,
  );
  const topicMastery = Object.fromEntries(
    (Array.isArray(profile.topic_mastery) ? profile.topic_mastery : []).map((item: AnyRecord) => [
      item.topic,
      {
        ...item,
        score: Number(item.mastery_score ?? item.score ?? 0),
        mastery_score: Number(item.mastery_score ?? item.score ?? 0),
      },
    ]),
  );
  const normalizePoints = (items: unknown, topic = "") =>
    (Array.isArray(items) ? items : []).map((item: unknown) =>
      typeof item === "string" ? { point: item, topic, times_seen: 1 } : item
    );
  return {
    ...profile,
    target_role: profile.target_role || "",
    stats: {
      total_sessions: Number(profile.completed_sessions ?? history.length ?? 0),
      total_answers: totalAnswers,
      avg_score: scored.length
        ? Number((scored.reduce((sum, item) => sum + Number(item.avg_score), 0) / scored.length).toFixed(1))
        : null,
      score_history: [...scored]
        .reverse()
        .map((item) => ({
          avg_score: Number(item.avg_score),
          mode: item.mode,
          topic: item.topic,
          date: item.created_at || "",
        })),
    },
    topic_mastery: topicMastery,
    weak_points: normalizePoints(profile.weak_points),
    strong_points: normalizePoints(profile.strong_points),
    behavior_signals: normalizePoints(profile.behavior_signals),
    action_items: Array.isArray(profile.action_items) ? profile.action_items : [],
    due_reviews: Array.isArray(profile.due_reviews) ? profile.due_reviews : [],
  } as any;
}

export async function markProfileViewed(): Promise<
  ApiResponse<"/api/profile/viewed", "post">
> {
  // QTrace does not need a separate acknowledgement endpoint; profile data is
  // read from the account store and remains available across sessions.
  return { ok: true } as any;
}

export async function sendPatternFeedback(
  point: string,
  verdict: string
): Promise<ApiResponse<"/api/profile/pattern/feedback", "post">> {
  void point;
  void verdict;
  throw new Error("当前 QTrace 尚未提供画像证据反馈接口");
}

export async function getTopicRetrospective(
  topic: string
): Promise<ApiResponse<"/api/profile/topic/{topic}/retrospective", "post">> {
  void topic;
  throw new Error("当前 QTrace 尚未提供主题长期回顾生成接口");
}

export async function getTopicHistory(
  topic: string
): Promise<ApiResponse<"/api/profile/topic/{topic}/history", "get">> {
  const sessions = await readJson<AnyRecord[]>(
    await authFetch(`${API_BASE}/profile/topic/${encodeURIComponent(topic)}/history`)
  );
  return sessions.map((session) => qtraceSession(session)) as any;
}

// ── Knowledge management ──

export async function getCoreKnowledge(
  topic: string
): Promise<ApiResponse<"/api/knowledge/{topic}/core", "get">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/core`
  );
  return res.json();
}

export async function updateCoreKnowledge(
  topic: string,
  filename: string,
  content: string
): Promise<ApiResponse<"/api/knowledge/{topic}/core/{filename}", "put">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/core/${encodeURIComponent(filename)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteCoreKnowledge(
  topic: string,
  filename: string
): Promise<ApiResponse<"/api/knowledge/{topic}/core/{filename}", "delete">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/core/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createCoreKnowledge(
  topic: string,
  filename: string,
  content: string
): Promise<ApiResponse<"/api/knowledge/{topic}/core", "post">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/core`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, content }),
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateKnowledge(
  topic: string
): Promise<ApiResponse<"/api/knowledge/{topic}/generate", "post">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/generate`,
    {
      method: "POST",
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Recording review ──

export async function transcribeRecording(
  audioBlob: Blob & { name?: string },
  mode = "dual"
): Promise<ApiResponse<"/api/recording/transcribe", "post">> {
  const form = new FormData();
  form.append("file", audioBlob, audioBlob.name || "recording.webm");
  form.append("mode", mode);
  const res = await authFetch(`${API_BASE}/recording/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function analyzeRecording(
  transcript: string,
  recordingMode: string,
  company?: string,
  position?: string
): Promise<ApiResponse<"/api/recording/analyze", "post">> {
  const body: Record<string, unknown> = {
    transcript,
    recording_mode: recordingMode,
  };
  if (company) body.company = company;
  if (position) body.position = position;
  const res = await authFetch(`${API_BASE}/recording/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getHighFreq(
  topic: string
): Promise<ApiResponse<"/api/knowledge/{topic}/high_freq", "get">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/high_freq`
  );
  return res.json();
}

export async function updateHighFreq(
  topic: string,
  content: string
): Promise<ApiResponse<"/api/knowledge/{topic}/high_freq", "put">> {
  const res = await authFetch(
    `${API_BASE}/knowledge/${encodeURIComponent(topic)}/high_freq`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Settings ──

export async function getSettings(): Promise<
  ApiResponse<"/api/settings", "get">
> {
  const res = await authFetch(`${API_BASE}/settings`);
  const data = await readJson<AnyRecord>(res);
  const embeddingMode = data.embedding_mode || "demo";
  return {
    // Shape expected by the imported TechSpar settings page. Secrets are
    // intentionally never returned by QTrace, so the page keeps blank inputs.
    llm: {
      api_base: data.llm_api_base || "",
      model: data.llm_model || "",
      api_key: "",
      temperature: 0.7,
    },
    embedding: {
      backend: embeddingMode === "local-model" ? "local" : embeddingMode === "openai-compatible" ? "api" : "",
      api_base: data.embedding_api_base || "",
      api_key: "",
      api_model: data.embedding_model || "",
      api_batch_size: 10,
      local_model: data.embedding_model || "",
      local_path: data.embedding_model_path || "",
    },
    services: {},
    system: { allow_registration: false },
    training: { num_questions: 8, divergence: 3 },
    is_admin: false,
    llm_configured: Boolean(data.llm_configured),
    embedding_configured: Boolean(data.embedding_configured),
    provider_mode: data.provider_mode || "none",
    embedding_mode: embeddingMode,
  } as any;
}

export async function updateSettings(
  payload: Record<string, unknown>
): Promise<ApiResponse<"/api/settings", "put">> {
  const llm = (payload.llm || {}) as AnyRecord;
  const embedding = (payload.embedding || {}) as AnyRecord;
  const llmRes = await authFetch(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      use_stub_provider: false,
      llm_api_base: llm.api_base || "",
      llm_model: llm.model || "",
      llm_api_key: llm.api_key || "",
    }),
  });
  const llmData = await readJson<AnyRecord>(llmRes);
  const embeddingMode = embedding.backend === "local"
    ? "local-model"
    : embedding.backend === "api"
      ? "openai-compatible"
      : "demo";
  const embeddingRes = await authFetch(`${API_BASE}/settings/embedding`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: embeddingMode,
      api_base: embedding.api_base || "",
      api_key: embedding.api_key || "",
      model: embedding.api_model || embedding.local_model || "",
      model_path: embedding.local_path || "",
    }),
  });
  const embeddingData = await readJson<AnyRecord>(embeddingRes);
  return {
    ...llmData,
    ...embeddingData,
    embedding_changed: true,
  } as any;
}

interface LLMConnectionPayload {
  api_base?: string;
  api_key?: string;
  model?: string;
}

// 连接测试：探测「表单里当前填的」配置（尚未保存也能测），返回 { ok, error }
export async function testLLMConnection({
  api_base,
  api_key,
  model,
}: LLMConnectionPayload): Promise<
  ApiResponse<"/api/settings/test-llm", "post">
> {
  void api_base;
  void api_key;
  void model;
  return { ok: false, error: "当前 QTrace 尚未提供独立 LLM 连接测试接口，请保存配置后进行一次合成数据训练验证。" } as any;
}

export async function testEmbeddingConnection(
  payload: Record<string, unknown>
): Promise<ApiResponse<"/api/settings/test-embedding", "post">> {
  void payload;
  return { ok: false, error: "当前 QTrace 尚未提供独立 Embedding 连接测试接口，请保存配置后重建索引验证。" } as any;
}

interface RebuildIndexCallbacks {
  /** data: { completed, total, label, status } */
  onProgress?: (data: Record<string, unknown>) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}

export async function rebuildEmbeddingIndex({
  onProgress,
  onDone,
  onError,
}: RebuildIndexCallbacks = {}): Promise<void> {
  const res = await authFetch(`${API_BASE}/agent/documents/reindex`, {
    method: "POST",
  });
  const data = await readJson<AnyRecord>(res);
  onProgress?.({ completed: data.document_count || 0, total: data.document_count || 0, status: "done" });
  onDone?.({ ...data, done: true, last_rebuild_at: new Date().toISOString() });
}
