"use client";

import Link from "next/link";

import { InsightCard } from "@/components/finance/InsightCard";
import { sortInsights } from "@/lib/finance-insight-links";
import type { FinanceInsight } from "@/lib/finance-schemas";

type FinanceAlertsPanelProps = {
  insights: FinanceInsight[];
};

export function FinanceAlertsPanel({ insights }: FinanceAlertsPanelProps) {
  const sorted = sortInsights(insights);
  const warnings = sorted.filter((i) => i.severity === "warning" || i.severity === "critical");
  const others = sorted.filter((i) => i.severity === "info");

  if (sorted.length === 0) {
    return (
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-4 py-4">
        <h2 className="text-lg font-semibold">Alerts &amp; recommendations</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          No active alerts right now. Connect your banks on{" "}
          <Link href="/finance/connect" className="underline">
            Connect banks
          </Link>{" "}
          for up-to-date balances and cash-flow warnings.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-label="Finance alerts">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Alerts &amp; recommendations</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {warnings.length
              ? `${warnings.length} item${warnings.length === 1 ? "" : "s"} need attention`
              : "Review these when you have a moment"}
          </p>
        </div>
        <Link href="/finance/reports" className="solar-btn-ghost text-sm">
          Full reports
        </Link>
      </div>

      {warnings.length ? (
        <div className="grid gap-3">
          {warnings.map((insight) => (
            <InsightCard key={insight.id} insight={insight} prominent />
          ))}
        </div>
      ) : null}

      {others.length ? (
        <details className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/30 px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium">
            {others.length} more recommendation{others.length === 1 ? "" : "s"}
          </summary>
          <div className="mt-3 grid gap-3">
            {others.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}
