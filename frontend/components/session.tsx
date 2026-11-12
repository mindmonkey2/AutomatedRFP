"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, PUBLIC_PATHS } from "@/lib/api";

export interface Me {
  id: number;
  email: string;
  name: string;
  role: "admin" | "member";
  org_id: number;
  org_name: string;
}

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);

/** Loads the signed-in user; sends visitors to /login on protected pages. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let live = true;
    api.get<Me>("/auth/me")
      .then((u) => { if (live) setMe(u); })
      .catch(() => {
        if (!live) return;
        setMe(null);
        if (!isPublic) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      })
      .finally(() => { if (live) setChecked(true); });
    return () => { live = false; };
  }, [pathname, isPublic, router]);

  return (
    <MeContext.Provider value={me}>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-4 sm:px-6">
          <Link href="/" className="text-sm font-semibold tracking-tight text-slate-900">RFP Engine</Link>
          {me && (
            <>
              <nav className="flex gap-1 text-sm">
                <NavLink href="/" label="Bids" active={pathname === "/" || pathname.startsWith("/bids")} />
                <NavLink href="/library" label="Library" active={pathname.startsWith("/library")} />
                <NavLink href="/team" label="Team" active={pathname.startsWith("/team")} />
              </nav>
              <div className="ml-auto flex items-center gap-3 text-sm">
                <span className="hidden text-slate-600 sm:inline">{me.name} · {me.org_name}</span>
                <button
                  className="rounded-md px-2 py-1 text-slate-600 hover:bg-slate-100"
                  onClick={async () => { await api.post("/auth/logout"); window.location.href = "/login"; }}
                >
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {isPublic || me ? children : checked ? null : <p className="text-sm text-slate-500">Loading…</p>}
      </main>
    </MeContext.Provider>
  );
}

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link href={href}
      className={`rounded-md px-3 py-1.5 ${active ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"}`}>
      {label}
    </Link>
  );
}
