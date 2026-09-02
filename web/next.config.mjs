/** @type {import('next').NextConfig} */
// Backend base URL. Rewrites run server-side at build/start, so a plain
// (non-public) env var works and avoids Vercel's NEXT_PUBLIC_ exposure warning.
// Priority:
//   1. API_BASE            (preferred override, no Vercel warning)
//   2. NEXT_PUBLIC_API_BASE (legacy override)
//   3. In production (Vercel build) default to the live Render backend so the
//      site works with zero dashboard config.
//   4. In local dev default to the local FastAPI server.
const PROD_API_BASE = "https://syncore-api.onrender.com";
const API_BASE =
  process.env.API_BASE ||
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.NODE_ENV === "production"
    ? PROD_API_BASE
    : "http://127.0.0.1:8000");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy API + SSE calls to the FastAPI backend during development so the
    // browser talks to a single origin (avoids CORS and eases SSE).
    return [
      { source: "/api/:path*", destination: `${API_BASE}/api/:path*` },
      { source: "/health", destination: `${API_BASE}/health` },
    ];
  },
};

export default nextConfig;
