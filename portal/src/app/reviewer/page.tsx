"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { VoiceNoteCard } from "@/components/voice-note-card";
import { useAuth } from "@/lib/store";
import { reviewerApi, ApiError } from "@/lib/api";
import type { VoiceNoteOut } from "@/lib/types";
import { statusBadge, formatDate } from "@/lib/utils";

export default function ReviewerPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [notes, setNotes] = useState<VoiceNoteOut[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<Record<string, string>>({});

  const load = async () => {
    setLoadingNotes(true);
    setError(null);
    try {
      const res = await reviewerApi.queue();
      setNotes(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load review queue.");
    } finally {
      setLoadingNotes(false);
    }
  };

  useEffect(() => {
    if (loading) return;
    if (!user) { router.replace("/signin"); return; }
    if (!user.is_reviewer) { router.replace("/dashboard"); return; }
    load();
  }, [user, loading, router]);

  const resolve = async (note: VoiceNoteOut, status: "accepted" | "rejected") => {
    setBusy(note.id);
    try {
      await reviewerApi.resolve(note.id, { status, reject_reason: status === "rejected" ? (rejectReason[note.id] || "Did not match assigned phrase.") : undefined });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not resolve note.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <DashboardShell title="Review Queue" active="review" actions={<button onClick={load} className="cv-btn-ghost">Refresh</button>}>
      <p className="mb-5 max-w-2xl text-sm cv-body">
        Voice notes in the middle quality band (neither clearly accepted nor rejected automatically) land here.
        Listen and resolve each one.
      </p>

      {error && <div className="cv-alert mb-4">{error}</div>}

      {loadingNotes ? (
        <p className="cv-muted">Loading…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--line)] bg-white p-10 text-center cv-muted">
          <p className="font-semibold cv-heading">Queue is empty 🎉</p>
          <p className="mt-1 text-sm">No notes need manual review right now.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {notes.map((n) => (
            <div key={n.id} className="cv-surface p-4">
              <VoiceNoteCard note={n} reviewerSignals />
              <div className="mt-4 flex flex-col gap-3 border-t border-[color:var(--line)] pt-4">
                <input
                  placeholder="Reject reason (only required if rejecting)"
                  value={rejectReason[n.id] || ""}
                  onChange={(e) => setRejectReason((r) => ({ ...r, [n.id]: e.target.value }))}
                  className="cv-input py-2.5"
                />
                <div className="flex gap-2">
                  <button disabled={busy === n.id}
                    onClick={() => resolve(n, "accepted")}
                    className="cv-btn flex-1 py-2.5">
                    Accept
                  </button>
                  <button disabled={busy === n.id}
                    onClick={() => resolve(n, "rejected")}
                    className="cv-btn-danger flex-1">
                    Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </DashboardShell>
  );
}
