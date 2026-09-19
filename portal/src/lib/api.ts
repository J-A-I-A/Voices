import type {
  TokenResponse, UserOut, VoiceNoteListResponse, VoiceNoteOut,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

let _token: string | null = null;
const TOKEN_KEY = "carib_token";

export function setToken(token: string | null) {
  _token = token;
  if (typeof window !== "undefined") {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return _token;
  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(BASE + path, { ...init, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const msg = data?.detail || res.statusText;
    throw new ApiError(msg, res.status);
  }
  return data as T;
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

// ─── Auth ──────────────────────────────────────────────────
export const authApi = {
  registerEmail: (body: {
    first_name: string; last_name: string; date_of_birth: string;
    email: string; password: string;
  }) => request<TokenResponse>("/auth/register/email", { method: "POST", body: JSON.stringify(body) }),

  google: (body: { id_token: string; date_of_birth: string; first_name?: string; last_name?: string }) =>
    request<TokenResponse>("/auth/google", { method: "POST", body: JSON.stringify(body) }),

  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),

  me: () => request<UserOut>("/auth/me"),

  agentLink: () => request<{ agent_url: string }>("/auth/agent-link"),

  requestOtp: (phone: string) =>
    request<{ status: string; phone: string }>("/auth/verify/request", { method: "POST", body: JSON.stringify({ phone }) }),

  resendOtp: (phone: string) =>
    request<{ status: string; phone: string }>("/auth/verify/resend", { method: "POST", body: JSON.stringify({ phone }) }),

  checkOtp: (phone: string, code: string) =>
    request<{ status: string; phone: string; agent_url: string }>("/auth/verify/check", { method: "POST", body: JSON.stringify({ phone, code }) }),
};

// ─── Voice notes ────────────────────────────────────────────
export const voiceNotesApi = {
  list: (status?: string) =>
    request<VoiceNoteListResponse>("/voice-notes" + (status ? ("?status=" + status) : "")),
  get: (id: string) => request<VoiceNoteOut>("/voice-notes/" + id),
};

// ─── Reviewer ────────────────────────────────────────────────
export const reviewerApi = {
  queue: () => request<VoiceNoteListResponse>("/reviewer/queue"),
  all: (status?: string) =>
    request<VoiceNoteListResponse>("/reviewer/all" + (status ? ("?status=" + status) : "")),
  resolve: (id: string, body: { status: "accepted" | "rejected"; reject_reason?: string }) =>
    request<VoiceNoteOut>("/reviewer/" + id + "/resolve", { method: "POST", body: JSON.stringify(body) }),
};
