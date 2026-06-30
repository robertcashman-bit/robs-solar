"use client";

import { useEffect, useState } from "react";

function format(now: Date): { time: string; date: string } {
  return {
    time: now.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
    date: now.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }),
  };
}

export function LiveClock() {
  // Start null to avoid a server/client hydration mismatch, then tick once mounted.
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const initial = window.setTimeout(() => setNow(new Date()), 0);
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, []);

  if (!now) {
    return (
      <div className="flex flex-col items-end" aria-hidden="true">
        <span className="h-6 w-20 animate-pulse rounded bg-[var(--border)]" />
        <span className="mt-1 h-3 w-32 animate-pulse rounded bg-[var(--border)]" />
      </div>
    );
  }

  const { time, date } = format(now);

  return (
    <div className="flex flex-col items-end leading-tight" aria-label={`Current date and time: ${date} ${time}`}>
      <time className="text-xl font-bold tabular-nums tracking-tight text-[var(--foreground)]" dateTime={now.toISOString()}>
        {time}
      </time>
      <span className="text-xs font-medium text-[var(--muted)]">{date}</span>
    </div>
  );
}
