import { API_BASE, authFetch } from "./client";

export interface DocumentItem {
  document_id: string;
  filename: string;
  extension: string;
  size_bytes: number;
  status: "indexing" | "needs_reindex" | "ready" | "error";
  chunk_count: number;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentSource {
  document_id: string;
  filename: string;
}

export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources?: AgentSource[];
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface DocumentsResponse {
  items: DocumentItem[];
  supported_extensions: string[];
  max_upload_bytes: number;
}

interface ConversationsResponse {
  items: ConversationSummary[];
}

export interface ConversationDetail extends ConversationSummary {
  user_id: string;
  messages: AgentMessage[];
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "请求失败");
  }
  return response.json() as Promise<T>;
}

export async function getDocuments(): Promise<DocumentsResponse> {
  const documents = await parseResponse<any[]>(await authFetch(`${API_BASE}/agent/documents`));
  return {
    items: documents.map(normalizeDocument),
    supported_extensions: [".pdf", ".md", ".markdown"],
    max_upload_bytes: 20 * 1024 * 1024,
  };
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  const document = await parseResponse<any>(await authFetch(`${API_BASE}/agent/documents/upload`, {
    method: "POST",
    body: form,
  }));
  return normalizeDocument(document);
}

export async function deleteDocument(documentId: string): Promise<void> {
  void documentId;
  throw new Error("当前 QTrace 尚未开放个人文档删除接口");
}

export async function getConversations(): Promise<ConversationsResponse> {
  const conversations = await parseResponse<any[]>(await authFetch(`${API_BASE}/agent/conversations`));
  return { items: conversations.map(normalizeConversation) };
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const conversation = await parseResponse<any>(await authFetch(`${API_BASE}/agent/conversations/${conversationId}`));
  return normalizeConversationDetail(conversation);
}

export async function deleteConversation(conversationId: string): Promise<void> {
  void conversationId;
  throw new Error("当前 QTrace 尚未开放 Agent 对话删除接口");
}

export async function sendAgentMessage(
  message: string,
  conversationId?: string | null,
): Promise<{ conversation_id: string; title: string; message: AgentMessage }> {
  const result = await parseResponse<any>(await authFetch(`${API_BASE}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId || null }),
  }));
  return {
    conversation_id: result.conversation_id || result.conversation?.id,
    title: result.title || result.conversation?.title || "个人 Agent",
    message: {
      role: "assistant",
      content: result.message?.content || result.message?.text || "",
      created_at: result.message?.created_at || new Date().toISOString(),
      sources: Array.isArray(result.message?.sources)
        ? result.message.sources.map((source: any) => ({
          document_id: source.document_id || source.id,
          filename: source.filename || source.title || "个人文档",
        }))
        : [],
    },
  };
}

function normalizeDocument(document: any): DocumentItem {
  return {
    document_id: document.document_id || document.id,
    filename: document.filename || document.title || "未命名文档",
    extension: document.extension || `.${document.source_type || "text"}`,
    size_bytes: Number(document.size_bytes ?? document.content_chars ?? 0),
    status: document.status || "ready",
    chunk_count: Number(document.chunk_count ?? 0),
    error: document.error || null,
    created_at: document.created_at || "",
    updated_at: document.updated_at || document.created_at || "",
  };
}

function normalizeConversation(conversation: any): ConversationSummary {
  return {
    conversation_id: conversation.conversation_id || conversation.id,
    title: conversation.title || "个人 Agent",
    message_count: Number(conversation.message_count ?? conversation.messages?.length ?? 0),
    created_at: conversation.created_at || "",
    updated_at: conversation.updated_at || conversation.created_at || "",
  };
}

function normalizeConversationDetail(conversation: any): ConversationDetail {
  const summary = normalizeConversation(conversation);
  return {
    ...summary,
    user_id: conversation.user_id || "",
    messages: Array.isArray(conversation.messages)
      ? conversation.messages.map((message: any) => ({
        role: message.role === "user" ? "user" : "assistant",
        content: message.content || message.text || "",
        created_at: message.created_at || "",
        sources: Array.isArray(message.sources)
          ? message.sources.map((source: any) => ({
            document_id: source.document_id || source.id,
            filename: source.filename || source.title || "个人文档",
          }))
          : [],
      }))
      : [],
  };
}
