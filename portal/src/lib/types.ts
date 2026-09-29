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
  email_verified: boolean;
  is_reviewer: boolean;
  is_admin: boolean;
  requires_completion: boolean;
}

export interface GoogleAuthResult {
  requires_completion: boolean;
  access_token: string | null;
  token_type: "bearer";
  user: UserOut | null;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
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
  // Known-AI-voice check; only present in reviewer responses.
  ai_voice_score?: number | null;
  ai_voice_closest?: string | null;
  ai_voice_match?: string | null;
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

// ─── Admin ───────────────────────────────────────────────────
export interface AdminStats {
  users_total: number;
  users_verified: number;
  users_consented: number;
  reviewers: number;
  admins: number;
  notes_total: number;
  notes_by_status: { status: string; count: number }[];
  phrases_total: number;
  phrases_active: number;
  total_audio_seconds: number;
  contributors_with_notes: number;
  acceptance_rate: number | null;
  needs_review: number;
}

export interface AdminUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  auth_provider: string;
  whatsapp_number: string | null;
  whatsapp_verified: boolean;
  is_reviewer: boolean;
  is_admin: boolean;
  has_consent: boolean;
  note_count: number;
  created_at: string;
}

export type PhraseLength = "short" | "medium" | "long";

export interface AdminPhrase {
  id: string;
  text: string;
  locale: string;
  active: boolean;
  note_count: number;
  word_count: number;
  estimated_seconds: number;
  length: PhraseLength;
}

export interface PhraseLengthBand {
  band: PhraseLength;
  min_words: number;
  max_words: number;
  max_seconds: number;
  count: number;
}

export interface PhraseLengthInfo {
  words_per_minute: number;
  bands: PhraseLengthBand[];
}

export interface ConsentRecordOut {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  policy_version: string;
  channel: string;
  evidence: string | null;
  phone: string | null;
  consented_at: string;
  withdrawn_at: string | null;
  is_active: boolean;
}

export interface EraseResult {
  user_id: string;
  consents_withdrawn: number;
  notes_deleted: number;
  audio_objects_deleted: number;
  note: string;
}

export interface ConsentStatus {
  has_consent: boolean;
  policy_version: string | null;
  consented_at: string | null;
  channel: string | null;
}

export interface ProfileDeleteResult {
  deleted: boolean;
  notes_deleted: number;
  audio_objects_deleted: number;
  consents_withdrawn: number;
  note: string;
}

export interface PhraseImportResult {
  added: number;
  duplicates: number;
  skipped: number;
  rows_read: number;
  by_length: Record<string, number>;
  details: string[];
}
