"use client";

import Link from "next/link";

import type { FinanceInsight } from "@/lib/finance-schemas";

const severityStyles: Record<string, string> = {
  info: "border-sky-400/35 bg-sky-500/10 text-sky-950 dark:text-sky-100",
  warning: "border-amber-400/35 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  critical: "border-rose-400/35 bg-rose-500/10 text-rose-950 dark:text-rose-100",
};

type InsightCardProps = {
  insight: FinanceInsight;
  onDismiss?: (id: number) => void;
};

export function InsightCard({ insight, onDismiss }: InsightCardProps) {
  const metadata = insight.metadata ?? {};
  const href = typeof metadata.action_href === "string" ? metadata.action_href : null;
  const label = typeof metadata.action_label === "string" ? metadata.action_label : "Review";

  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${severityStyles[insight.severity] ?? severityStyles.info}`}>
      <p className="font-semibold">{insight.title}</p>
      <p className="mt-1 opacity-90">{insight.message}</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <p className="text-xs uppercase tracking-wide opacity-70">{insight.severity} · {insight.category}</p>
        {href ? (
          <Link href={href} className="text-xs font-medium underline">
            {label}
          </Link>
        ) : null}
        {onDismiss ? (
          <button type="button" className="text-xs underline opacity-80" onClick={() => onDismiss(insight.id)}>
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
