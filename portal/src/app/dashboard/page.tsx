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
      actions={
        needsVerify ? (
          <button onClick={() => setShowVerify(true)}
            className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
            Verify WhatsApp
          </button>
        ) : (
          <a href={agentUrl || "https://wa.me/"}
            target="_blank" rel="noopener noreferrer"
            className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
            Message the Agent →
          </a>
        )
      }
    >
      {needsVerify && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-medium">Verify your WhatsApp number to start.</p>
          <p className="mt-1">You can&apos;t submit voice notes until your Jamaican number (876 or 658) is verified.</p>
          <button onClick={() => setShowVerify(true)} className="mt-2 rounded-full bg-amber-600 px-3 py-1.5 text-white text-xs font-medium hover:bg-amber-700">
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
            className={"rounded-full border px-3 py-1 " + (filter === val ? "border-neutral-900 bg-neutral-900 text-white" : "border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50")}>
            {label}
          </button>
        ))}
        {user?.whatsapp_verified && (
          <button onClick={load} className="ml-auto rounded-full border border-neutral-200 px-3 py-1 text-neutral-700 hover:bg-neutral-50">
            Refresh
          </button>
        )}
      </div>

      {error && <div className="mb-4 rounded-2xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {loading ? (
        <p className="text-neutral-400">Loading…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-300 bg-white p-10 text-center text-neutral-500">
          <p className="font-medium text-neutral-700">No voice notes yet</p>
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
