"use client";

import { useEffect, useState } from "react";
import { Field, SubmitButton } from "@/components/ui/field";
import { authApi, ApiError } from "@/lib/api";
import { normalizeJamaican, InvalidJamaicanNumberError } from "@/lib/phone";
import type { UserOut } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  open: boolean;
  user: UserOut | null;
  onClose: () => void;
  onVerified: (user: UserOut, agentUrl: string) => void;
}

type Step = "phone" | "code" | "done";

export function VerifyWhatsappModal({ open, user, onClose, onVerified }: Props) {
  const [step, setStep] = useState<Step>("phone");
  const [phoneInput, setPhoneInput] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [agentUrl, setAgentUrl] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (open && user?.whatsapp_number) setPhoneInput(user.whatsapp_number);
    if (open) { setStep("phone"); setError(null); setCode(""); }
  }, [open, user]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  if (!open) return null;

  const sendOtp = async () => {
    setError(null);
    let normalized: string;
    try {
      normalized = normalizeJamaican(phoneInput);
    } catch (e) {
      setError(e instanceof InvalidJamaicanNumberError ? e.message : "Invalid number");
      return;
    }
    setLoading(true);
    try {
      await authApi.requestOtp(normalized);
      setPhone(normalized);
      setStep("code");
      setCooldown(60);
    } catch (e) {
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
      setCooldown(60);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not resend");
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
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => { if (!loading) onClose(); }}
      >
        <motion.div
          className="relative w-full max-w-md rounded-3xl bg-white p-6 md:p-8 shadow-xl"
          initial={{ scale: 0.95, y: 10 }}
          animate={{ scale: 1, y: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            aria-label="Close"
            disabled={loading}
            onClick={() => onClose()}
            className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 disabled:opacity-40"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
          {step === "phone" && (
            <>
              <h2 className="text-xl font-semibold mb-1">Verify your WhatsApp number</h2>
              <p className="text-sm text-neutral-500 mb-5">
                Jamaican numbers only (area code 876 or 658). We&apos;ll text a 6-digit code to confirm it.
              </p>
              <div className="flex flex-col gap-4">
                <Field
                  label="WhatsApp number"
                  name="phone"
                  inputMode="tel"
                  placeholder="e.g. 876 555 1234"
                  value={phoneInput}
                  onChange={(e) => setPhoneInput(e.target.value)}
                  error={error ?? undefined}
                />
                <SubmitButton type="button" loading={loading} onClick={() => sendOtp()}>
                  Send code
                </SubmitButton>
              </div>
            </>
          )}

          {step === "code" && (
            <>
              <h2 className="text-xl font-semibold mb-1">Enter your code</h2>
              <p className="text-sm text-neutral-500 mb-5">
                We sent a 6-digit code to <span className="font-medium text-neutral-700">{phone}</span>.
                It expires in 10 minutes.
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
                <div className="flex justify-between text-xs text-neutral-500">
                  <button type="button" onClick={resend} disabled={cooldown > 0 || loading} className="text-neutral-700 hover:underline disabled:text-neutral-300 disabled:no-underline">
                    {cooldown > 0 ? "Resend in " + cooldown + "s" : "Resend code"}
                  </button>
                  <button type="button" onClick={() => { setStep("phone"); setError(null); }} className="text-neutral-700 hover:underline">
                    Change number
                  </button>
                </div>
              </div>
            </>
          )}

          {step === "done" && (
            <div className="text-center py-2">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </div>
              <h2 className="text-xl font-semibold mb-1">Number verified!</h2>
              <p className="text-sm text-neutral-500 mb-5">
                You can now submit voice notes. Tap below to open WhatsApp and message the agent.
              </p>
              {agentUrl && (
                <a href={agentUrl} target="_blank" rel="noopener noreferrer"
                  className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-emerald-600 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-700">
                  Message the Agent →
                </a>
              )}
              <button type="button" onClick={onClose} className="mt-3 text-sm text-neutral-500 hover:underline">
                Continue to dashboard
              </button>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
