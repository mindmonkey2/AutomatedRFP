"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorNote, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { BidListItem, Credential } from "@/lib/types";

export default function BidsPage() {
  const [bids, setBids] = useState<BidListItem[] | null>(null);
  const [expiring, setExpiring] = useState<Credential[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", agency: "", due_date: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [b, e] = await Promise.all([
        api.get<BidListItem[]>("/bids"),
        api.get<Credential[]>("/credentials/expiring?days=30"),
      ]);
      setBids(b);
      setExpiring(e);
      setError(null);
    } catch (err) {
      setError(`Could not reach the API: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      await api.post("/bids", { title: form.title, agency: form.agency || null, due_date: form.due_date || null });
      setForm({ title: "", agency: "", due_date: "" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Bids</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload a solicitation to build its compliance matrix, then draft cited answers from your library.
        </p>
      </div>

      <ErrorNote error={error} />

      {expiring.length > 0 && (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <strong>{expiring.length} credential{expiring.length > 1 ? "s" : ""} expiring within 30 days:</strong>{" "}
          {expiring.map((c) => `${c.name} (${c.days_to_expiry! < 0 ? "expired" : `${c.days_to_expiry} days`})`).join(", ")}.{" "}
          <Link href="/library#credentials" className="font-medium underline">Review</Link>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Active bids" className="lg:col-span-2">
          {bids === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : bids.length === 0 ? (
            <p className="text-sm text-slate-500">No bids yet. Create one to get started.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {bids.map((b) => (
                <li key={b.id}>
                  <Link href={`/bids/${b.id}`} className="flex items-center justify-between gap-4 rounded-md px-2 py-3 hover:bg-slate-50">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{b.title}</p>
                      <p className="text-xs text-slate-500">
                        {b.agency ?? "No agency"} · {b.due_date ? `Due ${b.due_date}` : "No due date"}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-xs tabular-nums text-slate-500">
                        {b.answered_count} answers approved · {b.requirement_count} requirements
                      </span>
                      <Badge>{b.status}</Badge>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="New bid">
          <form onSubmit={create} className="space-y-3">
            <Field label="Title">
              <input className={inputCls} value={form.title} required placeholder="e.g. Maple Elementary Replacement"
                onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </Field>
            <Field label="Agency or owner">
              <input className={inputCls} value={form.agency} placeholder="e.g. Maple Unified School District"
                onChange={(e) => setForm({ ...form, agency: e.target.value })} />
            </Field>
            <Field label="Due date">
              <input type="date" className={inputCls} value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </Field>
            <Button type="submit" disabled={saving} className="w-full">Create bid</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
