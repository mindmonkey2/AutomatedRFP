"use client";

import Link from "next/link";
import { Button, ErrorNote } from "@/components/ui";

export function AuthCard({ title, subtitle, error, children, footer }: {
  title: string; subtitle?: string; error: string | null; children: React.ReactNode; footer?: React.ReactNode;
}) {
  return (
    <div className="mx-auto mt-12 max-w-sm">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
      <div className="mt-6 space-y-4 rounded-lg bg-white p-5 ring-1 ring-slate-200">
        <ErrorNote error={error} />
        {children}
      </div>
      {footer && <p className="mt-4 text-center text-sm text-slate-600">{footer}</p>}
    </div>
  );
}

export function SubmitButton({ busy, children }: { busy: boolean; children: React.ReactNode }) {
  return <Button type="submit" disabled={busy} className="w-full">{busy ? "Please wait…" : children}</Button>;
}

export function AuthLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="font-medium text-slate-900 underline">{children}</Link>;
}

/** Only allow redirects to paths on this site. */
export function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}
