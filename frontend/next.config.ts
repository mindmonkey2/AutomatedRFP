import type { NextConfig } from "next";

// The browser only talks to this Next.js server; /api/* is proxied to the FastAPI backend.
// Keeping one origin means the session cookie is first-party and no CORS is needed.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";

// Content Security Policy: only this origin may supply scripts, styles, images and API calls, and
// no other site may embed the app in a frame. Next.js injects small inline scripts to start the app,
// hence 'unsafe-inline' for scripts; the dev server additionally needs eval and a WebSocket.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${isDev ? " ws:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Invite links carry a token in the URL; never send it to other sites as a referrer.
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  // Only when served over HTTPS (set FRONTEND_HTTPS=true): browsers then refuse plain HTTP.
  ...(process.env.FRONTEND_HTTPS === "true"
    ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
};

export default nextConfig;
