// All requests go to /api on this origin; next.config.ts proxies them to the backend.
const BASE = "/api";

export const PUBLIC_PATHS = ["/login", "/signup", "/invite"];

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function onUnauthorized() {
  if (typeof window === "undefined") return;
  const path = window.location.pathname;
  if (!PUBLIC_PATHS.some((p) => path.startsWith(p))) {
    window.location.href = `/login?next=${encodeURIComponent(path + window.location.search)}`;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...init.headers },
  });
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/")) onUnauthorized();
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
  upload: <T>(path: string, file: File, fields: Record<string, string>) => {
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    return request<T>(path, { method: "POST", body: fd });
  },
};

export async function download(path: string) {
  const res = await fetch(`${BASE}${path}`, { credentials: "same-origin" });
  if (res.status === 401) onUnauthorized();
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const blob = await res.blob();
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? "download";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
