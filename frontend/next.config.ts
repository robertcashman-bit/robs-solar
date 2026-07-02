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
    ];
  },
  async redirects() {
    return [
      { source: "/analytics", destination: "/energy/analytics", permanent: true },
      { source: "/octopus", destination: "/energy/octopus", permanent: true },
      { source: "/forecast", destination: "/energy/forecast", permanent: true },
      { source: "/scheduler", destination: "/energy/scheduler", permanent: true },
      { source: "/controls", destination: "/energy/controls", permanent: true },
      { source: "/assistant", destination: "/energy/assistant", permanent: true },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
