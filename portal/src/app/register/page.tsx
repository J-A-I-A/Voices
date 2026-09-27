"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AuthShell, { MotionItem } from "@/components/watermelon-ui/auth-07";
import { GoogleSignInButton } from "@/components/google";
import { Field, SubmitButton } from "@/components/ui/field";
import { authApi, ApiError, setToken } from "@/lib/api";
import { isAtLeast18 } from "@/lib/phone";
import { useAuth } from "@/lib/store";

export default function RegisterPage() {
  const router = useRouter();
  const setUser = useAuth((s) => s.setUser);
  const [form, setForm] = useState({
    first_name: "", last_name: "", date_of_birth: "", email: "", password: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.first_name.trim()) e.first_name = "First name is required.";
    if (!form.last_name.trim()) e.last_name = "Last name is required.";
    if (!form.date_of_birth) e.date_of_birth = "Date of birth is required.";
    else if (!isAtLeast18(form.date_of_birth)) e.date_of_birth = "You must be 18 or older to register.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) e.email = "Enter a valid email.";
    if (form.password.length < 8) e.password = "Password must be at least 8 characters.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      const res = await authApi.registerEmail(form);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    } catch (e) {
      setErrors({ form: e instanceof ApiError ? e.message : "Registration failed" });
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
    setGoogleLoading(true);
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
      setGoogleLoading(false);
    }
  };

  return (
    <AuthShell
      title="Create your account"
      subtitle="Join Carib Voices and help collect Jamaican speech."
      topExtra={<GoogleSignInButton label="Sign up with Google" onIdToken={onGoogle} />}
      divider
      footer={<>Already have an account? <a href="/signin" className="font-semibold text-[color:var(--jaia-green)] transition hover:text-[color:var(--jaia-green)]">Log in</a></>}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {errors.form && (
          <MotionItem>
            <div className="cv-alert">{errors.form}</div>
          </MotionItem>
        )}
        <MotionItem className="grid grid-cols-2 gap-3">
          <Field label="First name" name="first_name" placeholder="First name" value={form.first_name} onChange={(e) => set("first_name", e.target.value)} error={errors.first_name} />
          <Field label="Last name" name="last_name" placeholder="Last name" value={form.last_name} onChange={(e) => set("last_name", e.target.value)} error={errors.last_name} />
        </MotionItem>
        <MotionItem>
          <Field label="Date of birth" name="date_of_birth" type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)} error={errors.date_of_birth} max={new Date().toISOString().slice(0, 10)} />
        </MotionItem>
        <MotionItem>
          <Field label="Email" name="email" type="email" placeholder="you@example.com" value={form.email} onChange={(e) => set("email", e.target.value)} error={errors.email} />
        </MotionItem>
        <MotionItem>
          <Field label="Password" name="password" type="password" placeholder="At least 8 characters" value={form.password} onChange={(e) => set("password", e.target.value)} error={errors.password} />
        </MotionItem>
        <MotionItem className="mt-1">
          <SubmitButton loading={loading}>Sign Up</SubmitButton>
        </MotionItem>
        <MotionItem>
          <p className="px-2 text-xs leading-5 cv-muted">
            By signing up you confirm you are 18 or older and accept our{" "}
            <a href="/privacy" className="cv-link transition hover:text-[color:var(--jaia-green)]">
              Privacy Notice
            </a>
            .
          </p>
        </MotionItem>
      </form>
    </AuthShell>
  );
}
