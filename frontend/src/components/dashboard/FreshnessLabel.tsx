"use client";

import { useEffect, useState } from "react";

function relative(fromIso: string, now: number): string {
  const then = new Date(fromIso).getTime();
  if (!Number.isFinite(then)) {
    return "";
  }
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 5) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

export function FreshnessLabel({ timestamp }: { timestamp: string }) {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    const initial = window.setTimeout(() => setNow(Date.now()), 0);
    const timer = window.setInterval(() => setNow(Date.now()), 5000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, []);

  if (now === null) {
    return null;
  }

  const label = relative(timestamp, now);
  if (!label) {
    return null;
  }

  const stale = now - new Date(timestamp).getTime() > 120_000;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${
        stale ? "text-amber-600 dark:text-amber-400" : "text-[var(--muted)]"
      }`}
      title={`Inverter data sampled ${label}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${stale ? "bg-amber-400" : "bg-emerald-400"}`}
      />
      Updated {label}
    </span>
  );
}
