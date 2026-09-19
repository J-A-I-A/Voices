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
    <DashboardShell title="Review Queue" actions={<button onClick={load} className="rounded-full border border-neutral-200 px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50">Refresh</button>}>
      <p className="mb-4 text-sm text-neutral-500">
        Voice notes in the middle quality band (neither clearly accepted nor rejected automatically) land here.
        Listen and resolve each one.
      </p>

      {error && <div className="mb-4 rounded-2xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {loadingNotes ? (
        <p className="text-neutral-400">Loading…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-300 bg-white p-10 text-center text-neutral-500">
          <p className="font-medium text-neutral-700">Queue is empty 🎉</p>
          <p className="mt-1 text-sm">No notes need manual review right now.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {notes.map((n) => (
            <div key={n.id} className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
              <VoiceNoteCard note={n} />
              <div className="mt-4 flex flex-col gap-3 border-t border-neutral-100 pt-4">
                <input
                  placeholder="Reject reason (only required if rejecting)"
                  value={rejectReason[n.id] || ""}
                  onChange={(e) => setRejectReason((r) => ({ ...r, [n.id]: e.target.value }))}
                  className="w-full rounded-full border border-neutral-200 px-4 py-2 text-sm focus:border-neutral-900 focus:outline-none"
                />
                <div className="flex gap-2">
                  <button disabled={busy === n.id}
                    onClick={() => resolve(n, "accepted")}
                    className="flex-1 rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60">
                    Accept
                  </button>
                  <button disabled={busy === n.id}
                    onClick={() => resolve(n, "rejected")}
                    className="flex-1 rounded-full bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60">
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
