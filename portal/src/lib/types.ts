export type AuthProvider = "google" | "email";

export interface UserOut {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  email: string;
  auth_provider: AuthProvider;
  whatsapp_number: string | null;
  whatsapp_verified: boolean;
  is_reviewer: boolean;
  requires_completion: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: UserOut;
  requires_completion: boolean;
}

export interface QCMetadata {
  transcript?: string | null;
  wer?: number | null;
  snr_db?: number | null;
  duration_seconds?: number | null;
  vad_ratio?: number | null;
  loudness_dbfs?: number | null;
  clipping_ratio?: number | null;
  qc_stage_failed?: string | null;
  qc_reason?: string | null;
  asr_model?: string | null;
  checked_at?: string | null;
  [k: string]: unknown;
}

export type VoiceNoteStatus = "received" | "accepted" | "rejected" | "needs_review";

export interface VoiceNoteOut {
  id: string;
  phrase_text: string | null;
  phrase_id: string | null;
  whatsapp_message_id: string | null;
  duration_seconds: number | null;
  mime_type: string | null;
  status: VoiceNoteStatus;
  reject_reason: string | null;
  qc: QCMetadata | null;
  reviewed_at: string | null;
  reviewer_id: string | null;
  created_at: string;
  audio_url: string | null;
}

export interface VoiceNoteListResponse {
  items: VoiceNoteOut[];
  total: number;
}
