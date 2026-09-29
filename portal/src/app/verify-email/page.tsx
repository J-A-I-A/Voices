"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Logo } from "@/components/logo";
import { authApi, ApiError, getToken } from "@/lib/api";
import { useAuth } from "@/lib/store";

type State = { kind: "checking" } | { kind: "done" } | { kind: "error"; message: string };

function VerifyEmail() {
  const token = useSearchParams().get("token");
  const { user, setUser } = useAuth();
  const [state, setState] = useState<State>({ kind: "checking" });
  // StrictMode mounts effects twice; confirm only once.
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    if (!token) {
      setState({ kind: "error", message: "This link is missing its confirmation code." });
      return;
    }
    authApi
      .verifyEmail(token)
      .then((verified) => {
        // Refresh the signed-in session if it's the same account.
        if (user?.id === verified.id) setUser(verified);
        setState({ kind: "done" });
      })
      .catch((e) =>
        setState({ kind: "error", message: e instanceof ApiError ? e.message : "Could not confirm your email." })
      );
  }, [token, user, setUser]);

  const signedIn = !!getToken();

  return (
    <div className="cv-surface w-full max-w-md rounded-[1.75rem] p-8 text-center shadow-xl shadow-black/5">
      {state.kind === "checking" && (
        <>
          <h1 className="mb-2 text-2xl font-bold cv-heading">Confirming your email…</h1>
          <p className="text-sm cv-body">This only takes a moment.</p>
        </>
      )}

      {state.kind === "done" && (
        <>
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[color:var(--jaia-green-soft)] text-[color:var(--jaia-green)]">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <h1 className="mb-2 text-2xl font-bold cv-heading">Email confirmed</h1>
          <p className="mb-6 text-sm cv-body">
            Next, verify your WhatsApp number so you can start sending voice notes.
          </p>
          <a href={signedIn ? "/dashboard" : "/signin"} className="cv-btn w-full px-6 py-3.5">
            {signedIn ? "Go to dashboard" : "Sign in"}
          </a>
        </>
      )}

      {state.kind === "error" && (
        <>
          <h1 className="mb-2 text-2xl font-bold cv-heading">Link not valid</h1>
          <p className="mb-6 text-sm cv-body">{state.message}</p>
          <a href={signedIn ? "/dashboard" : "/signin"} className="cv-btn w-full px-6 py-3.5">
            {signedIn ? "Back to dashboard" : "Sign in"}
          </a>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="cv-canvas relative flex min-h-screen flex-col">
      <div className="cv-grid absolute inset-0" aria-hidden="true" />
      <div className="relative z-10 p-6 md:p-10">
        <Logo height={46} variant="flat" />
      </div>
      <div className="relative z-10 flex flex-1 items-start justify-center px-4 pt-4 md:pt-12">
        <Suspense fallback={null}>
          <VerifyEmail />
        </Suspense>
      </div>
    </div>
  );
}
