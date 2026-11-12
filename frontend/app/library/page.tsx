"use client";

import { useCallback, useState } from "react";
import {
  Badge, Button, Card, ErrorNote, Field, FilePicker, StatusBadge, inputCls, useLoad, usePoll,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { Credential, LibraryDocument, Project, SavedAnswer, SearchHit } from "@/lib/types";

const DOC_TYPES = ["proposal", "questionnaire", "policy", "resume", "project_sheet", "other"];

export default function LibraryPage() {
  const [docs, setDocs] = useState<LibraryDocument[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [creds, setCreds] = useState<Credential[]>([]);
  const [saved, setSaved] = useState<SavedAnswer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [docType, setDocType] = useState("proposal");

  const load = useCallback(async () => {
    try {
      const [d, p, c, a] = await Promise.all([
        api.get<LibraryDocument[]>("/library/documents"),
        api.get<Project[]>("/projects"),
        api.get<Credential[]>("/credentials"),
        api.get<SavedAnswer[]>("/library/answers"),
      ]);
      setDocs(d); setProjects(p); setCreds(c); setSaved(a); setError(null);
    } catch (err) {
      setError(`Could not reach the API: ${(err as Error).message}`);
    }
  }, []);

  useLoad(load);
  usePoll(load, docs.some((d) => d.status === "queued" || d.status === "processing"));

  const run = (fn: () => Promise<unknown>) => async () => {
    try { await fn(); await load(); } catch (err) { setError((err as Error).message); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Knowledge library</h1>
        <p className="mt-1 text-sm text-slate-600">
          Everything here can be cited in drafts: past proposals, policies, résumés, project records and credentials.
          Answers you approve are saved here too.
        </p>
      </div>
      <ErrorNote error={error} />

      <Card
        title={`Documents (${docs.length})`}
        actions={
          <div className="flex items-center gap-2">
            <select className={`${inputCls} w-40`} value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </select>
            <FilePicker label="Upload" onFile={(f) => run(() => api.upload("/library/documents", f, { doc_type: docType }))()} />
          </div>
        }
      >
        {docs.length === 0 ? (
          <p className="text-sm text-slate-500">Upload 5–10 past proposals to get useful drafts. PDF, DOCX, XLSX or TXT.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="pb-2 font-medium">File</th><th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Pages</th><th className="pb-2 font-medium">Passages</th>
                <th className="pb-2 font-medium">Status</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {docs.map((d) => (
                <tr key={d.id}>
                  <td className="py-2 pr-3">
                    <p className="font-medium text-slate-900">{d.filename}</p>
                    {d.error && <p className="text-xs text-red-600">{d.error}</p>}
                    {d.empty_pages.length > 0 && (
                      <p className="text-xs text-amber-700">{d.empty_pages.length} page(s) had no text (scanned?) and were skipped.</p>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{d.doc_type.replace("_", " ")}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-600">{d.page_count ?? "–"}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-600">{d.chunk_count}</td>
                  <td className="py-2 pr-3"><StatusBadge status={d.status} /></td>
                  <td className="py-2 text-right">
                    <Button variant="ghost" onClick={run(() => api.del(`/library/documents/${d.id}`))}>Delete</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <SavedAnswers saved={saved} onDelete={(id) => run(() => api.del(`/library/answers/${id}`))()} />

      <SearchBox />

      <div className="grid gap-6 lg:grid-cols-2">
        <Projects projects={projects} onChange={load} onError={setError} />
        <Credentials creds={creds} onChange={load} onError={setError} />
      </div>
    </div>
  );
}

function SavedAnswers({ saved, onDelete }: { saved: SavedAnswer[]; onDelete: (chunkId: number) => void }) {
  return (
    <Card title={`Saved answers (${saved.length})`}>
      {saved.length === 0 ? (
        <p className="text-sm text-slate-500">Answers you approve in a bid are saved here and reused in later drafts.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {saved.map((a) => (
            <li key={a.chunk_id} className="flex items-start justify-between gap-4 py-3">
              <div className="min-w-0 text-sm">
                <p className="font-medium text-slate-900">{a.question}</p>
                <p className="mt-1 line-clamp-3 whitespace-pre-line text-slate-600">{a.answer}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {a.label}{a.bid_deleted && " · its bid has been deleted"}
                </p>
              </div>
              <Button variant="ghost" onClick={() => onDelete(a.chunk_id)}>Remove</Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SearchBox() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  return (
    <Card title="Test retrieval">
      <form className="flex gap-2" onSubmit={async (e) => {
        e.preventDefault();
        if (q.trim()) setHits(await api.get<SearchHit[]>(`/library/search?q=${encodeURIComponent(q)}`));
      }}>
        <input className={inputCls} value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Type an RFP question to see which passages a draft would use" />
        <Button type="submit" variant="secondary">Search</Button>
      </form>
      {hits && (
        <ul className="mt-4 space-y-3">
          {hits.length === 0 && <li className="text-sm text-slate-500">No matching passages.</li>}
          {hits.map((h) => (
            <li key={h.chunk_id} className="rounded-md bg-slate-50 p-3 ring-1 ring-slate-200">
              <p className="mb-1 text-xs font-medium text-slate-600">
                {h.label}{h.page ? ` · p. ${h.page}` : ""}{h.heading ? ` · ${h.heading}` : ""} <Badge>{h.source_type}</Badge>
              </p>
              <p className="line-clamp-4 whitespace-pre-line text-sm text-slate-800">{h.text}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const EMPTY_PROJECT = { name: "", client: "", sector: "", contract_value: "", start_date: "", end_date: "", scope: "", reference_name: "", reference_contact: "" };

function Projects({ projects, onChange, onError }: { projects: Project[]; onChange: () => void; onError: (e: string) => void }) {
  const [f, setF] = useState(EMPTY_PROJECT);
  const [open, setOpen] = useState(false);
  const set = (k: keyof typeof EMPTY_PROJECT) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const body: Record<string, string | number | null> = Object.fromEntries(
      Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]),
    );
    body.contract_value = f.contract_value ? Number(f.contract_value) : null;
    try { await api.post("/projects", body); setF(EMPTY_PROJECT); setOpen(false); onChange(); }
    catch (err) { onError((err as Error).message); }
  }

  return (
    <Card title={`Past projects (${projects.length})`}
      actions={<Button variant="secondary" onClick={() => setOpen(!open)}>{open ? "Cancel" : "Add project"}</Button>}>
      {open && (
        <form onSubmit={save} className="mb-4 grid grid-cols-2 gap-3 rounded-md bg-slate-50 p-3 ring-1 ring-slate-200">
          <div className="col-span-2"><Field label="Project name"><input required className={inputCls} value={f.name} onChange={set("name")} /></Field></div>
          <Field label="Client / owner"><input className={inputCls} value={f.client} onChange={set("client")} /></Field>
          <Field label="Sector"><input className={inputCls} value={f.sector} onChange={set("sector")} placeholder="e.g. public K-12" /></Field>
          <Field label="Contract value (USD)"><input type="number" className={inputCls} value={f.contract_value} onChange={set("contract_value")} /></Field>
          <div />
          <Field label="Start"><input type="date" className={inputCls} value={f.start_date} onChange={set("start_date")} /></Field>
          <Field label="End"><input type="date" className={inputCls} value={f.end_date} onChange={set("end_date")} /></Field>
          <div className="col-span-2"><Field label="Scope"><textarea rows={3} className={inputCls} value={f.scope} onChange={set("scope")} /></Field></div>
          <Field label="Reference name"><input className={inputCls} value={f.reference_name} onChange={set("reference_name")} /></Field>
          <Field label="Reference contact"><input className={inputCls} value={f.reference_contact} onChange={set("reference_contact")} /></Field>
          <div className="col-span-2"><Button type="submit">Save project</Button></div>
        </form>
      )}
      {projects.length === 0 ? (
        <p className="text-sm text-slate-500">Add completed projects so drafts can cite past performance.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {projects.map((p) => (
            <li key={p.id} className="flex items-start justify-between gap-3 py-2">
              <div>
                <p className="text-sm font-medium text-slate-900">{p.name}</p>
                <p className="text-xs text-slate-500">
                  {[p.client, p.sector, p.contract_value ? `$${p.contract_value.toLocaleString()}` : null].filter(Boolean).join(" · ")}
                </p>
              </div>
              <Button variant="ghost" onClick={async () => { await api.del(`/projects/${p.id}`); onChange(); }}>Delete</Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const EMPTY_CRED = { kind: "license", name: "", number: "", issuer: "", expires_on: "", notes: "" };

function Credentials({ creds, onChange, onError }: { creds: Credential[]; onChange: () => void; onError: (e: string) => void }) {
  const [f, setF] = useState(EMPTY_CRED);
  const [open, setOpen] = useState(false);
  const set = (k: keyof typeof EMPTY_CRED) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]));
    try { await api.post("/credentials", body); setF(EMPTY_CRED); setOpen(false); onChange(); }
    catch (err) { onError((err as Error).message); }
  }

  return (
    <Card title={`Credentials (${creds.length})`}
      actions={<Button variant="secondary" onClick={() => setOpen(!open)}>{open ? "Cancel" : "Add credential"}</Button>}>
      <div id="credentials" />
      {open && (
        <form onSubmit={save} className="mb-4 grid grid-cols-2 gap-3 rounded-md bg-slate-50 p-3 ring-1 ring-slate-200">
          <Field label="Kind">
            <select className={inputCls} value={f.kind} onChange={set("kind")}>
              {["license", "bond", "insurance", "certification", "other"].map((k) => <option key={k}>{k}</option>)}
            </select>
          </Field>
          <Field label="Name"><input required className={inputCls} value={f.name} onChange={set("name")} placeholder="e.g. General contractor license" /></Field>
          <Field label="Number"><input className={inputCls} value={f.number} onChange={set("number")} /></Field>
          <Field label="Issuer"><input className={inputCls} value={f.issuer} onChange={set("issuer")} /></Field>
          <Field label="Expires on"><input type="date" className={inputCls} value={f.expires_on} onChange={set("expires_on")} /></Field>
          <Field label="Notes"><input className={inputCls} value={f.notes} onChange={set("notes")} placeholder="e.g. $2M per occurrence" /></Field>
          <div className="col-span-2"><Button type="submit">Save credential</Button></div>
        </form>
      )}
      {creds.length === 0 ? (
        <p className="text-sm text-slate-500">Licenses, bonds, insurance and certifications, with expiry alerts.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {creds.map((c) => {
            const d = c.days_to_expiry;
            return (
              <li key={c.id} className="flex items-start justify-between gap-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">{c.name} <Badge>{c.kind}</Badge></p>
                  <p className="text-xs text-slate-500">{[c.number, c.issuer].filter(Boolean).join(" · ")}</p>
                </div>
                <div className="flex items-center gap-2">
                  {d !== null && (
                    <Badge tone={d < 0 ? "red" : d <= 30 ? "amber" : "green"}>
                      {d < 0 ? `expired ${-d}d ago` : `expires in ${d}d`}
                    </Badge>
                  )}
                  <Button variant="ghost" onClick={async () => { await api.del(`/credentials/${c.id}`); onChange(); }}>Delete</Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
