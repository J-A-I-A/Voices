"use client";

import { useEffect, useRef, useState } from "react";

const GSI_SRC = "https://accounts.google.com/gsi/client";
const SCRIPT_ID = "google-gsi-script";

const GoogleIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" {...props}>
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.16v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.16C1.43 8.55 1 10.22 1 12s.43 3.45 1.16 4.93l3.68-2.84z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.16 7.07l3.68 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
);

function gsi(): any {
  return typeof window === "undefined" ? undefined : (window as any).google?.accounts?.id;
}

/**
 * Loads Google's GSI library exactly once per page and resolves only when
 * `window.google.accounts.id` is actually callable.
 *
 * The previous implementation treated "a <script> tag with our id exists" as
 * "the library is ready". Under React StrictMode (reactStrictMode: true) the
 * effect mounts twice: the first mount appends the tag, and the second mount
 * finds it already present and flips ready=true while the script is still in
 * flight. The render effect then ran against an undefined `window.google`,
 * where optional chaining swallowed the miss, and nothing retried — so the
 * button only appeared once some later re-render (e.g. a click) happened to
 * run the effect again. Sharing one promise keyed on the real global removes
 * that race.
 */
let gsiLoader: Promise<void> | null = null;

function loadGsi(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (gsi()) return Promise.resolve();
  if (gsiLoader) return gsiLoader;

  gsiLoader = new Promise<void>((resolve, reject) => {
    const done = () => (gsi() ? resolve() : reject(new Error("GSI loaded without accounts.id")));
    const fail = () => {
      gsiLoader = null; // allow a retry on a later mount
      reject(new Error("Failed to load Google Identity Services"));
    };

    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      // Tag is present but may still be downloading — wait for it either way.
      existing.addEventListener("load", done);
      existing.addEventListener("error", fail);
      return;
    }

    const s = document.createElement("script");
    s.id = SCRIPT_ID;
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.addEventListener("load", done);
    s.addEventListener("error", fail);
    document.body.appendChild(s);
  });

  return gsiLoader;
}

/** Decode a JWT payload. Uses atob (browser-native) rather than Node's Buffer. */
function decodeJwt(token: string): Record<string, string> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((ch) => "%" + ch.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

type Status = "loading" | "ready" | "error";

export function GoogleSignInButton({
  label = "Continue with Google",
  onIdToken,
}: {
  label?: string;
  onIdToken: (idToken: string, claims: { given_name?: string; family_name?: string; email?: string }) => void;
}) {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const btnRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");

  // Keep the latest callback in a ref so its changing identity never
  // re-triggers (or gates) the render effect.
  const onIdTokenRef = useRef(onIdToken);
  useEffect(() => {
    onIdTokenRef.current = onIdToken;
  });

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;

    loadGsi()
      .then(() => {
        if (cancelled) return;
        const id = gsi();
        const host = btnRef.current;
        if (!id || !host) {
          setStatus("error");
          return;
        }

        id.initialize({
          client_id: clientId,
          callback: (resp: { credential?: string }) => {
            if (!resp.credential) return;
            const claims = decodeJwt(resp.credential) || {};
            onIdTokenRef.current(resp.credential, {
              given_name: claims.given_name,
              family_name: claims.family_name,
              email: claims.email,
            });
          },
        });

        // StrictMode runs this twice; clear so we never stack two buttons.
        host.innerHTML = "";
        id.renderButton(host, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "pill",
          // Google caps width at 400; match the card instead of overflowing it.
          width: Math.max(200, Math.min(host.offsetWidth || 360, 400)),
        });
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (!clientId) {
    return (
      <FallbackButton title="NEXT_PUBLIC_GOOGLE_CLIENT_ID not set">
        Google not configured
      </FallbackButton>
    );
  }

  if (status === "error") {
    return (
      <FallbackButton title="Google Identity Services could not be reached">
        Google sign-in unavailable
      </FallbackButton>
    );
  }

  return (
    <div className="relative min-h-[44px]">
      {/* Reserve the row so the layout (and the "or" divider below it) never
          shifts or strands while GSI loads. */}
      {status === "loading" && (
        <div
          aria-hidden="true"
          className="absolute inset-0 flex animate-pulse items-center justify-center rounded-full border border-[color:var(--line)] bg-[color:var(--paper-warm)] text-sm cv-muted"
        >
          <GoogleIcon className="mr-3 text-lg opacity-50" /> {label}
        </div>
      )}
      <div ref={btnRef} className="flex justify-center" />
    </div>
  );
}

function FallbackButton({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <button
      type="button"
      disabled
      title={title}
      className="flex w-full cursor-not-allowed items-center justify-center gap-3 rounded-full border border-[color:var(--line)] bg-white px-6 py-3 text-sm font-medium cv-muted"
    >
      <GoogleIcon className="text-lg" /> {children}
    </button>
  );
}

export { GoogleIcon };
