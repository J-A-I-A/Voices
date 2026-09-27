"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { VerifyWhatsappModal } from "@/components/verify-modal";
import { Field } from "@/components/ui/field";
import { useAuth } from "@/lib/store";
import { profileApi, setToken, ApiError } from "@/lib/api";
import type { ConsentStatus } from "@/lib/types";
import { formatDate } from "@/lib/utils";

function Section({
  title, description, children, tone = "default",
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  tone?: "default" | "danger";
}) {
  return (
    <section
      className={
        tone === "danger"
          ? "rounded-2xl border border-rose-200 bg-rose-50 p-6 backdrop-blur-sm"
          : "cv-surface p-6"
      }
    >
      <h2 className={tone === "danger" ? "text-base font-bold text-rose-700" : "text-base font-semibold cv-heading"}>
        {title}
      </h2>
      {description && (
        <p className="mt-2 max-w-2xl text-sm leading-6 cv-body">{description}</p>
      )}
      <div className="mt-5">{children}</div>
    </section>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, setUser, logout } = useAuth();

  const [form, setForm] = useState({ first_name: "", last_name: "", date_of_birth: "" });
  const [consent, setConsent] = useState<ConsentStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showVerify, setShowVerify] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState("");

  useEffect(() => {
    if (user) {
      setForm({
        first_name: user.first_name || "",
        last_name: user.last_name || "",
        date_of_birth: user.date_of_birth || "",
      });
    }
  }, [user]);

  const loadConsent = useCallback(async () => {
    try {
      setConsent(await profileApi.consent());
    } catch {
      setConsent(null);
    }
  }, []);

  useEffect(() => {
    if (user) loadConsent();
  }, [user, loadConsent]);

  const run = async (key: string, fn: () => Promise<void>) => {
    setError(null);
    setNotice(null);
    setBusy(key);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  };

  const dirty =
    !!user &&
    (form.first_name !== user.first_name ||
      form.last_name !== user.last_name ||
      form.date_of_birth !== (user.date_of_birth || ""));

  return (
    <DashboardShell title="My profile" active="profile">
      {!user ? (
        <p className="cv-muted">Loading…</p>
      ) : (
        <div className="flex max-w-3xl flex-col gap-5">
          {error && <div className="cv-alert">{error}</div>}
          {notice && (
            <div className="rounded-2xl border border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] px-4 py-3 text-sm cv-body">
              {notice}
            </div>
          )}

          {/* ─── Details ─────────────────────────────────── */}
          <Section
            title="Your details"
            description="Correct your name or date of birth. Contributors must be 18 or older."
          >
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run("details", async () => {
                  const updated = await profileApi.update({
                    first_name: form.first_name.trim(),
                    last_name: form.last_name.trim(),
                    date_of_birth: form.date_of_birth || undefined,
                  });
                  setUser(updated);
                  setNotice("Your details have been updated.");
                });
              }}
              className="flex flex-col gap-4"
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="First name"
                  name="first_name"
                  value={form.first_name}
                  onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                />
                <Field
                  label="Last name"
                  name="last_name"
                  value={form.last_name}
                  onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                />
              </div>
              <Field
                label="Date of birth"
                name="date_of_birth"
                type="date"
                max={new Date().toISOString().slice(0, 10)}
                value={form.date_of_birth}
                onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))}
              />
              <div className="flex items-center gap-3">
                <button type="submit" disabled={!dirty || busy === "details"} className="cv-btn px-6 py-2.5">
                  {busy === "details" ? "Saving…" : "Save changes"}
                </button>
                <span className="text-xs cv-muted">
                  {user.email} · signed in with {user.auth_provider === "google" ? "Google" : "email"}
                </span>
              </div>
            </form>
          </Section>

          {/* ─── WhatsApp ────────────────────────────────── */}
          <Section
            title="WhatsApp number"
            description="The number the agent talks to. Changing it sends a 6-digit code to the new number; removing it stops all collection but keeps recordings you have already contributed."
          >
            {user.whatsapp_verified && user.whatsapp_number ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] px-3 py-1 text-sm font-medium text-[color:var(--jaia-green)]">
                  {user.whatsapp_number}
                </span>
                <button onClick={() => setShowVerify(true)} className="cv-btn-ghost">
                  Change number
                </button>
                <button
                  disabled={busy === "unlink"}
                  onClick={() => {
                    if (!window.confirm(
                      "Remove your WhatsApp number?\n\nYou will not be able to submit new voice notes until you verify a number again. " +
                      "Recordings you have already contributed are kept."
                    )) return;
                    run("unlink", async () => {
                      const updated = await profileApi.unlinkWhatsapp();
                      setUser(updated);
                      setNotice("Your WhatsApp number has been removed.");
                    });
                  }}
                  className="rounded-full border border-rose-300 px-4 py-2 text-sm text-rose-700 transition hover:bg-rose-100 disabled:opacity-40"
                >
                  Remove number
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm cv-muted">No number linked.</span>
                <button onClick={() => setShowVerify(true)} className="cv-btn px-5 py-2.5">
                  Verify a number
                </button>
              </div>
            )}
          </Section>

          {/* ─── Consent ─────────────────────────────────── */}
          <Section
            title="Consent"
            description="You consented before your first recording. You can withdraw at any time — we will stop collecting, though recordings already published in the open dataset in de-identified form cannot be recalled."
          >
            {consent?.has_consent ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-[color:var(--jaia-green)]/30 bg-[color:var(--jaia-green-soft)] px-3 py-1 text-sm font-medium text-[color:var(--jaia-green)]">
                  Given {formatDate(consent.consented_at)}
                </span>
                <span className="text-xs cv-muted">
                  via {consent.channel} · notice {consent.policy_version}
                </span>
                <button
                  disabled={busy === "withdraw"}
                  onClick={() => {
                    if (!window.confirm(
                      "Withdraw your consent?\n\nWe will stop collecting new recordings from you. " +
                      "Recordings already published in the open dataset cannot be recalled.\n\n" +
                      "You can consent again at any time by replying I AGREE to the agent on WhatsApp."
                    )) return;
                    run("withdraw", async () => {
                      setConsent(await profileApi.withdrawConsent());
                      setNotice("Your consent has been withdrawn. We will not collect any new recordings.");
                    });
                  }}
                  className="rounded-full border border-rose-300 px-4 py-2 text-sm text-rose-700 transition hover:bg-rose-100 disabled:opacity-40"
                >
                  Withdraw consent
                </button>
              </div>
            ) : (
              <p className="text-sm cv-body">
                No consent on file. Reply{" "}
                <span className="font-medium text-[color:var(--jaia-green)]">I AGREE</span> to the agent on
                WhatsApp to start contributing.
              </p>
            )}
            <p className="mt-4 text-xs cv-muted">
              Read the{" "}
              <a href="/privacy" className="cv-link">Privacy Notice</a>, or contact our Data
              Protection Officer at{" "}
              <a href="mailto:admin@jaia.org" className="cv-link">admin@jaia.org</a>.
            </p>
          </Section>

          {/* ─── Delete ──────────────────────────────────── */}
          <Section
            tone="danger"
            title="Delete your profile"
            description="This permanently deletes your recordings and personal details, withdraws your consent, and signs you out. An anonymous record that consent was given and withdrawn is kept, because we must be able to evidence it to the Office of the Information Commissioner. Recordings already published in a released open dataset cannot be recalled."
          >
            <div className="flex flex-col gap-3">
              <label htmlFor="confirm-delete" className="text-sm text-rose-700">
                Type <span className="font-semibold text-rose-700">DELETE</span> to confirm.
              </label>
              <input
                id="confirm-delete"
                value={confirmDelete}
                onChange={(e) => setConfirmDelete(e.target.value)}
                placeholder="DELETE"
                className="cv-input max-w-xs border-rose-300 py-2.5 focus:border-rose-400 focus:ring-rose-400/60"
              />
              <button
                disabled={confirmDelete !== "DELETE" || busy === "delete"}
                onClick={() => {
                  if (!window.confirm(
                    "Delete your profile permanently?\n\nThis cannot be undone."
                  )) return;
                  run("delete", async () => {
                    const r = await profileApi.deleteProfile();
                    // Token is dead server-side now; clear local state too.
                    setToken(null);
                    logout();
                    window.alert(
                      `Your profile has been deleted.\n\n` +
                      `${r.notes_deleted} recording(s) removed.\n\n${r.note}`
                    );
                    router.push("/");
                  });
                }}
                className="cv-btn-danger w-fit px-6 py-2.5 disabled:cursor-not-allowed"
              >
                {busy === "delete" ? "Deleting…" : "Delete my profile"}
              </button>
            </div>
          </Section>
        </div>
      )}

      <VerifyWhatsappModal
        open={showVerify}
        user={user}
        onClose={() => setShowVerify(false)}
        onVerified={(me) => {
          setUser(me);
          setShowVerify(false);
          setNotice("Your WhatsApp number has been verified.");
        }}
      />
    </DashboardShell>
  );
}
