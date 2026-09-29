import { statusBadge, formatDate } from "@/lib/utils";
import type { VoiceNoteOut } from "@/lib/types";

/** A single voice-note row-card with status badge, QC signals, and inline audio.
 *  `reviewerSignals` shows checks meant only for reviewers (AI-voice match). */
export function VoiceNoteCard({ note, reviewerSignals = false }: { note: VoiceNoteOut; reviewerSignals?: boolean }) {
  const badge = statusBadge(note.status);
  const qc = note.qc;
  return (
    <div className="cv-surface p-5 transition hover:border-[color:var(--jaia-green)]/40">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-2">
            <span className={"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium " + badge.className}>
              {badge.label}
            </span>
            <span className="text-xs cv-muted">{formatDate(note.created_at)}</span>
            {note.duration_seconds != null && (
              <span className="text-xs cv-muted">{note.duration_seconds}s</span>
            )}
          </div>
          <p className="line-clamp-2 text-sm font-medium cv-heading">
            “{note.phrase_text || "Unassigned phrase"}”
          </p>
        </div>
        {note.audio_url && (
          <audio controls preload="none" src={note.audio_url} className="h-9 w-full shrink-0 sm:w-64" />
        )}
      </div>

      {note.status === "rejected" && note.reject_reason && (
        <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          Rejected: {note.reject_reason}
        </p>
      )}

      {reviewerSignals && qc?.ai_voice_match && (
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Possible AI voice: matches known synthetic voice “{qc.ai_voice_match}”
          {qc.ai_voice_score != null && <> (similarity {qc.ai_voice_score.toFixed(2)})</>}
        </p>
      )}

      {qc && (
        <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-[color:var(--line)] pt-4 text-xs sm:grid-cols-4">
          {qc.transcript != null && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="cv-muted">Transcript (ASR{qc.asr_model ? " · " + qc.asr_model : ""})</dt>
              <dd className="mt-0.5 cv-body">{qc.transcript || "—"}</dd>
            </div>
          )}
          {qc.wer != null && (
            <Metric label="Match (WER)" value={Math.max(0, Math.round((1 - qc.wer) * 100)) + "%"} hint={"WER " + qc.wer} />
          )}
          {qc.vad_ratio != null && <Metric label="Speech" value={Math.round(qc.vad_ratio * 100) + "%"} />}
          {qc.snr_db != null && <Metric label="SNR" value={qc.snr_db + " dB"} />}
          {qc.loudness_dbfs != null && <Metric label="Loudness" value={qc.loudness_dbfs + " dBFS"} />}
          {reviewerSignals && qc.ai_voice_score != null && (
            <Metric
              label="AI-voice similarity"
              value={qc.ai_voice_score.toFixed(2)}
              hint={qc.ai_voice_closest ? "Closest: " + qc.ai_voice_closest : undefined}
            />
          )}
          {qc.qc_reason && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="cv-muted">QC note</dt>
              <dd className="mt-0.5 cv-body">{qc.qc_reason}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div title={hint}>
      <dt className="cv-muted">{label}</dt>
      <dd className="mt-0.5 font-medium cv-heading">{value}</dd>
    </div>
  );
}
