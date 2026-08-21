export type User = { id: string; email: string; name: string };

export type Settings = {
  use_stub_provider: boolean;
  provider_mode: "none" | "stub" | "openai" | string;
  llm_api_base: string;
  llm_model: string;
  llm_key_configured: boolean;
  embedding_mode: string;
  llm_configured: boolean;
  embedding_configured: boolean;
  needs_onboarding: boolean;
};

export type Message = { role: "user" | "assistant"; content: string };

export type Review = {
  summary: string;
  average_score: number;
  scores: number[];
  strengths: string[];
  weak_points: string[];
  behavior_signals?: string[];
  action_items: string[];
  transcript_meta?: {
    recording_mode: string;
    transcript_chars: number;
    message_count: number;
    question_count: number;
    answer_count: number;
    estimated_minutes: number;
    speaker_labels_detected: boolean;
    analysis_mode?: "rules" | "llm" | string;
  };
};

export type Session = {
  id: string;
  target_role: string;
  phase: string;
  phase_question_count: number;
  is_finished: boolean;
  messages: Message[];
  review: Review | null;
  mode?: "resume" | "topic_drill" | string;
  topic?: string | null;
  company?: string;
  position?: string;
  recording_mode?: "dual" | "solo" | string;
  recording_analysis_mode?: "rules" | "llm" | string;
};

export type Profile = {
  completed_sessions: number;
  mastery_score: number;
  weak_points: string[];
  strong_points: string[];
  behavior_signals: string[];
  action_items: string[];
  topic_mastery: TopicMastery[];
  due_reviews: DueReview[];
};

export type ResumeStatus = {
  has_resume: boolean;
  filename: string;
  size: number;
  text_chars: number;
};

export type Topic = { name: string; icon: string; dir: string };
export type KnowledgeFile = { filename: string; content: string };
export type TopicMastery = {
  topic: string;
  attempts: number;
  mastery_score: number;
  last_score: number;
  weak_points: string[];
  recent_scores: number[];
  trend: string;
  updated_at: string;
};
export type DueReview = {
  point: string;
  topic: string | null;
  interval_days: number;
  ease_factor: number;
  repetitions: number;
  next_review: string;
  last_score: number | null;
  updated_at: string;
};
export type JobPreview = {
  company: string;
  position: string;
  role_summary: string;
  focus_areas: { area: string; priority: string; reason: string }[];
  likely_question_groups: { title: string; reason: string; sample_questions: string[] }[];
  resume_alignment: {
    resume_used: boolean;
    fit_assessment: string;
    matching_evidence: string[];
    risk_gaps: string[];
    recommended_stories: { project: string; reason: string }[];
  };
  prep_priorities: string[];
  question_blueprint: { category: string; focus_area: string; objective: string; question: string }[];
  jd_excerpt: string;
  detected_skills: string[];
};

export type CopilotResult = {
  company: string;
  position: string;
  role_summary: string;
  detected_skills: string[];
  focus_areas: { area: string; priority: string; reason: string }[];
  resume_alignment: {
    resume_used: boolean;
    fit_assessment: string;
    matching_evidence: string[];
    risk_gaps: string[];
    recommended_stories: { project: string; reason: string }[];
  };
  strategy_tree: {
    root: string;
    nodes: { id: string; label: string; priority: string; trigger: string; follow_up: string }[];
  };
  risk_map: { risk: string; severity: string; evidence: string; mitigation: string }[];
  prep_hints: string[];
  question_blueprint: { category: string; focus_area: string; objective: string; question: string }[];
  source: { resume_used: boolean; profile_used: boolean; analysis_mode: string };
};

export type CopilotPrep = {
  id: string;
  company: string;
  position: string;
  jd_text: string;
  status: string;
  result: CopilotResult | null;
  error: string;
  created_at: string;
  updated_at: string;
};

export type CopilotStreamEvent = {
  event: string;
  data: {
    prep_id: string;
    stage: string;
    message?: string;
    result?: CopilotResult;
    detected_skills?: string[];
    risk_count?: number;
    node_count?: number;
  };
};

export type AgentMessage = {
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

export type AgentPlan = {
  intent: string;
  tool_calls: { name: string; reason: string }[];
};

export type AgentToolTrace = {
  name: string;
  status: "completed" | "failed" | string;
  reason: string;
  summary: string;
};

export type AgentChatResponse = {
  conversation_id: string;
  title: string;
  message: AgentMessage;
  plan: AgentPlan;
  tool_trace: AgentToolTrace[];
};

export type AgentConversation = {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type AgentConversationDetail = AgentConversation & {
  messages: AgentMessage[];
};

export function getCopilotPrepHistory(token: string) {
  return apiFetch<CopilotPrep[]>("/copilot/prep", {}, token);
}

export function getAgentConversations(token: string) {
  return apiFetch<AgentConversation[]>("/agent/conversations", {}, token);
}

export function getAgentConversation(conversationId: string, token: string) {
  return apiFetch<AgentConversationDetail>(
    `/agent/conversations/${encodeURIComponent(conversationId)}`,
    {},
    token,
  );
}

export function chatWithAgent(
  payload: { message: string; conversation_id?: string | null },
  token: string,
) {
  return apiFetch<AgentChatResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "请求失败");
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body?.detail ?? body);
  return body as T;
}

