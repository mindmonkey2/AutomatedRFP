"use client";

import { useCallback, useState } from "react";
import { useMe } from "@/components/session";
import { Badge, Button, Card, ErrorNote, Field, inputCls, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

interface Member { id: number; email: string; name: string; role: string; is_active: boolean }
interface Invite { id: number; email: string; role: string; expires_at: string; accepted_at: string | null; token: string | null }

export default function TeamPage() {
  const me = useMe();
  const isAdmin = me?.role === "admin";
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMembers(await api.get<Member[]>("/auth/members"));
      if (isAdmin) setInvites(await api.get<Invite[]>("/auth/invites"));
    } catch (e) { setError((e as Error).message); }
  }, [isAdmin]);

  useLoad(load);

  const run = (fn: () => Promise<unknown>) => async () => {
    try { setError(null); await fn(); await load(); } catch (e) { setError((e as Error).message); }
  };

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    try {
      const inv = await api.post<Invite>("/auth/invites", { email, role });
      setLink(`${window.location.origin}/invite?token=${inv.token}`);
      setEmail("");
      await load();
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Team</h1>
        <p className="mt-1 text-sm text-slate-600">Everyone here shares {me?.org_name ?? "your company"}&apos;s library and bids.</p>
      </div>
      <ErrorNote error={error} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={`Members (${members.length})`}>
          <ul className="divide-y divide-slate-100">
            {members.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">{m.name} {m.id === me?.id && <span className="text-slate-400">(you)</span>}</p>
                  <p className="text-xs text-slate-500">{m.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={m.role === "admin" ? "blue" : "neutral"}>{m.role}</Badge>
                  {!m.is_active && <Badge tone="red">deactivated</Badge>}
                  {isAdmin && m.id !== me?.id && (
                    <Button variant="ghost" className="text-xs"
                      onClick={run(() => api.patch(`/auth/members/${m.id}`, { is_active: !m.is_active }))}>
                      {m.is_active ? "Deactivate" : "Reactivate"}
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>

        {isAdmin ? (
          <Card title="Invite a teammate">
            <form onSubmit={invite} className="flex flex-wrap items-end gap-2">
              <div className="min-w-48 flex-1"><Field label="Email"><input type="email" required className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} /></Field></div>
              <Field label="Role">
                <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="member">member</option><option value="admin">admin</option>
                </select>
              </Field>
              <Button type="submit">Create invite link</Button>
            </form>
            {link && (
              <div className="mt-3 rounded-md bg-emerald-50 p-3 text-sm ring-1 ring-emerald-200">
                <p className="mb-1 text-emerald-900">Send this link to your teammate. It works once and expires in 7 days.</p>
                <div className="flex gap-2">
                  <input readOnly className={`${inputCls} font-mono text-xs`} value={link} onFocus={(e) => e.target.select()} />
                  <Button variant="secondary" onClick={() => navigator.clipboard.writeText(link)}>Copy</Button>
                </div>
              </div>
            )}
            {invites.length > 0 && (
              <ul className="mt-4 divide-y divide-slate-100">
                {invites.map((i) => (
                  <li key={i.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="text-slate-700">{i.email} <Badge>{i.role}</Badge></span>
                    {i.accepted_at ? <Badge tone="green">joined</Badge> : (
                      <Button variant="ghost" className="text-xs" onClick={run(() => api.del(`/auth/invites/${i.id}`))}>Revoke</Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ) : (
          <Card><p className="text-sm text-slate-500">Ask an admin to invite new teammates.</p></Card>
        )}
      </div>
    </div>
  );
}
