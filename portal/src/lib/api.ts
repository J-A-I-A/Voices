import type {
  TokenResponse, UserOut, VoiceNoteListResponse, VoiceNoteOut,
  AdminStats, AdminUser, AdminPhrase, ConsentRecordOut, EraseResult, GoogleAuthResult, ConsentStatus, ProfileDeleteResult, PhraseImportResult, PhraseLength, PhraseLengthInfo,
} from "./types";

// Same-origin by default: next.config.mjs proxies /api/* to the backend.
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

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

  /** date_of_birth is only needed the first time; returning users sign straight in. */
  google: (body: { id_token: string; date_of_birth?: string; first_name?: string; last_name?: string }) =>
    request<GoogleAuthResult>("/auth/google", { method: "POST", body: JSON.stringify(body) }),

  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),

  me: () => request<UserOut>("/auth/me"),

  verifyEmail: (token: string) =>
    request<UserOut>("/auth/email/verify", { method: "POST", body: JSON.stringify({ token }) }),

  resendVerificationEmail: () =>
    request<{ status: "sent" | "already_verified"; email?: string }>("/auth/email/resend", { method: "POST" }),

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

// ─── Admin ───────────────────────────────────────────────────
export const adminApi = {
  stats: () => request<AdminStats>("/admin/stats"),

  users: (q?: string) =>
    request<{ items: AdminUser[]; total: number }>(
      "/admin/users" + (q ? "?q=" + encodeURIComponent(q) : "")),

  setRoles: (id: string, body: { is_reviewer?: boolean; is_admin?: boolean }) =>
    request<AdminUser>("/admin/users/" + id + "/roles", { method: "PATCH", body: JSON.stringify(body) }),

  eraseUser: (id: string) =>
    request<EraseResult>("/admin/users/" + id + "/erase", { method: "POST" }),

  phrases: (opts?: { q?: string; length?: PhraseLength | ""; includeInactive?: boolean }) => {
    const p = new URLSearchParams();
    if (opts?.q) p.set("q", opts.q);
    if (opts?.length) p.set("length", opts.length);
    if (opts?.includeInactive === false) p.set("include_inactive", "false");
    const qs = p.toString();
    return request<AdminPhrase[]>("/admin/phrases" + (qs ? "?" + qs : ""));
  },

  phraseLengths: () => request<PhraseLengthInfo>("/admin/phrases/lengths"),

  /** Bulk import from .xlsx / .xls / .csv. Sent as multipart, not JSON. */
  importPhrases: async (file: File): Promise<PhraseImportResult> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(BASE + "/admin/phrases/import", {
      method: "POST",
      headers: getToken() ? { Authorization: "Bearer " + getToken() } : {},
      body: form, // no Content-Type: the browser sets the multipart boundary
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) throw new ApiError(data?.detail || res.statusText, res.status);
    return data as PhraseImportResult;
  },

  createPhrase: (body: { text: string; locale?: string; active?: boolean }) =>
    request<AdminPhrase>("/admin/phrases", { method: "POST", body: JSON.stringify(body) }),

  updatePhrase: (id: string, body: { text?: string; locale?: string; active?: boolean }) =>
    request<AdminPhrase>("/admin/phrases/" + id, { method: "PATCH", body: JSON.stringify(body) }),

  deletePhrase: (id: string) =>
    request<void>("/admin/phrases/" + id, { method: "DELETE" }),

  consents: (activeOnly = false) =>
    request<{ items: ConsentRecordOut[]; total: number }>(
      "/admin/consents" + (activeOnly ? "?active_only=true" : "")),

  /** Download a file through fetch so the bearer token is sent. */
  download: async (path: string, filename: string) => {
    const res = await fetch(BASE + path, {
      headers: getToken() ? { Authorization: "Bearer " + getToken() } : {},
    });
    if (!res.ok) throw new ApiError("Download failed", res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

// ─── Profile (self-service) ──────────────────────────────────
export const profileApi = {
  update: (body: { first_name?: string; last_name?: string; date_of_birth?: string }) =>
    request<UserOut>("/profile", { method: "PATCH", body: JSON.stringify(body) }),

  unlinkWhatsapp: () => request<UserOut>("/profile/whatsapp", { method: "DELETE" }),

  consent: () => request<ConsentStatus>("/profile/consent"),

  withdrawConsent: () =>
    request<ConsentStatus>("/profile/consent/withdraw", { method: "POST" }),

  deleteProfile: () => request<ProfileDeleteResult>("/profile", { method: "DELETE" }),
};
