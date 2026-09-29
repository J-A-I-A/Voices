"use client";

import { useEffect, useState } from "react";
import { authApi, ApiError } from "@/lib/api";

const RESEND_COOLDOWN_S = 60;

/** Pull the remaining wait out of the backend's "Please wait 60s ..." message. */
function cooldownFromError(e: unknown): number | null {
  if (!(e instanceof ApiError) || e.status !== 429) return null;
  const m = /wait (\d+)s/.exec(e.message);
  return m ? Math.max(1, Number(m[1])) : null;
}

export function EmailVerifyBanner({ email }: { email: string }) {
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [sending, setSending] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cooldown = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const startCooldown = (seconds: number) => {
    const t = Date.now();
    setNow(t);
    setCooldownUntil(t + seconds * 1000);
  };

  useEffect(() => {
    if (cooldownUntil <= Date.now()) return;
    const t = setInterval(() => {
      const n = Date.now();
      setNow(n);
      if (n >= cooldownUntil) clearInterval(t);
    }, 250);
    return () => clearInterval(t);
  }, [cooldownUntil]);

  const resend = async () => {
    setSending(true);
    setError(null);
    setNote(null);
    try {
      const res = await authApi.resendVerificationEmail();
      if (res.status === "already_verified") {
        // Confirmed in another tab or browser — reload to pick up the new state.
        window.location.reload();
        return;
      }
      setNote("Sent — check your inbox (and spam folder).");
      startCooldown(RESEND_COOLDOWN_S);
    } catch (e) {
      const wait = cooldownFromError(e);
      if (wait) startCooldown(wait);
      else setError(e instanceof ApiError ? e.message : "Could not send the email.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mb-6 rounded-2xl border border-[color:var(--jaia-gold)]/40 bg-[color:var(--jaia-gold-soft)] p-4 text-sm text-[#6d4700]">
      <p className="font-semibold text-[#5a3a00]">Confirm your email address to continue.</p>
      <p className="mt-1">
        We sent a link to <span className="font-semibold">{email}</span>. Open it to confirm your email, then verify your WhatsApp number.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={resend}
          disabled={sending || cooldown > 0}
          aria-live="polite"
          className="rounded-full bg-[color:var(--jaia-gold)] px-3.5 py-1.5 text-xs font-semibold text-[#3d2800] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:brightness-100"
        >
          {sending ? "Sending…" : cooldown > 0 ? (
            <>Resend email in <span className="tabular-nums">{Math.floor(cooldown / 60)}:{String(cooldown % 60).padStart(2, "0")}</span></>
          ) : "Resend email"}
        </button>
        {note && <span className="text-xs">{note}</span>}
        {error && <span className="text-xs text-rose-700">{error}</span>}
      </div>
    </div>
  );
}
