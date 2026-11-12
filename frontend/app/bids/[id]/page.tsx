"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import {
  Badge, Button, Card, Confidence, ErrorNote, Field, FilePicker, StatusBadge, inputCls, useLoad, usePoll,
} from "@/components/ui";
import { api, download } from "@/lib/api";
import type { Answer, Bid, FactIssue, Readiness, Requirement } from "@/lib/types";

type Filter = "all" | "response" | "mandatory" | "review" | "changed";

const FILTERS: { key: Filter; label: string; test: (r: Requirement) => boolean }[] = [
  { key: "all", label: "All", test: () => true },
  { key: "response", label: "Needs a response", test: (r) => r.needs_response },
  { key: "mandatory", label: "Mandatory", test: (r) => r.mandatory },
  { key: "review", label: "To review", test: (r) => !!r.answer && ["needs_review", "drafted", "stale", "failed"].includes(r.answer.status) },
  { key: "changed", label: "Changed by addendum", test: (r) => !!r.change_type },
];

const BUSY = new Set(["queued", "processing", "drafting"]);
const FACT_KIND: Record<FactIssue["kind"], string> = {
  amount: "amount", percent: "percentage", date: "date", year: "year", number: "number", id: "ID or number", name: "name",
};

export default function BidPage() {
  const { id } = useParams<{ id: string }>();
  const [bid, setBid] = useState<Bid | null>(null);
  const [reqs, setReqs] = useState<Requirement[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, r, rd] = await Promise.all([
        api.get<Bid>(`/bids/${id}`),
        api.get<Requirement[]>(`/bids/${id}/requirements`),
        api.get<Readiness>(`/bids/${id}/readiness`),
      ]);
      setBid(b); setReqs(r); setReadiness(rd); setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [id]);

  useLoad(load);

  const busy = !!bid && (bid.files.some((f) => BUSY.has(f.status)) || reqs.some((r) => r.answer && BUSY.has(r.answer.status)));
  usePoll(load, busy);

  const run = (fn: () => Promise<unknown>) => async () => {
    try { setError(null); await fn(); await load(); } catch (err) { setError((err as Error).message); }
  };

  const shown = useMemo(() => reqs.filter(FILTERS.find((f) => f.key === filter)!.test), [reqs, filter]);
  const current = reqs.find((r) => r.id === selected) ?? null;
  const hasBase = bid?.files.some((f) => f.kind === "base" && f.status === "ready");
  const drafting = reqs.filter((r) => r.answer && BUSY.has(r.answer.status)).length;

  if (!bid) return error ? <ErrorNote error={error} /> : <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link href="/" className="text-xs text-slate-500 hover:text-slate-900">← Bids</Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">{bid.title}</h1>
          <p className="text-sm text-slate-600">
            {bid.agency ?? "No agency"} · {bid.due_date ? `Due ${bid.due_date}` : "No due date"}
          </p>
          {bid.summary && <p className="mt-2 max-w-3xl text-sm text-slate-700">{bid.summary}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <FilePicker label={hasBase ? "Add RFP volume" : "Upload RFP"}
            onFile={(f) => run(() => api.upload(`/bids/${id}/files`, f, { kind: "base" }))()} />
          <FilePicker label="Upload addendum" disabled={!hasBase}
            onFile={(f) => run(() => api.upload(`/bids/${id}/files`, f, { kind: "addendum" }))()} />
          <Button disabled={!hasBase || drafting > 0} onClick={run(() => api.post(`/bids/${id}/draft`, {}))}>
            {drafting > 0 ? `Drafting ${drafting}…` : "Draft answers"}
          </Button>
        </div>
      </div>

      <ErrorNote error={error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Solicitation files" className="lg:col-span-2">
          {bid.files.length === 0 ? (
            <p className="text-sm text-slate-500">
              Upload the solicitation (PDF, DOCX, XLSX or TXT). Every requirement, form, page limit, deadline and
              evaluation criterion is extracted into the compliance matrix below.
            </p>
          ) : (
            <ul className="space-y-2">
              {bid.files.map((f) => (
                <li key={f.id} className="text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone={f.kind === "addendum" ? "violet" : "neutral"}>{f.kind === "addendum" ? `Addendum` : "RFP"}</Badge>
                    <span className="font-medium text-slate-900">{f.filename}</span>
                    <StatusBadge status={f.status} />
                  </div>
                  {BUSY.has(f.status) && (
                    <p className="mt-1 text-xs text-slate-500">
                      {f.progress ?? (f.status === "queued"
                        ? "Waiting to start. Files are read in upload order, so an addendum is compared against everything before it."
                        : "Reading the document and extracting requirements. This can take a few minutes for long RFPs.")}
                    </p>
                  )}
                  {f.error && <p className="mt-1 text-xs text-red-600">{f.error}</p>}
                  {f.change_summary && <p className="mt-1 text-xs text-slate-600">{f.change_summary}</p>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Submission readiness"
          actions={
            <div className="flex gap-1">
              <Button variant="secondary" disabled={!reqs.length} onClick={run(() => download(`/bids/${id}/export/response.docx`))}>Response .docx</Button>
              <Button variant="secondary" disabled={!reqs.length} onClick={run(() => download(`/bids/${id}/export/matrix.xlsx`))}>Matrix .xlsx</Button>
            </div>
          }>
          {readiness && (
            <div className="space-y-2 text-sm">
              <p className="font-medium">
                {readiness.ready ? <span className="text-emerald-700">Ready to submit</span> : <span className="text-amber-800">Not ready yet</span>}
              </p>
              <ul className="list-disc space-y-1 pl-5 text-slate-700">
                {readiness.issues.map((i) => <li key={i}>{i}</li>)}
              </ul>
              {readiness.warnings.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-amber-800">
                  {readiness.warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
              )}
              <p className="text-xs text-slate-500">
                {readiness.requirements_total} requirements · {readiness.response_items} need a written response · ~{readiness.estimated_pages} pages
                {readiness.page_limit ? ` of ${readiness.page_limit} allowed` : ""}
              </p>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card title={`Compliance matrix (${reqs.length})`} className="lg:col-span-3">
          <div className="mb-3 flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${filter === f.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
                {f.label} ({reqs.filter(f.test).length})
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <p className="text-sm text-slate-500">{reqs.length ? "Nothing matches this filter." : "No requirements yet."}</p>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white text-left text-xs text-slate-500">
                  <tr><th className="py-2 pr-2 font-medium">#</th><th className="py-2 pr-2 font-medium">Requirement</th>
                    <th className="py-2 pr-2 font-medium">Page</th><th className="py-2 pr-2 font-medium">Status</th>
                    <th className="py-2 font-medium">Answer</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {shown.map((r) => (
                    <tr key={r.id} onClick={() => setSelected(r.id)}
                      className={`cursor-pointer align-top ${selected === r.id ? "bg-blue-50" : "hover:bg-slate-50"}`}>
                      <td className="py-2 pr-2 tabular-nums text-slate-500">{r.sequence}</td>
                      <td className="py-2 pr-2">
                        <p className="line-clamp-2 text-slate-900">{r.text}</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <Badge>{r.kind.replace("_", " ")}</Badge>
                          {r.mandatory && <Badge tone="red">mandatory</Badge>}
                          {r.change_type && <StatusBadge status={r.change_type} />}
                        </div>
                      </td>
                      <td className="py-2 pr-2 tabular-nums text-slate-500">{r.page ?? "–"}</td>
                      <td className="py-2 pr-2"><StatusBadge status={r.status} /></td>
                      <td className="py-2">
                        {r.answer ? (
                          <div className="space-y-1"><StatusBadge status={r.answer.status} /><Confidence value={r.answer.confidence} /></div>
                        ) : r.needs_response ? <span className="text-xs text-slate-400">not started</span> : <span className="text-xs text-slate-300">n/a</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="lg:col-span-2">
          {current ? (
            <RequirementPanel key={current.id} req={current} bidId={id} onChange={load} onError={setError} />
          ) : (
            <Card><p className="text-sm text-slate-500">Select a requirement to see its source, edit its answer and check citations.</p></Card>
          )}
        </div>
      </div>
    </div>
  );
}

function RequirementPanel({ req, bidId, onChange, onError }: {
  req: Requirement; bidId: string; onChange: () => void; onError: (e: string) => void;
}) {
  const a: Answer | null = req.answer;
  const serverText = a?.final_text ?? a?.draft_text ?? "";
  const serverAssignee = a?.assignee ?? "";
  const [text, setText] = useState(serverText);
  const [assignee, setAssignee] = useState(serverAssignee);
  // The server values the form was last filled from; edits are measured against these.
  const [synced, setSynced] = useState({ text: serverText, assignee: serverAssignee });
  const dirty = !!a && (text !== synced.text || assignee !== synced.assignee);

  // When the server copy changes (redraft, addendum, another reviewer), refill the form, but only if
  // the user has no unsaved edits. Adjusting state during render is React's pattern for this.
  if (serverText !== synced.text || serverAssignee !== synced.assignee) {
    setSynced({ text: serverText, assignee: serverAssignee });
    if (!dirty) { setText(serverText); setAssignee(serverAssignee); }
  }

  const run = (fn: () => Promise<unknown>) => async () => {
    try { await fn(); onChange(); } catch (err) { onError((err as Error).message); }
  };
  const save = (extra: object = {}) => api.patch(`/answers/${a!.id}`, { final_text: text, assignee: assignee || null, ...extra });

  return (
    <Card title={`Requirement ${req.sequence}`}>
      <div className="space-y-4">
        <div>
          <p className="text-sm text-slate-900">{req.text}</p>
          {req.source_quote && (
            <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-xs italic text-slate-600">
              “{req.source_quote}”{req.page ? ` (page ${req.page})` : ""}{req.section ? ` · ${req.section}` : ""}
            </blockquote>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">Compliance status</span>
          {(["open", "met", "na"] as const).map((s) => (
            <Button key={s} variant={req.status === s ? "primary" : "secondary"} className="!px-2 !py-1 text-xs"
              onClick={run(() => api.patch(`/requirements/${req.id}`, { status: s }))}>
              {s === "na" ? "N/A" : s}
            </Button>
          ))}
          {!req.needs_response && (
            <Button variant="ghost" className="text-xs" onClick={run(() => api.patch(`/requirements/${req.id}`, { needs_response: true }))}>
              Needs a written response
            </Button>
          )}
        </div>

        {req.needs_response && !a && (
          <Button onClick={run(() => api.post(`/bids/${bidId}/draft`, { requirement_ids: [req.id] }))}>Draft this answer</Button>
        )}

        {a && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2"><StatusBadge status={a.status} /><Confidence value={a.confidence} /></div>
              <Button variant="ghost" className="text-xs" disabled={BUSY.has(a.status)}
                onClick={run(() => api.post(`/bids/${bidId}/draft`, { requirement_ids: [req.id], force: true }))}>
                Regenerate
              </Button>
            </div>
            {a.status === "stale" && <p className="text-xs text-amber-800">An addendum changed this requirement. Review or regenerate this answer.</p>}
            {a.error && <p className={`text-xs ${a.status === "failed" ? "text-red-600" : "text-amber-700"}`}>{a.error}</p>}
            {BUSY.has(a.status) ? (
              <p className="text-sm text-slate-500">Drafting from your library…</p>
            ) : (
              <textarea rows={12} className={`${inputCls} font-[inherit] leading-relaxed`} value={text} onChange={(e) => setText(e.target.value)} />
            )}

            {(a.confidence_reasons.length > 0 || a.unsupported_claims.length > 0) && (
              <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-900 ring-1 ring-amber-200">
                {a.confidence_reasons.map((r) => <p key={r}>{r}</p>)}
                {a.unsupported_claims.length > 0 && (
                  <ul className="mt-1 list-disc pl-4">{a.unsupported_claims.map((c) => <li key={c}>Missing: {c}</li>)}</ul>
                )}
              </div>
            )}

            {a.fact_issues.length > 0 && (
              <div className="rounded-md bg-red-50 p-3 text-xs text-red-900 ring-1 ring-red-200">
                <p className="font-medium">Check these against your records before approving:</p>
                <ul className="mt-1 space-y-1">
                  {a.fact_issues.map((f) => (
                    <li key={`${f.problem}-${f.text}`}>
                      <span className="font-mono font-semibold">{f.text}</span>{" "}
                      <span className="text-red-800">({FACT_KIND[f.kind]}): {f.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {a.citations.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-slate-600">Citations</p>
                <ol className="space-y-2">
                  {a.citations.map((c) => (
                    <li key={c.marker} className="rounded-md bg-slate-50 p-2 text-xs ring-1 ring-slate-200">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-slate-700">[{c.marker}] {c.label}{c.page ? `, p. ${c.page}` : ""}</span>
                        <Badge tone={c.verified ? "green" : "red"}>{c.verified ? "verified" : "not found in source"}</Badge>
                      </div>
                      <p className="mt-1 italic text-slate-600">“{c.quote}”</p>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <Field label="Assigned to">
              <input className={inputCls} value={assignee} onChange={(e) => setAssignee(e.target.value)} placeholder="Name or email of the reviewer" />
            </Field>

            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={!dirty} onClick={run(() => save())}>Save</Button>
              <Button variant="secondary" onClick={run(() => save({ status: "accepted" }))}>Accept</Button>
              <Button onClick={run(async () => { await save(); await api.post(`/answers/${a.id}/approve`); })}
                title="Marks the requirement met and saves the answer to the library for future bids">
                Approve and save to library
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
