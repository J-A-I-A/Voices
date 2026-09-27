"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/dashboard-shell";
import { VerifyWhatsappModal } from "@/components/verify-modal";
import { VoiceNoteCard } from "@/components/voice-note-card";
import { useAuth } from "@/lib/store";
import { voiceNotesApi, authApi, ApiError } from "@/lib/api";
import type { VoiceNoteOut } from "@/lib/types";

export default function DashboardPage() {
  const { user, setUser } = useAuth();
  const [notes, setNotes] = useState<VoiceNoteOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVerify, setShowVerify] = useState(false);
  const [filter, setFilter] = useState<string>("");
  const [agentUrl, setAgentUrl] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await voiceNotesApi.list(filter || undefined);
      setNotes(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load voice notes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.whatsapp_verified) {
      load();
      authApi.agentLink().then((r) => setAgentUrl(r.agent_url)).catch(() => setAgentUrl(null));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filter]);

  const needsVerify = !!user && (!user.whatsapp_verified || !user.whatsapp_number);

  return (
    <DashboardShell
      title="My Voice Notes"
      active="notes"
      actions={
        needsVerify ? (
          <button onClick={() => setShowVerify(true)} className="cv-btn px-5 py-2.5">
            Verify WhatsApp
          </button>
        ) : (
          <a href={agentUrl || "https://wa.me/"}
            target="_blank" rel="noopener noreferrer"
            className="cv-btn px-5 py-2.5">
            Message the Agent →
          </a>
        )
      }
    >
      {needsVerify && (
        <div className="mb-6 rounded-2xl border border-[color:var(--jaia-gold)]/40 bg-[color:var(--jaia-gold-soft)] p-4 text-sm text-[#8a5a00]">
          <p className="font-semibold text-[#6d4700]">Verify your WhatsApp number to start.</p>
          <p className="mt-1">You can&apos;t submit voice notes until your Jamaican number (876 or 658) is verified.</p>
          <button onClick={() => setShowVerify(true)} className="mt-3 rounded-full bg-[color:var(--jaia-gold)] px-3.5 py-1.5 text-xs font-semibold text-[#3d2800] transition hover:brightness-95">
            Verify now
          </button>
        </div>
      )}

      {/* Filter row */}
      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        {[
          ["", "All"], ["received", "Received"], ["accepted", "Accepted"],
          ["rejected", "Rejected"], ["needs_review", "Needs review"],
        ].map(([val, label]) => (
          <button key={val} onClick={() => setFilter(val)}
            className={"rounded-full border px-3 py-1.5 transition " + (filter === val ? "border-emerald-400 bg-[color:var(--jaia-green)] font-semibold cv-heading" : "border-[color:var(--line)] bg-white cv-body hover:border-emerald-300/70 hover:bg-white/10 hover:text-white")}>
            {label}
          </button>
        ))}
        {user?.whatsapp_verified && (
          <button onClick={load} className="cv-btn-ghost ml-auto px-3 py-1.5 text-xs">
            Refresh
          </button>
        )}
      </div>

      {error && <div className="cv-alert mb-4">{error}</div>}

      {loading ? (
        <p className="cv-muted">Loading…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--line)] bg-white p-10 text-center cv-muted">
          <p className="font-semibold cv-heading">No voice notes yet</p>
          <p className="mt-1 text-sm">
            {needsVerify
              ? "Verify your WhatsApp number, then message the agent to get a phrase."
              : "Message the agent on WhatsApp to get a phrase and send your first recording."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {notes.map((n) => <VoiceNoteCard key={n.id} note={n} />)}
        </div>
      )}

      <VerifyWhatsappModal
        open={showVerify}
        user={user}
        onClose={() => setShowVerify(false)}
        onVerified={(me) => { setUser(me); setShowVerify(false); load(); }}
      />
    </DashboardShell>
  );
}
