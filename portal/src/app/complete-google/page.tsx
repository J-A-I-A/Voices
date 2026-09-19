"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthShell, { MotionItem } from "@/components/watermelon-ui/auth-07";
import { Field, SubmitButton } from "@/components/ui/field";
import { authApi, ApiError, setToken } from "@/lib/api";
import { isAtLeast18 } from "@/lib/phone";
import { useAuth } from "@/lib/store";

/**
 * Google completion step. Google sign-in does NOT provide date of birth, so
 * we always collect it here (per spec). First/last name are pre-filled from
 * the Google profile claims when present (given_name / family_name), and the
 * user can confirm them. Only non-empty name fields are persisted server-side.
 */
export default function CompleteGooglePage() {
  const router = useRouter();
  const setUser = useAuth((s) => s.setUser);
  const [idToken, setIdToken] = useState<string>("");
  const [given, setGiven] = useState("");
  const [family, setFamily] = useState("");
  const [dob, setDob] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = sessionStorage.getItem("cv_google_id_token") || "";
    const g = sessionStorage.getItem("cv_google_given") || "";
    const f = sessionStorage.getItem("cv_google_family") || "";
    if (!t) {
      router.replace("/signin");
      return;
    }
    setIdToken(t);
    setGiven(g);
    setFamily(f);
  }, [router]);

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(null);
    if (!dob) { setError("Please enter your date of birth."); return; }
    if (!isAtLeast18(dob)) { setError("You must be 18 or older to register."); return; }
    setLoading(true);
    try {
      const res = await authApi.google({
        id_token: idToken,
        date_of_birth: dob,
        first_name: given.trim() || undefined,
        last_name: family.trim() || undefined,
      });
      setToken(res.access_token);
      setUser(res.user);
      sessionStorage.removeItem("cv_google_id_token");
      sessionStorage.removeItem("cv_google_given");
      sessionStorage.removeItem("cv_google_family");
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Google completion failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Finish your account"
      subtitle="Confirm your details and enter your date of birth."
      divider={false}
      footer={<button onClick={() => router.push("/signin")} className="text-neutral-700 hover:underline">← Back to sign in</button>}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {error && (
          <MotionItem>
            <div className="rounded-2xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">{error}</div>
          </MotionItem>
        )}
        <p className="text-sm text-neutral-500 -mt-1">
          Google doesn&apos;t share your date of birth, so we collect it here to confirm you&apos;re 18 or older.
        </p>
        <MotionItem className="grid grid-cols-2 gap-3">
          <Field label="First name" name="first_name" placeholder="First name" value={given} onChange={(e) => setGiven(e.target.value)} />
          <Field label="Last name" name="last_name" placeholder="Last name" value={family} onChange={(e) => setFamily(e.target.value)} />
        </MotionItem>
        <MotionItem>
          <Field label="Date of birth" name="date_of_birth" type="date" value={dob} onChange={(e) => setDob(e.target.value)} max={new Date().toISOString().slice(0, 10)} />
        </MotionItem>
        <MotionItem className="mt-1">
          <SubmitButton loading={loading}>Complete sign up</SubmitButton>
        </MotionItem>
      </form>
    </AuthShell>
  );
}
