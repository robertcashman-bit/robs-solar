import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
      {
        source: "/install-mac-shortcut.sh",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "text/plain; charset=utf-8" },
        ],
      },
      {
        source: "/pin-rob-finance-dock.py",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "text/plain; charset=utf-8" },
        ],
      },
      {
        source: "/install-windows-shortcut.ps1",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "text/plain; charset=utf-8" },
        ],
      },
      {
        source: "/RobsFinance.url",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "application/internet-shortcut" },
          { key: "Content-Disposition", value: "attachment; filename=\"Robs Finance.url\"" },
        ],
      },
    ];
  },
  async redirects() {
    return [
      { source: "/energy", destination: "/", permanent: false },
      { source: "/energy/:path*", destination: "/", permanent: false },
      { source: "/analytics", destination: "/", permanent: false },
      { source: "/octopus", destination: "/", permanent: false },
      { source: "/forecast", destination: "/", permanent: false },
      { source: "/scheduler", destination: "/", permanent: false },
      { source: "/controls", destination: "/", permanent: false },
      { source: "/assistant", destination: "/", permanent: false },
      { source: "/alerts", destination: "/", permanent: false },
      { source: "/audit", destination: "/", permanent: false },
      { source: "/finance/setup", destination: "/finance/onboarding", permanent: false },
    ];
  },
  async rewrites() {
    // On Vercel multi-service, vercel.json routes /backend to the FastAPI
    // service. A Next rewrite to BACKEND_URL (often localhost) would hang
    // session bootstrap on “Loading session…”.
    if (process.env.VERCEL) {
      return [];
    }
    return [
      {
        source: "/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
