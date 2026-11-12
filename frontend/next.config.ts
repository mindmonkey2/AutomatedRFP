import type { NextConfig } from "next";

// The browser only talks to this Next.js server; /api/* is proxied to the FastAPI backend.
// Keeping one origin means the session cookie is first-party and no CORS is needed.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
};

export default nextConfig;
