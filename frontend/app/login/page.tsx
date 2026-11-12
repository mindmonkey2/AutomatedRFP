"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthCard, AuthLink, SubmitButton, safeNext } from "@/components/auth-form";
import { Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/login", { email, password });
      window.location.href = safeNext(params.get("next"));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Sign in" error={error}
      footer={<>New to RFP Engine? <AuthLink href="/signup">Create an account</AuthLink></>}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Work email">
          <input type="email" required autoComplete="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password">
          <input type="password" required autoComplete="current-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <SubmitButton busy={busy}>Sign in</SubmitButton>
      </form>
    </AuthCard>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
