"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { VoiceNoteCard } from "@/components/voice-note-card";
import { useAuth } from "@/lib/store";
import { adminApi, ApiError } from "@/lib/api";
import type { AdminStats, AdminUser, AdminPhrase, ConsentRecordOut, PhraseImportResult,
  PhraseLength, PhraseLengthInfo, VoiceNoteOut } from "@/lib/types";
import { formatDate } from "@/lib/utils";

type Tab = "overview" | "users" | "phrases" | "rejected" | "consent" | "export";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "users", label: "Users" },
  { id: "phrases", label: "Phrase bank" },
  { id: "rejected", label: "Rejected notes" },
  { id: "consent", label: "Consent" },
  { id: "export", label: "Export" },
];

function fmtDuration(totalSeconds: number) {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const m = Math.floor(totalSeconds / 60);
  if (m < 60) return `${m}m ${totalSeconds % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="cv-surface p-5">
      <div className="text-xs font-medium uppercase tracking-wider cv-eyebrow">{label}</div>
      <div className="mt-2 text-3xl font-bold tracking-tight cv-heading">{value}</div>
      {hint && <div className="mt-1 text-xs cv-muted">{hint}</div>}
    </div>
  );
}

const LENGTH_STYLES: Record<PhraseLength, string> = {
  short: "border-sky-200 bg-sky-100 text-sky-700",
  medium: "border-[color:var(--jaia-gold)]/40 bg-[color:var(--jaia-gold-soft)] text-[#8a5a00]",
  long: "border-fuchsia-200 bg-fuchsia-100 text-fuchsia-700",
};

function LengthBadge({ length, seconds }: { length: PhraseLength; seconds: number }) {
  return (
    <span
      title={`about ${seconds}s to read aloud`}
      className={"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize " + LENGTH_STYLES[length]}
    >
      {length}
    </span>
  );
}

function Toggle({
  checked, onChange, disabled, label,
}: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition disabled:opacity-40 " +
        (checked
          ? "border-[color:var(--jaia-green)] bg-[color:var(--jaia-green)]"
          : "border-[color:var(--line)] bg-[color:var(--paper-warm)] hover:bg-white/[0.14]")
      }
    >
      <span
        className={
          "inline-block h-4 w-4 transform rounded-full bg-white transition " +
          (checked ? "translate-x-6" : "translate-x-1")
        }
      />
    </button>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [tab, setTabState] = useState<Tab>("overview");

  // Keep the active tab in the URL so it survives a refresh and can be linked
  // to. Read from location rather than useSearchParams to avoid needing a
  // Suspense boundary around the whole page.
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    if (t && TABS.some((x) => x.id === t)) setTabState(t);
  }, []);

  const setTab = useCallback((next: Tab) => {
    setTabState(next);
    const url = new URL(window.location.href);
    if (next === "overview") url.searchParams.delete("tab");
    else url.searchParams.set("tab", next);
    window.history.replaceState(null, "", url.toString());
  }, []);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [userQuery, setUserQuery] = useState("");
  const [phrases, setPhrases] = useState<AdminPhrase[]>([]);
  const [newPhrase, setNewPhrase] = useState("");
  const [phraseQuery, setPhraseQuery] = useState("");
  const [importResult, setImportResult] = useState<PhraseImportResult | null>(null);
  const [lengthFilter, setLengthFilter] = useState<PhraseLength | "">("");
  const [lengths, setLengths] = useState<PhraseLengthInfo | null>(null);
  const [consents, setConsents] = useState<ConsentRecordOut[]>([]);
  const [rejected, setRejected] = useState<VoiceNoteOut[]>([]);
  const [rejectedTotal, setRejectedTotal] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);

  // Admins only. Reviewers get bounced to their own queue.
  // This must not early-return before DashboardShell renders: the shell is what
  // calls bootstrap(), so returning null while the store is still empty would
  // mean auth never initialises and the page stays blank forever.
  useEffect(() => {
    if (loading || !user) return;
    if (!user.is_admin) router.replace(user.is_reviewer ? "/reviewer" : "/dashboard");
  }, [user, loading, router]);

  const guard = useCallback(async (fn: () => Promise<void>, key?: string) => {
    setError(null);
    if (key) setBusy(key);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      if (key) setBusy(null);
    }
  }, []);

  const loadTab = useCallback((which: Tab) => {
    if (which === "overview") return guard(async () => setStats(await adminApi.stats()));
    if (which === "users") return guard(async () => setUsers((await adminApi.users(userQuery || undefined)).items));
    if (which === "phrases") return guard(async () => {
      const [rows, info] = await Promise.all([
        adminApi.phrases({ q: phraseQuery || undefined, length: lengthFilter || undefined }),
        adminApi.phraseLengths(),
      ]);
      setPhrases(rows);
      setLengths(info);
    });
    if (which === "consent") return guard(async () => setConsents((await adminApi.consents()).items));
    if (which === "rejected") return guard(async () => {
      const res = await adminApi.rejectedNotes();
      setRejected(res.items);
      setRejectedTotal(res.total);
    });
    return Promise.resolve();
  }, [guard, userQuery, phraseQuery, lengthFilter]);

  useEffect(() => {
    if (user?.is_admin) loadTab(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, user?.is_admin]);

  return (
    <DashboardShell title="Admin" active="admin">
      {!user?.is_admin ? (
        <p className="cv-muted">Checking access…</p>
      ) : (
      <>
      {/* Tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => { setTab(t.id); setNotice(null); }}
            className={
              "rounded-full border px-4 py-1.5 text-sm transition " +
              (tab === t.id
                ? "border-emerald-400 bg-[color:var(--jaia-green)] font-semibold cv-heading"
                : "border-[color:var(--line)] bg-white cv-body hover:border-[color:var(--jaia-green)] hover:text-[color:var(--jaia-green)]")
            }
          >
            {t.label}
          </button>
        ))}
        <button onClick={() => loadTab(tab)} className="cv-btn-ghost ml-auto px-4 py-1.5 text-sm">
          Refresh
        </button>
      </div>

      {error && <div className="cv-alert mb-4">{error}</div>}
      {notice && (
        <div className="mb-4 rounded-2xl border border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] px-4 py-3 text-sm cv-body">
          {notice}
        </div>
      )}

      {/* ─── Rejected notes ───────────────────────────────── */}
      {tab === "rejected" && (
        <div className="flex flex-col gap-4">
          <p className="max-w-3xl text-sm cv-body">
            Recordings the automatic checks rejected. Speech recognition often mis-hears Patois, so a
            correct reading can fail the phrase match. Listen to each one and approve it if the speaker
            read the phrase clearly. Approved notes count as accepted and are included in the dataset export.
          </p>
          {rejected.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[color:var(--line)] bg-white p-10 text-center cv-muted">
              <p className="font-semibold cv-heading">No rejected voice notes</p>
            </div>
          ) : (
            <>
              <p className="text-xs cv-muted">
                Showing {rejected.length} of {rejectedTotal}, newest first.
              </p>
              {rejected.map((n) => (
                <div key={n.id} className="flex flex-col gap-3">
                  <VoiceNoteCard note={n} reviewerSignals />
                  <div className="-mt-1 flex justify-end">
                    <button
                      disabled={busy === "approve:" + n.id}
                      onClick={() => guard(async () => {
                        await adminApi.approveNote(n.id);
                        setRejected((rows) => rows.filter((r) => r.id !== n.id));
                        setRejectedTotal((t) => Math.max(0, t - 1));
                        setNotice("Voice note approved and marked accepted.");
                      }, "approve:" + n.id)}
                      className="cv-btn px-5 py-2"
                    >
                      {busy === "approve:" + n.id ? "Approving…" : "Approve"}
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {/* ─── Overview ─────────────────────────────────────── */}
      {tab === "overview" && (
        stats ? (
          <div className="flex flex-col gap-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Contributors" value={stats.users_total}
                    hint={`${stats.users_verified} WhatsApp verified`} />
              <Stat label="With consent" value={stats.users_consented}
                    hint={stats.users_consented < stats.users_verified
                      ? `${stats.users_verified - stats.users_consented} yet to consent` : "all verified users"} />
              <Stat label="Voice notes" value={stats.notes_total}
                    hint={`from ${stats.contributors_with_notes} contributor${stats.contributors_with_notes === 1 ? "" : "s"}`} />
              <Stat label="Audio collected" value={fmtDuration(stats.total_audio_seconds)} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Acceptance rate"
                    value={stats.acceptance_rate === null ? "—" : `${Math.round(stats.acceptance_rate * 100)}%`}
                    hint={stats.acceptance_rate === null ? "nothing resolved yet" : "accepted vs rejected"} />
              <Stat label="Needs review" value={stats.needs_review}
                    hint={stats.reviewers === 0 ? "⚠ no reviewers assigned" : `${stats.reviewers} reviewer(s)`} />
              <Stat label="Phrases" value={stats.phrases_active}
                    hint={`${stats.phrases_total - stats.phrases_active} inactive`} />
              <Stat label="Admins" value={stats.admins} />
            </div>

            <div className="cv-surface p-5">
              <h2 className="text-sm font-semibold cv-heading">Voice notes by status</h2>
              <div className="mt-4 flex flex-col gap-3">
                {stats.notes_by_status.map((s) => {
                  const pct = stats.notes_total ? (s.count / stats.notes_total) * 100 : 0;
                  return (
                    <div key={s.status} className="flex items-center gap-3 text-sm">
                      <span className="w-28 shrink-0 capitalize cv-body">
                        {s.status.replace("_", " ")}
                      </span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-[color:var(--paper-warm)]">
                        <div className="h-full rounded-full bg-gradient-to-r from-[color:var(--jaia-green)] to-[color:var(--jaia-gold)]"
                             style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-10 shrink-0 text-right font-medium cv-heading">{s.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : <p className="cv-muted">Loading…</p>
      )}

      {/* ─── Users ────────────────────────────────────────── */}
      {tab === "users" && (
        <div className="flex flex-col gap-4">
          <form
            onSubmit={(e) => { e.preventDefault(); loadTab("users"); }}
            className="flex gap-2"
          >
            <input
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              placeholder="Search name or email…"
              className="cv-input py-2.5"
            />
            <button type="submit" className="cv-btn px-5 py-2.5">Search</button>
          </form>

          <div className="cv-surface overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-[color:var(--line)] text-left text-xs uppercase tracking-wider cv-eyebrow">
                  <th className="px-5 py-3 font-medium">Contributor</th>
                  <th className="px-3 py-3 font-medium">WhatsApp</th>
                  <th className="px-3 py-3 font-medium">Consent</th>
                  <th className="px-3 py-3 font-medium">Notes</th>
                  <th className="px-3 py-3 font-medium">Reviewer</th>
                  <th className="px-3 py-3 font-medium">Admin</th>
                  <th className="px-5 py-3 font-medium">Data</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-[color:var(--line)] last:border-0">
                    <td className="px-5 py-3">
                      <div className="font-medium cv-heading">{u.first_name} {u.last_name}</div>
                      <div className="text-xs cv-muted">{u.email}</div>
                    </td>
                    <td className="px-3 py-3">
                      {u.whatsapp_verified ? (
                        <span className="text-[color:var(--jaia-green)]">{u.whatsapp_number}</span>
                      ) : (
                        <span className="cv-muted">not verified</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className={
                        "rounded-full border px-2.5 py-0.5 text-xs font-medium " +
                        (u.has_consent
                          ? "border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] text-[color:var(--jaia-green)]"
                          : "border-[color:var(--jaia-gold)]/40 bg-[color:var(--jaia-gold-soft)] text-[#8a5a00]")
                      }>
                        {u.has_consent ? "Given" : "None"}
                      </span>
                    </td>
                    <td className="px-3 py-3 cv-body">{u.note_count}</td>
                    <td className="px-3 py-3">
                      <Toggle
                        label={`Reviewer access for ${u.email}`}
                        checked={u.is_reviewer}
                        disabled={busy === u.id}
                        onChange={(v) => guard(async () => {
                          const updated = await adminApi.setRoles(u.id, { is_reviewer: v });
                          setUsers((list) => list.map((x) => (x.id === u.id ? updated : x)));
                        }, u.id)}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Toggle
                        label={`Admin access for ${u.email}`}
                        checked={u.is_admin}
                        disabled={busy === u.id || u.id === user.id}
                        onChange={(v) => guard(async () => {
                          const updated = await adminApi.setRoles(u.id, { is_admin: v });
                          setUsers((list) => list.map((x) => (x.id === u.id ? updated : x)));
                        }, u.id)}
                      />
                    </td>
                    <td className="px-5 py-3">
                      <button
                        disabled={busy === u.id}
                        onClick={() => {
                          const ok = window.confirm(
                            `Erase all stored recordings for ${u.email}?\n\n` +
                            `This withdraws their consent and permanently deletes ${u.note_count} recording(s) ` +
                            `from storage. The account and consent register are kept so the record stays auditable. ` +
                            `Anything already published in a released dataset cannot be recalled.`
                          );
                          if (!ok) return;
                          guard(async () => {
                            const r = await adminApi.eraseUser(u.id);
                            setNotice(`Erased ${r.notes_deleted} recording(s) and ${r.audio_objects_deleted} audio file(s) for ${u.email}. ${r.note}`);
                            await loadTab("users");
                          }, u.id);
                        }}
                        className="rounded-full border border-rose-300 px-3 py-1 text-xs text-rose-700 transition hover:bg-rose-100 disabled:opacity-40"
                      >
                        Erase
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={7} className="px-5 py-8 text-center cv-muted">No users found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Phrase bank ──────────────────────────────────── */}
      {tab === "phrases" && (
        <div className="flex flex-col gap-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const text = newPhrase.trim();
              if (text.length < 3) return;
              guard(async () => {
                await adminApi.createPhrase({ text });
                setNewPhrase("");
                await loadTab("phrases");
              }, "new-phrase");
            }}
            className="flex gap-2"
          >
            <input
              value={newPhrase}
              onChange={(e) => setNewPhrase(e.target.value)}
              placeholder="Add a phrase for contributors to read aloud…"
              className="cv-input py-2.5"
            />
            <button type="submit" disabled={busy === "new-phrase"} className="cv-btn px-5 py-2.5">
              Add
            </button>
          </form>

          {/* Search + bulk import */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <form
              onSubmit={(e) => { e.preventDefault(); loadTab("phrases"); }}
              className="flex flex-1 gap-2"
            >
              <input
                value={phraseQuery}
                onChange={(e) => setPhraseQuery(e.target.value)}
                placeholder="Search phrases…"
                className="cv-input py-2.5"
                aria-label="Search phrases"
              />
              <button type="submit" className="cv-btn-ghost px-5">Search</button>
              {phraseQuery && (
                <button
                  type="button"
                  onClick={() => { setPhraseQuery(""); setTimeout(() => loadTab("phrases"), 0); }}
                  className="cv-btn-ghost px-4"
                >
                  Clear
                </button>
              )}
            </form>

            <label className="cv-btn cursor-pointer px-5 py-2.5 sm:w-auto">
              {busy === "import" ? "Importing…" : "Import spreadsheet"}
              <input
                type="file"
                accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
                className="sr-only"
                disabled={busy === "import"}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = ""; // allow re-picking the same file
                  if (!file) return;
                  setImportResult(null);
                  guard(async () => {
                    const r = await adminApi.importPhrases(file);
                    setImportResult(r);
                    setPhraseQuery("");
                    setPhrases(await adminApi.phrases());
                  }, "import");
                }}
              />
            </label>
          </div>

          {/* Length bands */}
          {lengths && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setLengthFilter("")}
                className={
                  "rounded-full border px-3 py-1.5 text-xs transition " +
                  (lengthFilter === ""
                    ? "border-emerald-400 bg-[color:var(--jaia-green)] font-semibold cv-heading"
                    : "border-[color:var(--line)] bg-white cv-body hover:bg-white/10")
                }
              >
                All lengths
              </button>
              {lengths.bands.map((b) => (
                <button
                  key={b.band}
                  onClick={() => setLengthFilter(lengthFilter === b.band ? "" : b.band)}
                  title={`${b.min_words}-${b.max_words} words · up to ${b.max_seconds}s`}
                  className={
                    "rounded-full border px-3 py-1.5 text-xs capitalize transition " +
                    (lengthFilter === b.band
                      ? "border-emerald-400 bg-[color:var(--jaia-green)] font-semibold cv-heading"
                      : "border-[color:var(--line)] bg-white cv-body hover:bg-white/10")
                  }
                >
                  {b.band} · {b.count}
                </button>
              ))}
              <span className="text-xs cv-muted">
                at {lengths.words_per_minute} words/min — short &lt;{lengths.bands[0].max_seconds}s,
                medium &lt;{lengths.bands[1].max_seconds}s, long &lt;{lengths.bands[2].max_seconds}s
              </span>
            </div>
          )}

          <p className="text-xs leading-5 cv-muted">
            Spreadsheet format: one phrase per row — column A the phrase, B an optional
            locale (default en-JM), C an optional active flag. A header row is detected and
            skipped. Accepts .xlsx, .xls and .csv; duplicates are reported, not re-added.
          </p>

          {importResult && (
            <div className="rounded-2xl border border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] p-5 text-sm">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-medium cv-body">
                <span>{importResult.added} added</span>
                <span className="cv-body/70">{importResult.duplicates} duplicate</span>
                <span className="cv-body/70">{importResult.skipped} skipped</span>
                <span className="cv-muted">{importResult.rows_read} rows read</span>
                {Object.entries(importResult.by_length)
                  .filter(([, n]) => n > 0)
                  .map(([band, n]) => (
                    <span key={band} className="cv-body/70 capitalize">{n} {band}</span>
                  ))}
                <button
                  onClick={() => setImportResult(null)}
                  className="ml-auto text-xs cv-muted hover:text-white"
                >
                  Dismiss
                </button>
              </div>
              {importResult.details.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-[color:var(--jaia-green)]/20 pt-3 text-xs cv-body/65">
                  {importResult.details.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              )}
            </div>
          )}

          <div className="cv-surface overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-[color:var(--line)] text-left text-xs uppercase tracking-wider cv-eyebrow">
                  <th className="px-5 py-3 font-medium">Phrase</th>
                  <th className="px-3 py-3 font-medium">Length</th>
                  <th className="px-3 py-3 font-medium">Locale</th>
                  <th className="px-3 py-3 font-medium">Recordings</th>
                  <th className="px-3 py-3 font-medium">Active</th>
                  <th className="px-5 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {phrases.map((p) => (
                  <tr key={p.id} className="border-b border-[color:var(--line)] last:border-0">
                    <td className="px-5 py-3 cv-heading">{p.text}</td>
                    <td className="px-3 py-3">
                      <LengthBadge length={p.length} seconds={p.estimated_seconds} />
                      <div className="mt-1 text-xs cv-muted">
                        {p.word_count} words · {p.estimated_seconds}s
                      </div>
                    </td>
                    <td className="px-3 py-3 cv-muted">{p.locale}</td>
                    <td className="px-3 py-3 cv-body">{p.note_count}</td>
                    <td className="px-3 py-3">
                      <Toggle
                        label={`Active state for phrase: ${p.text}`}
                        checked={p.active}
                        disabled={busy === p.id}
                        onChange={(v) => guard(async () => {
                          const updated = await adminApi.updatePhrase(p.id, { active: v });
                          setPhrases((list) => list.map((x) => (x.id === p.id ? updated : x)));
                        }, p.id)}
                      />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        disabled={busy === p.id || p.note_count > 0}
                        title={p.note_count > 0
                          ? "Recordings reference this phrase — deactivate it instead"
                          : "Delete this unused phrase"}
                        onClick={() => guard(async () => {
                          await adminApi.deletePhrase(p.id);
                          await loadTab("phrases");
                        }, p.id)}
                        className="rounded-full border border-rose-300 px-3 py-1 text-xs text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {phrases.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-8 text-center cv-muted">
                    {phraseQuery ? `No phrases match “${phraseQuery}”.` : "No phrases yet."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Consent ──────────────────────────────────────── */}
      {tab === "consent" && (
        <div className="flex flex-col gap-4">
          <div className="cv-surface p-5">
            <h2 className="text-sm font-semibold cv-heading">Consent register</h2>
            <p className="mt-2 text-sm leading-6 cv-body">
              The Privacy Notice commits to keeping a record of each contributor&apos;s explicit
              consent so it can be produced for the Office of the Information Commissioner on
              request. Records are append-only — withdrawing marks a row rather than deleting it.
            </p>
            <button
              onClick={() => guard(async () =>
                adminApi.download("/admin/consents/export.csv", "carib-voices-consent-register.csv"),
              "consent-csv")}
              disabled={busy === "consent-csv"}
              className="cv-btn mt-4 px-5 py-2.5"
            >
              Download consent register (CSV)
            </button>
          </div>

          <div className="cv-surface overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-[color:var(--line)] text-left text-xs uppercase tracking-wider cv-eyebrow">
                  <th className="px-5 py-3 font-medium">Contributor</th>
                  <th className="px-3 py-3 font-medium">Channel</th>
                  <th className="px-3 py-3 font-medium">Evidence</th>
                  <th className="px-3 py-3 font-medium">Policy</th>
                  <th className="px-3 py-3 font-medium">Given</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {consents.map((c) => (
                  <tr key={c.id} className="border-b border-[color:var(--line)] last:border-0">
                    <td className="px-5 py-3">
                      <div className="font-medium cv-heading">{c.user_name}</div>
                      <div className="text-xs cv-muted">{c.phone || c.user_email}</div>
                    </td>
                    <td className="px-3 py-3 capitalize cv-body">{c.channel}</td>
                    <td className="px-3 py-3 cv-muted">{c.evidence || "—"}</td>
                    <td className="px-3 py-3 cv-muted">{c.policy_version}</td>
                    <td className="px-3 py-3 cv-muted">{formatDate(c.consented_at)}</td>
                    <td className="px-5 py-3">
                      <span className={
                        "rounded-full border px-2.5 py-0.5 text-xs font-medium " +
                        (c.is_active
                          ? "border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] text-[color:var(--jaia-green)]"
                          : "border-[color:var(--line)] bg-white/10 cv-body")
                      }>
                        {c.is_active ? "Active" : `Withdrawn ${formatDate(c.withdrawn_at)}`}
                      </span>
                    </td>
                  </tr>
                ))}
                {consents.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center cv-muted">
                      No consent records yet. Contributors consent by replying{" "}
                      <span className="font-medium text-[color:var(--jaia-green)]">I AGREE</span> to the agent on WhatsApp.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Export ───────────────────────────────────────── */}
      {tab === "export" && (
        <div className="flex flex-col gap-4">
          <div className="cv-surface p-6">
            <h2 className="text-base font-semibold cv-heading">Open dataset export</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 cv-body">
              De-identified export of the collected speech. Contributors appear as an opaque{" "}
              <code className="rounded bg-white/10 px-1 text-[color:var(--jaia-green)]">speaker_id</code>, age is
              reduced to a band, and no name, email, phone number or internal user id is included —
              matching what the Privacy Notice says is published.
            </p>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <button
                onClick={() => guard(async () =>
                  adminApi.download("/admin/export/dataset?fmt=jsonl&status=accepted",
                                    "carib-voices-dataset.jsonl"), "ds-jsonl")}
                disabled={busy === "ds-jsonl"}
                className="cv-btn py-3"
              >
                Accepted only (JSONL)
              </button>
              <button
                onClick={() => guard(async () =>
                  adminApi.download("/admin/export/dataset?fmt=csv&status=accepted",
                                    "carib-voices-dataset.csv"), "ds-csv")}
                disabled={busy === "ds-csv"}
                className="cv-btn-ghost py-3"
              >
                Accepted only (CSV)
              </button>
              <button
                onClick={() => guard(async () =>
                  adminApi.download("/admin/export/dataset?fmt=jsonl&status=all",
                                    "carib-voices-dataset-all.jsonl"), "ds-all")}
                disabled={busy === "ds-all"}
                className="cv-btn-ghost py-3"
              >
                All statuses (JSONL)
              </button>
              <button
                onClick={() => guard(async () =>
                  adminApi.download("/admin/export/dataset?fmt=jsonl&status=all&include_internal=true",
                                    "carib-voices-dataset-internal.jsonl"), "ds-int")}
                disabled={busy === "ds-int"}
                className="cv-btn-ghost py-3"
              >
                Internal (includes S3 keys)
              </button>
            </div>

            <p className="mt-5 rounded-xl border border-[color:var(--jaia-gold)]/40 bg-[color:var(--jaia-gold-soft)] px-4 py-3 text-xs leading-5 text-[#8a5a00]">
              The <strong>Internal</strong> export includes raw S3 object keys, which embed the
              internal user id. Use it for pipeline work — do not publish that file.
            </p>
          </div>
        </div>
      )}
      </>
      )}
    </DashboardShell>
  );
}
