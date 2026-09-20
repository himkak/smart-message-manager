/** Typed client for the Smart Messages Manager backend API. */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

export interface SyncStatus {
  connected: boolean;
  email: string | null;
  cursor: string | null;
}

export function getSyncStatus(): Promise<SyncStatus> {
  return request<SyncStatus>("/api/sync/status");
}

export function startGoogleAuthUrl(): string {
  return `${API_BASE_URL}/api/auth/google/start`;
}

export interface SyncResult {
  status: string;
  messages_processed: number;
  cursor: string;
  indexed: number;
}

export function syncGmail(): Promise<SyncResult> {
  return request<SyncResult>("/api/sync/gmail", { method: "POST" });
}

export type MessageSource = "gmail" | "whatsapp" | "sms";

export interface Message {
  id: string;
  source: MessageSource;
  conversation_id: string;
  timestamp: string;
  sender: string;
  recipients: string[];
  subject: string | null;
  text: string;
  attachment_ids: string[];
  participants: string[];
  metadata: Record<string, unknown>;
}

export interface SearchResultItem {
  score: number;
  message: Message;
}

export interface SearchResponse {
  results: SearchResultItem[];
}

export function search(query: string, top = 10): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({ query, top }),
  });
}

export interface Citation {
  message_id: string;
  source: MessageSource;
  quote: string;
}

export interface ChatResponse {
  answer: string;
  has_evidence: boolean;
  citations: Citation[];
}

export function askChat(question: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
