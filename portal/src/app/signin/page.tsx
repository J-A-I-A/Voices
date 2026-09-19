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

  const onGoogle = async (idToken: string) => {
    // Returning Google users: if DOB is already on file the backend finalizes
    // immediately; otherwise the backend returns requires_completion and we
    // route to the completion step. We send a placeholder DOB only here for
    // known users; for safety, always via completion step for consistency.
    sessionStorage.setItem("cv_google_id_token", idToken);
    router.push("/complete-google");
  };

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your Carib Voices account."
      topExtra={<GoogleSignInButton label="Sign in with Google" onIdToken={onGoogle} />}
      divider
      footer={<>Don&apos;t have an account? <a href="/register" className="font-semibold text-neutral-900 hover:underline">Sign up</a></>}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {errors.form && (
          <MotionItem>
            <div className="rounded-2xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">{errors.form}</div>
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
