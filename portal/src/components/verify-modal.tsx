"use client";

import { useEffect, useState } from "react";
import { Field, SubmitButton } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { authApi, ApiError } from "@/lib/api";
import { normalizeJamaican, formatPhoneInput, InvalidJamaicanNumberError } from "@/lib/phone";
import type { UserOut } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  open: boolean;
  user: UserOut | null;
  onClose: () => void;
  onVerified: (user: UserOut, agentUrl: string) => void;
}

type Step = "phone" | "code" | "done";

const RESEND_COOLDOWN_S = 60;

/** Pull the remaining wait out of the backend's "Please wait 42s ..." cooldown message. */
function cooldownFromError(e: unknown): number | null {
  if (!(e instanceof ApiError) || e.status !== 429) return null;
  const m = /wait (\d+)s/.exec(e.message);
  return m ? Math.max(1, Number(m[1])) : null;
}

function formatCountdown(s: number): string {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function VerifyWhatsappModal({ open, user, onClose, onVerified }: Props) {
  const [step, setStep] = useState<Step>("phone");
  const [phoneInput, setPhoneInput] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [agentUrl, setAgentUrl] = useState<string | null>(null);
  // Track an absolute deadline rather than decrementing a counter, so the
  // countdown stays correct even when the tab is throttled in the background.
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const cooldown = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  const startCooldown = (seconds: number) => {
    const t = Date.now();
    setNow(t);
    setCooldownUntil(t + seconds * 1000);
  };

  useEffect(() => {
    if (open && user?.whatsapp_number) setPhoneInput(formatPhoneInput(user.whatsapp_number));
    if (open) { setStep("phone"); setError(null); setCode(""); }
  }, [open, user]);

  useEffect(() => {
    if (cooldownUntil <= Date.now()) return;
    const t = setInterval(() => {
      const n = Date.now();
      setNow(n);
      if (n >= cooldownUntil) clearInterval(t);
    }, 250);
    return () => clearInterval(t);
  }, [cooldownUntil]);

  if (!open) return null;

  const sendOtp = async () => {
    setError(null);
    let normalized: string;
    try {
      normalized = normalizeJamaican("+1" + phoneInput.replace(/\D+/g, ""));
    } catch (e) {
      setError(e instanceof InvalidJamaicanNumberError ? e.message : "Invalid number");
      return;
    }
    setLoading(true);
    try {
      await authApi.requestOtp(normalized);
      setPhone(normalized);
      setStep("code");
      startCooldown(RESEND_COOLDOWN_S);
    } catch (e) {
      const wait = cooldownFromError(e);
      if (wait) {
        // A code for this number is still live — go to the code step and count down.
        setPhone(normalized);
        setStep("code");
        startCooldown(wait);
        return;
      }
      setError(e instanceof ApiError ? e.message : "Could not send code");
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    if (cooldown > 0) return;
    setError(null);
    setLoading(true);
    try {
      await authApi.resendOtp(phone);
      startCooldown(RESEND_COOLDOWN_S);
    } catch (e) {
      const wait = cooldownFromError(e);
      if (wait) startCooldown(wait);
      else setError(e instanceof ApiError ? e.message : "Could not resend");
    } finally {
      setLoading(false);
    }
  };

  const verify = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.checkOtp(phone, code);
      setAgentUrl(res.agent_url);
      setStep("done");
      // Refresh the user from the backend so whatsapp_verified flips true.
      const me = await authApi.me();
      onVerified(me, res.agent_url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--ink)]/40 p-4 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => { if (!loading) onClose(); }}
      >
        <motion.div
          className="cv-surface relative w-full max-w-md rounded-[1.75rem] p-6 shadow-xl shadow-black/10 md:p-8"
          initial={{ scale: 0.95, y: 10 }}
          animate={{ scale: 1, y: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            aria-label="Close"
            disabled={loading}
            onClick={() => onClose()}
            className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full cv-muted transition hover:bg-[color:var(--paper-warm)] hover:text-[color:var(--ink)] disabled:opacity-40"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
          {step === "phone" && (
            <>
              <h2 className="mb-1 text-xl font-bold cv-heading">Verify your WhatsApp number</h2>
              <p className="mb-5 text-sm cv-body">
                Jamaican numbers only (area code 876 or 658). We&apos;ll text a 6-digit code to confirm it.
              </p>
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label htmlFor="phone" className="text-sm font-medium cv-body">
                    WhatsApp number
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-sm font-medium text-[color:var(--ink)]">
                      +1
                    </span>
                    <input
                      id="phone"
                      name="phone"
                      type="tel"
                      inputMode="tel"
                      autoComplete="tel-national"
                      placeholder="(876) 555-1234"
                      maxLength={14}
                      value={phoneInput}
                      onChange={(e) => setPhoneInput(formatPhoneInput(e.target.value))}
                      onKeyDown={(e) => { if (e.key === "Enter") sendOtp(); }}
                      aria-invalid={error ? true : undefined}
                      className={cn("cv-input pl-11", error && "cv-input-error")}
                    />
                  </div>
                  {error && <span className="pl-2 text-xs text-rose-600">{error}</span>}
                </div>
                <SubmitButton type="button" loading={loading} onClick={() => sendOtp()}>
                  Send code
                </SubmitButton>
              </div>
            </>
          )}

          {step === "code" && (
            <>
              <h2 className="mb-1 text-xl font-bold cv-heading">Enter your code</h2>
              <p className="mb-5 text-sm cv-body">
                We sent a 6-digit code to <span className="font-medium cv-heading">{phone}</span>.
                It expires in 15 minutes.
              </p>
              <div className="flex flex-col gap-4">
                <Field
                  label="6-digit code"
                  name="code"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="••••••"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  error={error ?? undefined}
                />
                <SubmitButton type="button" loading={loading} onClick={() => verify()}>
                  Verify
                </SubmitButton>
                <button
                  type="button"
                  onClick={resend}
                  disabled={cooldown > 0 || loading}
                  aria-live="polite"
                  className="w-full rounded-full border border-[color:var(--jaia-green)] px-6 py-3 text-sm font-medium text-[color:var(--jaia-green)] transition hover:bg-[color:var(--jaia-green)]/10 disabled:cursor-not-allowed disabled:border-[color:var(--line)] disabled:opacity-60 disabled:hover:bg-transparent"
                >
                  {cooldown > 0 ? (
                    <>Resend code in <span className="tabular-nums">{formatCountdown(cooldown)}</span></>
                  ) : (
                    "Resend code"
                  )}
                </button>
                <div className="flex justify-end text-xs">
                  <button type="button" onClick={() => { setStep("phone"); setError(null); }} className="text-[color:var(--jaia-green)] transition hover:text-[color:var(--jaia-green)]">
                    Change number
                  </button>
                </div>
              </div>
            </>
          )}

          {step === "done" && (
            <div className="text-center py-2">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[color:var(--jaia-green-soft)] text-[color:var(--jaia-green)]">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </div>
              <h2 className="mb-1 text-xl font-bold cv-heading">Number verified!</h2>
              <p className="mb-5 text-sm cv-body">
                You can now submit voice notes. Tap below to open WhatsApp and message the agent.
              </p>
              {agentUrl && (
                <a href={agentUrl} target="_blank" rel="noopener noreferrer"
                  className="cv-btn w-full">
                  Message the Agent →
                </a>
              )}
              <button type="button" onClick={onClose} className="mt-3 text-sm cv-muted transition hover:text-[color:var(--ink)]">
                Continue to dashboard
              </button>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