export async function authenticate(
  mode: "login" | "register",
  payload: { email: string; password: string; name?: string },
) {
  return apiFetch<{ access_token: string; user: User }>(`/auth/${mode}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResumeStatus(token: string) {
  return apiFetch<ResumeStatus>("/resume/status", {}, token);
}

export function uploadResume(file: File, token: string) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ResumeStatus>("/resume/upload", { method: "POST", body: form }, token);
}

export function deleteResume(token: string) {
  return apiFetch<{ deleted: boolean }>("/resume", { method: "DELETE" }, token);
}

export function getTopics(token: string) {
  return apiFetch<Record<string, Topic>>("/topics", {}, token);
}

export function createTopic(payload: { key?: string; name: string; icon?: string }, token: string) {
  return apiFetch<{ ok: boolean | string; key: string }>("/topics", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function deleteTopic(topic: string, token: string) {
  return apiFetch<{ ok: boolean }>(`/topics/${encodeURIComponent(topic)}`, { method: "DELETE" }, token);
}

export function getCoreKnowledge(topic: string, token: string) {
  return apiFetch<KnowledgeFile[]>(`/knowledge/${encodeURIComponent(topic)}/core`, {}, token);
}

export function createCoreKnowledge(topic: string, payload: KnowledgeFile, token: string) {
  return apiFetch<{ ok: boolean | string; filename: string }>(`/knowledge/${encodeURIComponent(topic)}/core`, {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function updateCoreKnowledge(topic: string, filename: string, content: string, token: string) {
  return apiFetch<{ ok: boolean }>(`/knowledge/${encodeURIComponent(topic)}/core/${encodeURIComponent(filename)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  }, token);
}

export function deleteCoreKnowledge(topic: string, filename: string, token: string) {
  return apiFetch<{ ok: boolean }>(`/knowledge/${encodeURIComponent(topic)}/core/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  }, token);
}

export function getHighFreq(topic: string, token: string) {
  return apiFetch<{ content: string }>(`/knowledge/${encodeURIComponent(topic)}/high_freq`, {}, token);
}

export function updateHighFreq(topic: string, content: string, token: string) {
  return apiFetch<{ ok: boolean }>(`/knowledge/${encodeURIComponent(topic)}/high_freq`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  }, token);
}

export function getTopicMastery(token: string) {
  return apiFetch<TopicMastery[]>("/profile/topics", {}, token);
}

export function getTopicHistory(topic: string, token: string) {
  return apiFetch<Session[]>(`/profile/topic/${encodeURIComponent(topic)}/history`, {}, token);
}

export function getDueReviews(token: string, topic?: string) {
  const query = topic ? `?topic=${encodeURIComponent(topic)}` : "";
  return apiFetch<DueReview[]>(`/profile/due-reviews${query}`, {}, token);
}

export function previewJobPrep(
  payload: { company?: string; position?: string; jd_text: string; use_resume: boolean },
  token: string,
) {
  return apiFetch<{ preview: JobPreview }>("/job-prep/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function startJobPrep(
  payload: { company?: string; position?: string; jd_text: string; use_resume: boolean; preview?: JobPreview | null },
  token: string,
) {
  return apiFetch<Session>("/job-prep/start", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export async function streamCopilot(
  payload: { company?: string; position?: string; jd_text: string; use_resume: boolean },
  token: string,
  onEvent: (event: CopilotStreamEvent) => void,
): Promise<CopilotResult> {
  const response = await fetch(`${API_BASE}/copilot/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? body);
  }
  if (!response.body) throw new Error("浏览器不支持 SSE 流读取");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: CopilotResult | null = null;

  function dispatch(block: string) {
    const lines = block.split("\n");
    let eventName = "message";
    let dataText = "";
    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataText += line.slice(5).trim();
    }
    if (!dataText) return;
    const data = JSON.parse(dataText) as CopilotStreamEvent["data"];
    const event = { event: eventName, data } satisfies CopilotStreamEvent;
    onEvent(event);
    if (eventName === "error") throw new Error(data.message || "Copilot Prep 失败");
    if (eventName === "completed" && data.result) completed = data.result;
  }

  while (true) {
    const chunk = await reader.read();
    buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) dispatch(block);
    if (chunk.done) break;
  }
  if (buffer.trim()) dispatch(buffer);
  if (!completed) throw new Error("Copilot 流没有返回完成事件");
  return completed;
}

export function analyzeRecording(
  payload: { transcript: string; recording_mode: "dual" | "solo"; analysis_mode: "rules" | "llm"; company?: string; position?: string },
  token: string,
) {
  return apiFetch<Session>("/recording/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}
