"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AuthShell, { MotionItem } from "@/components/watermelon-ui/auth-07";
import { GoogleSignInButton } from "@/components/google";
import { Field, SubmitButton } from "@/components/ui/field";
import { authApi, ApiError, setToken } from "@/lib/api";
import { useAuth } from "@/lib/store";

export default function SignInPage() {
  const router = useRouter();
  const setUser = useAuth((s) => s.setUser);
  const [form, setForm] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setErrors({});
    setLoading(true);
    try {
      const res = await authApi.login(form);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    } catch (e) {
      setErrors({ form: e instanceof ApiError ? e.message : "Sign in failed" });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Try to sign in with Google directly. Only if the backend says it still
   * needs a date of birth (a genuinely new account) do we send the user to
   * the completion step — previously every sign-in went through that form,
   * so returning users were re-asked for their name and age each time.
   */
  const onGoogle = async (idToken: string, claims: { given_name?: string; family_name?: string }) => {
    setGoogleBusy(true);
    try {
      const res = await authApi.google({ id_token: idToken });
      if (!res.requires_completion && res.access_token && res.user) {
        setToken(res.access_token);
        setUser(res.user);
        router.push("/dashboard");
        return;
      }
      sessionStorage.setItem("cv_google_id_token", idToken);
      sessionStorage.setItem("cv_google_given", res.first_name || claims.given_name || "");
      sessionStorage.setItem("cv_google_family", res.last_name || claims.family_name || "");
      router.push("/complete-google");
    } catch (e) {
      setErrors({ form: e instanceof ApiError ? e.message : "Google sign-in failed" });
    } finally {
      setGoogleBusy(false);
    }
  };

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your Carib Voices account."
      topExtra={<GoogleSignInButton label="Sign in with Google" onIdToken={onGoogle} />}
      divider
      footer={<>Don&apos;t have an account? <a href="/register" className="font-semibold text-[color:var(--jaia-green)] transition hover:text-[color:var(--jaia-green)]">Sign up</a></>}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {errors.form && (
          <MotionItem>
            <div className="cv-alert">{errors.form}</div>
          </MotionItem>
        )}
        <MotionItem>
          <Field label="Email" name="email" type="email" placeholder="you@example.com" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
        </MotionItem>
        <MotionItem>
          <Field label="Password" name="password" type="password" placeholder="Enter your password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
        </MotionItem>
        <MotionItem className="mt-1">
          <SubmitButton loading={loading}>Log In</SubmitButton>
        </MotionItem>
      </form>
    </AuthShell>
  );
}
