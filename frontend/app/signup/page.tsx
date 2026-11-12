"use client";

import { useState } from "react";
import { AuthCard, AuthLink, SubmitButton } from "@/components/auth-form";
import { Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

export default function SignupPage() {
  const [f, setF] = useState({ org_name: "", name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/signup", f);
      window.location.href = "/library";
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Create your company account"
      subtitle="You'll be the admin and can invite your bid team afterwards."
      error={error} footer={<>Already have an account? <AuthLink href="/login">Sign in</AuthLink></>}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Company name"><input required className={inputCls} value={f.org_name} onChange={set("org_name")} /></Field>
        <Field label="Your name"><input required autoComplete="name" className={inputCls} value={f.name} onChange={set("name")} /></Field>
        <Field label="Work email"><input type="email" required autoComplete="email" className={inputCls} value={f.email} onChange={set("email")} /></Field>
        <Field label="Password (at least 10 characters)">
          <input type="password" required minLength={10} autoComplete="new-password" className={inputCls} value={f.password} onChange={set("password")} />
        </Field>
        <SubmitButton busy={busy}>Create account</SubmitButton>
      </form>
    </AuthCard>
  );
}
