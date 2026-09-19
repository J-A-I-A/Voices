import { statusBadge, formatDate } from "@/lib/utils";
import type { VoiceNoteOut } from "@/lib/types";

/** A single voice-note row-card with status badge, QC signals, and inline audio. */
export function VoiceNoteCard({ note }: { note: VoiceNoteOut }) {
  const badge = statusBadge(note.status);
  const qc = note.qc;
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium " + badge.className}>
              {badge.label}
            </span>
            <span className="text-xs text-neutral-400">{formatDate(note.created_at)}</span>
            {note.duration_seconds != null && (
              <span className="text-xs text-neutral-400">{note.duration_seconds}s</span>
            )}
          </div>
          <p className="text-sm text-neutral-900 font-medium line-clamp-2">
            “{note.phrase_text || "Unassigned phrase"}”
          </p>
        </div>
        {note.audio_url && (
          <audio controls preload="none" src={note.audio_url} className="h-9 w-full sm:w-64 shrink-0" />
        )}
      </div>

      {note.status === "rejected" && note.reject_reason && (
        <p className="mt-3 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
          Rejected: {note.reject_reason}
        </p>
      )}

      {qc && (
        <dl className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          {qc.transcript != null && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-neutral-400">Transcript (ASR{qc.asr_model ? " · " + qc.asr_model : ""})</dt>
              <dd className="text-neutral-700 mt-0.5">{qc.transcript || "—"}</dd>
            </div>
          )}
          {qc.wer != null && (
            <Metric label="Match (WER)" value={(1 - qc.wer).toFixed(0) + "%"} hint={"WER " + qc.wer} />
          )}
          {qc.vad_ratio != null && <Metric label="Speech" value={Math.round(qc.vad_ratio * 100) + "%"} />}
          {qc.snr_db != null && <Metric label="SNR" value={qc.snr_db + " dB"} />}
          {qc.loudness_dbfs != null && <Metric label="Loudness" value={qc.loudness_dbfs + " dBFS"} />}
          {qc.qc_reason && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-neutral-400">QC note</dt>
              <dd className="text-neutral-600 mt-0.5">{qc.qc_reason}</dd>
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
      <dt className="text-neutral-400">{label}</dt>
      <dd className="text-neutral-700 mt-0.5 font-medium">{value}</dd>
    </div>
  );
}
