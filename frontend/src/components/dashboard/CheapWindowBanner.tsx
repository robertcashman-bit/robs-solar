"use client";

import { useEffect, useState } from "react";

import type { ChargeWindowStatus } from "@/lib/schemas";
import { formatCountdown, formatLocalTime } from "@/lib/tariff-time";

import { BoltIcon } from "@/components/shared/icons";

type CheapWindowBannerProps = {
  status: ChargeWindowStatus | null;
};

function rateLine(status: ChargeWindowStatus, countdown: string): string {
  if (status.cheap_now) {
    const label =
      status.source === "smart-charge"
        ? "smart-charge window active"
        : `off-peak until ${status.offpeak_end || "morning"}`;
    return `Cheap rate now — ${label}`;
  }
  const nextTime = formatLocalTime(status.next_cheap_start);
  const source =
    status.next_cheap_source === "smart-charge" ? "smart-charge" : "off-peak";
  if (nextTime) {
    return `Peak rate now — next cheap ${source} from ${nextTime}${
      countdown ? ` (in ${countdown})` : ""
    }`;
  }
  if (status.offpeak_start && status.offpeak_end) {
    return `Peak rate now — cheap window ${status.offpeak_start}–${status.offpeak_end}`;
  }
  return "Peak rate now";
}

function severityClasses(severity: ChargeWindowStatus["severity"]): string {
  if (severity === "good") {
    return "border-sky-300/50 bg-sky-50/90 text-sky-900 dark:border-sky-800/50 dark:bg-sky-950/40 dark:text-sky-200";
  }
  if (severity === "caution") {
    return "border-amber-300/60 bg-amber-50/90 text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-200";
  }
  return "border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--foreground)]";
}

export function CheapWindowBanner({ status }: CheapWindowBannerProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!status?.next_cheap_start || status.cheap_now) {
      return;
    }
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [status?.next_cheap_start, status?.cheap_now]);

  if (!status) {
    return null;
  }

  const countdown =
    !status.cheap_now && status.next_cheap_start
      ? formatCountdown(status.next_cheap_start, nowMs)
      : "";

  const showImportDetail = status.state !== "idle" && status.message.trim().length > 0;

  return (
    <div className="space-y-2">
      <div
        role="status"
        className={`flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-sm ${
          status.cheap_now
            ? "border-emerald-300/50 bg-emerald-50/90 text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-200"
            : "border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)]"
        }`}
      >
        <span
          className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
            status.cheap_now ? "bg-emerald-500/15 text-emerald-600" : "bg-amber-500/15 text-amber-600"
          }`}
        >
          <BoltIcon size={16} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{rateLine(status, countdown)}</p>
          {!showImportDetail ? (
            <p className="mt-0.5 text-sm text-[var(--muted)]">
              {status.cheap_now
                ? "You are inside a cheap Octopus window."
                : "Grid import during this period uses your peak day rate."}
            </p>
          ) : null}
        </div>
      </div>

      {showImportDetail ? (
        <div
          role={status.severity === "caution" ? "alert" : "status"}
          className={`flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-sm ${severityClasses(status.severity)}`}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">
              {status.state === "cheap_import"
                ? "Importing on cheap power — this is intentional"
                : status.source === "unexpected"
                  ? "Unexpected grid import"
                  : "Importing at peak rate"}
            </p>
            <p className="mt-0.5 text-sm leading-relaxed">{status.message}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
