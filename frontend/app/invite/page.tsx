"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthCard, SubmitButton } from "@/components/auth-form";
import { Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

function AcceptInvite() {
  const token = useSearchParams().get("token") ?? "";
  const [info, setInfo] = useState<{ email: string; org_name: string } | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) { setError("This invite link is missing its token."); return; }
    api.get<{ email: string; org_name: string }>(`/auth/invites/lookup?token=${encodeURIComponent(token)}`)
      .then(setInfo).catch((e) => setError((e as Error).message));
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/accept-invite", { token, name, password });
      window.location.href = "/";
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthCard title={info ? `Join ${info.org_name}` : "Accept invite"}
      subtitle={info ? `You were invited as ${info.email}.` : undefined} error={error}>
      {info && (
        <form onSubmit={submit} className="space-y-3">
          <Field label="Your name"><input required className={inputCls} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Choose a password (at least 10 characters)">
            <input type="password" required minLength={10} autoComplete="new-password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <SubmitButton busy={busy}>Join team</SubmitButton>
        </form>
      )}
    </AuthCard>
  );
}

export default function InvitePage() {
  return <Suspense><AcceptInvite /></Suspense>;
}
